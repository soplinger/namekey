"""Command-line interface for namekey.

Exit codes:
  0  success, or a gate passed
  1  a CI gate failed (lint errors over the limit, or duplicates found)
  2  bad usage or unreadable input
"""

import argparse
import json
import sys

from . import core

EXIT_OK = 0
EXIT_GATE = 1
EXIT_USAGE = 2


def _read_text(path):
    if path == "-":
        return sys.stdin.read()
    with open(path, encoding="utf-8") as handle:
        return handle.read()


def _load_names(path):
    return [name for _, name in core.parse_names(_read_text(path))]


def _emit(payload, as_json, text_lines):
    if as_json:
        print(json.dumps(payload, indent=2, ensure_ascii=False))
    else:
        print("\n".join(text_lines))


def cmd_key(args):
    rows = [
        {"name": name, "surname": core.surname(name), "soundex": core.name_key(name),
         "skeleton": core.skeleton(name)}
        for name in args.names
    ]
    lines = [f"{r['name']:<30} soundex={r['soundex'] or '-':<5} skeleton={r['skeleton'] or '-'}"
             for r in rows]
    _emit(rows, args.json, lines)
    return EXIT_OK


def cmd_compare(args):
    report = core.compare(args.a, args.b)
    lines = [
        f"{report['a']!r} vs {report['b']!r}",
        f"  soundex:        {report['soundex_a'] or '-'} / {report['soundex_b'] or '-'}"
        f"  ({'sounds alike' if report['sounds_alike'] else 'different'})",
        f"  skeleton:       {report['skeleton_a'] or '-'} / {report['skeleton_b'] or '-'}"
        f"  ({'same' if report['same_skeleton'] else 'different'})",
        f"  jaro-winkler:   {report['jaro_winkler']:.4f}",
        f"  levenshtein:    {report['levenshtein']} edits"
        f"  (similarity {report['levenshtein_similarity']:.4f})",
        f"  same after fold: {'yes' if report['exact_after_fold'] else 'no'}",
    ]
    _emit(report, args.json, lines)
    return EXIT_OK


def cmd_match(args):
    names = _load_names(args.file)
    ranked = core.rank(args.query, names, limit=args.limit, min_score=args.min_score)
    rows = [{"name": n, "score": s, "sounds_alike": a} for n, s, a in ranked]
    lines = [f"{'match':<3} {'score':<7} name"]
    for row in rows:
        mark = "~" if row["sounds_alike"] else " "
        lines.append(f"{mark:<3} {row['score']:<7.4f} {row['name']}")
    if not rows:
        lines.append("no matches")
    _emit({"query": args.query, "matches": rows}, args.json, lines)
    return EXIT_OK


def cmd_dedupe(args):
    entries = core.parse_names(_read_text(args.file))
    groups = core.dedupe(entries, threshold=args.threshold)
    payload = {
        "threshold": args.threshold,
        "groups": [
            [{"line": number, "name": name} for number, name in group] for group in groups
        ],
    }
    lines = []
    for number, group in enumerate(groups, start=1):
        lines.append(f"group {number}:")
        for line_number, name in group:
            lines.append(f"  line {line_number}: {name}")
    if not groups:
        lines.append(f"no likely duplicates at threshold {args.threshold}")
    else:
        lines.append(f"{len(groups)} group(s) of likely duplicates")
    _emit(payload, args.json, lines)
    if groups and args.fail_on_groups:
        return EXIT_GATE
    return EXIT_OK


def cmd_lint(args):
    text = _read_text(args.file)
    findings = core.lint(text)
    errors = [f for f in findings if f[1] == "error"]
    warnings = [f for f in findings if f[1] == "warning"]
    payload = {
        "errors": len(errors),
        "warnings": len(warnings),
        "findings": [
            {"line": n, "severity": s, "code": c, "message": m} for n, s, c, m in findings
        ],
    }
    lines = [f"line {n}: {s} {c}: {m}" for n, s, c, m in findings]
    lines.append(f"{len(errors)} error(s), {len(warnings)} warning(s)")
    _emit(payload, args.json, lines)
    if len(errors) > args.max_errors:
        return EXIT_GATE
    if args.fail_on_warnings and warnings:
        return EXIT_GATE
    return EXIT_OK


def cmd_index(args):
    names = _load_names(args.file)
    buckets = core.index(names)
    payload = [{"soundex": code or None, "count": len(members), "names": members}
               for code, members in buckets]
    lines = []
    for code, members in buckets:
        lines.append(f"{code or '(no key)'} ({len(members)})")
        lines.extend(f"  {name}" for name in members)
    if not lines:
        lines.append("no names")
    _emit(payload, args.json, lines)
    return EXIT_OK


def build_parser():
    parser = argparse.ArgumentParser(
        prog="namekey",
        description="Offline name matching: Soundex and skeleton keys, fuzzy scores, "
                    "duplicate groups and line-numbered lint.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    def add_json(p):
        p.add_argument("--json", action="store_true", help="print machine-readable JSON")

    p = sub.add_parser("key", help="show Soundex and skeleton keys for names")
    p.add_argument("names", nargs="+")
    add_json(p)
    p.set_defaults(func=cmd_key)

    p = sub.add_parser("compare", help="compare two names in detail")
    p.add_argument("a")
    p.add_argument("b")
    add_json(p)
    p.set_defaults(func=cmd_compare)

    p = sub.add_parser("match", help="rank names from a file against a query")
    p.add_argument("query")
    p.add_argument("file", help="name list file, or - for stdin")
    p.add_argument("--limit", type=int, default=5, help="show at most N matches (0 = all)")
    p.add_argument("--min-score", type=float, default=0.0, help="hide scores below this")
    add_json(p)
    p.set_defaults(func=cmd_match)

    p = sub.add_parser("dedupe", help="find groups of likely duplicate names")
    p.add_argument("file", help="name list file, or - for stdin")
    p.add_argument("--threshold", type=float, default=0.9, help="Jaro-Winkler cut-off")
    p.add_argument("--fail-on-groups", action="store_true",
                   help="exit 1 if any duplicate group is found")
    add_json(p)
    p.set_defaults(func=cmd_dedupe)

    p = sub.add_parser("lint", help="check a name list with line-numbered findings")
    p.add_argument("file", help="name list file, or - for stdin")
    p.add_argument("--max-errors", type=int, default=0,
                   help="exit 1 if there are more errors than this")
    p.add_argument("--fail-on-warnings", action="store_true",
                   help="exit 1 if there are any warnings")
    add_json(p)
    p.set_defaults(func=cmd_lint)

    p = sub.add_parser("index", help="group names by surname Soundex code")
    p.add_argument("file", help="name list file, or - for stdin")
    add_json(p)
    p.set_defaults(func=cmd_index)

    return parser


def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except OSError as exc:
        print(f"namekey: {exc.strerror or exc}: {exc.filename or ''}".rstrip(), file=sys.stderr)
        return EXIT_USAGE
    except UnicodeDecodeError as exc:
        print(f"namekey: input is not valid UTF-8: {exc}", file=sys.stderr)
        return EXIT_USAGE
