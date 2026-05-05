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

Global options (work with all subcommands):
    --model MODEL       Claude model ID (default: claude-haiku-4-5-20251001)
    --project NAME      Project name for results isolation (default: cli)
    --timeout SECS      Max run time in seconds (default: 1200)
    --no-live           Suppress real-time output streaming
"""

import argparse
import sys
from pathlib import Path

# Ensure repo root is on path
sys.path.insert(0, str(Path(__file__).parent.resolve()))

from notebook_api import (
    run_workflow, run_cellatria, run_st_agent, run_biomni, run_geo_sra,
    list_workflows,
    _CELLATRIA_TEMPLATES, _ST_AGENT_TEMPLATES,
)

DEFAULT_MODEL = "claude-haiku-4-5-20251001"
SONNET_MODEL  = "claude-sonnet-4-6"


def _print_result(result: dict):
    if not result["success"]:
        print(f"\n[FAILED] exit code non-zero — check log: {result['log']}", file=sys.stderr)
        sys.exit(1)
    print(f"\nResults saved to: {result['run_dir']}")


def cmd_list(_args):
    list_workflows()


def cmd_cellatria(args):
    result = run_cellatria(
        args.input,
        analysis=args.analysis,
        gene=args.gene,
        model=args.model,
        project=args.project,
        timeout=args.timeout,
        live_output=args.live,
    )
    _print_result(result)


def cmd_st_agent(args):
    result = run_st_agent(
        args.h5ad,
        gene=args.gene,
        analysis=args.analysis,
        model=args.model,
        project=args.project,
        skip_vision=not args.vision,
        timeout=args.timeout,
        live_output=args.live,
    )
    _print_result(result)


def cmd_biomni(args):
    result = run_biomni(
        args.prompt,
        model=args.model,
        project=args.project,
        timeout=args.timeout,
        live_output=args.live,
    )
    _print_result(result)


def cmd_geo(args):
    result = run_geo_sra(
        args.prompt,
        model=args.model,
        project=args.project,
        timeout=args.timeout,
        live_output=args.live,
    )
    _print_result(result)


def cmd_run(args):
    result = run_workflow(
        args.workflow,
        args.prompt,
        model=args.model,
        project=args.project,
        timeout=args.timeout,
        live_output=args.live,
    )
    _print_result(result)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="co-scientist",
        description="Co-scientist — multi-workflow biomedical AI platform (CLI)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    # ── Global options ─────────────────────────────────────────────────────────
    def add_globals(p):
        p.add_argument("--model", default=DEFAULT_MODEL,
                       help=f"Claude model ID (default: {DEFAULT_MODEL})")
        p.add_argument("--project", default="cli",
                       help="Project name for results folder isolation (default: cli)")
        p.add_argument("--timeout", type=int, default=1200,
                       help="Max run time in seconds (default: 1200)")
        p.add_argument("--no-live", dest="live", action="store_false", default=True,
                       help="Suppress real-time output streaming")

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
    p_cel.set_defaults(model=SONNET_MODEL)   # sonnet recommended for CellAtria

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
    add_globals(p_bio)
    p_bio.set_defaults(model=SONNET_MODEL)

    # ── geo ───────────────────────────────────────────────────────────────────
    p_geo = sub.add_parser("geo", help="GEO/SRA dataset search and DEG analysis")
    p_geo.add_argument("prompt", help="Free-form GEO/SRA query or accession")
    add_globals(p_geo)

    # ── run ───────────────────────────────────────────────────────────────────
    p_run = sub.add_parser("run", help="Run any workflow with a free-form prompt")
    p_run.add_argument("--workflow", required=True,
                       help='Workflow name: "Biomni", "GEO/SRA", "ST Agent", "CellAtria"')
    p_run.add_argument("--prompt", required=True,
                       help="Full prompt to send to the agent")
    add_globals(p_run)

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
    }
    dispatch[args.command](args)


if __name__ == "__main__":
    main()
