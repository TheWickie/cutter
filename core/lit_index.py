import os
import re
import json
import hashlib
from typing import List, Dict, Any, Optional, Tuple

from core.redis_store import get_client

try:
    from openai import OpenAI  # type: ignore
except Exception:
    OpenAI = None


OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
EMBED_MODEL = os.getenv("OPENAI_EMBED_MODEL", "text-embedding-3-small")


def _slug(s: str) -> str:
    s = re.sub(r"[^A-Za-z0-9]+", "-", s.strip())
    return s.strip("-").lower()


def _abbrev_from_filename(name: str) -> str:
    base = os.path.splitext(os.path.basename(name))[0]
    words = re.findall(r"[A-Za-z0-9]+", base)
    # Special cases
    base_up = base.upper()
    if "STEP" in base_up and "GUIDE" in base_up:
        return "SWG"
    if "BASIC" in base_up and "TEXT" in base_up:
        return "BT"
    if "JUST" in base_up and "TODAY" in base_up:
        return "JFT"
    abbr = "".join(w[0] for w in words[:6]).upper() or "DOC"
    return abbr[:6]


def _embed_client():
    if OpenAI and OPENAI_API_KEY:
        return OpenAI(api_key=OPENAI_API_KEY)
    return None


def _embed_texts(texts: List[str]) -> Optional[List[List[float]]]:
    client = _embed_client()
    if not client:
        return None
    try:
        resp = client.embeddings.create(model=EMBED_MODEL, input=texts)
        return [d.embedding for d in resp.data]
    except Exception:
        return None


def _cosine(a: List[float], b: List[float]) -> float:
    import math
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    if na == 0 or nb == 0:
        return 0.0
    return dot / (na * nb)


def _keyword_score(q: str, text: str) -> float:
    qs = {w for w in re.findall(r"[A-Za-z]{3,}", q.lower())}
    ts = re.findall(r"[A-Za-z]{3,}", text.lower())
    if not qs or not ts:
        return 0.0
    count = sum(1 for w in ts if w in qs)
    return count / max(5, len(ts))


def extract_pdf(path: str) -> List[Tuple[int, str]]:
    """Return list of (page_number starting at 1, text)."""
    from PyPDF2 import PdfReader  # lazy import

    try:
        reader = PdfReader(path)
    except Exception as e:
        raise ValueError(f"Failed to open PDF '{os.path.basename(path)}': {e}")
    pages: List[Tuple[int, str]] = []
    for i, page in enumerate(reader.pages, start=1):
        try:
            txt = page.extract_text() or ""
        except Exception:
            txt = ""
        pages.append((i, txt))
    return pages


def chunk_text(text: str, target_words: int = 180) -> List[str]:
    words = re.findall(r"\S+", text)
    chunks: List[str] = []
    i = 0
    while i < len(words):
        chunk = words[i : i + target_words]
        chunks.append(" ".join(chunk))
        i += target_words
    return [c.strip() for c in chunks if c.strip()]


def index_dir(content_dir: str = "content/na", overwrite: bool = False) -> Dict[str, Any]:
    r = get_client()
    added = 0
    updated = 0
    skipped = 0
    os.makedirs(content_dir, exist_ok=True)
    pdfs = [
        os.path.join(content_dir, f)
        for f in os.listdir(content_dir)
        if f.lower().endswith(".pdf")
    ]
    all_chunk_ids: List[str] = []
    errors: List[Dict[str, Any]] = []
    for pdf in pdfs:
        try:
            with open(pdf, "rb") as fh:
                data = fh.read()
            sha = hashlib.sha256(data).hexdigest()
        except Exception as e:
            skipped += 1
            errors.append({"file": os.path.basename(pdf), "error": f"read_failed: {e}"})
            continue
        title = os.path.splitext(os.path.basename(pdf))[0]
        abbrev = _abbrev_from_filename(pdf)
        doc_id = _slug(title)
        doc_key = f"lit:doc:{doc_id}"
        existing = r.get(doc_key)
        if existing and not overwrite:
            # still account its chunk ids
            ids = r.get(f"lit:chunks:{doc_id}")
            if ids:
                try:
                    for cid in json.loads(ids):
                        all_chunk_ids.append(cid)
                except Exception:
                    pass
            skipped += 1
            continue

        try:
            pages = extract_pdf(pdf)
        except Exception as e:
            skipped += 1
            errors.append({"file": os.path.basename(pdf), "error": str(e)})
            continue
        chunks_payload: List[Dict[str, Any]] = []
        for page_num, page_txt in pages:
            if not page_txt.strip():
                continue
            for frag in chunk_text(page_txt):
                chunks_payload.append(
                    {
                        "doc_id": doc_id,
                        "title": title,
                        "abbrev": abbrev,
                        "page": page_num,
                        "text": frag,
                    }
                )
        # embeddings (optional)
        embs = _embed_texts([c["text"] for c in chunks_payload])
        if embs:
            for c, e in zip(chunks_payload, embs):
                c["emb"] = e

        # store
        chunk_ids: List[str] = []
        for i, c in enumerate(chunks_payload):
            cid = f"{doc_id}:{i}"
            chunk_ids.append(cid)
            all_chunk_ids.append(cid)
            r.set(f"lit:chunk:{cid}", json.dumps(c))
        r.set(doc_key, json.dumps({"title": title, "abbrev": abbrev, "pages": len(pages), "sha256": sha}))
        r.set(f"lit:chunks:{doc_id}", json.dumps(chunk_ids))
        if existing:
            updated += 1
        else:
            added += 1

    r.set("lit:index:all", json.dumps(all_chunk_ids))
    return {"added": added, "updated": updated, "skipped": skipped, "total_chunks": len(all_chunk_ids), "errors": errors}


