"""Core name-matching logic for namekey.

Everything here is pure standard library and works offline. The main ideas:

* ``fold`` normalises a name for comparison (accents, case, punctuation,
  spacing, and ``Last, First`` order).
* ``soundex`` gives the classic American Soundex code of a surname.
* ``skeleton`` gives a consonant-only key that is a looser, heuristic
  phonetic bucket. It is not a standard algorithm.
* ``jaro_winkler`` and ``levenshtein`` score how close two spellings are.
* ``dedupe`` and ``rank`` build on those to find likely duplicates and
  likely matches.
"""

import re
import unicodedata

SOUNDEX_LENGTH = 4

_SOUNDEX_CODES = {
    **dict.fromkeys("BFPV", "1"),
    **dict.fromkeys("CGJKQSXZ", "2"),
    **dict.fromkeys("DT", "3"),
    "L": "4",
    **dict.fromkeys("MN", "5"),
    "R": "6",
}

_SKELETON_START = (("kn", "n"), ("wr", "r"), ("ps", "s"))
_SKELETON_RULES = (
    ("sch", "sk"),
    ("ph", "f"),
    ("ck", "k"),
    ("ce", "se"),
    ("ci", "si"),
    ("cy", "sy"),
    ("c", "k"),
    ("q", "k"),
    ("z", "s"),
    ("x", "ks"),
)

_DROPPED_IN_SKELETON = set("aeiouyhw")


def _ascii_letters(text):
    """Return ``text`` with accents removed, lowercased, and only a-z kept."""
    decomposed = unicodedata.normalize("NFKD", text)
    stripped = "".join(ch for ch in decomposed if not unicodedata.combining(ch))
    return re.sub(r"[^a-z]", "", stripped.lower())


def flip_comma(name):
    """Turn ``"Smith, John"`` into ``"John Smith"``. Other names are unchanged."""
    if "," not in name:
        return name
    last, _, first = name.partition(",")
    return f"{first.strip()} {last.strip()}".strip()


def fold(name):
    """Normalise a name for comparison.

    Accents are removed, case is lowered, apostrophes disappear, other
    punctuation becomes a space, and runs of whitespace collapse to one space.
    """
    decomposed = unicodedata.normalize("NFKD", name)
    stripped = "".join(ch for ch in decomposed if not unicodedata.combining(ch))
    lowered = stripped.lower().replace("'", "").replace("’", "")
    spaced = re.sub(r"[^\w\s]", " ", lowered)
    return " ".join(spaced.split())


def surname(name):
    """Return the part of a name that Soundex should encode.

    ``"Smith, John"`` gives ``"Smith"``. ``"John Smith"`` gives ``"Smith"``.
    A single word is its own surname.
    """
    if "," in name:
        return name.partition(",")[0].strip()
    parts = name.split()
    return parts[-1] if parts else ""


def soundex(word):
    """Classic American Soundex, four characters, using the H/W rule.

    Returns ``""`` if the word has no Latin letters.
    """
    letters = _ascii_letters(word).upper()
    if not letters:
        return ""
    first = letters[0]
    code = first
    previous = _SOUNDEX_CODES.get(first, "")
    for letter in letters[1:]:
        if letter in "HW":
            # H and W do not separate equal codes, so they are skipped.
            continue
        digit = _SOUNDEX_CODES.get(letter, "")
        if digit and digit != previous:
            code += digit
        # Vowels reset the previous code, so equal codes separated by a
        # vowel are both kept.
        previous = digit
        if len(code) == SOUNDEX_LENGTH:
            break
    return code.ljust(SOUNDEX_LENGTH, "0")


def name_key(name):
    """Soundex code of the surname, or ``""`` if the name has no letters."""
    return soundex(surname(name))


