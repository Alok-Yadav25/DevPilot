from slugify import slugify


def test_separator() -> None:
    assert slugify("Hello   World") == "hello-world"


def test_empty() -> None:
    assert slugify("  ") == ""
