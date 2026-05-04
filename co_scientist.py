"""Co-scientist: Multi-workflow agentic research platform."""
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, simpledialog
import threading
import subprocess
import sys
import os
import json
import datetime
from pathlib import Path
from dotenv import load_dotenv

import memory as mem
from workflows import WORKFLOWS

# ── Config ────────────────────────────────────────────────────────────────────
load_dotenv()

HOME = Path.home()
RESULTS_DIR = Path(__file__).parent / "results"
DATA_SOURCES_FILE = HOME / "co_scientist_data_sources.json"
PROJECTS_FILE = HOME / "co_scientist_projects.json"
WORKFLOW_BINS_FILE = HOME / "co_scientist_workflow_bins.json"
DEFAULT_DATA_DIR = str(HOME / "biomni_data")
DEFAULT_TIMEOUT = 1200

MODELS = [
    "claude-haiku-4-5-20251001",
    "claude-sonnet-4-6",
    "claude-opus-4-6",
    "gpt-4o",
    "gpt-4-turbo",
    "gemini-2.0-flash",
]


# ── Helpers ───────────────────────────────────────────────────────────────────
def load_projects():
    if PROJECTS_FILE.exists():
        try:
            return json.loads(PROJECTS_FILE.read_text())
        except Exception:
            pass
    return ["Default"]


def save_projects(projects):
    PROJECTS_FILE.write_text(json.dumps(projects, indent=2))


def load_data_sources():
    if DATA_SOURCES_FILE.exists():
        try:
            return json.loads(DATA_SOURCES_FILE.read_text())
        except Exception:
            pass
    return []


def save_data_sources(sources):
    DATA_SOURCES_FILE.write_text(json.dumps(sources, indent=2))


def load_workflow_bins():
    if WORKFLOW_BINS_FILE.exists():
        try:
            return json.loads(WORKFLOW_BINS_FILE.read_text())
        except Exception:
            pass
    return {}


def save_workflow_bins(bins):
    WORKFLOW_BINS_FILE.write_text(json.dumps(bins, indent=2))