def skeleton(name):
    """A consonant skeleton used as a loose phonetic bucket.

    Spaces and non-Latin characters are ignored. Common spelling variants
    are mapped to one letter (``ph`` to ``f``, ``ck`` to ``k``, ``c`` to
    ``k`` or ``s``, and so on). Vowels, ``h`` and ``w`` are dropped after
    the first letter, and doubled letters are collapsed.
    """
    text = _ascii_letters(name)
    if not text:
        return ""
    for old, new in _SKELETON_START:
        if text.startswith(old):
            text = new + text[len(old):]
            break
    for old, new in _SKELETON_RULES:
        text = text.replace(old, new)
    head, tail = text[0], text[1:]
    body = head + "".join(ch for ch in tail if ch not in _DROPPED_IN_SKELETON)
    collapsed = []
    for ch in body:
        if not collapsed or collapsed[-1] != ch:
            collapsed.append(ch)
    return "".join(collapsed)


def levenshtein(a, b):
    """Edit distance between two strings, with unit cost for each operation."""
    if a == b:
        return 0
    if not a:
        return len(b)
    if not b:
        return len(a)
    previous = list(range(len(b) + 1))
    for i, ca in enumerate(a, start=1):
        current = [i]
        for j, cb in enumerate(b, start=1):
            cost = 0 if ca == cb else 1
            current.append(min(previous[j] + 1, current[j - 1] + 1, previous[j - 1] + cost))
        previous = current
    return previous[-1]


