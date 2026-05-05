"""
Co-scientist Notebook API
-------------------------
Programmatic interface for running co-scientist workflows from Jupyter notebooks
or any Python script — no tkinter / GUI required.

Usage
-----
    from notebook_api import run_workflow, run_cellatria, run_st_agent, list_workflows

    # List available workflows
    list_workflows()

    # Run any workflow with a free-form prompt
    result = run_workflow("CellAtria", "Fetch GEO metadata for GSE284775", project="demo")

    # Convenience helpers
    result = run_cellatria("GSE284775", analysis="Full Pipeline", gene="IFNG")
    result = run_st_agent("/path/to/data.h5ad", gene="IFNG", analysis="Spatial Gene Expression")
"""

import os
import sys
import subprocess
from pathlib import Path
from datetime import datetime

# ── Repo root ──────────────────────────────────────────────────────────────────
REPO_ROOT = Path(__file__).parent.resolve()
RESULTS_DIR = REPO_ROOT / "results"

# Add repo to path so workflows can be imported
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


# ── Helpers ────────────────────────────────────────────────────────────────────

def list_workflows():
    """Print all available workflow names and descriptions."""
    from workflows import WORKFLOWS
    print(f"{'Workflow':<14} {'Description'}")
    print("-" * 70)
    for wf in WORKFLOWS:
        print(f"{wf.icon} {wf.name:<12} {wf.description}")


def _stream(proc, log_path: Path, live: bool) -> str:
    """Stream subprocess stdout, write to log, return full output."""
    lines = []
    with open(log_path, "w", encoding="utf-8") as log_file:
        for line in proc.stdout:
            if live:
                print(line, end="", flush=True)
            log_file.write(line)
            lines.append(line)
    proc.wait()
    return "".join(lines)


# ── Core runner ────────────────────────────────────────────────────────────────

def run_workflow(
    workflow_name: str,
    prompt: str,
    *,
    model: str = "claude-haiku-4-5-20251001",
    project: str = "notebook",
    data_dir: str | None = None,
    timeout: int = 1200,
    skip_datalake: bool = False,
    skip_vision: bool = False,
    live_output: bool = True,
) -> dict:
    """
    Run any co-scientist workflow headlessly.

    Parameters
    ----------
    workflow_name : str
        Workflow name — one of "Biomni", "GEO/SRA", "ST Agent", "CellAtria".
    prompt : str
        The full prompt / query to send to the agent.
    model : str
        Claude model ID (default: haiku — cheapest).
    project : str
        Project name used for results folder isolation.
    data_dir : str | None
        Data directory passed to Biomni / GEO workflows. Defaults to ./data.
    timeout : int
        Max seconds for the run (default 1200).
    skip_datalake : bool
        Skip datalake integration (GEO/SRA workflow).
    skip_vision : bool
        Disable vision re-encoding for STAgent (saves tokens).
    live_output : bool
        Print output lines in real-time (default True).

    Returns
    -------
    dict with keys:
        success  : bool
        output   : str (full stdout)
        run_dir  : Path
        log      : Path
        result   : Path (result.txt)
    """
    from workflows import WORKFLOWS

    wf = next((w for w in WORKFLOWS if w.name == workflow_name), None)
    if wf is None:
        names = [w.name for w in WORKFLOWS]
        raise ValueError(f"Unknown workflow '{workflow_name}'. Available: {names}")

    if data_dir is None:
        data_dir = str(REPO_ROOT / "data")

    # Per-run output folder
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_wf = workflow_name.lower().replace(" ", "_").replace("/", "_")
    run_dir = RESULTS_DIR / project / f"{safe_wf}_{ts}"
    run_dir.mkdir(parents=True, exist_ok=True)

    script = wf.get_run_script(model, data_dir, timeout, skip_datalake, prompt)
    python_bin = wf.get_python_bin()

    env = {
        **os.environ,
        "PYTHONUTF8": "1",
        "PYTHONUNBUFFERED": "1",
        "STAGENT_SKIP_VISION": "1" if skip_vision else "0",
        "STAGENT_PLOT_DIR": str(run_dir),
        "COSCIENTIST_RUN_DIR": str(run_dir),
        "STAGENT_PROJECT": project,
    }

    proc = subprocess.Popen(
        [python_bin, "-c", script],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=env,
    )

    log_path = run_dir / "run.log"
    output = _stream(proc, log_path, live=live_output)

    result_path = run_dir / "result.txt"
    result_path.write_text(output, encoding="utf-8")

    success = proc.returncode == 0
    if live_output:
        status = "✓ Completed" if success else f"✗ Failed (exit {proc.returncode})"
        print(f"\n{status} — results in {run_dir}")

    return {
        "success": success,
        "output": output,
        "run_dir": run_dir,
        "log": log_path,
        "result": result_path,
    }


