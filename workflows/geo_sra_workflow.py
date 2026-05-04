"""GEO/SRA agentic workflow plugin."""
import tkinter as tk
from tkinter import ttk
from .base import BaseWorkflow

DEFAULT_GENE = "IFNG"

SPECIES_OPTIONS = ["Homo sapiens", "Mus musculus", "Rattus norvegicus", "Other"]
DEG_METHODS = ["DESeq2", "edgeR", "limma-voom", "pyDESeq2"]
YEARS_OPTIONS = [2, 3, 5, 10]

ANALYSIS_PROMPTS = {
    "Search & Discover": (
        "Search NCBI GEO for RNA-seq datasets related to {GENE} in {SPECIES}. "
        "Return a ranked list of the top studies including: accession numbers, titles, sample counts, "
        "publication dates, and brief summaries. Filter to studies with at least 10 samples. "
        "Use the past {YEARS} years of data."
    ),
    "Download & Extract": (
        "Download the GEO dataset {ACCESSION} for {GENE} analysis. "
        "Extract the expression count matrix and sample metadata. "
        "Report: number of samples, conditions/groups found, data type (raw counts vs normalized), "
        "and any supplementary files available. Organism: {SPECIES}."
    ),
    "DEG Analysis": (
        "Download GEO dataset {ACCESSION} for {GENE}. "
        "Run differential expression analysis using {DEG_METHOD} comparing the main experimental conditions. "
        "Output: top 50 DEGs ranked by adjusted p-value, log2 fold change statistics, "
        "volcano plot, and heatmap of significant genes. Use FDR < 0.05 and |log2FC| > 1 thresholds. "
        "If sample size is small (n < 10/group), use nominal p < 0.01 and report as exploratory."
    ),
    "Full Pipeline": (
        "Execute the complete GEO/SRA pipeline for {GENE} in {SPECIES}: "
        "1) Search GEO for RNA-seq datasets (past {YEARS} years, ≥ 10 samples), "
        "2) Select the best-powered study and download the expression data, "
        "3) Run {DEG_METHOD} differential expression analysis, "
        "4) Perform GSEA pathway enrichment (GO Biological Process + KEGG), "
        "5) Generate volcano plot and pathway dot plot. "
        "Report all significant findings with accession number used."
    ),
}

# Skill context injected into every GEO/SRA prompt
GEO_SRA_SKILL_CONTEXT = """
=== GEO/SRA SKILL CONTEXT ===
Accession formats: GSE (series), GSM (sample), GPL (platform), SRX (experiment), SRR (run), PRJNA (bioproject).
Search via Biopython Entrez (esearch db=gds). Download via GEOquery (R) or GEOparse (Python).
DEG methods: DESeq2 (default, n<20/group), edgeR-QL (faster), limma-voom (n≥20 or microarray), pyDESeq2 (Python).
Always use RAW counts for DESeq2/edgeR/limma-voom — never TPM/FPKM.
Small samples (n<10/group): use nominal p<0.01 + GSEA ranked list instead of FDR cutoff.
GSEA: use shrunken LFC ranked list with clusterProfiler gseGO + gseKEGG.
Rate limit: set NCBI_API_KEY env var for 10 req/sec (vs 3 req/sec default).
=== END SKILL CONTEXT ===
"""


