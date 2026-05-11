#!/usr/bin/env python3
"""
Co-scientist CLI
----------------
Run any co-scientist workflow from the terminal — no GUI or Jupyter required.

Usage
-----
    # List workflows
    python cli.py list

    # CellAtria
    python cli.py cellatria GSE284775 --analysis "Full Pipeline" --gene IFNG

    # ST Agent
    python cli.py st-agent data/sample.h5ad --gene IFNG --analysis "Spatial Gene Expression"

    # Biomni
    python cli.py biomni "Characterize the role of IFNG in tumor immune evasion."

    # GEO/SRA
    python cli.py geo "Download GSE96058 and run DESeq2 DEG analysis for IFNG."

    # Any workflow with a free-form prompt
    python cli.py run --workflow CellAtria --prompt "Convert BD Rhapsody files in data/GSM123 to h5ad."

    # List saved memory entries for a project
    python cli.py memory --project myproject

Global options (work with all subcommands):
    --model MODEL       Claude model ID (default: claude-haiku-4-5-20251001)
    --project NAME      Project name for results isolation and memory (default: cli)
    --timeout SECS      Max run time in seconds (default: 1200)
    --no-live           Suppress real-time output streaming
    --no-memory         Skip memory lookup and do not save result to memory
    --base-url URL      Custom API base URL (e.g. http://localhost:4000 for LiteLLM/Ollama)
"""

import argparse
import sys
from pathlib import Path

# Ensure repo root is on path
sys.path.insert(0, str(Path(__file__).parent.resolve()))

from notebook_api import (
    run_workflow, list_workflows,
    _CELLATRIA_TEMPLATES, _ST_AGENT_TEMPLATES,
)

DEFAULT_MODEL = "claude-haiku-4-5-20251001"
SONNET_MODEL  = "claude-sonnet-4-6"


# ── Memory helpers ─────────────────────────────────────────────────────────────

def _build_memory_context(project: str, query: str, workflow_name: str) -> str:
    """Search project memory and return a formatted context block, or empty string."""
    try:
        import memory as mem
        entries = mem.search(project, query, workflow_filter=workflow_name)
        if not entries:
            return ""
        lines = [
            "=== RELEVANT PROJECT MEMORY ===",
            f"(Project: {project} — {len(entries)} prior result(s) found)\n",
        ]
        for i, e in enumerate(entries, 1):
            lines.append(f"[{i}] {e['workflow']} | {e['preset']} | gene={e['gene']}")
            lines.append(f"    Timestamp : {e['timestamp'][:19]}")
            lines.append(f"    Summary   : {e['summary']}")
            if e.get("notes"):
                lines.append(f"    Notes     : {e['notes']}")
            lines.append("")
        lines.append("=== END MEMORY — use the above findings to inform your analysis ===\n")
        return "\n".join(lines)
    except Exception as exc:
        print(f"[Memory] Search skipped: {exc}", file=sys.stderr)
        return ""


