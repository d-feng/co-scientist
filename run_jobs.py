#!/usr/bin/env python3
"""
Co-scientist Job Runner
-----------------------
File-driven batch execution — no GUI, no HTTP port required.
Reads a YAML or JSON job file and runs workflows sequentially.

Usage
-----
    python run_jobs.py jobs.yaml
    python run_jobs.py jobs.json
    python run_jobs.py jobs.yaml --dry-run   # preview without running

Job file format (YAML)
----------------------
    defaults:                        # optional — applied to all jobs
      model: claude-haiku-4-5-20251001
      project: batch_run
      timeout: 1200

    jobs:
      - name: "GEO metadata fetch"
        workflow: cellatria
        input: GSE284775
        analysis: "GEO Dataset Retrieval"
        gene: IFNG

      - name: "Spatial expression"
        workflow: st-agent
        h5ad: data/sample.h5ad
        gene: IFNG
        analysis: "Spatial Gene Expression"
        model: claude-sonnet-4-6      # overrides default

      - name: "Biomni literature"
        workflow: biomni
        prompt: "Characterize the role of IFNG in tumor immune evasion."

      - name: "GEO DEG analysis"
        workflow: geo
        prompt: "Download GSE96058 and run DESeq2 DEG analysis for IFNG."

      - name: "Custom CellAtria"
        workflow: run
        workflow_name: CellAtria
        prompt: "Convert BD Rhapsody files in data/GSM123 to h5ad."
        model: claude-sonnet-4-6
        timeout: 3600
"""

import sys
import json
import argparse
from pathlib import Path
from datetime import datetime

# Ensure repo root is on path
sys.path.insert(0, str(Path(__file__).parent.resolve()))

from notebook_api import (
    run_workflow,
    _CELLATRIA_TEMPLATES, _ST_AGENT_TEMPLATES,
)


def _memory_prefix(project: str, query: str, workflow_name: str) -> str:
    """Return formatted memory context block, or empty string on failure."""
    try:
        import memory as mem
        entries = mem.search(project, query, workflow_filter=workflow_name)
        if not entries:
            return ""
        lines = [
            "=== RELEVANT PROJECT MEMORY ===",
            f"(Project: {project} — {len(entries)} prior result(s))\n",
        ]
        for i, e in enumerate(entries, 1):
            lines.append(f"[{i}] {e['workflow']} | {e['preset']} | gene={e['gene']}")
            lines.append(f"    Timestamp : {e['timestamp'][:19]}")
            lines.append(f"    Summary   : {e['summary']}")
            if e.get("notes"):
                lines.append(f"    Notes     : {e['notes']}")
            lines.append("")
        lines.append("=== END MEMORY ===\n")
        print(f"[Memory] {len(entries)} relevant entry/entries prepended from project '{project}'.")
        return "\n".join(lines)
    except Exception as exc:
        print(f"[Memory] Search skipped: {exc}", file=sys.stderr)
        return ""


def _auto_save(project, workflow_name, gene, preset, model, base_prompt, result):
    """Auto-keep result in project memory (no interactive prompt for batch runs)."""
    try:
        import memory as mem
        full_text = result.get("output", "")
        log_path  = result.get("log", Path("/dev/null"))
        run_id = mem.save_pending(
            project, workflow_name, gene, preset, model,
            base_prompt, full_text, log_path,
        )
        if run_id:
            mem.keep(project, run_id)
            print(f"[Memory] Result auto-saved to project '{project}'.")
    except Exception as exc:
        print(f"[Memory] Save skipped: {exc}", file=sys.stderr)


def _load_job_file(path: str) -> dict:
    p = Path(path)
    if not p.exists():
        print(f"ERROR: Job file not found: {path}", file=sys.stderr)
        sys.exit(1)
    text = p.read_text(encoding="utf-8")
    if p.suffix in (".yaml", ".yml"):
        try:
            import yaml
            return yaml.safe_load(text)
        except ImportError:
            print("ERROR: PyYAML not installed. Run: pip install pyyaml", file=sys.stderr)
            sys.exit(1)
    elif p.suffix == ".json":
        return json.loads(text)
    else:
        print(f"ERROR: Unsupported file format '{p.suffix}'. Use .yaml or .json", file=sys.stderr)
        sys.exit(1)


def _merge(defaults: dict, job: dict) -> dict:
    """Merge defaults with job-level overrides (job takes precedence)."""
    merged = {**defaults, **job}
    return merged


