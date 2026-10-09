# Configuration: rule files and setup files

Two YAML files, and no others. A **rule file** switches check codes on and off for chosen
rows, and is the subject of this document. A **setup file** names which check files and
which rule files a run loads, so configuring the library is one call instead of two — the
last section here covers it. There are no environment variables and nothing is read from a
fixed location: every path comes from the entry point, on the command line or in code.

A relative path is resolved against the working directory, or against the `base_dir` the
call names — an entry point passes a directory found from its own location, a wrapper passes
the directory of the configuration the paths were read from. Nothing is searched for: a
path that is not a file is an error naming the absolute path that was tried.<sup>[1](#errors)</sup>

Rules let a non-developer enable a normally-off code, or disable a normally-on
code, **for specific rows**, without touching Python. They cannot define new checks,
change a message, or alter what a check does.<sup>[2](writing-checks.md#the-shape-of-a-check)</sup>

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
  message: "Internal test accounts shouldn't trigger email format errors"
  action: disable
  codes:
    - EMAIL_MISSING_AT
    - EMAIL_DOMAIN_INVALID
  match:
    - column: email
      pattern: "@internal\\.test$"

- name: "disable_age_integer_check_globally"
  message: "Example: disable AGE_NOT_INTEGER for every row, no filtering"
  action: disable
  codes:
    - AGE_NOT_INTEGER
  match: all
```

That is `examples/rules/error_rules.yaml` in the project root, verbatim but for its
comments; a test compares the two. The same rules split across files live in
`examples/rules/split_by_topic/` and `examples/rules/from_another_directory/`.

An empty file holds no rules and loads as none.

## Keys

| Key | Required | Type | Meaning |
|---|---|---|---|
| `name` | yes | non-empty string | Identifies the rule in tables and errors. Must be unique across *every* file loaded together. |
| `action` | yes | `enable` or `disable` | Exactly one of the two literals; anything else is an error. |
| `codes` | yes | non-empty list of strings | The codes the rule switches. Every code must already be registered when the file loads. |
| `match` | yes | list of criteria, or the literal `all` | Which rows the rule applies to. See below. |
| `message` | yes | string | Why the rule exists, in your words. Shown beside the rule by `rules_table`, so somebody deciding whether it still applies can read it. |

There are no other keys. An unrecognized key is rejected, naming the rule and listing what
is allowed: in a file edited by hand, a key that is silently ignored is a setting that
quietly does nothing.

A key written twice in one mapping — a second `codes:` appended to a rule — is refused
too, naming both lines. YAML itself would keep the last and drop the first without a word,
so the rule would say something other than it appears to.<sup>[1](#errors)</sup>

## Matching

Matching is **regex only**. There is no glob or wildcard alternative: one mechanism is
easier for non-developers to get right than two.

Each criterion is a mapping with both `column` and `pattern`, and nothing else: an extra
key such as `negate: true` is refused, since ignoring it would apply the rule to exactly the
rows it was meant to spare. The pattern is a Python
regular expression applied with `re.search`, so it matches anywhere in the value unless
anchored with `^`/`$`. Values are compared as the text the report prints for them: a
whole number is `41` even when pandas holds it as `41.0` — which it does for an integer
column with one blank cell, and for every column of an all-numeric frame — and a fraction
keeps its decimals. Anything else is `str(value)`. (Checks still receive the cell as
pandas holds it; only matching and the report turn it into text.)<sup>[3](reporting.md#showing-data-alongside-the-failures)</sup>

A rule applies to a row only when **every** criterion matches (AND). A criterion whose
column is absent from the row, or whose value is null, does not match.<sup>[4](#warnings)</sup>

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

Nothing reads a directory or sorts file names: a directory in the list is an error, and
the order is the list's. `examples/rules/split_by_topic/` numbers its files `01_`, `02_`
only so a listing shows them in the order a caller should name them.

In `examples/rules/error_rules.yaml` the third rule (`match: all`, disable) is listed after the first
(enable for legacy batch rows) and therefore wins on every row, including legacy batch
rows — that is the precedence demonstration, not a mistake.

It is also the shape worth finding when it *is* a mistake, so it is reported.
`warn_shadowed_rules` takes the loaded rules and names every rule a later
`match: all` rule overrules for every row; `python3 examples/main.py --rules-table`
prints those warnings under the rules table, which is why the shipped file's own
demonstration shows up there. Nothing else tells you: the registry table lists both
rules under `could_be_overridden_by`, which is right in general and unhelpful in this
one case where every row gives the same answer.<sup>[5](interfaces.md#registry_tablerulesnone---dataframe)</sup> The
pattern that works is the reverse order — disable for every row, then enable for the
rows that match — and it reports nothing.

To see which rule decided a check on a row, read the report's `rule` column: it names
the last matching rule, enable or disable, and is empty where the check's default
stood. `build_report(include="all")` shows it for checks that passed too.<sup>[6](reporting.md#shape-one-row-per-failure)</sup>

Two conditional rules are not compared. Whether their patterns overlap is a question
about the regexes rather than about the file, and a wrong answer would be worse than
none.

## Copies of one row: rules match each copy

Under `validate(repeat_key=...)`, rows sharing a key value are copies of one row, and a
check without `repeat=True` runs on one copy and is recorded `shared` on the others.
Rules still match every copy. A rule that disables `VAL_IN_RANGE` where `dirname`
matches `^eps2$` records `disabled` on the `eps2` copy, and skips its dependents there,
whichever copy `eps2` is. If it is the first copy, the next copy that enables the check
runs it, and the copies after that one share the result. A check that every copy
disables is `disabled` on each.<sup>[7](writing-checks.md#one-row-many-copies)</sup>

## Disabling a check disables what depends on it

A check runs only once every check it depends on has passed, and a disabled one has not.
Disabling `AGE_PRESENT` for some rows therefore switches off `AGE_NOT_A_NUMBER`,
`AGE_NEGATIVE`, `AGE_TOO_HIGH` and the off-by-default `AGE_NOT_INTEGER` on those rows as
well: a negative or unreadable age there
passes without a line in the report, and only the summary's `skipped` column counts it.<sup>[8](writing-checks.md#layering-one-problem-one-error)</sup> A
rule cannot say "this field may be blank"; the check has to know which rows may leave it
empty.

`warn_blocking_rules` takes the loaded rules and names, for each disabled code, the checks
below it the rule does not list itself. `python3 examples/main.py --rules-table` prints
those warnings under the rules table. Listing the dependents in the same rule says the
silence is meant and ends the warning: the shipped file's
`suppress_email_checks_for_test_accounts` disables `EMAIL_MISSING_AT` together with the
check that depends on it, and reports nothing.<sup>[9](interfaces.md#warn_blocking_rulesrules---liststr)</sup>

## Errors

Everything is validated when the file loads, never when a rule first meets a row, so a
malformed file stops the run before any data is processed. Each message names the file,
and the rule too once the entry has a name to give; before then, its place in the file.
A value the file got wrong is shown as it was read: a `True` or `False` where you wrote
text means YAML read an unquoted `yes`, `no`, `on` or `off` as a boolean, so quote it.

| Problem | Message |
|---|---|
| empty `match: []` | `'match' is an empty list. Use 'match: all' if you really mean every row.` |
| missing `match` | `missing 'match'. Use 'match: all' to apply the rule to every row.` |
| `match: al` | `'match' must be a list of criteria or the literal 'all', got 'al'.` |
| criterion missing a key | `'match' entry {'column': 'email'} needs both 'column' and 'pattern'.` |
| criterion with another key | `'match' entry {'column': 'email', 'pattern': 'x', 'negate': True} has unknown key(s) 'negate'. A criterion holds only 'column' and 'pattern'.` |
| a key given twice | `key 'codes' appears twice in one mapping, on lines 4 and 5. YAML would keep only the last; remove one.` |
| a file not saved as UTF-8 | `not UTF-8 text: 'utf-8' codec can't decode byte 0xe9 in position 11: invalid continuation byte. Save the file as UTF-8.` |
| bad regex | `invalid regex '([unclosed' for column 'email': unterminated character set at position 1` |
| bad action | `'action' must be exactly 'enable' or 'disable', got 'turn_on'.` |
| unknown code | `unknown code 'NO_SUCH_CODE'. Load the check file that defines it before loading rules, or fix the code.` |
| duplicate name | `Duplicate rule name 'same_name': defined in a.yaml and again in b.yaml.` |
| nested under a key | `rule files must contain a flat top-level list of rules (no 'rules:' key), got dict.` |
| misspelled key | `unknown key(s) 'codez'. Allowed: 'action', 'codes', 'match', 'message', 'name'.` |
| `on:` unquoted, which YAML reads as a bool | `unknown key(s) True. Allowed: 'action', 'codes', 'match', 'message', 'name'.` |
| an entry that is not a mapping | `each rule must be a mapping, got str.` |
| no `name`, or not text (`name: off`, second in the file) | `rule 2: every rule needs a non-empty string 'name', got False.` |
| `codes` not a list of text (`codes: [ON]`) | `'codes' must be a non-empty list of code strings, got [True].` |
| no `message` | `'message' must be the text saying why the rule exists, got None. It is printed beside the rule wherever the rules are listed.` |
| a criterion that is not a mapping | `each 'match' entry must be a mapping with 'column' and 'pattern'.` |
| a criterion value that is not text | `'column' and 'pattern' must both be strings in {'column': 'country', 'pattern': False}.` |
| `load_rules("rules.yaml")` | `load_rules takes a list of paths, not one string: pass ['rules.yaml'].` |
| `load_rules(["rules.yaml", "rules.yaml"])` | `Rule file listed twice: /abs/path/rules.yaml.` |

An "unknown code" that you know exists usually means its check file was not loaded by this
entry point — see [writing-checks.md](writing-checks.md#troubleshooting).

A file that is not there is refused before it is read, by rule file, check file and
setup file alike, naming the path it tried:

| Problem | Message |
|---|---|
| relative path, nothing there | `No rule file at 'rules/missing.yaml': nothing at /home/me/run/rules/missing.yaml, where a relative path is resolved against the working directory. load_rules() names files explicitly; nothing is discovered.` |
| the same, with `base_dir` | `No rule file at 'missing.yaml': nothing at /srv/run/missing.yaml, where a relative path is resolved against base_dir /srv/run. load_rules() names files explicitly; nothing is discovered.` |
| a directory | `No rule file at 'rules': /home/me/run/rules is a directory, so name the file in it. load_rules() names files explicitly; nothing is discovered.` |
| absolute path, nothing there | `No rule file at '/srv/missing.yaml'. load_rules() names files explicitly; nothing is discovered.` |

A check file reads `No check file at` and `load_checks()`; a setup file, `No setup file
at` and `load_setup()`.

### Warnings

Three mistakes load cleanly and are only visible against the registry or the data, so
they are warnings, returned as lines by the functions in
[interfaces.md](interfaces.md#warn_missing_rule_columnsdf-rules---liststr) rather than
raised:

| Function | Line |
|---|---|
| `warn_missing_rule_columns` | `rule 'uk_only' matches on column 'country', which is not in the data: the rule will never apply` |
| `warn_shadowed_rules` | `rule 'uk_only' is overruled for <code> by the later rule 'everyone', which matches every row: it can never apply to <code>` |
| `warn_blocking_rules` | `rule 'no_age' disables <code>, which also stops <dependents> on the rows it matches: a check whose prerequisite is off is skipped, and reports nothing` |

## Secrets

Rule files are matching patterns and code names only. Nothing in the format is a
credential, and none should be put there: patterns are echoed verbatim into
`rules_table`.

## Setup files: naming the checks and the rules at once

Configuring this library is two calls -- `load_checks` for the check files, `load_rules` for
the rule files. A setup file is those two lists in one place, so it is one call and the
lists are a file you can commit beside a bug report rather than arguments typed twice:

```yaml
checks:
  - checks/check_age.py
  - checks/check_email.py
rules:
  - rules/error_rules.yaml      # precedence order; optional
```

```python
import pandas as pd
from jobcheck import build_report, load_setup, validate

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
path you type.<sup>[10](interfaces.md#loading-both-at-once)</sup>

`checks` is required: a setup naming only rules configures nothing, because rules switch
checks on and off. `rules` may be absent or empty -- the no-rules baseline every rule file
is a deviation from.

Rules are named by path rather than written into the setup file. A rule file is a flat
top-level list with no `rules:` key, which a setup file would have to contradict, and a rule
file is meant to be shared between runs -- inline rules would be copied into every setup
that wanted them and drift apart. `examples/setup.yaml` is the shipped example.

`load_checks` and `load_rules` stay: this composes them and does nothing they do not. A
caller that computed its paths itself -- jobchain reads them from its own run configuration -- has no file to write.

A setup file configures the library; it does not say what data to read or what to print.
`examples/run_from_config.py` shows one way to put those beside it: a run file naming a
setup file, the data and the tables; [cli.md](cli.md) describes it.

Every refusal names the file: a document that is not a mapping (a flat list is the *rule*
file's shape, and the mistake somebody makes having written one first), a key given twice
(a second `checks:` would otherwise replace the first list), an unknown key, a
string where a list belongs (`checks: one.py` is a string, and a string is a list of
characters), an entry that is not a path, and an empty `checks`:

| Problem | Message |
|---|---|
| a flat list | `setup.yaml: a setup file is a mapping of 'checks' and 'rules', got list.` |
| an unknown key | `setup.yaml: unknown key(s) 'extra'. A setup file holds 'checks', 'rules'.` |
| no `checks` | `setup.yaml: 'checks' is required: a setup file names the files to load.` |
| `checks: one.py` | `setup.yaml: 'checks' must be a list of paths, got str. Write it as a list even for one file.` |
| `checks: [3]` | `setup.yaml: 'checks' entry 1 must be a path, got int.` |
| `checks: []` | `setup.yaml: 'checks' is empty: name at least one file.` |

`setup.yaml` stands for the setup file's absolute path, which every one of these
messages starts with.

## References

| # | Section | What it covers |
|---|---|---|
| 1 | [Errors](#errors) | every message a rule or setup file can raise |
| 2 | [writing-checks.md: The shape of a check](writing-checks.md#the-shape-of-a-check) | where checks are defined instead |
| 3 | [reporting.md: Showing data](reporting.md#showing-data-alongside-the-failures) | the same rendering in the report |
| 4 | [Warnings](#warnings) | `warn_missing_rule_columns`, for a column the data lacks |
| 5 | [interfaces.md: registry_table](interfaces.md#registry_tablerulesnone---dataframe) | what `could_be_overridden_by` says |
| 6 | [reporting.md: Shape](reporting.md#shape-one-row-per-failure) | the report's columns, `rule` among them |
| 7 | [writing-checks.md: One row, many copies](writing-checks.md#one-row-many-copies) | `repeat_key` and `repeat=True` |
| 8 | [writing-checks.md: Layering](writing-checks.md#layering-one-problem-one-error) | why a skipped check reports nothing |
| 9 | [interfaces.md: warn_blocking_rules](interfaces.md#warn_blocking_rulesrules---liststr) | the function in full |
| 10 | [interfaces.md: Loading both at once](interfaces.md#loading-both-at-once) | `load_setup` as a call |
