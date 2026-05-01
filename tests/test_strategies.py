import textwrap

from chatapp.history import strategies
from chatapp.profiles.loader import load_profile


def _make(tmp_path, slug, body):
    d = tmp_path / slug
    d.mkdir()
    (d / "profile.toml").write_text(textwrap.dedent(body))
    (d / "system.md").write_text("")
    return load_profile(tmp_path, slug)


def test_single_path(tmp_path):
    prof = _make(tmp_path, "p", '[behavior]\nhistory_strategy = "single"\n')
    assert strategies.current_history_path(prof).name == "history.md"


def test_daily_path_uses_date(tmp_path):
    prof = _make(tmp_path, "p", '[behavior]\nhistory_strategy = "daily"\n')
    p = strategies.current_history_path(prof)
    assert p.parent.name == "history"
    # YYYY-MM-DD.md
    assert len(p.stem) == 10 and p.suffix == ".md"


def test_session_creates_new(tmp_path):
    prof = _make(tmp_path, "p", '[behavior]\nhistory_strategy = "session"\n')
    p = strategies.current_history_path(prof)
    # YYYY-MM-DD-HHMM.md
    assert p.suffix == ".md" and len(p.stem) == 15


def test_find_history_rejects_traversal(tmp_path):
    prof = _make(tmp_path, "p", '[behavior]\nhistory_strategy = "daily"\n')
    assert strategies.find_history_by_name(prof, "../etc/passwd") is None
