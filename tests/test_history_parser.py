from chatapp.history.parser import parse


BASIC = """## user
Hello

## assistant
Hi there.

## user
Tell me about ## headings in markdown.

## assistant
Sure. A `## heading` line in the body is fine — it does not split a turn
because we only treat lines that *exactly* match `## user|assistant|system`
as boundaries.

## subheading inside body
content under that heading still belongs to this assistant turn.
"""


def test_parses_three_user_turns_and_two_assistant_turns():
    msgs = parse(BASIC)
    roles = [m.role for m in msgs]
    assert roles == ["user", "assistant", "user", "assistant"]


def test_body_can_contain_hash_hash_lines():
    msgs = parse(BASIC)
    last = msgs[-1].content
    assert "## subheading inside body" in last
    assert "Sure." in last


def test_empty_returns_empty():
    assert parse("") == []
    assert parse("\n\n") == []


def test_only_role_with_blank_body_dropped():
    msgs = parse("## user\n\n")
    assert msgs == []


def test_system_role_supported():
    msgs = parse("## system\nbe brief\n\n## user\nhi\n")
    assert [m.role for m in msgs] == ["system", "user"]
    assert msgs[0].content == "be brief"
