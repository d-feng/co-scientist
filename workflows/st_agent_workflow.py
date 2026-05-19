"""Spatial Transcriptomics (STAgent) workflow plugin — Harvard Liu Lab."""
import os
from pathlib import Path
from .base import BaseWorkflow

DEFAULT_GENE = "IFNG"
ST_AGENT_SRC = Path(__file__).parent.parent / "vendors" / "STAgent" / "src"

ANALYSIS_TYPES = {
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


class StAgentWorkflow(BaseWorkflow):
    name = "ST Agent"
    description = "Spatial transcriptomics analysis — Harvard Liu Lab STAgent"
    icon = "🗺️"

    def __init__(self):
        # Allow override via UI Python: field or STAGENT_PYTHON_BIN env var.
        # Defaults to blank = current pip venv (sys.executable).
        self.python_bin = os.environ.get("STAGENT_PYTHON_BIN", "")
        self.h5ad_var = None
        self.gene_var = None
        self.analysis_var = None
        self.mode_var = None
        self.query_text = None

    def build_input_panel(self, parent):
        import tkinter as tk
        from tkinter import ttk, filedialog
        frame = ttk.LabelFrame(parent, text="Spatial Transcriptomics — STAgent", padding=6)
        frame.columnconfigure(1, weight=1)
        frame.rowconfigure(5, weight=1)

        # Row 0: h5ad file
        ttk.Label(frame, text="H5AD file:").grid(row=0, column=0, sticky="w", padx=(0, 4))
        self.h5ad_var = tk.StringVar(value="")
        h5ad_entry = ttk.Entry(frame, textvariable=self.h5ad_var, width=38)
        h5ad_entry.grid(row=0, column=1, sticky="ew", padx=(0, 4))
        ttk.Button(frame, text="Browse…", command=self._browse_h5ad).grid(row=0, column=2, sticky="w")
        self.h5ad_var.trace_add("write", self._update_query)

        # Row 1: gene + analysis type
        ttk.Label(frame, text="Gene:").grid(row=1, column=0, sticky="w", padx=(0, 4), pady=(4, 0))
        self.gene_var = tk.StringVar(value=DEFAULT_GENE)
        ttk.Entry(frame, textvariable=self.gene_var, width=14).grid(
            row=1, column=1, sticky="w", pady=(4, 0))
        self.gene_var.trace_add("write", self._update_query)

        # Row 2: analysis type
        ttk.Label(frame, text="Analysis:").grid(row=2, column=0, sticky="w", padx=(0, 4), pady=(4, 0))
        self.analysis_var = tk.StringVar(value=list(ANALYSIS_TYPES.keys())[0])
        analysis_cb = ttk.Combobox(frame, textvariable=self.analysis_var,
                                   values=list(ANALYSIS_TYPES.keys()),
                                   state="readonly", width=28)
        analysis_cb.grid(row=2, column=1, sticky="w", pady=(4, 0))
        analysis_cb.bind("<<ComboboxSelected>>", self._update_query)

        # Row 3: run mode (headless only)
        self.mode_var = tk.StringVar(value="Headless (in output panel)")

        # Row 4: separator
        ttk.Separator(frame, orient="horizontal").grid(
            row=4, column=0, columnspan=3, sticky="ew", pady=6)

        # Row 5: query text
        ttk.Label(frame, text="Query:").grid(row=5, column=0, sticky="nw", padx=(0, 4))
        self.query_text = tk.Text(frame, wrap="word", height=9)
        self.query_text.grid(row=5, column=1, columnspan=2, sticky="nsew")
        scroll = ttk.Scrollbar(frame, command=self.query_text.yview)
        scroll.grid(row=5, column=3, sticky="ns")
        self.query_text.configure(yscrollcommand=scroll.set)

        self._update_query()
        return frame

    def _browse_h5ad(self):
        path = filedialog.askopenfilename(
            title="Select H5AD file",
            filetypes=[("H5AD files", "*.h5ad"), ("All files", "*.*")]
        )
        if path:
            self.h5ad_var.set(path)

    def _update_query(self, *_):
        if not self.query_text:
            return
        template = ANALYSIS_TYPES[self.analysis_var.get()]
        gene = self.gene_var.get().strip() or DEFAULT_GENE
        h5ad = self.h5ad_var.get().strip() or "[select an h5ad file]"
        query = template.replace("{GENE}", gene).replace("{H5AD}", h5ad)
        self.query_text.delete("1.0", "end")
        self.query_text.insert("1.0", query)

    def get_prompt(self) -> str:
        if self.query_text:
            return self.query_text.get("1.0", "end-1c").strip()
        return ""

    def get_run_script(self, model, data_dir, timeout, skip_datalake, full_prompt) -> str:
        st_src = str(ST_AGENT_SRC).replace("\\", "/")
        project_root = str(Path(__file__).parent.parent).replace("\\", "/")
        return f"""
import sys, os
from pathlib import Path
from dotenv import load_dotenv

st_src = {repr(st_src)}
# Load project .env first so GEMINI_API_KEY / OPENAI_API_KEY override any stale system vars
load_dotenv(Path({repr(project_root)}) / ".env", override=True)
# STAgent uses GOOGLE_API_KEY; forward GEMINI_API_KEY if set
if os.environ.get("GEMINI_API_KEY") and not os.environ.get("GOOGLE_API_KEY"):
    os.environ["GOOGLE_API_KEY"] = os.environ["GEMINI_API_KEY"]
# Suppress Streamlit "missing ScriptRunContext" warnings before importing anything
os.environ["STREAMLIT_LOGGER_LEVEL"] = "error"
import logging
logging.getLogger("streamlit").setLevel(logging.ERROR)
import warnings
warnings.filterwarnings("ignore")
sys.path.insert(0, st_src)
os.chdir(st_src)
load_dotenv(Path(st_src) / ".env")   # STAgent's own .env (lower priority)
# Set dummy keys for providers not in use so SDKs don't raise credential errors
os.environ.setdefault("GOOGLE_API_KEY", "dummy")
os.environ.setdefault("OPENAI_API_KEY", "dummy")
# Force non-interactive matplotlib backend so plots save to file instead of opening a window
import matplotlib
matplotlib.use("Agg")

# Patch STAgent config to register gemini-2.5-flash before UnifiedLLMGraph is imported
import config as _st_config
_st_config.app_config.models.setdefault("gemini", {{}})
_st_config.app_config.models["gemini"].setdefault("gemini-2.5-flash", {{"temperature": 0}})

from langchain_core.messages import HumanMessage, ToolMessage
from graph_unified import invoke_our_graph, UnifiedLLMGraph

# Reduce squidpy ligand-receptor permutations (default 500 → 50 for speed).
# Patch after graph_unified import so tools.py has already imported squidpy.gr.
import squidpy.gr as _sqgr
import tools as _st_tools
_orig_ligrec = _sqgr.ligrec
def _patched_ligrec(*args, **kwargs):
    kwargs.setdefault("n_perms", int(os.environ.get("STAGENT_N_PERMS", "50")))
    return _orig_ligrec(*args, **kwargs)
_sqgr.ligrec = _patched_ligrec
if hasattr(_st_tools, "ligrec"):
    _st_tools.ligrec = _patched_ligrec

# Truncate tool output content to save tokens (option 3).
# Long Python REPL outputs and metadata dumps get re-sent on every LLM call.
_TOOL_OUTPUT_LIMIT = int(os.environ.get("STAGENT_TOOL_OUTPUT_LIMIT", "2000"))

_orig_call_model = UnifiedLLMGraph._call_model

def _patched_call_model(self, state, config):
    # Truncate all tool message content in history before passing to LLM
    n_msgs = len(state.get("messages", []))
    for msg in state.get("messages", []):
        if isinstance(msg, ToolMessage):
            if isinstance(msg.content, str) and len(msg.content) > _TOOL_OUTPUT_LIMIT:
                msg.content = msg.content[:_TOOL_OUTPUT_LIMIT] + "\\n...[truncated]"
        # Skip vision: clear plot artifacts so images aren't base64-encoded
        if os.environ.get("STAGENT_SKIP_VISION", "1") == "1":
            if isinstance(msg, ToolMessage) and getattr(msg, "artifact", None):
                msg.artifact = None
    import datetime as _dt
    print(f"[{{_dt.datetime.now().strftime('%H:%M:%S')}}] LLM call ({{n_msgs}} messages in context)...")
    return _orig_call_model(self, state, config)

UnifiedLLMGraph._call_model = _patched_call_model

# STAgent requires conversations to end with a user message (no prefill).
# Map shorthand model IDs to dated versions compatible with STAgent.
_model_map = {{
    "claude-haiku-4-5-20251001": "claude-haiku-4-5-20251001",
    "claude-sonnet-4-6": "claude-sonnet-4-20250514",
    "claude-opus-4-6":   "claude-opus-4-20250514",
    "gemini-2.5-flash":  "gemini-2.5-flash",
    "gpt-4o":            "gpt-4o",
}}
_model = _model_map.get({repr(model)}, {repr(model)})

_run_dir = os.environ.get("STAGENT_PLOT_DIR", "")
_headless = (
    "This is a headless automated run — do NOT ask for confirmation or follow-up questions. "
    "Execute the full requested analysis and deliver the complete result directly."
)
_output_dir_hint = (" Use output_dir=" + repr(_run_dir) + " for all file outputs.") if _run_dir else ""
query = {repr(full_prompt)} + _output_dir_hint + " " + _headless
messages = [HumanMessage(content=query)]

print("Running STAgent headless...")
print("=" * 60)

result = invoke_our_graph(messages, model_name=_model)

print("\\n=== RESULT ===")
messages = result.get("messages", [])

def _extract_text(content):
    if isinstance(content, list):
        parts = [b["text"] for b in content if isinstance(b, dict) and b.get("type") == "text"]
        return "\\n".join(parts)
    return str(content) if content else ""

# Walk backwards to find the last message with non-empty text
output = ""
for msg in reversed(messages):
    text = _extract_text(msg.content)
    if text.strip():
        output = text
        break

print(output if output else "(no text output)")
"""

    def get_metadata(self) -> dict:
        return {
            "gene": self.gene_var.get().strip() if self.gene_var else DEFAULT_GENE,
            "preset": self.analysis_var.get() if self.analysis_var else "",
        }
