#!/usr/bin/env python3
"""Generate the example data files the catalog validates.

Two files, both deliberately messy in the ways real exports are:

- ``customers.csv`` — 49 rows, written by hand-shaped rules so every example
  test has something to say about it and most rows are fine. Small enough that
  a reader can open it beside a report and check the tool's answer themselves.
- ``customers_clean.csv`` — 24 rows with nothing wrong, for showing what a
  passing run looks like: an empty report is a result, and a reader needs to
  have seen one.
- ``customers_large.csv`` — 2,000 rows on the same shape, generated from a fixed
  seed, for the cases and load tests that need volume rather than readability.

Deterministic: the seed is fixed and the row order is stable, so regenerating
produces the same bytes and a diff means the generator changed.

Usage: scripts/make_example_data.py [--rows N]
"""

from __future__ import annotations

import argparse
import csv
import random
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "examples" / "data"

COLUMNS = ["id", "name", "age", "email", "start_date", "end_date",
           "source_system", "record_type", "region"]

# The small file, row by row, so each problem is visible in the source rather
# than emerging from a generator. Every value here is one a real export has
# produced: a blank field, an age typed as a decimal, a sentinel 999, an
# address with no dot in the domain, a date range the wrong way round, a name
# holding a comma, and a cell a spreadsheet would treat as a formula.
SMALL_ROWS: list[dict[str, str]] = [
    {"id": "1001", "name": "Ada Lovelace", "age": "36", "email": "ada@example.com",
     "start_date": "2024-01-05", "end_date": "2024-06-30",
     "source_system": "MODERN", "record_type": "STREAM", "region": "EU"},
    {"id": "1002", "name": "Grace Hopper", "age": "45", "email": "grace@example.com",
     "start_date": "2024-02-01", "end_date": "2024-08-01",
     "source_system": "MODERN", "record_type": "STREAM", "region": "US"},
    {"id": "1003", "name": "Katherine Johnson", "age": "", "email": "kj@example.com",
     "start_date": "2024-01-15", "end_date": "2024-07-15",
     "source_system": "MODERN", "record_type": "STREAM", "region": "US"},
    {"id": "1004", "name": "Alan Turing", "age": "-4", "email": "alan@example.com",
     "start_date": "2024-03-01", "end_date": "2024-04-01",
     "source_system": "MODERN", "record_type": "STREAM", "region": "EU"},
    {"id": "1005", "name": "Jean Bartik", "age": "999", "email": "jean@example.com",
     "start_date": "2024-01-01", "end_date": "2024-12-31",
     "source_system": "MODERN", "record_type": "BATCH", "region": "US"},
    {"id": "1006", "name": "Mary Jackson", "age": "thirty", "email": "mary@example.com",
     "start_date": "2024-02-10", "end_date": "2024-03-10",
     "source_system": "MODERN", "record_type": "STREAM", "region": "US"},
    {"id": "1007", "name": "Frances Allen", "age": "52", "email": "frances-example.com",
     "start_date": "2024-04-01", "end_date": "2024-09-01",
     "source_system": "MODERN", "record_type": "STREAM", "region": "US"},
    {"id": "1008", "name": "Barbara Liskov", "age": "61", "email": "barbara@localhost",
     "start_date": "2024-01-20", "end_date": "2024-02-20",
     "source_system": "MODERN", "record_type": "STREAM", "region": "US"},
    {"id": "1009", "name": "Sophie Wilson", "age": "48", "email": "",
     "start_date": "2024-05-01", "end_date": "2024-05-31",
     "source_system": "MODERN", "record_type": "STREAM", "region": "UK"},
    {"id": "1010", "name": "Karen Spärck Jones", "age": "58", "email": "karen@example.com",
     "start_date": "2024-09-01", "end_date": "2024-03-01",
     "source_system": "MODERN", "record_type": "STREAM", "region": "UK"},
    {"id": "1011", "name": "Radia Perlman", "age": "57", "email": "radia@example.com",
     "start_date": "", "end_date": "2024-08-01",
     "source_system": "MODERN", "record_type": "STREAM", "region": "US"},
    {"id": "1012", "name": "Shafi Goldwasser", "age": "60", "email": "shafi@example.com",
     "start_date": "2024-02-14", "end_date": "",
     "source_system": "MODERN", "record_type": "STREAM", "region": "IL"},
    {"id": "1013", "name": "Éva Tardos", "age": "62", "email": "eva@example.com",
     "start_date": "2024-03-03", "end_date": "2024-10-03",
     "source_system": "LEGACY_A", "record_type": "BATCH", "region": "HU"},
    {"id": "1014", "name": "Xiaoyun Wang", "age": "58.5", "email": "xiaoyun@example.com",
     "start_date": "2024-01-08", "end_date": "2024-11-08",
     "source_system": "LEGACY_A", "record_type": "BATCH", "region": "CN"},
    {"id": "1015", "name": "Fan Chung", "age": "74.0", "email": "fan@example.com",
     "start_date": "2024-06-01", "end_date": "2024-07-01",
     "source_system": "LEGACY_B", "record_type": "BATCH", "region": "US"},
    {"id": "1016", "name": "Sun Microsystems, Inc.", "age": "41", "email": "ops@example.com",
     "start_date": "2024-02-02", "end_date": "2024-03-02",
     "source_system": "LEGACY_B", "record_type": "STREAM", "region": "US"},
    {"id": "1017", "name": "QA Account", "age": "33", "email": "qa@internal.test",
     "start_date": "2024-01-01", "end_date": "2024-02-01",
     "source_system": "MODERN", "record_type": "STREAM", "region": "US"},
    {"id": "1018", "name": "Load Test", "age": "34", "email": "load-test@internal.test",
     "start_date": "2024-01-01", "end_date": "2024-02-01",
     "source_system": "MODERN", "record_type": "STREAM", "region": "US"},
    # The name is a formula, and the row fails a test on purpose: a value only
    # reaches the report through a failing row, so an escaping example needs one.
    {"id": "1019", "name": "=SUM(A1:A9)", "age": "29", "email": "sheet-example.com",
     "start_date": "2024-03-15", "end_date": "2024-04-15",
     "source_system": "MODERN", "record_type": "STREAM", "region": "EU"},
    {"id": "1020", "name": "  Padded Name  ", "age": " 44 ", "email": " spaced@example.com ",
     "start_date": "2024-01-11", "end_date": "2024-02-11",
     "source_system": "MODERN", "record_type": "STREAM", "region": "EU"},
    {"id": "1021", "name": "", "age": "", "email": "", "start_date": "", "end_date": "",
     "source_system": "", "record_type": "", "region": ""},
    # Every column blank: the base suite's ROW_ALL_NULL exists for this row, and
    # a real export produces one whenever a trailing delimiter line survives.
    {"id": "", "name": "", "age": "", "email": "", "start_date": "", "end_date": "",
     "source_system": "", "record_type": "", "region": ""},
    {"id": "", "name": "No Id At All", "age": "38", "email": "noid@example.com",
     "start_date": "2024-02-01", "end_date": "2024-03-01",
     "source_system": "MODERN", "record_type": "STREAM", "region": "EU"},
    {"id": "1023", "name": "Duplicate Id", "age": "31", "email": "dup@example.com",
     "start_date": "2024-01-02", "end_date": "2024-02-02",
     "source_system": "MODERN", "record_type": "STREAM", "region": "EU"},
    {"id": "1023", "name": "Duplicate Id Again", "age": "31", "email": "dup2@example.com",
     "start_date": "2024-01-02", "end_date": "2024-02-02",
     "source_system": "MODERN", "record_type": "STREAM", "region": "EU"},
]