# ── Convenience wrappers ───────────────────────────────────────────────────────

# CellAtria analysis type templates (mirrors cellatria_workflow.py)
_CELLATRIA_TEMPLATES = {
    "Metadata Extraction (URL)": (
        "Extract structured scRNA-seq metadata from this article URL: {INPUT}. "
        "Identify: organism, tissue type, cell types, GEO accession IDs, sample count, "
        "and experimental conditions. Focus on any mention of {GENE}."
    ),
    "Metadata Extraction (PDF)": (
        "Extract structured scRNA-seq metadata from the uploaded PDF: {INPUT}. "
        "Identify: organism, tissue type, cell types, GEO accession IDs, sample count, "
        "and experimental conditions. Focus on any mention of {GENE}."
    ),
    "GEO Dataset Retrieval": (
        "Retrieve the GEO dataset {INPUT}. "
        "Fetch metadata, list available files, and download the raw count matrix. "
        "Report sample count, conditions, and data format. "
        "Organize files into the working directory."
    ),
    "Full Pipeline": (
        "Execute the full CellAtria pipeline for GEO accession {INPUT}: "
        "1) Fetch GEO metadata and sample annotations, "
        "2) Download raw count data, "
        "3) Configure and run CellExpress for QC, normalization, clustering, and cell type annotation, "
        "4) Report findings including cell type composition and any {GENE} expression patterns."
    ),
    "Custom Query": "{INPUT}",
}

# ST Agent analysis type templates (mirrors st_agent_workflow.py)
_ST_AGENT_TEMPLATES = {
    "Explore Metadata": (
        "Load the spatial transcriptomics dataset from {H5AD}. "
        "Explore and summarize the metadata: number of cells/spots, tissue sections, "
        "available cell type annotations, spatial coordinates, and key gene statistics. "
        "Focus on {GENE} expression distribution across the tissue."
    ),
    "Quality Control": (
        "Load {H5AD} and perform quality control analysis. "
        "Report: total counts per spot, number of genes per spot, mitochondrial gene fraction, "
        "spatial distribution of QC metrics, and flag any low-quality spots. "
        "Highlight any spatial patterns in QC metrics relevant to {GENE}."
    ),
    "Spatial Gene Expression": (
        "Load {H5AD} and visualize the spatial expression pattern of {GENE} across the tissue. "
        "Generate a spatial expression map, identify high-expression regions, "
        "and report co-expressed genes in the same spatial domains. "
        "Describe the tissue context of {GENE} expression."
    ),
    "Cell Type Mapping": (
        "Load {H5AD} and perform cell type annotation. "
        "Generate a spatial cell type map, report cell type composition per tissue region, "
        "and identify which cell types express {GENE} most highly. "
        "Visualize UMAP colored by cell type and {GENE} expression."
    ),
    "Cell-Cell Interaction": (
        "Load {H5AD} and perform ligand-receptor interaction analysis focused on {GENE}. "
        "Identify significant interactions involving {GENE} or its pathway partners, "
        "visualize the spatial interaction network, and report the top interacting cell type pairs."
    ),
    "Full Analysis Report": (
        "Load {H5AD} and perform a complete spatial transcriptomics analysis for {GENE}: "
        "1) QC and preprocessing, "
        "2) Cell type annotation and UMAP, "
        "3) Spatial expression map for {GENE}, "
        "4) Ligand-receptor interaction analysis, "
        "5) Literature synthesis of {GENE} spatial expression findings. "
        "Generate a comprehensive report with all visualizations."
    ),
}


