"""CellAtria (AstraZeneca) single-cell RNA-seq workflow plugin."""
import os
from pathlib import Path
from .base import BaseWorkflow

DEFAULT_GENE = "IFNG"
CELLATRIA_AGENT = Path(__file__).parent.parent / "vendors" / "cellatria" / "agent"

ANALYSIS_TYPES = {
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
    "Custom Query": (
        "{INPUT}"
    ),
}


class CellatriaWorkflow(BaseWorkflow):
    name = "CellAtria"
    description = "Single-cell RNA-seq agent — AstraZeneca CellAtria"
    icon = "🧫"

    def __init__(self):
        self.input_var = None
        self.gene_var = None
        self.analysis_var = None
        self.query_text = None

    def build_input_panel(self, parent):
        import tkinter as tk
        from tkinter import ttk, filedialog
        frame = ttk.LabelFrame(parent, text="CellAtria — Single-cell RNA-seq", padding=6)
        frame.columnconfigure(1, weight=1)
        frame.rowconfigure(4, weight=1)

        # Row 0: analysis type
        ttk.Label(frame, text="Analysis:").grid(row=0, column=0, sticky="w", padx=(0, 4))
        self.analysis_var = tk.StringVar(value=list(ANALYSIS_TYPES.keys())[0])
        analysis_cb = ttk.Combobox(frame, textvariable=self.analysis_var,
                                   values=list(ANALYSIS_TYPES.keys()),
                                   state="readonly", width=30)
        analysis_cb.grid(row=0, column=1, columnspan=2, sticky="w")
        analysis_cb.bind("<<ComboboxSelected>>", self._update_query)

        # Row 1: input (URL / accession / PDF path)
        ttk.Label(frame, text="Input:").grid(row=1, column=0, sticky="w", padx=(0, 4), pady=(4, 0))
        self.input_var = tk.StringVar(value="")
        ttk.Entry(frame, textvariable=self.input_var, width=38).grid(
            row=1, column=1, sticky="ew", padx=(0, 4), pady=(4, 0))
        ttk.Button(frame, text="Browse…", command=self._browse_pdf).grid(
            row=1, column=2, sticky="w", pady=(4, 0))
        self.input_var.trace_add("write", self._update_query)

        # Row 2: gene
        ttk.Label(frame, text="Gene:").grid(row=2, column=0, sticky="w", padx=(0, 4), pady=(4, 0))
        self.gene_var = tk.StringVar(value=DEFAULT_GENE)
        ttk.Entry(frame, textvariable=self.gene_var, width=14).grid(
            row=2, column=1, sticky="w", pady=(4, 0))
        self.gene_var.trace_add("write", self._update_query)

        # Row 3: separator
        ttk.Separator(frame, orient="horizontal").grid(
            row=3, column=0, columnspan=3, sticky="ew", pady=6)

        # Row 4: query text
        ttk.Label(frame, text="Query:").grid(row=4, column=0, sticky="nw", padx=(0, 4))
        self.query_text = tk.Text(frame, wrap="word", height=9)
        self.query_text.grid(row=4, column=1, columnspan=2, sticky="nsew")
        scroll = ttk.Scrollbar(frame, command=self.query_text.yview)
        scroll.grid(row=4, column=3, sticky="ns")
        self.query_text.configure(yscrollcommand=scroll.set)

        self._update_query()
        return frame

    def _browse_pdf(self):
        from tkinter import filedialog
        path = filedialog.askopenfilename(
            title="Select PDF",
            filetypes=[("PDF files", "*.pdf"), ("All files", "*.*")]
        )
        if path:
            self.input_var.set(path)

    def _update_query(self, *_):
        if not self.query_text:
            return
        template = ANALYSIS_TYPES[self.analysis_var.get()]
        gene = self.gene_var.get().strip() or DEFAULT_GENE
        inp = self.input_var.get().strip() or "[enter URL / GEO accession / PDF path]"
        query = template.replace("{GENE}", gene).replace("{INPUT}", inp)
        self.query_text.delete("1.0", "end")
        self.query_text.insert("1.0", query)

    def get_prompt(self) -> str:
        if self.query_text:
            return self.query_text.get("1.0", "end-1c").strip()
        return ""

    def get_run_script(self, model, data_dir, timeout, skip_datalake, full_prompt) -> str:
        agent_src = str(CELLATRIA_AGENT).replace("\\", "/")
        project_root = str(Path(__file__).parent.parent).replace("\\", "/")
        _model_map = {
            "claude-haiku-4-5-20251001": "claude-haiku-4-5-20251001",
            "claude-sonnet-4-6": "claude-sonnet-4-6",
            "claude-opus-4-6": "claude-opus-4-5",
            "gemini-2.5-flash": "gemini-2.5-flash",
            "gpt-4o": "gpt-4o",
        }
        return f"""
import sys, os
from pathlib import Path
from dotenv import load_dotenv

agent_src = {repr(agent_src)}
sys.path.insert(0, agent_src)
os.chdir(agent_src)

# Stub out gradio before any cellatria import so no server is launched.
# utils.py does `import gradio as gr` at module level and accesses gr.themes.
import types as _types

class _Stub:
    # Catches any attribute access and returns a no-op callable
    def __getattr__(self, name):
        return _Stub()
    def __call__(self, *a, **kw):
        return _Stub()
    def __iter__(self):
        return iter([])

_gr_stub = _types.ModuleType("gradio")
_gr_stub.themes = _Stub()
for _k in ["Blocks","Row","Column","Chatbot","Textbox","Button",
           "File","Image","HTML","Markdown","Tab","Tabs",
           "update","Warning","Info","Error","CSS"]:
    setattr(_gr_stub, _k, _Stub())
sys.modules.setdefault("gradio", _gr_stub)

# Stub google.generativeai so utils.py imports cleanly without the package installed
if "google.generativeai" not in sys.modules:
    _genai_stub = _types.ModuleType("google.generativeai")
    _genai_stub.configure = lambda **kw: None
    _genai_stub.GenerativeModel = _Stub
    sys.modules["google.generativeai"] = _genai_stub
    try:
        import google as _google_pkg
        if not hasattr(_google_pkg, "generativeai"):
            setattr(_google_pkg, "generativeai", _genai_stub)
    except ImportError:
        pass

# Load project .env with override so GEMINI/OPENAI/ANTHROPIC keys win over stale system vars
load_dotenv(Path({repr(project_root)}) / ".env", override=True)

_run_dir = os.environ.get("COSCIENTIST_RUN_DIR", {repr(data_dir)})
Path(_run_dir).mkdir(parents=True, exist_ok=True)

_model_raw = {repr(model)}
_model_map = {repr(_model_map)}
_model = _model_map.get(_model_raw, _model_raw)

import uuid
from typing import Annotated, List
from typing_extensions import TypedDict
from langchain_core.messages import HumanMessage, AIMessage
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langgraph.graph import StateGraph
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode, tools_condition
from langgraph.checkpoint.memory import MemorySaver

# Build graph directly — avoids importing Gradio UI from base.py
from toolkit import tools as _cellatria_tools

# Construct LLM based on model provider
if "gemini" in _model:
    from langchain_openai import ChatOpenAI
    _llm = ChatOpenAI(
        model=_model,
        openai_api_key=os.environ.get("GEMINI_API_KEY", ""),
        base_url="https://generativelanguage.googleapis.com/v1beta/openai/",
        temperature=0,
    )
elif _model.startswith("gpt-"):
    from langchain_openai import ChatOpenAI
    _llm = ChatOpenAI(model=_model, openai_api_key=os.environ.get("OPENAI_API_KEY", ""))
else:
    # Anthropic — write .env for get_llm_from_env
    _cellatria_env = Path(agent_src) / ".env"
    _cellatria_env.write_text(
        f"PROVIDER=Anthropic\\n"
        f"ANTHROPIC_API_KEY={{os.environ.get('ANTHROPIC_API_KEY', '')}}\\n"
        f"ANTHROPIC_MODEL={{_model}}\\n"
    )
    from utils import get_llm_from_env
    _llm = get_llm_from_env(agent_src)
with open(f"{{agent_src}}/system_prompts.md", encoding="utf-8") as _f:
    _system_message = _f.read()
_prompt = ChatPromptTemplate.from_messages([
    ("system", _system_message),
    MessagesPlaceholder("messages"),
])
_chat_fn = _prompt | _llm.bind_tools(_cellatria_tools)

class _AgentState(TypedDict):
    messages: Annotated[List, add_messages]

_gb = StateGraph(_AgentState)
_gb.add_node("tools", ToolNode(_cellatria_tools, handle_tool_errors=True))
_gb.add_node("chatbot", lambda state: {{"messages": _chat_fn.invoke(state["messages"])}})
_gb.add_edge("tools", "chatbot")
_gb.add_conditional_edges("chatbot", tools_condition)
_gb.set_entry_point("chatbot")
_graph = _gb.compile(checkpointer=MemorySaver())
_thread_id = str(uuid.uuid4())

_headless = (
    "This is a headless automated run — do NOT ask for confirmation or follow-up questions. "
    f"Save all output files to {{_run_dir}}. "
    "Execute the full requested analysis and deliver the complete result directly."
)
query = {repr(full_prompt)} + " " + _headless

print("Running CellAtria headless...")
print("=" * 60)
sys.stdout.flush()

config = {{"configurable": {{"thread_id": _thread_id}}}}
result = _graph.invoke({{"messages": [HumanMessage(content=query)]}}, config)

print("\\n=== RESULT ===")
messages = result.get("messages", [])

def _extract_text(content):
    if isinstance(content, list):
        parts = [b["text"] for b in content if isinstance(b, dict) and b.get("type") == "text"]
        return "\\n".join(parts)
    return str(content) if content else ""

output = ""
for msg in reversed(messages):
    if isinstance(msg, AIMessage):
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