def _run_job(job: dict, dry_run: bool) -> bool:
    name       = job.get("name", "(unnamed)")
    workflow   = job.get("workflow", "").lower().strip()
    model      = job.get("model", "claude-haiku-4-5-20251001")
    project    = job.get("project", "batch_run")
    timeout    = int(job.get("timeout", 1200))
    base_url   = job.get("base_url") or None
    use_memory = job.get("memory", True)

    print(f"\n{'='*60}")
    print(f"Job: {name}")
    print(f"Workflow: {workflow} | Model: {model} | Project: {project}")
    print(f"{'='*60}")

    if dry_run:
        print("[DRY RUN] Skipping execution.")
        return True

    try:
        # Build base_prompt and metadata for each workflow type
        if workflow == "cellatria":
            analysis   = job.get("analysis", "Full Pipeline")
            inp        = job.get("input", "")
            gene       = job.get("gene", "IFNG")
            preset     = analysis
            wf_name    = "CellAtria"
            if not inp:
                print("ERROR: 'input' required for cellatria workflow")
                return False
            template   = _CELLATRIA_TEMPLATES.get(analysis, _CELLATRIA_TEMPLATES["Full Pipeline"])
            base_prompt = template.replace("{INPUT}", inp).replace("{GENE}", gene)

        elif workflow == "st-agent":
            h5ad       = job.get("h5ad", "")
            gene       = job.get("gene", "IFNG")
            analysis   = job.get("analysis", "Spatial Gene Expression")
            vision     = job.get("vision", False)
            preset     = analysis
            wf_name    = "ST Agent"
            if not h5ad:
                print("ERROR: 'h5ad' required for st-agent workflow")
                return False
            template   = _ST_AGENT_TEMPLATES.get(analysis, _ST_AGENT_TEMPLATES["Spatial Gene Expression"])
            base_prompt = template.replace("{H5AD}", h5ad).replace("{GENE}", gene)

        elif workflow == "biomni":
            base_prompt = job.get("prompt", "")
            gene        = job.get("gene", "")
            preset      = ""
            wf_name     = "Biomni"
            if not base_prompt:
                print("ERROR: 'prompt' required for biomni workflow")
                return False

        elif workflow == "geo":
            base_prompt = job.get("prompt", "")
            gene        = job.get("gene", "")
            preset      = ""
            wf_name     = "GEO/SRA"
            if not base_prompt:
                print("ERROR: 'prompt' required for geo workflow")
                return False

        elif workflow == "run":
            wf_name     = job.get("workflow_name", "")
            base_prompt = job.get("prompt", "")
            gene        = job.get("gene", "")
            preset      = ""
            if not wf_name or not base_prompt:
                print("ERROR: 'workflow_name' and 'prompt' required for run workflow")
                return False

        else:
            print(f"ERROR: Unknown workflow '{workflow}'. "
                  f"Use: cellatria, st-agent, biomni, geo, run")
            return False

        # Memory lookup
        prefix = _memory_prefix(project, base_prompt, wf_name) if use_memory else ""
        full_prompt = prefix + base_prompt

        # Run
        run_kwargs = {"model": model, "project": project, "timeout": timeout, "base_url": base_url}
        if workflow == "st-agent":
            run_kwargs["skip_vision"] = not vision
        result = run_workflow(wf_name, full_prompt, **run_kwargs)

        # Auto-save to memory
        if use_memory and result["success"]:
            _auto_save(project, wf_name, gene, preset, model, base_prompt, result)

        return result["success"]

    except Exception as e:
        print(f"ERROR: Job failed with exception: {e}", file=sys.stderr)
        return False


def main():
    parser = argparse.ArgumentParser(
        prog="run_jobs",
        description="Co-scientist file-driven batch job runner",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("job_file", help="Path to YAML or JSON job file")
    parser.add_argument("--dry-run", action="store_true",
                        help="Parse and preview jobs without executing")
    args = parser.parse_args()

    data     = _load_job_file(args.job_file)
    defaults = data.get("defaults", {})
    jobs     = data.get("jobs", [])

    if not jobs:
        print("No jobs found in job file.")
        sys.exit(0)

    print(f"Co-scientist Job Runner")
    print(f"Job file : {args.job_file}")
    print(f"Jobs     : {len(jobs)}")
    print(f"Dry run  : {args.dry_run}")
    print(f"Started  : {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    passed = failed = 0
    for i, job in enumerate(jobs, 1):
        merged = _merge(defaults, job)
        print(f"\n[{i}/{len(jobs)}] Starting: {merged.get('name', '(unnamed)')}")
        ok = _run_job(merged, dry_run=args.dry_run)
        if ok:
            passed += 1
            print(f"[{i}/{len(jobs)}] PASSED")
        else:
            failed += 1
            print(f"[{i}/{len(jobs)}] FAILED")

    print(f"\n{'='*60}")
    print(f"Done: {passed} passed, {failed} failed")
    print(f"Finished: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'='*60}")

    sys.exit(0 if failed == 0 else 1)


if __name__ == "__main__":
    main()
