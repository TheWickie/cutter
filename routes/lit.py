import os
from fastapi import APIRouter, HTTPException, Request, UploadFile, File

from core.rate_limit import rate_limit
from core.lit_index import index_dir, list_docs, search
from routes.admin import _require_admin  # reuse token check

router = APIRouter(prefix="/v2")


@router.get("/lit/docs")
def docs(request: Request):
    rate_limit(request)
    try:
        return {"docs": list_docs()}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/lit/search")
def lit_search(q: str, k: int = 4, request: Request = None):
    rate_limit(request)
    return {"results": search(q, k=k)}


@router.post("/admin/lit/reindex")
def lit_reindex(request: Request, overwrite: bool = False):
    rate_limit(request)
    _require_admin(request)
    try:
        content_dir = os.getenv("NA_LIT_DIR", "content/na")
        stats = index_dir(content_dir=content_dir, overwrite=overwrite)
        return {"status": "ok", **stats}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/admin/lit/upload")
def lit_upload(request: Request, file: UploadFile = File(...), overwrite: bool = False):
    rate_limit(request)
    _require_admin(request)
    try:
        content_dir = os.getenv("NA_LIT_DIR", "content/na")
        os.makedirs(content_dir, exist_ok=True)
        # sanitize filename
        base = os.path.basename(file.filename or "document.pdf")
        safe = "".join(ch if ch.isalnum() or ch in (".", "-", "_") else "-" for ch in base)
        if not safe.lower().endswith(".pdf"):
            safe += ".pdf"
        dest = os.path.join(content_dir, safe)
        if (not overwrite) and os.path.exists(dest):
            return {"status": "exists", "file": safe}
        with open(dest, "wb") as out:
            out.write(file.file.read())
        # index newly uploaded content (non-destructive)
        stats = index_dir(content_dir=content_dir, overwrite=False)
        return {"status": "uploaded", "file": safe, **stats}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