# ── Main App ──────────────────────────────────────────────────────────────────
class CoScientist(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Co-scientist")
        self.resizable(True, True)
        self.minsize(1100, 780)

        self.projects = load_projects()
        self.data_sources = load_data_sources()
        self.workflow_bins = load_workflow_bins()
        self._agent_thread = None
        self._stop_flag = threading.Event()
        self._memory_entries = []
        self._memory_include_vars = []
        self._active_workflow = WORKFLOWS[0]
        self._workflow_panel = None

        # Restore saved python_bin for each workflow
        for wf in WORKFLOWS:
            if wf.name in self.workflow_bins:
                wf.python_bin = self.workflow_bins[wf.name]

        self._build_ui()
        self._refresh_data_sources()

    # ── UI ─────────────────────────────────────────────────────────────────────
    def _build_ui(self):
        # ── Top config bar ────────────────────────────────────────────────────
        cfg = ttk.LabelFrame(self, text="Configuration", padding=6)
        cfg.pack(fill="x", padx=8, pady=(8, 4))

        ttk.Label(cfg, text="Project:").grid(row=0, column=0, sticky="w", padx=(0, 4))
        self.project_var = tk.StringVar(value=self.projects[0])
        self.project_cb = ttk.Combobox(cfg, textvariable=self.project_var,
                                        values=self.projects + ["＋ New Project…"],
                                        width=18, state="readonly")
        self.project_cb.grid(row=0, column=1, sticky="w", padx=(0, 12))
        self.project_cb.bind("<<ComboboxSelected>>", self._on_project_change)

        ttk.Label(cfg, text="Model:").grid(row=0, column=2, sticky="w", padx=(0, 4))
        self.model_var = tk.StringVar(value=MODELS[0])
        ttk.Combobox(cfg, textvariable=self.model_var, values=MODELS,
                     width=28, state="readonly").grid(row=0, column=3, sticky="w", padx=(0, 12))

        ttk.Label(cfg, text="Data dir:").grid(row=0, column=4, sticky="w", padx=(0, 4))
        self.data_dir_var = tk.StringVar(value=DEFAULT_DATA_DIR)
        ttk.Entry(cfg, textvariable=self.data_dir_var, width=26).grid(
            row=0, column=5, sticky="w", padx=(0, 4))
        ttk.Button(cfg, text="Dir…", command=self._browse_data_dir).grid(row=0, column=6, padx=(0, 2))
        ttk.Button(cfg, text="File…", command=self._browse_data_file).grid(row=0, column=7)

        ttk.Label(cfg, text="Timeout (s):").grid(row=1, column=0, sticky="w", padx=(0, 4), pady=(4, 0))
        self.timeout_var = tk.IntVar(value=DEFAULT_TIMEOUT)
        ttk.Spinbox(cfg, from_=60, to=7200, increment=60, textvariable=self.timeout_var,
                    width=8).grid(row=1, column=1, sticky="w", pady=(4, 0))

        self.skip_datalake_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(cfg, text="Skip data lake",
                        variable=self.skip_datalake_var).grid(row=1, column=2, sticky="w", pady=(4, 0))

        self.auto_memory_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(cfg, text="Auto-include memory",
                        variable=self.auto_memory_var).grid(row=1, column=3, sticky="w", pady=(4, 0))

        self.skip_vision_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(cfg, text="Skip vision analysis",
                        variable=self.skip_vision_var).grid(row=1, column=4, sticky="w", pady=(4, 0))

        # Row 2: per-workflow Python binary
        ttk.Label(cfg, text="Python:").grid(row=2, column=0, sticky="w", padx=(0, 4), pady=(4, 0))
        self.python_bin_var = tk.StringVar(value=self._active_workflow.python_bin)
        python_bin_entry = ttk.Entry(cfg, textvariable=self.python_bin_var, width=46)
        python_bin_entry.grid(row=2, column=1, columnspan=4, sticky="ew", pady=(4, 0), padx=(0, 4))
        ttk.Button(cfg, text="pip env", command=self._use_pip_env).grid(
            row=2, column=5, pady=(4, 0), padx=(0, 2))
        ttk.Button(cfg, text="Browse…", command=self._browse_python_bin).grid(
            row=2, column=6, pady=(4, 0))
        ttk.Label(cfg, text="(blank = current pip env)", foreground="gray").grid(
            row=2, column=7, sticky="w", padx=(4, 0), pady=(4, 0))

        # ── Main body ─────────────────────────────────────────────────────────
        body = ttk.Frame(self)
        body.pack(fill="both", expand=True, padx=8, pady=4)
        body.columnconfigure(0, minsize=130)   # workflow selector
        body.columnconfigure(1, weight=3)      # workflow input
        body.columnconfigure(2, weight=2)      # data sources + memory
        body.rowconfigure(0, weight=1)

        # Left: workflow selector
        wf_frame = ttk.LabelFrame(body, text="Workflows", padding=4)
        wf_frame.grid(row=0, column=0, sticky="nsew", padx=(0, 4))
        wf_frame.rowconfigure(0, weight=1)

        self.wf_listbox = tk.Listbox(wf_frame, selectmode="single", font=("Consolas", 10),
                                     activestyle="dotbox", width=16)
        for wf in WORKFLOWS:
            self.wf_listbox.insert("end", f"  {wf.icon}  {wf.name}")
        self.wf_listbox.select_set(0)
        self.wf_listbox.grid(row=0, column=0, sticky="nsew")
        self.wf_listbox.bind("<<ListboxSelect>>", self._on_workflow_select)

        wf_scroll = ttk.Scrollbar(wf_frame, command=self.wf_listbox.yview)
        wf_scroll.grid(row=0, column=1, sticky="ns")
        self.wf_listbox.configure(yscrollcommand=wf_scroll.set)

        ttk.Label(wf_frame, text="Select workflow", foreground="gray",
                  font=("Consolas", 8)).grid(row=1, column=0, columnspan=2, sticky="w", pady=(4, 0))

        # Center: workflow input panel (dynamic)
        self.input_container = ttk.Frame(body)
        self.input_container.grid(row=0, column=1, sticky="nsew", padx=(0, 4))
        self.input_container.rowconfigure(0, weight=1)
        self.input_container.columnconfigure(0, weight=1)
        self._load_workflow_panel(self._active_workflow)

        # Right: data sources + memory
        right = ttk.Frame(body)
        right.grid(row=0, column=2, sticky="nsew")
        right.rowconfigure(0, weight=1)
        right.rowconfigure(1, weight=2)
        right.columnconfigure(0, weight=1)

        # Data Sources
        ds_frame = ttk.LabelFrame(right, text="Data Sources", padding=6)
        ds_frame.grid(row=0, column=0, sticky="nsew", pady=(0, 4))
        ds_frame.rowconfigure(0, weight=1)
        ds_frame.columnconfigure(0, weight=1)

        cols = ("Name", "Type", "Value")
        self.ds_tree = ttk.Treeview(ds_frame, columns=cols, show="headings",
                                    selectmode="browse", height=4)
        for col in cols:
            self.ds_tree.heading(col, text=col)
        self.ds_tree.column("Name", width=75)
        self.ds_tree.column("Type", width=45)
        self.ds_tree.column("Value", width=150)
        self.ds_tree.grid(row=0, column=0, columnspan=3, sticky="nsew")
        ds_scroll = ttk.Scrollbar(ds_frame, command=self.ds_tree.yview)
        ds_scroll.grid(row=0, column=3, sticky="ns")
        self.ds_tree.configure(yscrollcommand=ds_scroll.set)
        self.ds_tree.bind("<ButtonRelease-1>", self._on_ds_click)

        ds_btn = ttk.Frame(ds_frame)
        ds_btn.grid(row=1, column=0, columnspan=4, sticky="ew", pady=(4, 0))
        ttk.Button(ds_btn, text="Add File", command=self._add_file).pack(side="left", padx=2)
        ttk.Button(ds_btn, text="Add Path", command=self._add_path).pack(side="left", padx=2)
        ttk.Button(ds_btn, text="Add URL", command=self._add_url).pack(side="left", padx=2)
        ttk.Button(ds_btn, text="Remove", command=self._remove_ds).pack(side="left", padx=2)
        ttk.Label(ds_frame, text="Click to append to prompt", foreground="gray").grid(
            row=2, column=0, columnspan=4, sticky="w", pady=(2, 0))

        # Memory
        mem_frame = ttk.LabelFrame(right, text="Memory", padding=6)
        mem_frame.grid(row=1, column=0, sticky="nsew")
        mem_frame.rowconfigure(1, weight=1)
        mem_frame.columnconfigure(0, weight=1)

        search_row = ttk.Frame(mem_frame)
        search_row.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 4))
        search_row.columnconfigure(0, weight=1)
        self.mem_search_var = tk.StringVar()
        ttk.Entry(search_row, textvariable=self.mem_search_var).grid(
            row=0, column=0, sticky="ew", padx=(0, 4))
        ttk.Button(search_row, text="Search", command=self._memory_search).grid(row=0, column=1)
        ttk.Button(search_row, text="Recent", command=self._memory_recent).grid(
            row=0, column=2, padx=(4, 0))

        self.mem_canvas = tk.Canvas(mem_frame, highlightthickness=0)
        self.mem_canvas.grid(row=1, column=0, sticky="nsew")
        mem_scroll = ttk.Scrollbar(mem_frame, orient="vertical", command=self.mem_canvas.yview)
        mem_scroll.grid(row=1, column=1, sticky="ns")
        self.mem_canvas.configure(yscrollcommand=mem_scroll.set)
        self.mem_inner = ttk.Frame(self.mem_canvas)
        self.mem_canvas.create_window((0, 0), window=self.mem_inner, anchor="nw")
        self.mem_inner.bind("<Configure>", lambda e: self.mem_canvas.configure(
            scrollregion=self.mem_canvas.bbox("all")))
        ttk.Label(mem_frame, text="Checked = injected into prompt",
                  foreground="gray").grid(row=2, column=0, columnspan=2, sticky="w", pady=(2, 0))

        # ── Output ────────────────────────────────────────────────────────────
        out_frame = ttk.LabelFrame(self, text="Output", padding=6)
        out_frame.pack(fill="both", expand=True, padx=8, pady=(4, 4))
        out_frame.rowconfigure(0, weight=1)
        out_frame.columnconfigure(0, weight=1)

        self.output_text = tk.Text(out_frame, wrap="word", state="disabled",
                                   bg="#1e1e1e", fg="#d4d4d4", font=("Consolas", 9))
        self.output_text.grid(row=0, column=0, sticky="nsew")
        out_scroll = ttk.Scrollbar(out_frame, command=self.output_text.yview)
        out_scroll.grid(row=0, column=1, sticky="ns")
        self.output_text.configure(yscrollcommand=out_scroll.set)

        # ── Action bar ────────────────────────────────────────────────────────
        btn_bar = ttk.Frame(self)
        btn_bar.pack(fill="x", padx=8, pady=(0, 8))
        self.start_btn = ttk.Button(btn_bar, text="▶  Start Workflow", command=self._start)
        self.start_btn.pack(side="left", padx=(0, 8))
        self.stop_btn = ttk.Button(btn_bar, text="■  Stop", command=self._stop, state="disabled")
        self.stop_btn.pack(side="left")
        ttk.Button(btn_bar, text="Clear Output", command=self._clear_output).pack(side="left", padx=8)
        ttk.Button(btn_bar, text="Results Manager", command=self._open_results_manager).pack(side="left")
        self.status_var = tk.StringVar(value="Ready")
        ttk.Label(btn_bar, textvariable=self.status_var, foreground="gray").pack(side="right")

    # ── Workflow switching ─────────────────────────────────────────────────────
    def _on_workflow_select(self, _=None):
        sel = self.wf_listbox.curselection()
        if not sel:
            return
        wf = WORKFLOWS[sel[0]]
        if wf is not self._active_workflow:
            # Save current python_bin before switching
            self._save_python_bin()
            self._active_workflow = wf
            self._load_workflow_panel(wf)
            # Load the new workflow's python_bin into the field
            self.python_bin_var.set(wf.python_bin)

    def _load_workflow_panel(self, wf):
        if self._workflow_panel:
            self._workflow_panel.destroy()
        self._workflow_panel = wf.build_input_panel(self.input_container)
        self._workflow_panel.grid(row=0, column=0, sticky="nsew")

    # ── Project ────────────────────────────────────────────────────────────────
    def _on_project_change(self, _=None):
        val = self.project_var.get()
        if val == "＋ New Project…":
            name = simpledialog.askstring("New Project", "Enter project name:")
            if name and name.strip():
                name = name.strip()
                if name not in self.projects:
                    self.projects.append(name)
                    save_projects(self.projects)
                self.project_var.set(name)
                self.project_cb["values"] = self.projects + ["＋ New Project…"]
            else:
                self.project_var.set(self.projects[0])
        self._render_memory_entries([])

    # ── Data Sources ───────────────────────────────────────────────────────────
    def _refresh_data_sources(self):
        self.ds_tree.delete(*self.ds_tree.get_children())
        for entry in self.data_sources:
            self.ds_tree.insert("", "end", values=(entry["name"], entry["type"], entry["value"]))

    def _on_ds_click(self, _=None):
        sel = self.ds_tree.selection()
        if not sel:
            return
        ds_type = self.ds_tree.item(sel[0], "values")[1]
        value = self.ds_tree.item(sel[0], "values")[2]
        wf = self._active_workflow
        # FILE entries: set the h5ad_var directly if the workflow has one
        if ds_type == "FILE" and hasattr(wf, "h5ad_var") and wf.h5ad_var:
            wf.h5ad_var.set(value)
            return
        # Otherwise append to prompt text
        if hasattr(wf, "prompt_text") and wf.prompt_text:
            wf.prompt_text.insert("end", f" {value}")
        elif hasattr(wf, "query_text") and wf.query_text:
            wf.query_text.insert("end", f" {value}")

    def _add_file(self):
        path = filedialog.askopenfilename(
            title="Select file",
            initialdir=str(Path(__file__).parent / "data"),
            filetypes=[("H5AD files", "*.h5ad"), ("All files", "*.*")]
        )
        if not path:
            return
        name = simpledialog.askstring("Name", "Short name:", initialvalue=Path(path).name)
        if not name:
            return
        self.data_sources.append({"name": name, "type": "FILE", "value": path})
        save_data_sources(self.data_sources)
        self._refresh_data_sources()

    def _add_path(self):
        path = filedialog.askdirectory(title="Select directory")
        if not path:
            return
        name = simpledialog.askstring("Name", "Short name:", initialvalue=Path(path).name)
        if not name:
            return
        self.data_sources.append({"name": name, "type": "PATH", "value": path})
        save_data_sources(self.data_sources)
        self._refresh_data_sources()

    def _add_url(self):
        url = simpledialog.askstring("URL", "Enter URL:")
        if not url:
            return
        name = simpledialog.askstring("Name", "Short name:")
        if not name:
            return
        self.data_sources.append({"name": name, "type": "URL", "value": url})
        save_data_sources(self.data_sources)
        self._refresh_data_sources()

    def _remove_ds(self):
        sel = self.ds_tree.selection()
        if not sel:
            return
        self.data_sources.pop(self.ds_tree.index(sel[0]))
        save_data_sources(self.data_sources)
        self._refresh_data_sources()

    def _browse_data_dir(self):
        path = filedialog.askdirectory()
        if path:
            self.data_dir_var.set(path)

    def _browse_data_file(self):
        path = filedialog.askopenfilename(
            title="Select data file",
            initialdir=str(Path(__file__).parent / "data"),
            filetypes=[("H5AD files", "*.h5ad"), ("All files", "*.*")]
        )
        if path:
            self.data_dir_var.set(path)

    def _use_pip_env(self):
        """Reset to blank = use current pip venv (sys.executable)."""
        self.python_bin_var.set("")
        self._save_python_bin()

    def _browse_python_bin(self):
        if sys.platform == "win32":
            filetypes = [("Python executable", "python*.exe"), ("All files", "*.*")]
        else:
            filetypes = [("All files", "*")]
        path = filedialog.askopenfilename(
            title="Select Python interpreter",
            filetypes=filetypes,
        )
        if path:
            self.python_bin_var.set(path)
            self._save_python_bin()

    def _save_python_bin(self):
        """Persist current python_bin for the active workflow."""
        wf = self._active_workflow
        bin_path = self.python_bin_var.get().strip()
        wf.python_bin = bin_path
        self.workflow_bins[wf.name] = bin_path
        save_workflow_bins(self.workflow_bins)

    # ── Memory ─────────────────────────────────────────────────────────────────
    def _memory_search(self):
        query = self.mem_search_var.get().strip()
        if query:
            self._render_memory_entries(
                mem.search(self.project_var.get(), query,
                           workflow_filter=self._active_workflow.name))

    def _memory_recent(self):
        wf = self._active_workflow
        meta = wf.get_metadata()
        gene = meta.get("gene", "")
        self._render_memory_entries(
            mem.search(self.project_var.get(), gene,
                       workflow_filter=wf.name))

    def _render_memory_entries(self, entries):
        for w in self.mem_inner.winfo_children():
            w.destroy()
        self._memory_entries = entries
        self._memory_include_vars = []

        if not entries:
            ttk.Label(self.mem_inner, text="No kept results found.",
                      foreground="gray").pack(anchor="w", pady=4)
            return

        for i, entry in enumerate(entries):
            var = tk.BooleanVar(value=True)
            self._memory_include_vars.append(var)
            row = ttk.Frame(self.mem_inner, relief="groove", padding=4)
            row.pack(fill="x", pady=2, padx=2)
            header = ttk.Frame(row)
            header.pack(fill="x")
            ttk.Checkbutton(header, variable=var).pack(side="left")
            lbl = ttk.Label(
                header,
                text=f"[{entry['workflow']}]  {entry['gene']}  |  {entry['preset']}  |  {entry['timestamp'][:16]}",
                font=("Consolas", 8, "bold"), cursor="hand2"
            )
            lbl.pack(side="left", fill="x", expand=True)
            summary_lbl = ttk.Label(row, text=entry["summary"][:110] + "…",
                                    wraplength=270, foreground="gray", font=("Consolas", 8))
            summary_lbl.pack(anchor="w", pady=(2, 0))
            for w in (lbl, summary_lbl):
                w.bind("<Button-1>", lambda e, ent=entry: self._show_memory_detail(ent))

    def _show_memory_detail(self, entry):
        win = tk.Toplevel(self)
        win.title(f"{entry['workflow']} — {entry['gene']} / {entry['preset']}")
        win.geometry("720x520")
        txt = tk.Text(win, wrap="word", font=("Consolas", 9))
        txt.pack(fill="both", expand=True, padx=8, pady=8)
        txt.insert("1.0",
            f"Workflow: {entry['workflow']}\nGene: {entry['gene']}\nPreset: {entry['preset']}\n"
            f"Model: {entry['model']}\nTimestamp: {entry['timestamp']}\n"
            f"Log: {entry['log_path']}\nNotes: {entry['notes']}\n\n"
            f"{'='*60}\nSOLUTION:\n{'='*60}\n{entry['solution']}\n\n"
            f"{'='*60}\nSUMMARY:\n{'='*60}\n{entry['summary']}"
        )
        txt.configure(state="disabled")

    def _build_memory_context(self):
        lines = []
        for i, var in enumerate(self._memory_include_vars):
            if var.get() and i < len(self._memory_entries):
                e = self._memory_entries[i]
                lines.append(
                    f"[Past analysis — {e['workflow']} / {e['gene']} / "
                    f"{e['preset']} / {e['timestamp'][:16]}]:\n{e['summary']}"
                )
        if not lines:
            return ""
        return "=== RELEVANT PAST ANALYSES ===\n" + "\n\n".join(lines) + "\n=== END PAST ANALYSES ===\n\n"

    # ── Output ─────────────────────────────────────────────────────────────────
    def _append_output(self, text):
        self.output_text.configure(state="normal")
        self.output_text.insert("end", text)
        self.output_text.see("end")
        self.output_text.configure(state="disabled")

    def _clear_output(self):
        self.output_text.configure(state="normal")
        self.output_text.delete("1.0", "end")
        self.output_text.configure(state="disabled")

    # ── Workflow execution ─────────────────────────────────────────────────────
    def _start(self):
        wf = self._active_workflow
        base_prompt = wf.get_prompt()
        if not base_prompt.strip():
            messagebox.showwarning("Empty prompt", "Please enter a prompt.")
            return

        project = self.project_var.get()

        # Auto-search memory
        if self.auto_memory_var.get():
            meta = wf.get_metadata()
            query = f"{meta.get('gene', '')} {base_prompt[:120]}"
            entries = mem.search(project, query, workflow_filter=wf.name)
            self._render_memory_entries(entries)
            if entries:
                self._append_output(
                    f"[Memory] Found {len(entries)} relevant past result(s) "
                    f"for '{wf.name}' in project '{project}'.\n"
                )

        memory_context = self._build_memory_context() if self.auto_memory_var.get() else ""
        full_prompt = memory_context + base_prompt

        self._stop_flag.clear()
        self.start_btn.configure(state="disabled")
        self.stop_btn.configure(state="normal")
        self.status_var.set(f"Running {wf.name}…")
        self._clear_output()

        if memory_context:
            self._append_output(f"[Memory] Injecting past context.\n{'='*60}\n")

        # Persist whatever is in the Python bin field before running
        self._save_python_bin()

        self._agent_thread = threading.Thread(
            target=self._run_workflow,
            args=(wf, full_prompt, base_prompt),
            daemon=True
        )
        self._agent_thread.start()

    def _stop(self):
        self._stop_flag.set()
        self.status_var.set("Stopping…")

    def _run_workflow(self, wf, full_prompt, base_prompt):
        meta = wf.get_metadata()
        gene = meta.get("gene", "unknown")
        preset = meta.get("preset", "")
        model = self.model_var.get()
        project = self.project_var.get()
        data_dir = self.data_dir_var.get()
        timeout = self.timeout_var.get()
        skip_datalake = self.skip_datalake_var.get()
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")

        # Per-project/per-run results folder — log lives here too
        safe_preset = preset.lower().replace(" ", "_").replace("/", "_").replace("-", "_")
        run_dir = RESULTS_DIR / project / f"{gene}_{safe_preset}_{timestamp}"
        run_dir.mkdir(parents=True, exist_ok=True)
        log_path = run_dir / "run.log"

        script = wf.get_run_script(model, data_dir, timeout, skip_datalake, full_prompt)

        python_bin = wf.get_python_bin()
        self._append_output(
            f"[{timestamp}] Workflow: {wf.name} | Project: {project}\n"
            f"Gene: {gene} | Preset: {preset} | Model: {model}\n"
            f"Python: {python_bin}\n"
            f"Results: {run_dir}\n"
            f"Log: {log_path}\n{'='*60}\n"
        )

        full_result = []
        completed = False

        try:
            with open(log_path, "w", encoding="utf-8") as log_file:
                log_file.write(
                    f"Co-scientist — {timestamp}\nWorkflow: {wf.name}\nProject: {project}\n"
                    f"Gene: {gene}\nPreset: {preset}\nModel: {model}\n"
                    f"Prompt:\n{base_prompt}\n\n{'='*60}\n\n"
                )
                python_bin = wf.get_python_bin()
                proc = subprocess.Popen(
                    [python_bin, "-c", script],
                    stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                    text=True, encoding="utf-8", errors="replace",
                    env={**os.environ, "PYTHONUTF8": "1", "PYTHONUNBUFFERED": "1",
                         "STAGENT_SKIP_VISION": "1" if self.skip_vision_var.get() else "0",
                         "STAGENT_PLOT_DIR": str(run_dir),   # STAgent reads this natively
                         "COSCIENTIST_RUN_DIR": str(run_dir),  # general per-run folder for all workflows
                         "STAGENT_PROJECT": project},
                )
                _noise = ("WARNING", "scriptrunner", "ScriptRunContext",
                          "session_state", "streamlit run [FILE", "run it with")
                for line in proc.stdout:
                    if self._stop_flag.is_set():
                        proc.terminate()
                        self._append_output("\n[Stopped by user]\n")
                        log_file.write("\n[Stopped by user]\n")
                        break
                    if any(n in line for n in _noise):
                        continue
                    self._append_output(line)
                    log_file.write(line)
                    full_result.append(line)

                proc.wait()
                completed = proc.returncode == 0
                status = "Completed" if completed else f"Exited with code {proc.returncode}"
                self._append_output(f"\n[{status}]\n")
                log_file.write(f"\n[{status}]\n")

        except Exception as e:
            self._append_output(f"\n[ERROR] {e}\n")

        if completed:
            full_text = "".join(full_result)
            # Save result text to run folder
            try:
                (run_dir / "result.txt").write_text(full_text, encoding="utf-8")
            except Exception:
                pass
            run_id = mem.save_pending(
                project, wf.name, gene, preset, model, base_prompt, full_text, log_path)
            self.after(0, lambda: self._show_review_popup(project, run_id, full_text))

        self.after(0, self._on_workflow_done)

    def _on_workflow_done(self):
        self.start_btn.configure(state="normal")
        self.stop_btn.configure(state="disabled")
        self.status_var.set("Ready")

    # ── Results Review popup ───────────────────────────────────────────────────
    def _show_review_popup(self, project, run_id, full_text):
        if not run_id:
            return
        solution = mem.extract_solution(full_text)

        win = tk.Toplevel(self)
        win.title("Results Review — Keep or Delete?")
        win.geometry("760x560")
        win.grab_set()

        ttk.Label(win,
                  text="Review the result. Keep → saves to project memory (used in future runs). Delete → discards.",
                  wraplength=720).pack(padx=10, pady=(10, 4))

        txt = tk.Text(win, wrap="word", font=("Consolas", 9), bg="#f9f9f9")
        txt.pack(fill="both", expand=True, padx=10, pady=4)
        txt.insert("1.0", solution)
        txt.configure(state="disabled")

        notes_row = ttk.Frame(win)
        notes_row.pack(fill="x", padx=10, pady=(0, 4))
        ttk.Label(notes_row, text="Notes:").pack(side="left", padx=(0, 6))
        notes_var = tk.StringVar()
        ttk.Entry(notes_row, textvariable=notes_var, width=55).pack(side="left", fill="x", expand=True)

        btn_row = ttk.Frame(win)
        btn_row.pack(pady=(0, 10))

        def on_keep():
            mem.keep(project, run_id, notes_var.get().strip())
            self._append_output(f"[Memory] Result kept in project '{project}'.\n")
            win.destroy()

        def on_delete():
            mem.delete(project, run_id)
            self._append_output("[Memory] Result discarded.\n")
            win.destroy()

        ttk.Button(btn_row, text="Keep  (save to memory)", command=on_keep).pack(side="left", padx=12)
        ttk.Button(btn_row, text="Delete  (discard)", command=on_delete).pack(side="left", padx=12)

    # ── Results Manager ────────────────────────────────────────────────────────
    def _open_results_manager(self):
        project = self.project_var.get()
        win = tk.Toplevel(self)
        win.title(f"Results Manager — {project}")
        win.geometry("960x560")

        top = ttk.Frame(win)
        top.pack(fill="x", padx=8, pady=6)
        ttk.Label(top, text="Filter gene:").pack(side="left")
        filter_var = tk.StringVar()
        ttk.Entry(top, textvariable=filter_var, width=12).pack(side="left", padx=4)
        ttk.Label(top, text="Workflow:").pack(side="left", padx=(8, 4))
        wf_filter_var = tk.StringVar(value="All")
        ttk.Combobox(top, textvariable=wf_filter_var,
                     values=["All"] + [wf.name for wf in WORKFLOWS],
                     state="readonly", width=12).pack(side="left")
        ttk.Button(top, text="Filter", command=lambda: _refresh()).pack(side="left", padx=4)
        ttk.Button(top, text="Show All", command=lambda: _refresh(reset=True)).pack(side="left")

        cols = ("Workflow", "Gene", "Preset", "Model", "Timestamp", "Notes")
        tree = ttk.Treeview(win, columns=cols, show="headings", selectmode="browse")
        for col in cols:
            tree.heading(col, text=col)
        tree.column("Workflow", width=90)
        tree.column("Gene", width=70)
        tree.column("Preset", width=150)
        tree.column("Model", width=150)
        tree.column("Timestamp", width=130)
        tree.column("Notes", width=200)
        tree.pack(fill="both", expand=True, padx=8, pady=4)
        scroll = ttk.Scrollbar(win, orient="vertical", command=tree.yview)
        tree.configure(yscrollcommand=scroll.set)

        all_entries = []

        def _refresh(reset=False):
            if reset:
                filter_var.set("")
                wf_filter_var.set("All")
            tree.delete(*tree.get_children())
            all_entries.clear()
            wf_f = None if wf_filter_var.get() == "All" else wf_filter_var.get()
            entries = mem.list_all(project, workflow_filter=wf_f)
            for e in entries:
                if filter_var.get() and filter_var.get().upper() not in e["gene"].upper():
                    continue
                all_entries.append(e)
                tree.insert("", "end", values=(
                    e["workflow"], e["gene"], e["preset"],
                    e["model"], e["timestamp"][:16], e["notes"]
                ))

        _refresh()

        def on_view():
            sel = tree.selection()
            if sel:
                self._show_memory_detail(all_entries[tree.index(sel[0])])

        def on_delete():
            sel = tree.selection()
            if not sel:
                return
            e = all_entries[tree.index(sel[0])]
            if messagebox.askyesno("Delete", f"Delete {e['workflow']} result for {e['gene']}?"):
                mem.delete(project, e["id"])
                _refresh()

        btn_row = ttk.Frame(win)
        btn_row.pack(pady=(0, 8))
        ttk.Button(btn_row, text="View Summary", command=on_view).pack(side="left", padx=8)
        ttk.Button(btn_row, text="Delete Selected", command=on_delete).pack(side="left", padx=8)


# ── Entry point ────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    app = CoScientist()
    app.mainloop()