# The rest of the small file: ordinary rows, so the failures above sit in a
# majority of valid data the way they do in a real export.
FILLER_NAMES = [
    "Anita Borg", "Carol Shaw", "Erna Hoover", "Evelyn Boyd Granville",
    "Hedy Lamarr", "Ida Rhodes", "Jean Sammet", "Joan Clarke", "Kathleen Booth",
    "Lois Haibt", "Margaret Hamilton", "Marlyn Meltzer", "Mary Allen Wilkes",
    "Milly Koss", "Ruth Teitelbaum", "Sister Mary Kenneth Keller",
    "Thelma Estrin", "Frances Spence", "Betty Holberton", "Kathleen Antonelli",
    "Adele Goldstine", "Klara Dan von Neumann", "Elizabeth Feinler", "Susan Kare",
]


def small_rows() -> list[dict[str, str]]:
    """The 49 rows of ``customers.csv``: the shaped ones, then the ordinary ones."""

    rows = list(SMALL_ROWS)
    for offset, name in enumerate(FILLER_NAMES):
        number = 1030 + offset
        rows.append({
            "id": str(number),
            "name": name,
            "age": str(28 + (offset * 3) % 45),
            "email": f"{name.split()[0].lower()}{number}@example.com",
            "start_date": f"2024-0{1 + offset % 9}-0{1 + offset % 8}",
            "end_date": f"2024-1{offset % 2}-1{offset % 9}",
            "source_system": "LEGACY_A" if offset % 8 == 0 else "MODERN",
            "record_type": "BATCH" if offset % 8 == 0 else "STREAM",
            "region": ["EU", "US", "UK", "APAC"][offset % 4],
        })
    return rows


