import pytest

from namekey import core


@pytest.mark.parametrize(
    "word, code",
    [
        ("Robert", "R163"),
        ("Rupert", "R163"),
        ("Rubin", "R150"),
        ("Ashcraft", "A261"),
        ("Tymczak", "T522"),
        ("Pfister", "P236"),
    ],
)
def test_soundex_known_values(word, code):
    assert core.soundex(word) == code


def test_soundex_empty_when_no_latin_letters():
    assert core.soundex("") == ""
    assert core.soundex("1234") == ""
    assert core.soundex("李") == ""


def test_fold_strips_accents_case_and_punctuation():
    assert core.fold("Zoë  O'Brien-Smith") == "zoe obrien smith"


def test_flip_comma_and_surname():
    assert core.flip_comma("Smith, John") == "John Smith"
    assert core.surname("Smith, John") == "Smith"
    assert core.surname("John Ernest Smith") == "Smith"
    assert core.surname("Cher") == "Cher"


def test_sounds_alike_uses_surname_only():
    assert core.sounds_alike("John Smith", "Jon Smyth")
    assert not core.sounds_alike("John Smith", "Mary Lee")
    assert not core.sounds_alike("1234", "5678")


def test_skeleton_maps_spelling_variants_together():
    assert core.skeleton("Phillip") == core.skeleton("Filip")
    assert core.skeleton("Ann") == core.skeleton("Anne") == "an"
    assert core.skeleton("") == ""
    assert core.skeleton("Knight") == core.skeleton("Night") == "ngt"


def test_levenshtein_known_distance():
    assert core.levenshtein("kitten", "sitting") == 3
    assert core.levenshtein("", "abc") == 3
    assert core.levenshtein("same", "same") == 0


def test_jaro_winkler_known_value():
    assert core.jaro_winkler("MARTHA", "MARHTA") == pytest.approx(0.9611, abs=1e-4)
    assert core.jaro_winkler("abc", "xyz") == 0.0


def test_compare_flags_comma_reordering_as_same_after_fold():
    report = core.compare("Smith, John", "John Smith")
    assert report["exact_after_fold"] is True
    assert report["sounds_alike"] is True


def test_rank_puts_sound_alike_names_first():
    names = ["Mary Lee", "Jon Smyth", "John Smith", "Smithers Bob"]
    ranked = core.rank("John Smith", names, limit=0)
    assert ranked[0][0] in {"John Smith", "Jon Smyth"}
    assert [alike for _, _, alike in ranked[:2]] == [True, True]
    assert not any(alike for _, _, alike in ranked[2:])


def test_rank_respects_limit_and_min_score():
    names = ["John Smith", "Jon Smyth", "Mary Lee"]
    assert len(core.rank("John Smith", names, limit=1)) == 1
    assert all(score >= 0.95 for _, score, _ in core.rank("John Smith", names, limit=0, min_score=0.95))


def test_parse_names_skips_blanks_and_comments_and_keeps_line_numbers():
    text = "# header\n\nAnn Lee\n  Bob Ray  \n# note\nCy Ort\n"
    assert core.parse_names(text) == [(3, "Ann Lee"), (4, "Bob Ray"), (6, "Cy Ort")]


def test_lint_reports_line_numbered_errors_and_warnings():
    text = "Ann Lee\nBob 2\nDoe,\nann  lee\nCy@Ort\n"
    findings = {(n, c) for n, _, c, _ in core.lint(text)}
    assert (2, "E002") in findings
    assert (3, "E005") in findings
    assert (4, "W002") in findings
    assert (4, "W003") in findings
    assert (5, "E003") in findings


def test_lint_clean_file_has_no_findings():
    assert core.lint("John Smith\nMary Lee\n") == []


def test_dedupe_groups_likely_duplicates_only():
    entries = core.parse_names("John Smith\nJon Smyth\nMary Lee\nSmith, John\n")
    groups = core.dedupe(entries, threshold=0.9)
    assert len(groups) == 1
    assert [line for line, _ in groups[0]] == [1, 2, 4]


def test_dedupe_threshold_one_only_links_identical_spellings():
    entries = core.parse_names("John Smith\nJon Smyth\n")
    assert core.dedupe(entries, threshold=1.0) == []


def test_index_buckets_by_soundex_and_puts_keyless_last():
    buckets = core.index(["John Smith", "Mary Lee", "Jon Smyth", "李"])
    codes = [code for code, _ in buckets]
    assert codes[-1] == ""
    assert dict(buckets)["S530"] == ["John Smith", "Jon Smyth"]
