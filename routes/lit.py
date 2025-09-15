import os
from fastapi import APIRouter, HTTPException, Request

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

