from __future__ import annotations

import json

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse

from ..config import Settings
from ..history import parser as history_parser
from ..history import strategies
from ..profiles.loader import (
    InvalidProfile,
    ProfileNotFound,
    list_profiles,
    load_profile,
    read_system_prompt,
)
from ..rendering import render_markdown, render_plain


router = APIRouter()


def _settings(request: Request) -> Settings:
    return request.app.state.settings


def _templates(request: Request):
    return request.app.state.templates


@router.get("/", response_class=HTMLResponse)
async def index(request: Request):
    settings = _settings(request)
    profiles = list_profiles(settings.profiles_root)
    return _templates(request).TemplateResponse(
        request,
        "profile_list.html",
        {"profiles": profiles},
    )


@router.get("/p/{profile}", response_class=HTMLResponse)
async def profile_page(profile: str, request: Request):
    settings = _settings(request)
    try:
        prof = load_profile(settings.profiles_root, profile)
    except ProfileNotFound:
        raise HTTPException(status_code=404, detail="profile not found")
    except InvalidProfile as e:
        raise HTTPException(status_code=500, detail=str(e))

    history_path = strategies.current_history_path(prof)
    messages = history_parser.parse_file(history_path)

    rendered = []
    for m in messages:
        if m.role == "assistant" and prof.ui.markdown_render:
            html_body = render_markdown(m.content)
        elif m.role == "user":
            # Users typed it themselves; render as plain text but allow
            # newlines via white-space: pre-wrap in CSS.
            html_body = render_plain(m.content) if False else _user_html(m.content)
        else:
            html_body = render_markdown(m.content)
        rendered.append({"role": m.role, "html": html_body, "raw": m.content})

    history_files = [p.name for p in strategies.list_history_files(prof)]

    return _templates(request).TemplateResponse(
        request,
        "conversation.html",
        {
            "profile": prof,
            "messages": rendered,
            "history_files": history_files,
            "current_history": history_path.name,
            "system_prompt": read_system_prompt(prof),
        },
    )


@router.get("/p/{profile}/history/{name}", response_class=HTMLResponse)
async def profile_history(profile: str, name: str, request: Request):
    settings = _settings(request)
    try:
        prof = load_profile(settings.profiles_root, profile)
    except ProfileNotFound:
        raise HTTPException(status_code=404, detail="profile not found")

    p = strategies.find_history_by_name(prof, name)
    if p is None:
        raise HTTPException(status_code=404, detail="history not found")

    messages = history_parser.parse_file(p)
    rendered = [
        {
            "role": m.role,
            "html": (
                render_markdown(m.content)
                if m.role != "user" or not prof.ui.markdown_render
                else _user_html(m.content)
            ),
            "raw": m.content,
        }
        for m in messages
    ]
    history_files = [hp.name for hp in strategies.list_history_files(prof)]

    return _templates(request).TemplateResponse(
        request,
        "conversation.html",
        {
            "profile": prof,
            "messages": rendered,
            "history_files": history_files,
            "current_history": p.name,
            "system_prompt": read_system_prompt(prof),
            "readonly": True,
        },
    )


@router.get("/p/{profile}/manifest.json")
async def profile_manifest(profile: str, request: Request):
    settings = _settings(request)
    try:
        prof = load_profile(settings.profiles_root, profile)
    except ProfileNotFound:
        raise HTTPException(status_code=404, detail="profile not found")
    return JSONResponse({
        "name": prof.meta.display_name or prof.slug,
        "short_name": prof.slug,
        "start_url": f"/p/{prof.slug}",
        "scope": f"/p/{prof.slug}",
        "display": "standalone",
        "background_color": "#ffffff",
        "theme_color": "#222222",
        "icons": [],
    })


def _user_html(text: str) -> str:
    import html
    return f'<div class="user-text">{html.escape(text)}</div>'
