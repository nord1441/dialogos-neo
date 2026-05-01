from chatapp.history.parser import parse
from chatapp.history.writer import append_message
from chatapp.profiles.models import Message


def test_append_round_trips(tmp_path):
    p = tmp_path / "history.md"
    append_message(p, Message(role="user", content="hello"))
    append_message(p, Message(role="assistant", content="hi"))
    append_message(p, Message(role="user", content="multi\nline\nmessage"))

    msgs = parse(p.read_text())
    assert [m.role for m in msgs] == ["user", "assistant", "user"]
    assert msgs[0].content == "hello"
    assert msgs[2].content == "multi\nline\nmessage"


def test_append_creates_parents(tmp_path):
    p = tmp_path / "history" / "2026-05-01.md"
    append_message(p, Message(role="user", content="hi"))
    assert p.exists()