def list_docs() -> List[Dict[str, Any]]:
    r = get_client()
    docs: List[Dict[str, Any]] = []
    # naive: scan keys by known prefix
    # Assuming small corpus
    for k in [k for k in r.store.keys() if isinstance(r, type(get_client())) and hasattr(r, "store")] if False else []:
        pass
    # generic list by known ids container
    # For robustness with real redis, derive doc ids via chunks index
    doc_set: Dict[str, Dict[str, Any]] = {}
    for key in r.scan_iter("lit:doc:*") if hasattr(r, "scan_iter") else []:
        payload = r.get(key)
        if not payload:
            continue
        try:
            data = json.loads(payload)
            doc_id = key.split(":", 2)[2]
            doc_set[doc_id] = {"doc_id": doc_id, **data}
        except Exception:
            continue
    # If scan_iter not available (MemoryStore), try reading known index
    if not doc_set:
        # try to guess by reading chunk index and extracting doc ids
        idx = r.get("lit:index:all")
        if idx:
            try:
                for cid in json.loads(idx):
                    did = cid.split(":", 1)[0]
                    dk = r.get(f"lit:doc:{did}")
                    if dk and did not in doc_set:
                        doc_set[did] = {"doc_id": did, **json.loads(dk)}
            except Exception:
                pass
    return list(doc_set.values())


def _iter_chunks() -> List[Dict[str, Any]]:
    r = get_client()
    ids_raw = r.get("lit:index:all")
    chunks: List[Dict[str, Any]] = []
    if ids_raw:
        try:
            ids = json.loads(ids_raw)
            for cid in ids:
                raw = r.get(f"lit:chunk:{cid}")
                if raw:
                    try:
                        chunks.append(json.loads(raw))
                    except Exception:
                        pass
        except Exception:
            pass
    return chunks


def search(query: str, k: int = 4) -> List[Dict[str, Any]]:
    chunks = _iter_chunks()
    if not chunks:
        return []
    # try embeddings
    emb = _embed_texts([query])
    scored: List[Tuple[float, Dict[str, Any]]] = []
    if emb and chunks and "emb" in chunks[0]:
        qv = emb[0]
        for c in chunks:
            sim = _cosine(qv, c.get("emb", []))
            scored.append((sim, c))
    else:
        for c in chunks:
            s = _keyword_score(query, c.get("text", ""))
            scored.append((s, c))
    scored.sort(key=lambda x: x[0], reverse=True)
    results = []
    for score, c in scored[:k]:
        results.append({"score": float(score), **c})
    return results


def build_context(snippets: List[Dict[str, Any]]) -> str:
    lines = [
        "Use only NA-approved literature below for step guidance. If insufficient, say so and stick to NA principles.",
        "Cite each suggestion with [ABBREV p.N].",
    ]
    for s in snippets:
        abbrev = s.get("abbrev", "DOC")
        page = s.get("page", 0)
        text = s.get("text", "")
        lines.append(f"[{abbrev} p.{page}] {text}")
    return "\n".join(lines)
