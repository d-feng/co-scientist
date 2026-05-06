"""Biomni agentic workflow plugin."""
from .base import BaseWorkflow

DEFAULT_GENE = "IFNG"

PROMPTS = {
    "Protein Expression": (
        "Analyze protein expression changes for {GENE} across protein datasets. "
        "Identify significant expression differences, associated conditions, and potential biological implications."
    ),
    "DEG & Pathway": (
        "Perform differential expression analysis for {GENE} and identify enriched pathways, "
        "GO terms, and KEGG annotations."
    ),
    "Target Characterization": (
        "Characterize {GENE} by: summarizing key findings from literature including known functions and therapeutic relevance; "
        "identifying protein-protein interaction partners and mapping downstream signaling pathways; "
        "summarizing GWAS findings and disease associations across genomic databases."
    ),
    "scRNA-seq Full Pipeline": (
        "Download single-cell RNA-seq data for {GENE} from public repositories, preprocess, "
        "create an h5ad AnnData dataframe with cell metadata and gene expression matrix, "
        "then perform cell type annotation focusing on {GENE} expression patterns across cell clusters."
    ),
}


class BiomniWorkflow(BaseWorkflow):
    name = "Biomni"
    description = "General-purpose biomedical AI agent (Stanford SNAP)"
    icon = "🧬"

    def __init__(self):
        self.preset_var = None
        self.gene_var = None
        self.prompt_text = None

    def build_input_panel(self, parent):
        import tkinter as tk
        from tkinter import ttk
        frame = ttk.LabelFrame(parent, text="Biomni — Prompt", padding=6)
        frame.columnconfigure(1, weight=1)
        frame.rowconfigure(2, weight=1)

        ttk.Label(frame, text="Preset:").grid(row=0, column=0, sticky="w", padx=(0, 4))
        self.preset_var = tk.StringVar(value=list(PROMPTS.keys())[0])
        cb = ttk.Combobox(frame, textvariable=self.preset_var,
                          values=list(PROMPTS.keys()), state="readonly", width=34)
        cb.grid(row=0, column=1, sticky="ew", pady=(0, 4))
        cb.bind("<<ComboboxSelected>>", self._on_preset_change)

        ttk.Label(frame, text="Gene:").grid(row=1, column=0, sticky="w", padx=(0, 4))
        self.gene_var = tk.StringVar(value=DEFAULT_GENE)
        ttk.Entry(frame, textvariable=self.gene_var, width=16).grid(
            row=1, column=1, sticky="w", pady=(0, 4))
        self.gene_var.trace_add("write", self._on_gene_change)

        ttk.Label(frame, text="Prompt:").grid(row=2, column=0, sticky="nw", padx=(0, 4))
        self.prompt_text = tk.Text(frame, wrap="word", height=10)
        self.prompt_text.grid(row=2, column=1, sticky="nsew")
        scroll = ttk.Scrollbar(frame, command=self.prompt_text.yview)
        scroll.grid(row=2, column=2, sticky="ns")
        self.prompt_text.configure(yscrollcommand=scroll.set)

        self._fill_prompt()
        return frame

    def _fill_prompt(self):
        if not self.prompt_text:
            return
        template = PROMPTS[self.preset_var.get()]
        gene = self.gene_var.get().strip() or DEFAULT_GENE
        self.prompt_text.delete("1.0", "end")
        self.prompt_text.insert("1.0", template.replace("{GENE}", gene))

    def _on_preset_change(self, _=None):
        self._fill_prompt()

    def _on_gene_change(self, *_):
        self._fill_prompt()

    def get_prompt(self) -> str:
        if self.prompt_text:
            return self.prompt_text.get("1.0", "end-1c").strip()
        return ""

    def get_run_script(self, model, data_dir, timeout, skip_datalake, full_prompt) -> str:
        return f"""
import sys, os
from pathlib import Path
from dotenv import load_dotenv
load_dotenv()

from biomni.agent import A1
from biomni.config import default_config

default_config.timeout_seconds = {timeout}

# Biomni data dir: shared across runs so data lake is downloaded only once.
# Per-run results folder is separate (used for log/result.txt by co-scientist).
_data_dir = {repr(data_dir)}
Path(_data_dir).mkdir(parents=True, exist_ok=True)

kwargs = dict(path=_data_dir, llm={repr(model)})
if {repr(skip_datalake)}:
    kwargs['expected_data_lake_files'] = []

agent = A1(**kwargs)
result = agent.go({repr(full_prompt)})
print("\\n=== RESULT ===")
print(result)
"""

    def get_metadata(self) -> dict:
        return {
            "gene": self.gene_var.get().strip() if self.gene_var else DEFAULT_GENE,
            "preset": self.preset_var.get() if self.preset_var else "",
        }