def run_cellatria(
    input: str,
    *,
    analysis: str = "Full Pipeline",
    gene: str = "IFNG",
    model: str = "claude-sonnet-4-6",
    project: str = "notebook",
    timeout: int = 1800,
    **kwargs,
) -> dict:
    """
    Run the CellAtria scRNA-seq workflow.

    Parameters
    ----------
    input : str
        GEO accession (e.g. "GSE284775"), article URL, or PDF path.
    analysis : str
        One of: "Metadata Extraction (URL)", "Metadata Extraction (PDF)",
        "GEO Dataset Retrieval", "Full Pipeline", "Custom Query".
    gene : str
        Target gene symbol (default "IFNG").
    model : str
        Claude model ID (default sonnet — recommended for CellAtria).

    Examples
    --------
    >>> run_cellatria("GSE284775", analysis="Full Pipeline", gene="IFNG")
    >>> run_cellatria("https://doi.org/...", analysis="Metadata Extraction (URL)")
    """
    template = _CELLATRIA_TEMPLATES.get(analysis)
    if template is None:
        raise ValueError(f"Unknown CellAtria analysis '{analysis}'. "
                         f"Choose from: {list(_CELLATRIA_TEMPLATES)}")
    prompt = template.replace("{INPUT}", input).replace("{GENE}", gene)
    return run_workflow("CellAtria", prompt, model=model, project=project,
                        timeout=timeout, **kwargs)


def run_st_agent(
    h5ad: str,
    *,
    gene: str = "IFNG",
    analysis: str = "Spatial Gene Expression",
    model: str = "claude-haiku-4-5-20251001",
    project: str = "notebook",
    skip_vision: bool = True,
    timeout: int = 1200,
    **kwargs,
) -> dict:
    """
    Run the ST Agent spatial transcriptomics workflow.

    Parameters
    ----------
    h5ad : str
        Path to the .h5ad spatial transcriptomics file.
    gene : str
        Target gene symbol (default "IFNG").
    analysis : str
        One of: "Explore Metadata", "Quality Control", "Spatial Gene Expression",
        "Cell Type Mapping", "Cell-Cell Interaction", "Full Analysis Report".
    skip_vision : bool
        Disable image re-encoding in LLM context (saves 30-50% tokens, default True).

    Examples
    --------
    >>> run_st_agent("data/sample.h5ad", gene="IFNG", analysis="Full Analysis Report")
    """
    template = _ST_AGENT_TEMPLATES.get(analysis)
    if template is None:
        raise ValueError(f"Unknown ST Agent analysis '{analysis}'. "
                         f"Choose from: {list(_ST_AGENT_TEMPLATES)}")
    prompt = template.replace("{H5AD}", h5ad).replace("{GENE}", gene)
    return run_workflow("ST Agent", prompt, model=model, project=project,
                        skip_vision=skip_vision, timeout=timeout, **kwargs)


def run_biomni(
    prompt: str,
    *,
    model: str = "claude-sonnet-4-6",
    project: str = "notebook",
    data_dir: str | None = None,
    timeout: int = 1200,
    **kwargs,
) -> dict:
    """
    Run the Biomni general-purpose biomedical agent.

    Parameters
    ----------
    prompt : str
        Free-form biomedical query.

    Examples
    --------
    >>> run_biomni("Analyze differential expression of IFNG in GSE96058")
    """
    return run_workflow("Biomni", prompt, model=model, project=project,
                        data_dir=data_dir, timeout=timeout, **kwargs)


def run_geo_sra(
    prompt: str,
    *,
    model: str = "claude-haiku-4-5-20251001",
    project: str = "notebook",
    data_dir: str | None = None,
    timeout: int = 1200,
    **kwargs,
) -> dict:
    """
    Run the GEO/SRA dataset search and analysis workflow.

    Parameters
    ----------
    prompt : str
        Free-form GEO/SRA query or accession.

    Examples
    --------
    >>> run_geo_sra("Download GSE96058 and run DESeq2 DEG analysis for IFNG")
    """
    return run_workflow("GEO/SRA", prompt, model=model, project=project,
                        data_dir=data_dir, timeout=timeout, **kwargs)
