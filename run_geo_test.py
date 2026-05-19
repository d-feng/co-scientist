"""
GEO/SRA workflow test runner — invokes biomni the same way the co-scientist UI does.
Not a hardcoded analysis script; biomni generates and executes all analysis code.
"""
import sys, os
os.environ.setdefault("PYTHONIOENCODING", "utf-8")
sys.stdout.reconfigure(encoding="utf-8")
sys.stderr.reconfigure(encoding="utf-8")
from pathlib import Path
from dotenv import load_dotenv
load_dotenv(override=True)

sys.path.insert(0, str(Path(__file__).parent))
from workflows.geo_sra_workflow import GEO_SRA_SKILL_CONTEXT

from biomni.agent import A1
from biomni.config import default_config

default_config.timeout_seconds = 1800

DATA_DIR  = "C:/Users/difen/biomni_data/biomni_data"
OUTDIR    = "C:/Users/difen/co-scientist/results/gse272019_v2"

MODEL_FALLBACK_CHAIN = ["gemini-2.5-flash", "gpt-4o", "claude-sonnet-4-6"]
QUOTA_PATTERNS = ("insufficient_quota", "credit balance is too low",
                  "RateLimitError", "You exceeded your current quota",
                  "AuthenticationError", "invalid_api_key")

TASK_PROMPT = f"""
Analyze GSE272019 (PMID study: Opposing Regulation of TNF Responses and IL-1b+ Macrophages
by PGE2-cAMP Signaling and IFN-gamma).

Raw count files are already downloaded at:
  C:/Users/difen/biomni_data/biomni_data/data_lake/GSE272019/suppl/
  - GSE272019_rawcounts_IFNg.txt  (24 samples, 8 conditions × 3 donors)
    Column format: Sample_US-{{COND}}-Do{{N}}  where COND ∈ {{G,GP,GT,GTP,P,R,T,TP}}
  - GSE272019_rawcounts_PGE.txt   (25 cols including gene_name; 4 conditions × 2 timepoints × 3 donors)
    Column format: EC.US.{{ID}}_{{Sex}}_{{COND}}_{{TIME}}_Rep{{N}}  COND ∈ {{CTRL,PGE,TNF,TNF.PGE}}

Steps to perform:
1. Load raw counts (IFNg file: first column is gene ID; PGE file: drop gene_name column).
2. Parse sample metadata from column names.
3. Run pyDESeq2 on IFNg experiment with donor as blocking variable (design_factors=["donor","condition"]):
   - Contrast A: TP vs T    (PGE2 effect on TNF response)
   - Contrast B: GT vs T    (IFN-gamma effect on TNF response)
   - Contrast C: GTP vs TP  (IFN-gamma opposing PGE2)
4. Run pyDESeq2 on PGE experiment 24h timepoint with donor as blocking variable:
   - Contrast D: TNF.PGE vs TNF  (PGE2 effect on TNF response)
   - Contrast E: PGE vs CTRL     (pure PGE2 effect)
5. Annotate Ensembl IDs with gene symbols using mygene (strip version suffix first).
6. Save each contrast's results as a CSV with columns: symbol, gene, log2FoldChange, lfcSE, stat, pvalue, padj
   Save to: {OUTDIR}/
7. Generate a volcano plot (PNG) for each contrast with genes of interest labeled.
8. Report the following genes of interest (padj<0.05) for each contrast:
   IL1B, IL1A, IL18, NLRP3, TNF, IL6, CXCL10, CXCL8, CXCL9, CXCL11,
   CCL5, PTGS2, PTGES, NR4A1, NR4A2, NR4A3, FOSL1, FOSL2, CEBPD, CEBPB,
   NFKB1, IRF1, STAT1, DLL1, NOTCH1, S100A8, S100A9, MMP9, VEGFA, IL10
9. Summarize the opposing PGE2-cAMP vs IFN-gamma regulatory axis based on the results.
"""

full_prompt = GEO_SRA_SKILL_CONTEXT + TASK_PROMPT

Path(OUTDIR).mkdir(parents=True, exist_ok=True)

for model in MODEL_FALLBACK_CHAIN:
    print(f"\n[Trying model: {model}]")
    try:
        agent = A1(path=DATA_DIR, llm=model, expected_data_lake_files=[])
        result = agent.go(full_prompt)
        print("\n=== RESULT ===")
        print(result)
        break
    except Exception as e:
        err = str(e)
        if any(p in err for p in QUOTA_PATTERNS):
            print(f"[Quota/auth error with {model} — trying next model]\n{err[:200]}")
            continue
        raise
