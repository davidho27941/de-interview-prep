#!/usr/bin/env python3
"""Attempt log for DE interview prep: one JSON object per line.

  progress.py add --id d07/p3 --type pyspark --tags R:M,O:M --pattern sessionization \
                  --result fail --time 22 --target 18 --miss ritual-boundary,sort --note "..."
  progress.py summary            # pass rate by type / tag / pattern, miss frequency, overtime
  progress.py seen               # problem ids already attempted (avoid repeats)

The log defaults to progress/attempts.jsonl under the current directory; override with --log.
"""
import argparse
import json
import sys
from collections import Counter, defaultdict
from datetime import date
from pathlib import Path

TYPES = ("sql", "python", "pyspark", "debug", "algo")
RESULTS = ("pass", "fail", "guided")
MISSES = (
    "ritual-empty", "ritual-coalesce", "ritual-join", "ritual-boundary",
    "decoy-leak", "sort", "truthiness", "dedup", "null-handling", "precision",
    "spec-misread", "toolchain", "syntax", "timeout", "other",
)


def load(path):
    if not path.exists():
        return []
    rows = []
    with path.open(encoding="utf-8") as f:
        for n, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError as e:
                sys.exit(f"{path}:{n}: invalid JSON ({e})")
    return rows


def split(value):
    return [v.strip() for v in value.split(",") if v.strip()] if value else []


def cmd_add(args):
    misses = split(args.miss)
    unknown = [m for m in misses if m not in MISSES]
    if unknown:
        sys.exit(f"unknown miss code(s) {unknown}; allowed: {', '.join(MISSES)}")
    if args.result == "pass" and misses and not args.note:
        sys.exit("a pass with misses needs --note explaining what was caught before submitting")
    row = {
        "date": args.date or date.today().isoformat(),
        "id": args.id,
        "type": args.type,
        "tags": split(args.tags),
        "pattern": args.pattern,
        "result": args.result,
        "time_min": args.time,
        "target_min": args.target,
        "misses": misses,
        "note": args.note or "",
    }
    args.log.parent.mkdir(parents=True, exist_ok=True)
    with args.log.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")
    print(f"logged {row['id']} ({row['result']}) -> {args.log}")


def rate_table(title, groups):
    print(f"\n{title}")
    for key in sorted(groups):
        results = groups[key]
        passed = sum(r == "pass" for r in results)
        print(f"  {key:<24} {passed}/{len(results)} pass ({passed / len(results):.0%})")


def cmd_summary(args):
    rows = load(args.log)
    if not rows:
        print(f"no attempts logged in {args.log}")
        return
    print(f"{len(rows)} attempts, {rows[0]['date']} .. {rows[-1]['date']}")
    by_type, by_tag, by_pattern = defaultdict(list), defaultdict(list), defaultdict(list)
    misses, overtime, untimed = Counter(), [], 0
    for r in rows:
        by_type[r["type"]].append(r["result"])
        for t in r.get("tags", []):
            by_tag[t].append(r["result"])
        if r.get("pattern"):
            by_pattern[r["pattern"]].append(r["result"])
        misses.update(r.get("misses", []))
        if r.get("time_min") is None or r.get("target_min") is None:
            untimed += 1
        elif r["time_min"] > r["target_min"]:
            overtime.append(r)
    rate_table("By type", by_type)
    rate_table("By calibration tag", by_tag)
    rate_table("By pattern", by_pattern)
    print("\nMiss frequency")
    for code, n in misses.most_common():
        print(f"  {code:<24} {n}")
    if not misses:
        print("  (none recorded)")
    print(f"\nOver target time: {len(overtime)} of {len(rows) - untimed} timed attempts ({untimed} untimed)")
    for r in overtime:
        print(f"  {r['id']:<24} {r['time_min']} min vs target {r['target_min']}")


def cmd_seen(args):
    latest = {}
    for r in load(args.log):
        latest[r["id"]] = r["result"]
    for pid in sorted(latest):
        print(f"{pid}\t{latest[pid]}")


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--log", type=Path, default=Path("progress/attempts.jsonl"))
    sub = p.add_subparsers(dest="cmd", required=True)

    a = sub.add_parser("add")
    a.add_argument("--id", required=True, help="e.g. d07/p3, mock2/q4, lc-1280")
    a.add_argument("--type", required=True, choices=TYPES)
    a.add_argument("--tags", help="calibration, e.g. R:H,O:M")
    a.add_argument("--pattern", help="e.g. sessionization, top-n-per-group")
    a.add_argument("--result", required=True, choices=RESULTS)
    a.add_argument("--time", type=float, help="minutes actually spent")
    a.add_argument("--target", type=float, help="target minutes")
    a.add_argument("--miss", help=f"comma-separated: {', '.join(MISSES)}")
    a.add_argument("--note")
    a.add_argument("--date", help="YYYY-MM-DD, defaults to today")
    a.set_defaults(func=cmd_add)

    sub.add_parser("summary").set_defaults(func=cmd_summary)
    sub.add_parser("seen").set_defaults(func=cmd_seen)

    args = p.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
