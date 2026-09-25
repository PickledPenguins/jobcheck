# Configuration: rule files and setup files

Two YAML files, and no others. A **rule file** switches check codes on and off for chosen
rows, and is the subject of this document. A **setup file** names which check files and
which rule files a run loads, so configuring the library is one call instead of two — the
last section here covers it. There are no environment variables and nothing is read from a
fixed location: every path comes from the entry point, on the command line or in code.

A relative path is resolved against the working directory, or against the `base_dir` the
call names — an entry point passes the directory its own files sit in, a wrapper passes
the directory of the configuration the paths were read from. Nothing is searched for: a
path that is not a file is an error naming the absolute path that was tried.

Rules let a non-developer enable a normally-off code, or disable a normally-on
code, **for specific rows**, without touching Python. They cannot define new checks,
change a message, or alter what a check does.

Back to the [README](../README.md). Checks themselves are written in
[Python](writing-checks.md); the Python loaders are in
[interfaces.md](interfaces.md#loading-rules).

## File shape

A flat top-level YAML list of rule mappings. There is no `rules:` key and no other
top-level structure — the syntax is kept as shallow as possible for people who do not
write code.

```yaml
- name: "enable_legacy_integer_check"
  message: "Turn on strict integer check for legacy-system batch rows"
  action: enable
  codes:
    - AGE_NOT_INTEGER
  match:
    - column: source_system
      pattern: "^LEGACY_.*"
    - column: record_type
      pattern: "^BATCH$"

- name: "suppress_email_checks_for_test_accounts"
  message: "Internal check accounts shouldn't trigger email format errors"
  action: disable
  codes:
    - EMAIL_MISSING_AT
    - EMAIL_DOMAIN_INVALID
  match:
    - column: email
      pattern: "@internal\\.check$"

- name: "disable_age_integer_check_globally"
  message: "Example: disable AGE_NOT_INTEGER for every row, no filtering"
  action: disable
  codes:
    - AGE_NOT_INTEGER
  match: all
```

That is `examples/rules/error_rules.yaml` in the project root, verbatim. The same rules split across
files live in `examples/rules/split_by_topic/` and `examples/rules/from_another_directory/`.

## Keys

| Key | Required | Type | Meaning |
|---|---|---|---|
| `name` | yes | non-empty string | Identifies the rule in tables, errors, and `list_rule_codes`. Must be unique across *every* file loaded together. |
| `action` | yes | `enable` or `disable` | Exactly one of the two literals; anything else is an error. |
| `codes` | yes | non-empty list of strings | The codes the rule switches. Every code must already be registered when the file loads. |
| `match` | yes | list of criteria, or the literal `all` | Which rows the rule applies to. See below. |
| `message` | yes | string | Why the rule exists, in your words. Printed beside the rule by `print_rules`, so somebody deciding whether it still applies can read it. |

There are no other keys. An unrecognized key is rejected, naming the rule and listing what
is allowed: in a file edited by hand, a key that is silently ignored is a setting that
quietly does nothing.

## Matching

Matching is **regex only**. There is no glob or wildcard alternative: one mechanism is
easier for non-developers to get right than two.

Each criterion is a mapping with both `column` and `pattern`. The pattern is a Python
regular expression applied with `re.search`, so it matches anywhere in the value unless
anchored with `^`/`$`. Values are compared as the text the report prints for them: a
whole number is `41` even when pandas holds it as `41.0` — which it does for an integer
column with one blank cell, and for every column of an all-numeric frame — and a fraction
keeps its decimals. Anything else is `str(value)`. (Checks still receive the cell as
pandas holds it; only matching and the report render it.)

A rule applies to a row only when **every** criterion matches (AND). A criterion whose
column is absent from the row, or whose value is null, does not match.

`match: all` is the explicit way to say "every row, no column filtering".

Two shapes are rejected rather than treated as match-everything:

- `match: []` — an empty list is far more likely an accidentally deleted criterion or an
  unfilled template than a deliberate global rule, and getting it wrong disables checks
  across a whole dataset.
- a missing `match` key — same reason; it must never default to anything.

`match: al` and any other bare string is rejected as a typo.

### What a pattern costs, and what is not bounded

A pattern runs once per criterion per row, so a 4,000-row frame runs it 4,000 times.
Anchored literals — what every rule here uses — cost nothing worth measuring.

**A pattern that backtracks catastrophically is not bounded, and that is deliberate.**
A quantifier applied to a group that is itself quantified (`(a+)+$`), or alternation
whose branches can match the same text (`(a|a)+$`), takes time that doubles with each
character of the value. Measured with `(a+)+$` against a value of *n* `a`s and one
character that cannot match: 20 characters 0.16s, 24 characters 2.5s, 26 characters
11s, 28 characters 42s. A 35-character cell would take hours, per row, with nothing to
interrupt it and no message naming the rule.

Nothing in the loader refuses such a pattern, and nothing times one out at match time:

- Python's `re` has no timeout. The third-party `regex` module has one, and a runtime
  dependency is not something this library takes.
- A load-time heuristic cannot be drawn accurately. Refusing "a quantifier inside a
  quantified group" also refuses `^(\d+,)+$`, an ordinary comma-separated-list pattern,
  while still passing `(a|a)+$` — a rule file that worked yesterday failing to load, and
  the catastrophic case getting through anyway.

Rule files are the owner's own configuration, so the exposure is a run that hangs, not an
untrusted input. Keep patterns anchored and simple; if a run stops making progress, the
rule file is the first place to look. `tests/test_safety.py` pins that a cell-sized value
(23 characters) survives, which is a statement about the value's length, not about the
matcher being safe.

## Precedence: last rule wins

For a given row, the state of a code starts at the check's `default_enabled`, then every
matching rule is applied in load order. The **last** matching rule decides. There is no
priority field, so ordering is entirely positional — which makes load order part of the
configuration:

| Loader | Order |
|---|---|
| one file | position in the file |
| `load_rules(paths)` / `--rules` | the order the paths are given |

With directory loading, filenames carry precedence: name files `01_x.yaml`, `02_y.yaml`
when the ordering between them matters.

In `examples/rules/error_rules.yaml` the third rule (`match: all`, disable) is listed after the first
(enable for legacy batch rows) and therefore wins on every row, including legacy batch
rows — that is the precedence demonstration, not a mistake.

It is also the shape worth finding when it *is* a mistake, so it is reported.
`warn_shadowed_rules` takes the loaded rules and names every rule a later
`match: all` rule overrules for every row; `python3 examples/main.py --rules-table`
prints those warnings under the rules table, which is why the shipped file's own
demonstration shows up there. Nothing else tells you: the registry table lists both
rules under `could_be_overridden_by` and answers `depends on row`, which is right in
general and unhelpful in this one case where every row gives the same answer. The
pattern that works is the reverse order — disable for every row, then enable for the
rows that match — and it reports nothing.

Two conditional rules are not compared. Whether their patterns overlap is a question
about the regexes rather than about the file, and a wrong answer would be worse than
none.

## Errors

Everything is validated when the file loads, never when a rule first meets a row, so a
malformed file stops the run before any data is processed. Each message names the rule and
the file it came from.

| Problem | Message |
|---|---|
| empty `match: []` | `'match' is an empty list. Use 'match: all' if you really mean every row.` |
| missing `match` | `missing 'match'. Use 'match: all' to apply the rule to every row.` |
| `match: al` | `'match' must be a list of criteria or the literal 'all', got 'al'.` |
| criterion missing a key | `'match' entry {'column': 'email'} needs both 'column' and 'pattern'.` |
| bad regex | `invalid regex '([unclosed' for column 'email': unterminated character set at position 1` |
| bad action | `'action' must be exactly 'enable' or 'disable', got 'turn_on'.` |
| unknown code | `unknown code 'NO_SUCH_CODE'. Load the check file that defines it before loading rules, or fix the code.` |
| duplicate name | `Duplicate rule name 'same_name': defined in a.yaml and again in b.yaml.` |
| nested under a key | `rule files must contain a flat top-level list of rules (no 'rules:' key), got dict.` |
| misspelled key | `unknown key(s) codez. Allowed: action, codes, match, message, name.` |

An "unknown code" that you know exists usually means its check file was not loaded by this
entry point — see [writing-checks.md](writing-checks.md#troubleshooting).

## Secrets

Rule files are matching patterns and code names only. Nothing in the format is a
credential, and none should be put there: patterns are echoed verbatim into the
`print_rules` table.

## Setup files: naming the checks and the rules at once

Configuring this library is two calls -- `load_checks` for the check files, `load_rules` for
the rule files. A setup file is those two lists in one place, so it is one call and the
lists are a file you can commit beside a bug report rather than arguments typed twice:

```yaml
checks:
  - checks/all_checks.py        # a bundle, or list the files
rules:
  - rules/error_rules.yaml      # precedence order; optional
```

```python
import pandas as pd
from jobcheck import build_report, load_setup, print_report, validate

rules = load_setup("examples/setup.yaml")
frame = pd.DataFrame([{"id": 1, "age": -5, "email": "nope"}])
report = build_report(validate(frame, rules=rules), df=frame, key_column="id")
print(len(report), "failure(s)")
```

```
3 failure(s)
```

`load_setup` returns the rules for `validate`, having already registered the check files.
Both lists resolve against **the setup file's own directory**, so a setup file and the paths
in it travel together; the setup file's own path is relative to where you stand, like any
path you type.

`checks` is required: a setup naming only rules configures nothing, because rules switch
checks on and off. `rules` may be absent or empty -- the no-rules baseline every rule file
is a deviation from.

Rules are named by path rather than written into the setup file. A rule file is a flat
top-level list with no `rules:` key, which a setup file would have to contradict, and a rule
file is meant to be shared between runs -- inline rules would be copied into every setup
that wanted them and drift apart. `examples/setup.yaml` is the shipped example.

`load_checks` and `load_rules` stay: this composes them and does nothing they do not. A
bundle calls `load_checks` from inside a check file, and a caller that computed its paths
itself -- jobchain reads them from its own run configuration -- has no file to write.

A setup file configures the library; it does not say what data to read or what to print.
`examples/run_from_config.py` shows one way to put those beside it: a run file naming a
setup file, the data and the tables; [cli.md](cli.md) describes it.

Every refusal names the file: a document that is not a mapping (a flat list is the *rule*
file's shape, and the mistake somebody makes having written one first), an unknown key, a
string where a list belongs (`checks: one.py` is a string, and a string is a list of
characters), an entry that is not a path, and an empty `checks`.