class GeoSraWorkflow(BaseWorkflow):
    name = "GEO/SRA"
    description = "Search, download, and analyze NCBI GEO/SRA datasets"
    icon = "🔬"

    def __init__(self):
        self.gene_var = None
        self.accession_var = None
        self.species_var = None
        self.analysis_var = None
        self.deg_method_var = None
        self.years_var = None
        self.query_text = None

    def build_input_panel(self, parent):
        frame = ttk.LabelFrame(parent, text="GEO/SRA — Query", padding=6)
        frame.columnconfigure(1, weight=1)
        frame.columnconfigure(3, weight=1)
        frame.rowconfigure(5, weight=1)

        # Row 0: gene + accession
        ttk.Label(frame, text="Gene:").grid(row=0, column=0, sticky="w", padx=(0, 4))
        self.gene_var = tk.StringVar(value=DEFAULT_GENE)
        ttk.Entry(frame, textvariable=self.gene_var, width=14).grid(
            row=0, column=1, sticky="w", padx=(0, 16))
        self.gene_var.trace_add("write", self._update_prompt)

        ttk.Label(frame, text="Accession:").grid(row=0, column=2, sticky="w", padx=(0, 4))
        self.accession_var = tk.StringVar(value="")
        ttk.Entry(frame, textvariable=self.accession_var, width=14).grid(
            row=0, column=3, sticky="w")
        self.accession_var.trace_add("write", self._update_prompt)

        # Row 1: species + years
        ttk.Label(frame, text="Species:").grid(row=1, column=0, sticky="w", padx=(0, 4), pady=(4, 0))
        self.species_var = tk.StringVar(value=SPECIES_OPTIONS[0])
        ttk.Combobox(frame, textvariable=self.species_var, values=SPECIES_OPTIONS,
                     width=18, state="readonly").grid(row=1, column=1, sticky="w", pady=(4, 0))
        self.species_var.trace_add("write", self._update_prompt)

        ttk.Label(frame, text="Years back:").grid(row=1, column=2, sticky="w", padx=(0, 4), pady=(4, 0))
        self.years_var = tk.IntVar(value=5)
        ttk.Spinbox(frame, from_=1, to=20, textvariable=self.years_var, width=6).grid(
            row=1, column=3, sticky="w", pady=(4, 0))
        self.years_var.trace_add("write", self._update_prompt)

        # Row 2: analysis type + DEG method
        ttk.Label(frame, text="Analysis:").grid(row=2, column=0, sticky="w", padx=(0, 4), pady=(4, 0))
        self.analysis_var = tk.StringVar(value=list(ANALYSIS_PROMPTS.keys())[0])
        analysis_cb = ttk.Combobox(frame, textvariable=self.analysis_var,
                                   values=list(ANALYSIS_PROMPTS.keys()),
                                   state="readonly", width=22)
        analysis_cb.grid(row=2, column=1, sticky="w", pady=(4, 0))
        analysis_cb.bind("<<ComboboxSelected>>", self._update_prompt)

        ttk.Label(frame, text="DEG method:").grid(row=2, column=2, sticky="w", padx=(0, 4), pady=(4, 0))
        self.deg_method_var = tk.StringVar(value=DEG_METHODS[0])
        ttk.Combobox(frame, textvariable=self.deg_method_var, values=DEG_METHODS,
                     state="readonly", width=14).grid(row=2, column=3, sticky="w", pady=(4, 0))
        self.deg_method_var.trace_add("write", self._update_prompt)

        # Row 3: separator
        ttk.Separator(frame, orient="horizontal").grid(
            row=3, column=0, columnspan=4, sticky="ew", pady=6)

        # Row 4: prompt label
        ttk.Label(frame, text="Prompt:").grid(row=4, column=0, sticky="nw", padx=(0, 4))

        # Row 5: prompt text area
        self.query_text = tk.Text(frame, wrap="word", height=8)
        self.query_text.grid(row=5, column=0, columnspan=4, sticky="nsew")
        scroll = ttk.Scrollbar(frame, command=self.query_text.yview)
        scroll.grid(row=5, column=4, sticky="ns")
        self.query_text.configure(yscrollcommand=scroll.set)

        self._update_prompt()
        return frame

    def _update_prompt(self, *_):
        if not self.query_text:
            return
        template = ANALYSIS_PROMPTS[self.analysis_var.get()]
        gene = self.gene_var.get().strip() or DEFAULT_GENE
        accession = self.accession_var.get().strip() or f"[search for {gene}]"
        species = self.species_var.get()
        years = str(self.years_var.get())
        deg_method = self.deg_method_var.get()

        prompt = template.replace("{GENE}", gene) \
                         .replace("{ACCESSION}", accession) \
                         .replace("{SPECIES}", species) \
                         .replace("{YEARS}", years) \
                         .replace("{DEG_METHOD}", deg_method)

        self.query_text.delete("1.0", "end")
        self.query_text.insert("1.0", prompt)

    def get_prompt(self) -> str:
        if self.query_text:
            base = self.query_text.get("1.0", "end-1c").strip()
            return GEO_SRA_SKILL_CONTEXT + base
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

kwargs = dict(path={repr(data_dir)}, llm={repr(model)})
if {repr(skip_datalake)}:
    kwargs['expected_data_lake_files'] = []

agent = A1(**kwargs)
result = agent.go({repr(full_prompt)})
print("\\n=== RESULT ===")
print(result)
"""

    def get_metadata(self) -> dict:
        gene = self.gene_var.get().strip() if self.gene_var else DEFAULT_GENE
        preset = self.analysis_var.get() if self.analysis_var else ""
        return {"gene": gene, "preset": preset}