def clean_rows() -> list[dict[str, str]]:
    """24 rows every example test passes, so a clean run has something to show."""

    rows: list[dict[str, str]] = []
    for offset, name in enumerate(FILLER_NAMES[:24]):
        number = 2000 + offset
        rows.append({
            "id": str(number),
            "name": name,
            "age": str(24 + offset),
            "email": f"{name.split()[0].lower()}{number}@example.com",
            "start_date": "2024-01-01",
            "end_date": "2024-12-31",
            "source_system": "MODERN",
            "record_type": "STREAM",
            "region": ["EU", "US", "UK", "APAC"][offset % 4],
        })
    return rows


def large_rows(count: int, seed: int = 20260910) -> list[dict[str, str]]:
    """*count* rows on the same shape, from a fixed seed.

    Roughly one row in six carries a problem, which is the proportion that makes
    a summary worth reading: enough failures to see the layering work, not so
    many that everything is red.
    """

    rng = random.Random(seed)
    rows: list[dict[str, str]] = []
    for index in range(count):
        number = 5000 + index
        broken = rng.randrange(6) == 0
        age = str(rng.randrange(18, 92))
        email = f"user{number}@example.com"
        start, end = "2024-01-01", "2024-06-01"
        if broken:
            which = rng.randrange(5)
            if which == 0:
                age = ""
            elif which == 1:
                age = str(-rng.randrange(1, 40))
            elif which == 2:
                age = str(rng.randrange(140, 1000))
            elif which == 3:
                email = f"user{number}-example.com"
            else:
                start, end = end, start
        legacy = rng.randrange(10) == 0
        rows.append({
            "id": str(number),
            "name": f"Person {number}",
            "age": age,
            "email": email,
            "start_date": start,
            "end_date": end,
            "source_system": "LEGACY_A" if legacy else "MODERN",
            "record_type": "BATCH" if legacy else "STREAM",
            "region": ["EU", "US", "UK", "APAC"][index % 4],
        })
    return rows


def write(path: Path, rows: list[dict[str, str]]) -> None:
    """Write *rows* as CSV with a stable newline, so the bytes do not drift."""

    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=COLUMNS, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    print(f"{path.relative_to(ROOT)}: {len(rows)} rows")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rows", type=int, default=2000,
                        help="rows in the large file (default 2000)")
    args = parser.parse_args(argv)

    DATA.mkdir(parents=True, exist_ok=True)
    write(DATA / "customers.csv", small_rows())
    write(DATA / "customers_clean.csv", clean_rows())
    write(DATA / "customers_large.csv", large_rows(args.rows))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
