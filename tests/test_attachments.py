import textwrap
from pathlib import Path

import pytest

from chatapp import attachments
from chatapp.attachments import (
    AttachmentError,
    AttachmentRef,
    extract_refs,
    media_type_for,
    resolve,
    save_upload,
)
from chatapp.profiles.loader import load_profile


PNG_BYTES = (
    # 1x1 transparent PNG.
    b"\x89PNG\r\n\x1a\n"
    b"\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15\xc4\x89"
    b"\x00\x00\x00\rIDATx\x9cc\xf8\x0f\x00\x00\x01\x01\x00\x05\x18\xb1\x06\x96"
    b"\x00\x00\x00\x00IEND\xaeB`\x82"
)


def _make_profile(tmp_path):
    d = tmp_path / "p"
    d.mkdir()
    (d / "profile.toml").write_text(textwrap.dedent("""
        [meta]
        display_name = "Test"
    """))
    (d / "system.md").write_text("")
    return load_profile(tmp_path, "p")


def test_media_type_lookup():
    assert media_type_for("foo.PNG") == "image/png"
    assert media_type_for("foo.jpg") == "image/jpeg"
    assert media_type_for("foo.txt") is None


def test_save_upload_writes_file(tmp_path):
    prof = _make_profile(tmp_path)
    ref = save_upload(prof, "shot.png", PNG_BYTES)
    assert ref.rel_path.startswith("attachments/")
    assert ref.media_type == "image/png"
    assert (prof.root / ref.rel_path).read_bytes() == PNG_BYTES


def test_save_upload_rejects_unknown_extension(tmp_path):
    prof = _make_profile(tmp_path)
    with pytest.raises(AttachmentError):
        save_upload(prof, "evil.exe", b"hi")


def test_save_upload_rejects_oversize(tmp_path, monkeypatch):
    prof = _make_profile(tmp_path)
    monkeypatch.setattr(attachments, "MAX_BYTES", 4)
    with pytest.raises(AttachmentError):
        save_upload(prof, "shot.png", b"toolong")


def test_resolve_blocks_traversal(tmp_path):
    prof = _make_profile(tmp_path)
    save_upload(prof, "ok.png", PNG_BYTES)
    assert resolve(prof, "attachments/../profile.toml") is None
    assert resolve(prof, "/etc/passwd") is None
    assert resolve(prof, "attachments/missing.png") is None


def test_extract_refs_finds_only_local_paths():
    text = (
        "Look at this:\n"
        "![one](attachments/abc.png) and ![two](attachments/def.jpg)\n"
        "But not ![](https://example.com/x.png) or ![](/abs/y.png)\n"
        "Or this duplicate ![](attachments/abc.png).\n"
    )
    refs = extract_refs(text)
    assert [r.rel_path for r in refs] == [
        "attachments/abc.png",
        "attachments/def.jpg",
    ]
    assert refs[0].alt == "one"


def test_extract_refs_skips_unsupported_extensions():
    text = "![bad](attachments/foo.bmp)"
    assert extract_refs(text) == []
