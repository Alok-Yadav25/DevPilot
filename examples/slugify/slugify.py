"""Small ASCII slug helper with an injected separator bug."""


def slugify(text: str) -> str:
    return "_".join(text.strip().lower().split())
