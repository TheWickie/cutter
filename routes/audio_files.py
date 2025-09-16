import os
import time
from typing import List, Dict

from fastapi import APIRouter, HTTPException, Request, UploadFile, File

from routes.admin import _require_admin
from core.rate_limit import rate_limit


router = APIRouter(prefix="/v2")


def _audio_dir() -> str:
    return os.getenv("AUDIO_DIR", "content/audio")


def _safe_name(name: str) -> str:
    # keep alnum, dash, underscore, dot; collapse others to '-'
    base = "".join(ch if (ch.isalnum() or ch in ("-", "_", ".")) else "-" for ch in (name or "").strip())
    base = base.strip(".-_") or "track.mp3"
    # enforce mp3 extension if none
    if "." not in os.path.basename(base):
        base += ".mp3"
    return base


@router.get("/audio/list")
def list_audio(request: Request) -> Dict[str, List[Dict]]:
    rate_limit(request)
    adir = _audio_dir()
    os.makedirs(adir, exist_ok=True)
    items: List[Dict] = []
    for f in sorted(os.listdir(adir)):
        if not f.lower().endswith((".mp3", ".wav", ".m4a", ".aac", ".ogg")):
            continue
        p = os.path.join(adir, f)
        try:
            st = os.stat(p)
            items.append({
                "name": f,
                "bytes": int(st.st_size),
                "mtime": int(st.st_mtime),
                "url": f"/audio/{f}",
            })
        except Exception:
            continue
    return {"files": items}


@router.post("/admin/audio/upload")
def upload_audio(request: Request, file: UploadFile = File(...), overwrite: bool = False):
    rate_limit(request)
    _require_admin(request)
    adir = _audio_dir()
    os.makedirs(adir, exist_ok=True)
    # sanitize filename
    base = _safe_name(os.path.basename(file.filename or "track.mp3"))
    dest = os.path.join(adir, base)
    if (not overwrite) and os.path.exists(dest):
        return {"status": "exists", "name": base, "url": f"/audio/{base}"}
    # write
    try:
        with open(dest, "wb") as out:
            out.write(file.file.read())
        st = os.stat(dest)
        return {
            "status": "uploaded",
            "name": base,
            "bytes": int(st.st_size),
            "mtime": int(st.st_mtime),
            "url": f"/audio/{base}",
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/admin/audio/delete")
def delete_audio(request: Request, name: str):
    rate_limit(request)
    _require_admin(request)
    adir = _audio_dir()
    base = _safe_name(name)
    dest = os.path.join(adir, base)
    if not os.path.exists(dest):
        return {"status": "not_found", "name": base}
    try:
        os.remove(dest)
        return {"status": "deleted", "name": base}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