def jaro(a, b):
    """Jaro similarity in the range 0 to 1."""
    if a == b:
        return 1.0
    len_a, len_b = len(a), len(b)
    if not len_a or not len_b:
        return 0.0
    window = max(max(len_a, len_b) // 2 - 1, 0)
    a_matched = [False] * len_a
    b_matched = [False] * len_b
    matches = 0
    for i, ca in enumerate(a):
        low = max(0, i - window)
        high = min(i + window + 1, len_b)
        for j in range(low, high):
            if not b_matched[j] and b[j] == ca:
                a_matched[i] = b_matched[j] = True
                matches += 1
                break
    if not matches:
        return 0.0
    transpositions = 0
    k = 0
    for i in range(len_a):
        if a_matched[i]:
            while not b_matched[k]:
                k += 1
            if a[i] != b[k]:
                transpositions += 1
            k += 1
    transpositions /= 2
    return (matches / len_a + matches / len_b + (matches - transpositions) / matches) / 3


def jaro_winkler(a, b, prefix_scale=0.1):
    """Jaro-Winkler similarity. Shared prefixes of up to four letters count extra."""
    base = jaro(a, b)
    prefix = 0
    for ca, cb in zip(a[:4], b[:4]):
        if ca != cb:
            break
        prefix += 1
    return base + prefix * prefix_scale * (1 - base)


def _variants(name):
    """Folded forms of a name, with and without ``Last, First`` flipping."""
    return {fold(name), fold(flip_comma(name))}


def similarity(a, b):
    """Best Jaro-Winkler score over the folded variants of two names."""
    return max(jaro_winkler(x, y) for x in _variants(a) for y in _variants(b))


def sounds_alike(a, b):
    """True when both names have the same non-empty surname Soundex code."""
    key = name_key(a)
    return bool(key) and key == name_key(b)


def compare(a, b):
    """Full comparison report for two names."""
    fa, fb = fold(a), fold(b)
    distance = levenshtein(fa, fb)
    longest = max(len(fa), len(fb)) or 1
    return {
        "a": a,
        "b": b,
        "soundex_a": name_key(a),
        "soundex_b": name_key(b),
        "sounds_alike": sounds_alike(a, b),
        "skeleton_a": skeleton(a),
        "skeleton_b": skeleton(b),
        "same_skeleton": bool(skeleton(a)) and skeleton(a) == skeleton(b),
        "jaro_winkler": round(similarity(a, b), 4),
        "levenshtein": distance,
        "levenshtein_similarity": round(1 - distance / longest, 4),
        "exact_after_fold": fa == fb or fold(flip_comma(a)) == fb,
    }


def rank(query, names, limit=5, min_score=0.0):
    """Rank candidate names against a query.

    Names that sound alike come first, then names with a higher score.
    Returns a list of ``(name, score, sounds_alike)`` tuples.
    """
    scored = []
    for name in names:
        score = round(similarity(query, name), 4)
        if score < min_score:
            continue
        scored.append((name, score, sounds_alike(query, name)))
    scored.sort(key=lambda item: (not item[2], -item[1], item[0]))
    return scored[:limit] if limit else scored


def parse_names(text):
    """Split a plain-text name list into ``(line_number, name)`` entries.

    Blank lines and lines starting with ``#`` are skipped. Line numbers
    refer to the original text, so they still match the file.
    """
    entries = []
    for number, raw in enumerate(text.splitlines(), start=1):
        stripped = raw.strip()
        if not stripped or stripped.startswith("#"):
            continue
        entries.append((number, stripped))
    return entries


ALLOWED_PUNCTUATION = " '-.,"
MAX_NAME_LENGTH = 80


def lint(text):
    """Check a name list line by line.

    Returns a list of findings ``(line_number, severity, code, message)``.
    ``severity`` is ``"error"`` or ``"warning"``.
    """
    findings = []
    first_seen = {}
    for number, raw in enumerate(text.splitlines(), start=1):
        line = raw.rstrip("\r")
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        if line != line.strip():
            findings.append((number, "warning", "W001", "leading or trailing whitespace"))
        name = line.strip()
        if len(name) > MAX_NAME_LENGTH:
            findings.append((number, "error", "E004", f"name longer than {MAX_NAME_LENGTH} characters"))
        if re.search(r"\d", name):
            findings.append((number, "error", "E002", "name contains a digit"))
        bad = sorted({ch for ch in name if not (ch.isalpha() or ch.isdigit() or ch in ALLOWED_PUNCTUATION)})
        if bad:
            findings.append((number, "error", "E003", f"unexpected character {bad[0]!r}"))
        if not re.search(r"[^\W\d_]", name):
            findings.append((number, "error", "E001", "line has no letters"))
        if "," in name:
            last, _, first = name.partition(",")
            if not last.strip() or not first.strip():
                findings.append((number, "error", "E005", "'Last, First' form is missing a part"))
        if "  " in name:
            findings.append((number, "warning", "W002", "double space inside name"))
        key = fold(name)
        if key and key in first_seen:
            findings.append(
                (number, "warning", "W003", f"duplicate of line {first_seen[key]} after folding")
            )
        elif key:
            first_seen[key] = number
    findings.sort(key=lambda item: item[0])
    return findings


class _UnionFind:
    def __init__(self, size):
        self.parent = list(range(size))

    def find(self, x):
        while self.parent[x] != x:
            self.parent[x] = self.parent[self.parent[x]]
            x = self.parent[x]
        return x

    def union(self, x, y):
        root_x, root_y = self.find(x), self.find(y)
        if root_x != root_y:
            self.parent[max(root_x, root_y)] = min(root_x, root_y)


def dedupe(entries, threshold=0.9):
    """Group likely duplicates from ``(line_number, name)`` entries.

    Two names are linked when they share a surname Soundex code and their
    best Jaro-Winkler score is at least ``threshold``. Links are merged
    transitively. Only groups with two or more members are returned.
    Each group is a list of ``(line_number, name)`` tuples, in file order.
    """
    union = _UnionFind(len(entries))
    for i in range(len(entries)):
        for j in range(i + 1, len(entries)):
            a, b = entries[i][1], entries[j][1]
            if not sounds_alike(a, b):
                continue
            if similarity(a, b) >= threshold:
                union.union(i, j)
    groups = {}
    for index, entry in enumerate(entries):
        groups.setdefault(union.find(index), []).append(entry)
    return [members for members in groups.values() if len(members) > 1]


def index(names):
    """Bucket names by surname Soundex code.

    Returns a list of ``(code, [names])`` sorted by code. Names with no
    Latin letters go into the ``""`` bucket.
    """
    buckets = {}
    for name in names:
        buckets.setdefault(name_key(name), []).append(name)
    return sorted(buckets.items(), key=lambda item: (item[0] == "", item[0]))
