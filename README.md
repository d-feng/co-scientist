# Co-scientist

A multi-workflow agentic research platform. Run specialized biomedical AI workflows from a single desktop UI — no web server required.

## Workflows

| Workflow | Description |
|----------|-------------|
| **Biomni** | General-purpose biomedical AI agent (Stanford SNAP) — protein expression, DEG, target characterization, scRNA-seq |
| **GEO/SRA** | Search, download, and analyze NCBI GEO/SRA datasets — DESeq2, edgeR, limma-voom, pathway enrichment |
| **ST Agent** | Spatial transcriptomics analysis — Harvard Liu Lab STAgent (h5ad → cell type mapping, spatial gene expression, cell-cell interaction, full report) |

## Requirements

- Python 3.11+
- pip (all dependencies installed via pip — no conda required)
- NVIDIA GPU recommended (CPU-only also works)
- Anthropic API key (or OpenAI / Gemini key)

## Setup

### 1. Configure API key

Create a `.env` file in this folder:

```
ANTHROPIC_API_KEY=your_key_here
NCBI_API_KEY=your_ncbi_key_here   # optional, raises GEO rate limit to 10 req/sec
```

### 2. Create virtual environment

**Windows:**
```bat
setup_venv.bat
```

**Linux:**
```bash
chmod +x setup_venv.sh && ./setup_venv.sh
```

## How to Run

**Windows:**
```bat
venv\Scripts\activate
python co_scientist.py
```

**Linux:**
```bash
source venv/bin/activate
python co_scientist.py
```

## UI Overview

```
┌─────────────────────────────────────────────────────────────┐
│  Configuration: Project | Model | Data dir | Timeout | Flags │
├──────────┬──────────────────────────┬───────────────────────┤
│Workflows │  Workflow Input Panel    │  Data Sources         │
│          │  (changes per workflow)  ├───────────────────────┤
│ Biomni   │                          │  Memory               │
│ GEO/SRA  │                          │  (semantic search)    │
├──────────┴──────────────────────────┴───────────────────────┤
│  Output (live streaming terminal)                           │
├─────────────────────────────────────────────────────────────┤
│  ▶ Start | ■ Stop | Clear | Results Manager       [status]  │
└─────────────────────────────────────────────────────────────┘
```

## Memory System

Each project has isolated semantic memory (ChromaDB, `all-MiniLM-L6-v2`).

**Flow per run:**
1. Click **▶ Start** → auto-searches current project for relevant past results
2. Top 3 matches shown in Memory panel (pre-checked)
3. Checked results injected into prompt as context
4. After completion → **Results Review** popup: **Keep** or **Delete**
5. Kept results used in all future runs for that project

Toggle **"Auto-include memory"** to disable injection without clearing results.

## ST Agent Workflow

Powered by [STAgent](https://github.com/LiuLab-Bioelectronics-Harvard/STAgent) (Harvard Liu Lab).

| Input | Description |
|-------|-------------|
| H5AD file | Spatial transcriptomics dataset (`.h5ad`) |
| Gene | Target gene symbol (default: IFNG) |
| Analysis | Explore Metadata / QC / Spatial Expression / Cell Type Mapping / Cell-Cell Interaction / Full Report |
| Mode | **Headless** (output in panel) or **Streamlit UI** (launches browser at `localhost:8501`) |

**Analysis types:**
- **Explore Metadata** — summarize cells, spatial coords, gene stats
- **Quality Control** — QC metrics per spot, spatial distribution
- **Spatial Gene Expression** — expression map, co-expressed genes, tissue context
- **Cell Type Mapping** — annotation, spatial map, UMAP
- **Cell-Cell Interaction** — ligand-receptor analysis, interaction network
- **Full Analysis Report** — complete pipeline + literature synthesis

**Sample data:** Available from the [STAgent repo](https://github.com/LiuLab-Bioelectronics-Harvard/STAgent) Google Drive link — place `.h5ad` files in `./data/`.

## GEO/SRA Workflow

| Input | Description |
|-------|-------------|
| Gene | Target gene symbol (default: IFNG) |
| Accession | Direct GEO accession (e.g. GSE96058) — leave blank to search |
| Species | Homo sapiens, Mus musculus, etc. |
| Years back | Search window for GEO discovery |
| Analysis | Search & Discover / Download & Extract / DEG Analysis / Full Pipeline |
| DEG method | DESeq2 (default), edgeR, limma-voom, pyDESeq2 |

## GEO/SRA Test Results (2026-05-03)

Tested **Search & Discover** for IFNG in Homo sapiens (past 5 years, ≥10 samples).
Found 14 qualifying studies. Top 10 ranked by sample size:

| Accession | Samples | Title | Date |
|-----------|---------|-------|------|
| GSE313775 | 66 | Circulating Th1/Th17 cells in endometriosis | 2025-12 |
| GSE255517 | 57 | CRISPR screen of tumor microenvironment modulators | 2026-01 |
| GSE318083 | 43 | BAF complexes and stimulus-responsive chromatin | 2026-04 |
| GSE302854 | 40 | PBMCs transcriptome in pulmonary sarcoidosis | 2025-12 |
| GSE324594 | 36 | IFN-γ transcriptional changes in keratinocytes | 2026-03 |
| GSE255658 | 30 | IFN-γ in PILRA knockout iPSC-derived microglia | 2025-11 |
| GSE322659 | 24 | NOS2 in metastatic triple-negative breast cancer | 2026-03 |
| GSE294918 | 20 | IFN-γ-induced memory in human macrophages | 2025-12 |
| GSE261696 | 19 | Transcriptional profiling of human monocytes/macrophages | 2026-01 |
| GSE264636 | 15 | Single-cell profiling of cutaneous T-cell lymphomas | 2026-04 |

Recommended next step: run **DEG Analysis** on GSE294918 (IFN-γ macrophage memory, 20 samples, well-powered).

## File Locations

| File | Path |
|------|------|
| Run logs | `~/co_scientist_logs/` |
| Memory database | `~/co_scientist_memory/` |
| Data sources | `~/co_scientist_data_sources.json` |
| Projects list | `~/co_scientist_projects.json` |

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

Then add it to `workflows/__init__.py`:
```python
from .my_workflow import MyWorkflow
WORKFLOWS = [BiomniWorkflow(), GeoSraWorkflow(), MyWorkflow()]
```
