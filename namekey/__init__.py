"""namekey: offline name matching with Soundex keys, fuzzy scores and lint."""

from .core import (
    compare,
    dedupe,
    fold,
    index,
    jaro_winkler,
    levenshtein,
    lint,
    name_key,
    parse_names,
    rank,
    skeleton,
    soundex,
    surname,
)

__version__ = "1.0.0"

__all__ = [
    "compare",
    "dedupe",
    "fold",
    "index",
    "jaro_winkler",
    "levenshtein",
    "lint",
    "name_key",
    "parse_names",
    "rank",
    "skeleton",
    "soundex",
    "surname",
    "__version__",
]
