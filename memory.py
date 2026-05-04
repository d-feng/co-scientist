"""Shared project-based memory system (ChromaDB + semantic search)."""
import re
import uuid
import datetime
from pathlib import Path

HOME = Path.home()
MEMORY_DB_DIR = HOME / "co_scientist_memory"
MEMORY_TOP_K = 3
MEMORY_SUMMARY_WORDS = 150


def _safe_collection_name(project):
    name = re.sub(r"[^a-zA-Z0-9_-]", "_", project).strip("_")
    return f"proj_{name}"[:63] or "proj_default"


def _get_collection(project):
    import chromadb
    MEMORY_DB_DIR.mkdir(parents=True, exist_ok=True)
    client = chromadb.PersistentClient(path=str(MEMORY_DB_DIR))
    return client.get_or_create_collection(_safe_collection_name(project))


def summarize(text, max_words=MEMORY_SUMMARY_WORDS):
    words = str(text).split()
    return " ".join(words[:max_words]) + ("…" if len(words) > max_words else "")


def extract_solution(text):
    m = re.search(r"<solution>(.*?)</solution>", text, re.DOTALL | re.IGNORECASE)
    if m:
        return m.group(1).strip()
    m = re.search(r"=== RESULT ===(.*?)$", text, re.DOTALL)
    if m:
        return m.group(1).strip()
    return summarize(text)


def save_pending(project, workflow, gene, preset, model, prompt, full_result, log_path):
    try:
        col = _get_collection(project)
        run_id = str(uuid.uuid4())
        timestamp = datetime.datetime.now().isoformat()
        col.add(
            ids=[run_id],
            documents=[f"{prompt}\n{summarize(full_result)}"],
            metadatas=[{
                "workflow": workflow,
                "gene": gene, "preset": preset, "model": model,
                "prompt": prompt,
                "summary": summarize(full_result),
                "solution": extract_solution(full_result),
                "log_path": str(log_path),
                "timestamp": timestamp,
                "status": "pending", "notes": "",
            }],
        )
        return run_id
    except Exception as e:
        print(f"[Memory] Save failed: {e}")
        return None


def keep(project, run_id, notes=""):
    try:
        col = _get_collection(project)
        result = col.get(ids=[run_id])
        if not result["ids"]:
            return
        meta = result["metadatas"][0]
        meta["status"] = "kept"
        meta["notes"] = notes
        col.update(ids=[run_id], metadatas=[meta])
    except Exception as e:
        print(f"[Memory] Keep failed: {e}")


def delete(project, run_id):
    try:
        _get_collection(project).delete(ids=[run_id])
    except Exception as e:
        print(f"[Memory] Delete failed: {e}")


def search(project, query, top_k=MEMORY_TOP_K, workflow_filter=None):
    try:
        col = _get_collection(project)
        total = col.count()
        if total == 0:
            return []
        where = {"status": "kept"}
        if workflow_filter:
            where = {"$and": [{"status": "kept"}, {"workflow": workflow_filter}]}
        results = col.query(
            query_texts=[query],
            n_results=min(top_k * 3, total),
            where=where,
        )
        entries = []
        for i, meta in enumerate(results["metadatas"][0]):
            entries.append({
                "id": results["ids"][0][i],
                "workflow": meta.get("workflow", ""),
                "gene": meta.get("gene", ""),
                "preset": meta.get("preset", ""),
                "model": meta.get("model", ""),
                "prompt": meta.get("prompt", ""),
                "summary": meta.get("summary", ""),
                "solution": meta.get("solution", ""),
                "log_path": meta.get("log_path", ""),
                "timestamp": meta.get("timestamp", ""),
                "notes": meta.get("notes", ""),
            })
            if len(entries) >= top_k:
                break
        return entries
    except Exception as e:
        print(f"[Memory] Search failed: {e}")
        return []


def list_all(project, workflow_filter=None):
    try:
        col = _get_collection(project)
        if col.count() == 0:
            return []
        where = {"status": "kept"}
        if workflow_filter:
            where = {"$and": [{"status": "kept"}, {"workflow": workflow_filter}]}
        results = col.get(where=where)
        entries = []
        for i, run_id in enumerate(results["ids"]):
            meta = results["metadatas"][i]
            entries.append({
                "id": run_id,
                "workflow": meta.get("workflow", ""),
                "gene": meta.get("gene", ""),
                "preset": meta.get("preset", ""),
                "model": meta.get("model", ""),
                "prompt": meta.get("prompt", ""),
                "summary": meta.get("summary", ""),
                "solution": meta.get("solution", ""),
                "log_path": meta.get("log_path", ""),
                "timestamp": meta.get("timestamp", ""),
                "notes": meta.get("notes", ""),
            })
        return sorted(entries, key=lambda x: x["timestamp"], reverse=True)
    except Exception as e:
        print(f"[Memory] List failed: {e}")
        return []
