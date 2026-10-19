import json

from namekey.cli import EXIT_GATE, EXIT_OK, EXIT_USAGE, main


def _write(tmp_path, text, name="names.txt"):
    path = tmp_path / name
    path.write_text(text, encoding="utf-8")
    return str(path)


def test_lint_gate_fails_on_errors(tmp_path, capsys):
    path = _write(tmp_path, "Ann Lee\nBob 2\n")
    assert main(["lint", path]) == EXIT_GATE
    assert "line 2: error E002" in capsys.readouterr().out


def test_lint_gate_respects_max_errors(tmp_path):
    path = _write(tmp_path, "Ann Lee\nBob 2\n")
    assert main(["lint", path, "--max-errors", "1"]) == EXIT_OK


def test_lint_json_output(tmp_path, capsys):
    path = _write(tmp_path, "Ann Lee\nAnn Lee\n")
    assert main(["lint", path, "--json"]) == EXIT_OK
    payload = json.loads(capsys.readouterr().out)
    assert payload["errors"] == 0
    assert payload["warnings"] == 1
    assert payload["findings"][0]["code"] == "W003"


def test_dedupe_fail_on_groups(tmp_path):
    path = _write(tmp_path, "John Smith\nJon Smyth\n")
    assert main(["dedupe", path, "--fail-on-groups"]) == EXIT_GATE
    assert main(["dedupe", path]) == EXIT_OK


def test_dedupe_json_lists_line_numbers(tmp_path, capsys):
    path = _write(tmp_path, "John Smith\nMary Lee\nJon Smyth\n")
    main(["dedupe", path, "--json"])
    payload = json.loads(capsys.readouterr().out)
    assert [item["line"] for item in payload["groups"][0]] == [1, 3]


def test_match_ranks_from_file(tmp_path, capsys):
    path = _write(tmp_path, "Mary Lee\nJon Smyth\nJohn Smith\n")
    assert main(["match", "John Smith", path, "--limit", "2", "--json"]) == EXIT_OK
    payload = json.loads(capsys.readouterr().out)
    assert len(payload["matches"]) == 2
    assert payload["matches"][0]["sounds_alike"] is True


def test_key_and_compare_run(capsys):
    assert main(["key", "Robert", "Rupert"]) == EXIT_OK
    assert "R163" in capsys.readouterr().out
    assert main(["compare", "Smith, John", "John Smith", "--json"]) == EXIT_OK
    assert json.loads(capsys.readouterr().out)["exact_after_fold"] is True


def test_index_command(tmp_path, capsys):
    path = _write(tmp_path, "John Smith\nJon Smyth\n")
    assert main(["index", path, "--json"]) == EXIT_OK
    payload = json.loads(capsys.readouterr().out)
    assert payload[0]["soundex"] == "S530"
    assert payload[0]["count"] == 2


def test_missing_file_is_usage_error(tmp_path, capsys):
    assert main(["lint", str(tmp_path / "nope.txt")]) == EXIT_USAGE
    assert "namekey:" in capsys.readouterr().err