def _save_to_memory(project, workflow_name, gene, preset, model, base_prompt, result):
    """Save run result as pending and interactively ask user to keep or discard."""
    try:
        import memory as mem
        full_text = result.get("output", "")
        log_path  = result.get("log", Path("/dev/null"))
        run_id = mem.save_pending(
            project, workflow_name, gene, preset, model,
            base_prompt, full_text, log_path,
        )
        if run_id is None:
            return

        # Show a brief summary
        solution = mem.extract_solution(full_text)
        print("\n" + "─" * 60)
        print(f"[Memory] Project: {project}")
        print(f"[Memory] Result preview:\n{solution[:400]}{'…' if len(solution) > 400 else ''}")
        print("─" * 60)

        try:
            answer = input("Keep result in project memory? [y/N]: ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            answer = "n"

        if answer == "y":
            try:
                notes = input("Notes (optional, press Enter to skip): ").strip()
            except (EOFError, KeyboardInterrupt):
                notes = ""
            mem.keep(project, run_id, notes)
            print(f"[Memory] Saved to project '{project}'.")
        else:
            mem.delete(project, run_id)
            print("[Memory] Result discarded.")
    except Exception as exc:
        print(f"[Memory] Save skipped: {exc}", file=sys.stderr)


def _run_with_memory(
    workflow_name: str,
    base_prompt: str,
    *,
    gene: str = "",
    preset: str = "",
    args,
    **run_kwargs,
):
    """
    Search project memory → prepend context → run workflow → save to memory.
    Central dispatcher used by all cmd_* functions.
    """
    use_memory = not getattr(args, "no_memory", False)

    # 1. Memory lookup
    memory_prefix = ""
    if use_memory:
        memory_prefix = _build_memory_context(args.project, base_prompt, workflow_name)
        if memory_prefix:
            print(f"[Memory] {memory_prefix.count('[') - memory_prefix.count('[Memory]')} "
                  f"relevant entries found in project '{args.project}'.")

    full_prompt = memory_prefix + base_prompt

    # 2. Run
    result = run_workflow(
        workflow_name,
        full_prompt,
        model=args.model,
        project=args.project,
        timeout=args.timeout,
        live_output=args.live,
        base_url=args.base_url,
        **run_kwargs,
    )

    # 3. Save to memory
    if use_memory and result["success"]:
        _save_to_memory(
            args.project, workflow_name, gene, preset,
            args.model, base_prompt, result,
        )

    return result


def _print_result(result: dict):
    if not result["success"]:
        print(f"\n[FAILED] exit code non-zero — check log: {result['log']}", file=sys.stderr)
        sys.exit(1)
    print(f"\nResults saved to: {result['run_dir']}")


# ── Command handlers ───────────────────────────────────────────────────────────

def cmd_list(_args):
    list_workflows()


def cmd_cellatria(args):
    template = _CELLATRIA_TEMPLATES.get(args.analysis)
    if template is None:
        print(f"Unknown analysis '{args.analysis}'.", file=sys.stderr)
        sys.exit(1)
    base_prompt = template.replace("{INPUT}", args.input).replace("{GENE}", args.gene)
    result = _run_with_memory(
        "CellAtria", base_prompt,
        gene=args.gene, preset=args.analysis,
        args=args,
    )
    _print_result(result)


def cmd_st_agent(args):
    template = _ST_AGENT_TEMPLATES.get(args.analysis)
    if template is None:
        print(f"Unknown analysis '{args.analysis}'.", file=sys.stderr)
        sys.exit(1)
    base_prompt = template.replace("{H5AD}", args.h5ad).replace("{GENE}", args.gene)
    result = _run_with_memory(
        "ST Agent", base_prompt,
        gene=args.gene, preset=args.analysis,
        args=args,
        skip_vision=not args.vision,
    )
    _print_result(result)


def cmd_biomni(args):
    result = _run_with_memory(
        "Biomni", args.prompt,
        gene="", preset="",
        args=args,
        data_dir=args.data_dir,
    )
    _print_result(result)


def cmd_geo(args):
    result = _run_with_memory(
        "GEO/SRA", args.prompt,
        gene="", preset="",
        args=args,
        data_dir=args.data_dir,
    )
    _print_result(result)


def cmd_run(args):
    result = _run_with_memory(
        args.workflow, args.prompt,
        gene="", preset="",
        args=args,
    )
    _print_result(result)


def cmd_memory(args):
    """List kept memory entries for a project."""
    try:
        import memory as mem
        entries = mem.list_all(args.project, workflow_filter=args.workflow or None)
        if not entries:
            print(f"No memory entries found for project '{args.project}'.")
            return
        print(f"Project '{args.project}' — {len(entries)} kept result(s):\n")
        for e in entries:
            print(f"  [{e['timestamp'][:19]}] {e['workflow']} | {e['preset']} | gene={e['gene']}")
            print(f"    {e['summary'][:120]}{'…' if len(e['summary']) > 120 else ''}")
            if e.get("notes"):
                print(f"    Notes: {e['notes']}")
            print(f"    Log: {e['log_path']}")
            print()
    except Exception as exc:
        print(f"[Memory] Error: {exc}", file=sys.stderr)
        sys.exit(1)


# ── Argument parser ────────────────────────────────────────────────────────────

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="co-scientist",
        description="Co-scientist — multi-workflow biomedical AI platform (CLI)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    def add_globals(p):
        p.add_argument("--model", default=DEFAULT_MODEL,
                       help=f"Claude model ID (default: {DEFAULT_MODEL})")
        p.add_argument("--project", default="cli",
                       help="Project name for results folder and memory (default: cli)")
        p.add_argument("--timeout", type=int, default=1200,
                       help="Max run time in seconds (default: 1200)")
        p.add_argument("--no-live", dest="live", action="store_false", default=True,
                       help="Suppress real-time output streaming")
        p.add_argument("--no-memory", action="store_true", default=False,
                       help="Skip memory lookup and do not save result to project memory")
        p.add_argument("--base-url", default=None,
                       help="Custom API base URL (e.g. http://localhost:4000 for LiteLLM/Ollama)")

    sub = parser.add_subparsers(dest="command", required=True)

    # ── list ──────────────────────────────────────────────────────────────────
    sub.add_parser("list", help="List available workflows")

    # ── cellatria ─────────────────────────────────────────────────────────────
    p_cel = sub.add_parser("cellatria", help="Single-cell RNA-seq (CellAtria / AstraZeneca)")
    p_cel.add_argument("input",
                       help="GEO accession (e.g. GSE284775), article URL, or PDF path")
    p_cel.add_argument("--analysis", default="Full Pipeline",
                       choices=list(_CELLATRIA_TEMPLATES.keys()),
                       help="Analysis type (default: Full Pipeline)")
    p_cel.add_argument("--gene", default="IFNG",
                       help="Target gene symbol (default: IFNG)")
    add_globals(p_cel)
    p_cel.set_defaults(model=SONNET_MODEL)

    # ── st-agent ──────────────────────────────────────────────────────────────
    p_st = sub.add_parser("st-agent", help="Spatial transcriptomics (STAgent / Harvard)")
    p_st.add_argument("h5ad", help="Path to .h5ad spatial transcriptomics file")
    p_st.add_argument("--gene", default="IFNG",
                      help="Target gene symbol (default: IFNG)")
    p_st.add_argument("--analysis", default="Spatial Gene Expression",
                      choices=list(_ST_AGENT_TEMPLATES.keys()),
                      help="Analysis type (default: Spatial Gene Expression)")
    p_st.add_argument("--vision", action="store_true", default=False,
                      help="Enable vision (image re-encoding) — disabled by default to save tokens")
    add_globals(p_st)

    # ── biomni ────────────────────────────────────────────────────────────────
    p_bio = sub.add_parser("biomni", help="General biomedical agent (Biomni / Stanford)")
    p_bio.add_argument("prompt", help="Free-form biomedical query")
    p_bio.add_argument("--data-dir", default=None,
                       help="Data directory for Biomni agent (default: COSCIENTIST_DATA_DIR or ~/biomni_data)")
    add_globals(p_bio)
    p_bio.set_defaults(model=SONNET_MODEL)

    # ── geo ───────────────────────────────────────────────────────────────────
    p_geo = sub.add_parser("geo", help="GEO/SRA dataset search and DEG analysis")
    p_geo.add_argument("prompt", help="Free-form GEO/SRA query or accession")
    p_geo.add_argument("--data-dir", default=None,
                       help="Data directory for GEO/SRA downloads (default: COSCIENTIST_DATA_DIR or ~/biomni_data)")
    add_globals(p_geo)

    # ── run ───────────────────────────────────────────────────────────────────
    p_run = sub.add_parser("run", help="Run any workflow with a free-form prompt")
    p_run.add_argument("--workflow", required=True,
                       help='Workflow name: "Biomni", "GEO/SRA", "ST Agent", "CellAtria"')
    p_run.add_argument("--prompt", required=True,
                       help="Full prompt to send to the agent")
    add_globals(p_run)

    # ── memory ────────────────────────────────────────────────────────────────
    p_mem = sub.add_parser("memory", help="List kept memory entries for a project")
    p_mem.add_argument("--project", default="cli",
                       help="Project name (default: cli)")
    p_mem.add_argument("--workflow", default=None,
                       help='Filter by workflow name (e.g. "CellAtria")')

    return parser


def main():
    parser = build_parser()
    args = parser.parse_args()

    dispatch = {
        "list":      cmd_list,
        "cellatria": cmd_cellatria,
        "st-agent":  cmd_st_agent,
        "biomni":    cmd_biomni,
        "geo":       cmd_geo,
        "run":       cmd_run,
        "memory":    cmd_memory,
    }
    dispatch[args.command](args)


if __name__ == "__main__":
    main()
