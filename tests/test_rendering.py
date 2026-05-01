from chatapp.rendering import render_user_html


def test_user_html_renders_image_ref():
    html = render_user_html(
        "before\n![cap](attachments/abc.png)\nafter",
        "coding",
    )
    assert "<img class=\"attached\"" in html
    assert 'src="/p/coding/attachments/abc.png"' in html
    assert "alt=\"cap\"" in html
    assert "before" in html and "after" in html


def test_user_html_escapes_text_around_image():
    html = render_user_html("a<b ![](attachments/x.png) c<d", "p")
    assert "a&lt;b" in html
    assert "c&lt;d" in html


def test_user_html_no_image_passes_text_through_escaped():
    html = render_user_html("<script>x</script>", "p")
    assert "<script>" not in html
    assert "&lt;script&gt;" in html


def test_user_html_blocks_external_image():
    html = render_user_html("![](https://evil.example/x.png)", "p")
    # Outside attachments/ prefix is treated as text and escaped, not rendered.
    assert "<img" not in html
    assert "evil.example" in html  # escaped text still contains the URL substring
