from __future__ import annotations

from fastapi import APIRouter, File, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, JSONResponse

from ..attachments import (
    AttachmentError,
    MAX_BYTES,
    media_type_for,
    resolve,
    save_upload,
)
from ..services import get_profile_or_404


router = APIRouter()


@router.post("/p/{profile}/attachments")
async def upload_attachment(profile: str, request: Request, file: UploadFile = File(...)):
    settings = request.app.state.settings
    prof = get_profile_or_404(settings, profile)

    if file.filename is None or media_type_for(file.filename) is None:
        raise HTTPException(status_code=415, detail="unsupported file type")

    data = await file.read(MAX_BYTES + 1)
    if len(data) > MAX_BYTES:
        raise HTTPException(status_code=413, detail="file too large")

    try:
        ref = save_upload(prof, file.filename, data)
    except AttachmentError as e:
        raise HTTPException(status_code=400, detail=str(e))

    return JSONResponse({
        "rel_path": ref.rel_path,
        "media_type": ref.media_type,
        "markdown": f"![]({ref.rel_path})",
    })


@router.get("/p/{profile}/attachments/{name}")
async def serve_attachment(profile: str, name: str, request: Request):
    settings = request.app.state.settings
    prof = get_profile_or_404(settings, profile)

    rel = f"attachments/{name}"
    p = resolve(prof, rel)
    if p is None:
        raise HTTPException(status_code=404, detail="attachment not found")

    return FileResponse(
        p,
        media_type=media_type_for(name) or "application/octet-stream",
        headers={"Cache-Control": "private, max-age=3600"},
    )
