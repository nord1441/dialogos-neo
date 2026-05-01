import textwrap

import pytest

from chatapp.profiles.loader import (
    InvalidProfile,
    ProfileNotFound,
    list_profiles,
    load_profile,
)


def _make_profile(root, slug, toml_body, system_text="be helpful"):
    p = root / slug
    p.mkdir(parents=True)
    (p / "profile.toml").write_text(textwrap.dedent(toml_body))
    (p / "system.md").write_text(system_text)
    return p


def test_load_profile_minimal(tmp_path):
    _make_profile(tmp_path, "coding", """
        [meta]
        display_name = "Coding"

        [model]
        provider = "anthropic"
        name = "claude-opus-4-7"

        [api]
        key_ref = "anthropic_main"
    """)
    prof = load_profile(tmp_path, "coding")
    assert prof.slug == "coding"
    assert prof.meta.display_name == "Coding"
    assert prof.model.name == "claude-opus-4-7"
    assert prof.behavior.history_strategy == "single"


def test_unknown_strategy_rejected(tmp_path):
    _make_profile(tmp_path, "bad", """
        [behavior]
        history_strategy = "weekly"
    """)
    with pytest.raises(InvalidProfile):
        load_profile(tmp_path, "bad")


def test_missing_profile(tmp_path):
    with pytest.raises(ProfileNotFound):
        load_profile(tmp_path, "missing")


def test_path_traversal_rejected(tmp_path):
    with pytest.raises(ProfileNotFound):
        load_profile(tmp_path, "../etc")


def test_list_profiles(tmp_path):
    _make_profile(tmp_path, "a", "[meta]\ndisplay_name = \"A\"")
    _make_profile(tmp_path, "b", "[meta]\ndisplay_name = \"B\"")
    (tmp_path / "not-a-profile").mkdir()
    profs = list_profiles(tmp_path)
    assert [p.slug for p in profs] == ["a", "b"]
