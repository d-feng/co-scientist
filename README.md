# Co-scientist

A multi-workflow agentic research platform. Run specialized biomedical AI workflows from a single desktop UI — no web server required.

## Workflows

| Workflow | Description |
|----------|-------------|
| **Biomni** | General-purpose biomedical AI agent (Stanford SNAP) — protein expression, DEG, target characterization, scRNA-seq |
| **GEO/SRA** | Search, download, and analyze NCBI GEO/SRA datasets — DESeq2, edgeR, limma-voom, pathway enrichment |
| **ST Agent** | Spatial transcriptomics analysis — Harvard Liu Lab STAgent (h5ad → cell type mapping, spatial gene expression, cell-cell interaction, full report) |
| **CellAtria** | Single-cell RNA-seq agent — AstraZeneca [CellAtria](https://github.com/AstraZeneca/cellatria) (GEO metadata extraction, dataset retrieval, QC → clustering → cell type annotation via CellExpress) |

## Requirements

- Python 3.11+
- pip (no conda required)
- NVIDIA GPU recommended (CPU-only also works)
- Anthropic API key (or OpenAI / Gemini key)

## Setup

### 1. Clone the repository

```bash
git clone https://github.com/d-feng/co-scientist.git
cd co-scientist
git submodule update --init --recursive
```

### 2. Configure API keys

Create a `.env` file in the repo root:

```
ANTHROPIC_API_KEY=your_key_here
NCBI_API_KEY=your_ncbi_key_here   # optional — raises GEO rate limit to 10 req/sec
```

### 3. Create virtual environment

**Windows:**
```bat
setup_venv.bat
```

**Linux / Mac:**
```bash
chmod +x setup_venv.sh && ./setup_venv.sh
```

The setup script:
- Creates `venv/` in the repo root
- Installs core dependencies (biomni, langgraph, chromadb)
- Auto-detects CUDA and installs the matching PyTorch build (CUDA 12.x, 11.x, or CPU)
- Installs the full STAgent spatial transcriptomics stack (squidpy, scanpy, anndata, spatialdata, etc.)
- Installs CellAtria / CellExpress dependencies (gradio, GEOparse, celltypist, scrublet, harmonypy, scimilarity, zarr)
- On Debian/Ubuntu: installs `python3-venv` and `python3-tk` via apt-get if missing

> **Note:** `PIP_NO_BUILD_ISOLATION=1` is set automatically during install. This is required for `pims` (a squidpy dependency that uses a legacy `setup.py`).

## How to Run

**Windows:**
```bat
venv\Scripts\activate
python co_scientist.py
```

**Linux / Mac:**
```bash
source venv/bin/activate
python co_scientist.py
```

### Running on a headless Linux server

The UI requires a display (tkinter). Three options:

**Option 1 — SSH with X forwarding:**
```bash
ssh -X user@your-server
source venv/bin/activate
python co_scientist.py
```

**Option 2 — VNC / virtual display:**
```bash
Xvfb :99 -screen 0 1024x768x24 &
DISPLAY=:99 source venv/bin/activate
DISPLAY=:99 python co_scientist.py
```

**Option 3 — Run STAgent directly (no GUI):**
```python
# headless_run.py — run from the repo root with the venv active
import sys, os
from pathlib import Path
from dotenv import load_dotenv

st_src = str(Path("vendors/STAgent/src").resolve())
sys.path.insert(0, st_src)
os.chdir(st_src)
load_dotenv(Path(st_src) / ".env")
os.environ.setdefault("GOOGLE_API_KEY", "dummy")
os.environ.setdefault("OPENAI_API_KEY", "dummy")
import matplotlib; matplotlib.use("Agg")

from langchain_core.messages import HumanMessage
from graph_unified import invoke_our_graph

result = invoke_our_graph(
    [HumanMessage(content="Load /path/to/data.h5ad and visualize spatial expression of IFNG.")],
    model_name="claude-sonnet-4-20250514"
)
messages = result.get("messages", [])
print(messages[-1].content if messages else "(no output)")
```

## UI Overview

```
┌─────────────────────────────────────────────────────────────────┐
│  Project | Model | Python | Data dir | Timeout | Skip vision    │
├──────────┬────────────────────────────┬─────────────────────────┤
│Workflows │  Workflow Input Panel      │  Data Sources           │
│          │  (changes per workflow)    ├─────────────────────────┤
│ Biomni   │                            │  Memory                 │
│ GEO/SRA  │                            │  (semantic search)      │
│ ST Agent │                            │                         │
│ CellAtria│                            │                         │
├──────────┴────────────────────────────┴─────────────────────────┤
│  Output (live streaming terminal)                               │
├─────────────────────────────────────────────────────────────────┤
│  ▶ Start | ■ Stop | Clear | Results Manager          [status]   │
└─────────────────────────────────────────────────────────────────┘
```

**Configuration row:**
| Field | Description |
|-------|-------------|
| Project | Isolates memory and results by project name |
| Model | LLM to use — defaults to Haiku (cheapest); Sonnet for complex analyses |
| Python | Path to Python interpreter for the active workflow — leave blank to use the current venv |
| Data dir | Default data directory passed to Biomni / GEO workflows |
| Timeout | Max seconds per run (default 1200) |
| Skip vision | Prevents STAgent from re-sending plot images to the LLM (saves 30–50% tokens) |

## Memory System

Each project has isolated semantic memory (ChromaDB, `all-MiniLM-L6-v2`).

**Flow per run:**
1. Click **▶ Start** → auto-searches current project for relevant past results
2. Top matches shown in the Memory panel (pre-checked)
3. Checked results injected into the prompt as context
4. After completion → **Results Review** popup: **Keep** or **Delete**
5. Kept results are used in all future runs for that project

Toggle **"Auto-include memory"** to disable injection without clearing stored results.

## Results

Every run creates a self-contained folder:

```
results/
└── {project}/
    └── {gene}_{analysis}_{timestamp}/
        ├── run.log       — full streaming output
        ├── result.txt    — final LLM answer
        ├── *.png         — plots generated by STAgent
        ├── *.csv         — tabular outputs
        └── *.json        — structured results
```

H5AD files written by STAgent are moved to `data/processed/{project}/` and shared across runs (not duplicated per run).

## ST Agent Workflow

Powered by [STAgent](https://github.com/LiuLab-Bioelectronics-Harvard/STAgent) (Harvard Liu Lab).

**Input fields:**

| Field | Description |
|-------|-------------|
| H5AD file | Spatial transcriptomics dataset — browse or select from Data Sources |
| Gene | Target gene symbol (default: IFNG) |
| Analysis | Select from the analysis types below |
| Query | Auto-generated prompt — editable before running |

**Analysis types:**

| Type | What it does |
|------|-------------|
| Explore Metadata | Summarize spots, spatial coordinates, cell type annotations, gene stats |
| Quality Control | QC metrics per spot, mitochondrial fraction, spatial distribution |
| Spatial Gene Expression | Expression map, high-expression regions, co-expressed genes |
| Cell Type Mapping | Cell type annotation, spatial map, UMAP colored by cell type and gene |
| Cell-Cell Interaction | Ligand-receptor analysis (squidpy), top interacting cell type pairs |
| Full Analysis Report | Complete pipeline: QC → annotation → spatial expression → interactions → literature |

**Cost-saving options (enabled by default):**
- **Skip vision** — disables image re-encoding in LLM context (saves ~30–50% tokens)
- Squidpy ligand-receptor permutations reduced 500 → 50 (controllable via `STAGENT_N_PERMS`)
- Tool output truncated to 2000 chars per message (controllable via `STAGENT_TOOL_OUTPUT_LIMIT`)
- Default model is Haiku — switch to Sonnet for higher accuracy

**Sample data:** Available from the [STAgent repo](https://github.com/LiuLab-Bioelectronics-Harvard/STAgent) Google Drive link — place `.h5ad` files in `./data/`.

**Estimated cost per run (Haiku):**

| Analysis | Approx. cost |
|----------|-------------|
| Explore Metadata | ~$0.01 |
| Cell Type Mapping | ~$0.05–0.10 |
| Cell-Cell Interaction | ~$0.10–0.20 |
| Full Analysis Report | ~$0.30–0.60 |

## CellAtria Workflow

Powered by [CellAtria](https://github.com/AstraZeneca/cellatria) (AstraZeneca) — a LangGraph-based scRNA-seq agent with 33 tools.

**Input fields:**

| Field | Description |
|-------|-------------|
| Analysis | Preset analysis type (see below) |
| Input | URL, GEO accession (e.g. GSE284775), or path to a PDF |
| Gene | Target gene symbol (default: IFNG) |
| Query | Auto-generated prompt — editable before running |

**Analysis types:**

| Type | What it does |
|------|-------------|
| Metadata Extraction (URL) | Extract scRNA-seq metadata (organism, tissue, cell types, GEO IDs) from an article URL |
| Metadata Extraction (PDF) | Same extraction from an uploaded PDF |
| GEO Dataset Retrieval | Fetch GEO metadata, list files, download raw count matrix |
| Full Pipeline | End-to-end: fetch → download → QC → normalize → cluster → annotate cell types |
| Custom Query | Free-form prompt — full access to all 33 CellAtria tools |

**Supported input formats:**

| Format | Notes |
|--------|-------|
| 10X Genomics (MTX) | `matrix.mtx.gz`, `features.tsv.gz`, `barcodes.tsv.gz` — native CellExpress input |
| H5 / H5AD | Direct CellExpress input |
| BD Rhapsody | `*_DBEC_MolsPerCell.csv.gz` or `*_ReadsPerCell.csv.gz` — auto-converted to H5AD |

**Estimated cost per run (Sonnet):**

| Analysis | Approx. cost |
|----------|-------------|
| Metadata Extraction | ~$0.02–0.05 |
| GEO Dataset Retrieval | ~$0.05–0.10 |
| Full Pipeline | ~$0.20–0.50 |

## GEO/SRA Workflow

| Input | Description |
|-------|-------------|
| Gene | Target gene symbol (default: IFNG) |
| Accession | Direct GEO accession (e.g. GSE96058) — leave blank to search |
| Species | Homo sapiens, Mus musculus, etc. |
| Years back | Search window for GEO discovery |
| Analysis | Search & Discover / Download & Extract / DEG Analysis / Full Pipeline |
| DEG method | DESeq2 (default), edgeR, limma-voom, pyDESeq2 |

## File Locations

| Path | Contents |
|------|----------|
| `results/{project}/{gene}_{analysis}_{timestamp}/` | Per-run outputs: plots, CSVs, result text, log |
| `data/processed/{project}/` | Processed H5AD files (shared across runs) |
| `data/` | Raw input data (place `.h5ad` files here) |
| `~/co_scientist_memory/` | ChromaDB semantic memory database |
| `~/co_scientist_data_sources.json` | Saved data source entries |
| `~/co_scientist_projects.json` | Project list |
| `~/co_scientist_workflow_bins.json` | Per-workflow Python interpreter paths |

## Jupyter Notebook

All workflows can be run headlessly from `co_scientist.ipynb` — no tkinter / GUI required.

```bash
# activate venv first, then:
jupyter notebook co_scientist.ipynb
```

```python
from notebook_api import list_workflows, run_cellatria, run_st_agent, run_biomni, run_geo_sra

# List available workflows
list_workflows()

# Run CellAtria full pipeline
result = run_cellatria("GSE284775", analysis="Full Pipeline", gene="IFNG")

# Run ST Agent spatial expression
result = run_st_agent("data/sample.h5ad", gene="IFNG", analysis="Spatial Gene Expression")

# Run Biomni
result = run_biomni("Characterize the role of IFNG in tumor immune evasion.")

# Run GEO/SRA
result = run_geo_sra("Download GSE96058 and run DESeq2 DEG analysis for IFNG.")

# Display plots generated by the run
from IPython.display import Image, display
for png in sorted(result["run_dir"].glob("*.png")):
    display(Image(filename=str(png)))
```

All results are saved to `results/{project}/{workflow}_{timestamp}/` — same folder structure as the GUI.

## Adding New Workflows

Create `workflows/my_workflow.py` implementing `BaseWorkflow`:

```python
from .base import BaseWorkflow

class MyWorkflow(BaseWorkflow):
    name = "My Workflow"
    description = "..."
    icon = "⚗️"

    def build_input_panel(self, parent): ...
    def get_prompt(self) -> str: ...
    def get_run_script(self, model, data_dir, timeout, skip_datalake, full_prompt) -> str: ...
    def get_metadata(self) -> dict: ...
```

Then register it in `workflows/__init__.py`:
```python
from .my_workflow import MyWorkflow
WORKFLOWS = [BiomniWorkflow(), GeoSraWorkflow(), StAgentWorkflow(), MyWorkflow()]
```
