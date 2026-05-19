# Co-scientist

Agentic biomedical research platform. Run specialized AI workflows from the CLI, Jupyter, or a desktop GUI — no R required.

## Workflows

| Workflow | What it does |
|----------|-------------|
| **Biomni** | General biomedical AI agent — protein expression, DEG, target characterization, scRNA-seq |
| **GEO/SRA** | Search, download, and analyze NCBI GEO/SRA datasets — pyDESeq2, pathway enrichment |
| **ST Agent** | Spatial transcriptomics — cell type mapping, spatial gene expression, cell-cell interaction |
| **CellAtria** | Single-cell RNA-seq agent — GEO retrieval, QC → clustering → cell type annotation |

## Requirements

- Python 3.11+
- Linux / Mac / Windows
- At least one API key (Gemini free tier works)

## Setup

```bash
git clone https://github.com/d-feng/co-scientist.git
cd co-scientist
git submodule update --init --recursive
chmod +x setup_venv.sh && ./setup_venv.sh
source venv/bin/activate
```

The setup script creates `venv/`, installs all dependencies, and auto-detects CUDA vs CPU PyTorch.

### API keys

Create `.env` in the repo root. One key is enough to get started:

```bash
# Gemini (free tier available — recommended starting point)
GEMINI_API_KEY=your_key_here

# OpenAI
OPENAI_API_KEY=your_key_here

# Anthropic
ANTHROPIC_API_KEY=your_key_here

# Optional — raises NCBI rate limit from 3 to 10 req/sec
NCBI_API_KEY=your_ncbi_key_here

# Optional — shared data directory for Biomni/GEO data lake (default: ~/biomni_data)
COSCIENTIST_DATA_DIR=/data/co_scientist_data
```

Get keys: [Google AI Studio](https://aistudio.google.com) · [OpenAI](https://platform.openai.com) · [Anthropic](https://console.anthropic.com) · [NCBI](https://www.ncbi.nlm.nih.gov/account/)

> **Model fallback:** if the selected model hits a quota or auth error, the platform automatically retries with the next available model (`gemini-2.5-flash → gpt-4o → claude-sonnet-4-6`).

## Running (Linux headless — no display needed)

### CLI

```bash
source venv/bin/activate

# GEO/SRA — DEG analysis
python cli.py geo "Download GSE272019 and run pyDESeq2 differential expression analysis for IFNG." \
    --project my_project --timeout 1800

# GEO/SRA — full pipeline (search → download → DEG → pathway enrichment)
python cli.py geo "Run full GEO pipeline for IFNG in Homo sapiens: find best dataset, pyDESeq2 DEG, GSEA." \
    --model gemini-2.5-flash --timeout 3600

# Biomni — general biomedical agent
python cli.py biomni "Characterize the role of IFNG in tumor immune evasion." --project my_project

# CellAtria — single-cell RNA-seq
python cli.py cellatria GSE284775 --analysis "Full Pipeline" --gene IFNG --model gemini-2.5-flash

# ST Agent — spatial transcriptomics
python cli.py st-agent data/sample.h5ad --gene IFNG --analysis "Spatial Gene Expression"

# List all workflows
python cli.py list
```

**Global CLI options:**

| Option | Default | Description |
|--------|---------|-------------|
| `--model` | `gemini-2.5-flash` | Model ID |
| `--project` | `cli` | Results isolation namespace |
| `--timeout` | `1200` | Max seconds per run |
| `--base-url` | — | Custom endpoint (LiteLLM / Ollama) |
| `--no-live` | — | Suppress live output streaming |

### Batch runner (YAML job file)

```bash
python run_jobs.py jobs.yaml
python run_jobs.py jobs.yaml --dry-run   # preview without running
```

```yaml
# jobs.yaml
defaults:
  model: gemini-2.5-flash
  project: batch_run
  timeout: 1800

jobs:
  - name: "GEO DEG analysis"
    workflow: geo
    prompt: "Download GSE272019, run pyDESeq2 DEG for IFNG, annotate gene symbols."

  - name: "Biomni characterization"
    workflow: biomni
    prompt: "Characterize the role of IFNG in tumor immune evasion."

  - name: "CellAtria full pipeline"
    workflow: cellatria
    input: GSE284775
    analysis: "Full Pipeline"
    gene: IFNG
    model: gemini-2.5-flash

  - name: "Spatial expression"
    workflow: st-agent
    h5ad: data/sample.h5ad
    gene: IFNG
    analysis: "Spatial Gene Expression"
```

### Jupyter notebook

```bash
jupyter notebook co_scientist.ipynb
```

```python
from notebook_api import run_geo_sra, run_biomni, run_cellatria, run_st_agent

result = run_geo_sra("Download GSE272019 and run pyDESeq2 DEG analysis for IFNG.")
result = run_biomni("Characterize the role of IFNG in tumor immune evasion.")
result = run_cellatria("GSE284775", analysis="Full Pipeline", gene="IFNG")
result = run_st_agent("data/sample.h5ad", gene="IFNG", analysis="Spatial Gene Expression")

# View plots
from IPython.display import Image, display
for png in sorted(result["run_dir"].glob("*.png")):
    display(Image(filename=str(png)))
```

## Desktop GUI (requires display)

```bash
source venv/bin/activate
python co_scientist.py
```

For headless servers, use X forwarding or a virtual display:

```bash
# X forwarding
ssh -X user@your-server && python co_scientist.py

# Virtual display
Xvfb :99 -screen 0 1024x768x24 &
DISPLAY=:99 python co_scientist.py
```

## Models

| Model ID | Provider | Notes |
|----------|----------|-------|
| `gemini-2.5-flash` | Google | **Default** — free tier available |
| `gpt-4o` | OpenAI | Strong general performance |
| `claude-sonnet-4-6` | Anthropic | Recommended for CellAtria / complex tasks |
| `claude-haiku-4-5-20251001` | Anthropic | Cheapest Anthropic option |
| `claude-opus-4-6` | Anthropic | Most capable Anthropic model |

## Results

Every run saves to a self-contained folder:

```
results/{project}/{gene}_{analysis}_{timestamp}/
├── run.log       — full output
├── result.txt    — final answer
├── *.csv         — DEG tables, metadata
└── *.png         — plots and volcano plots
```

## GEO/SRA — No R Required

All differential expression uses **pyDESeq2** (Python). Gene symbol annotation uses **mygene** (Python). No R installation needed.

The agent receives injected skill context with the correct pyDESeq2 v0.5.4 API, mygene annotation, and Ensembl ID handling — it generates and runs the analysis code autonomously.

## Adding a Workflow

Implement `BaseWorkflow` in `workflows/my_workflow.py`:

```python
from .base import BaseWorkflow

class MyWorkflow(BaseWorkflow):
    name = "My Workflow"
    description = "..."
    icon = "⚗️"

    def build_input_panel(self, parent): ...   # tkinter UI (optional for CLI-only)
    def get_prompt(self) -> str: ...
    def get_run_script(self, model, data_dir, timeout, skip_datalake, full_prompt) -> str: ...
    def get_metadata(self) -> dict: ...
```

Register in `workflows/__init__.py`:

```python
from .my_workflow import MyWorkflow
WORKFLOWS = [..., MyWorkflow()]
```
