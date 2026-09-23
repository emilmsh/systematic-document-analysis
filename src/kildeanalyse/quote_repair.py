"""Conservative recovery of quotation whitespace from one extracted source unit."""
from __future__ import annotations

import re


def unique_source_span(quote: str, source: str) -> tuple[int, int, str] | None:
    """Return the sole source span with identical non-whitespace tokens, if any.

    Token boundaries and every non-whitespace character must already agree. This
    only restores the source's whitespace; ambiguity or any other edit fails.
    """
    if not quote or quote in source:
        return None
    tokens = re.findall(r'\S+', quote)
    if len(tokens) < 2:
        return None
    pattern = re.compile(r'\s+'.join(re.escape(token) for token in tokens))
    matches = list(pattern.finditer(source))
    if len(matches) != 1:
        return None
    match = matches[0]
    restored = match.group()
    if restored == quote or re.findall(r'\S+', restored) != tokens:
        return None
    return match.start(), match.end(), restored
