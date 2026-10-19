# namekey

**Offline name matching for messy lists: Soundex keys, fuzzy scores, duplicate groups and line-numbered lint.**

namekey reads a plain-text list of names and tells you which spellings probably mean the same person. It also says which lines are malformed, so you can fix the list before you merge it. It runs entirely on your machine with the Python 3 standard library. It makes no network calls, needs no account and reads no API keys.

## Features

- **Soundex surname keys.** Classic American Soundex with the H/W rule. Keys are computed on the surname, so `Smith, John` and `John Smith` share the key `S530`.
- **Consonant skeleton keys.** A looser phonetic bucket that maps common spelling variants together (`Phillip` and `Filip` both give `flp`).
- **Name folding.** Strips accents, case, apostrophes and punctuation. `Zoë O'Brien-Smith` folds to `zoe obrien smith`.
- **`Last, First` handling.** Comma-reversed names are compared in both orders, so you don't get false negatives.
- **Jaro-Winkler similarity.** Scores 0 to 1, with extra credit for a shared prefix. Good at typos and transpositions.
- **Levenshtein distance.** Exact edit counts, plus a normalised similarity, for a second opinion.
- **Ranked matching.** Find the names in a file that best match a query. Names that sound alike are listed first.
- **Duplicate groups.** Groups likely duplicates by sounds-alike plus a tunable score threshold, with links merged transitively and reported in file order.
- **Soundex index.** Buckets a whole list by surname key, so you can see clusters at a glance.
- **Line-numbered lint.** Flags digits, stray symbols, over-long lines, empty `Last, First` parts, double spaces, stray whitespace and duplicates after folding. Every finding carries its line number.
- **CI gates.** `lint --max-errors N` and `--fail-on-warnings`, and `dedupe --fail-on-groups`, exit 1 when a gate fails.
- **Machine-readable output.** Every command takes `--json`.
- **stdin support.** Pass `-` as the file to read from a pipe.
- **Comments and blank lines.** `#` lines and empty lines are skipped, and line numbers still match the original file.

## Quick start

Requires Python 3.8 or newer. There is nothing to install.

Save this as `guests.txt` (`examples/guests.txt` is a longer sample):

```text
John Smith
Jon Smyth
Smith, John
Mary Lee
Ann Taylor
ann  taylor
```

Lint it:

```console
$ python3 -m namekey lint guests.txt
line 6: warning W002: double space inside name
line 6: warning W003: duplicate of line 5 after folding
0 error(s), 2 warning(s)
```

Find likely duplicates:

```console
$ python3 -m namekey dedupe guests.txt
group 1:
  line 1: John Smith
  line 2: Jon Smyth
  line 3: Smith, John
group 2:
  line 5: Ann Taylor
  line 6: ann  taylor
2 group(s) of likely duplicates
```

Compare two spellings:

```console
$ python3 -m namekey compare "Smith, John" "John Smith"
'Smith, John' vs 'John Smith'
  soundex:        S530 / S530  (sounds alike)
  ...
  same after fold: yes
```

Rank the closest names in a list to a query:

```console
$ python3 -m namekey match "Jon Smith" guests.txt --limit 3
```

## Commands

| Command | What it does |
| --- | --- |
| `key NAME...` | Show surname Soundex and consonant skeleton for each name |
| `compare A B` | Full comparison: keys, Jaro-Winkler, Levenshtein, same-after-fold |
| `match QUERY FILE` | Rank names in FILE against QUERY (`--limit`, `--min-score`) |
| `dedupe FILE` | Group likely duplicates (`--threshold`, `--fail-on-groups`) |
| `lint FILE` | Line-numbered errors and warnings (`--max-errors`, `--fail-on-warnings`) |
| `index FILE` | Bucket names by surname Soundex code |

Add `--json` to any command for machine-readable output.

### Exit codes

| Code | Meaning |
| --- | --- |
| `0` | Success, or a gate passed |
| `1` | A CI gate failed (too many lint errors, or duplicate groups found with `--fail-on-groups`) |
| `2` | Bad usage or unreadable input |

## How to run

From the project directory:

```console
$ python3 -m namekey --help
```

As a CI step, lint the name list and fail the build on any error:

```console
$ python3 -m namekey lint names.txt --max-errors 0
```

Read a list from a pipe:

```console
$ cat names.txt | python3 -m namekey index -
```

## How to test

namekey's tests use pytest:

```console
$ python3 -m pytest
```

The tests in `tests/` cover Soundex known values, folding, comma handling, skeleton keys, Levenshtein and Jaro-Winkler, ranking, parsing with line numbers, lint findings, duplicate grouping, the index, and the CLI exit codes.

## Project layout

```text
namekey/
  core.py      matching, keys, scoring, lint and dedupe logic
  cli.py       argparse front end and exit codes
  __main__.py  python3 -m namekey entry point
tests/
  test_core.py
  test_cli.py
examples/
  guests.txt   sample list with deliberate near-duplicates
pytest.ini
```

## Limits

- Soundex is English-oriented. It produces an empty key for names with no Latin letters, and such names only match on fuzzy score.
- The skeleton key is a heuristic and isn't a standard phonetic algorithm. Treat it as a bucketing aid, not an identity test.
- Duplicate detection suggests candidates. A person still has to decide whether two entries are the same.
