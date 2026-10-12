def slugify(text: str) -> str:
    """Return a URL slug for text.

    - Lowercase the text.
    - Treat every run of characters that are not ASCII letters or digits as one separator.
    - Join the remaining ASCII letter-and-digit words with single hyphens.
    - Return "" if no ASCII letters or digits remain.

    Examples: "Hello, World!" -> "hello-world"; "  a--b  " -> "a-b"; "Café 2" -> "caf-2".
    """
    raise NotImplementedError
