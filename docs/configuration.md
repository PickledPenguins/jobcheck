# Configuration: override rule files

The only configuration this project has is the override YAML. There are no environment
variables and no settings file: suites and rule paths are chosen by the entry point, on
the command line or in code.

Override rules let a non-developer enable a normally-off code, or disable a normally-on
code, **for specific rows**, without touching Python. They cannot define new checks,
change a message, or alter what a check does.

Back to the [README](../README.md). Checks themselves are written in
[Python](writing-checks.md); the Python loaders are in
[interfaces.md](interfaces.md#loading-override-rules).

## File shape

A flat top-level YAML list of rule mappings. There is no `rules:` key and no other
top-level structure — the syntax is kept as shallow as possible for people who do not
write code.

```yaml
- name: "enable_legacy_integer_check"
  description: "Turn on strict integer check for legacy-system batch rows"
  action: enable
  codes:
    - AGE_NOT_INTEGER
  match:
    - column: source_system
      pattern: "^LEGACY_.*"
    - column: record_type
      pattern: "^BATCH$"

- name: "suppress_email_checks_for_test_accounts"
  description: "Internal check accounts shouldn't trigger email format errors"
  action: disable
  codes:
    - EMAIL_MISSING_AT
    - EMAIL_DOMAIN_INVALID
  match:
    - column: email
      pattern: "@internal\\.check$"

- name: "disable_age_integer_check_globally"
  description: "Example: disable AGE_NOT_INTEGER for every row, no filtering"
  action: disable
  codes:
    - AGE_NOT_INTEGER
  match: all
```

That is `examples/rules/error_overrides.yaml` in the project root, verbatim. The same rules split across
files live in `examples/rules/split_by_topic/` and `examples/rules/from_another_directory/`.

## Keys

| Key | Required | Type | Meaning |
|---|---|---|---|
| `name` | yes | non-empty string | Identifies the rule in tables, errors, and `list_rule_codes`. Must be unique across *every* file loaded together. |
| `action` | yes | `enable` or `disable` | Exactly one of the two literals; anything else is an error. |
| `codes` | yes | non-empty list of strings | The codes the rule switches. Every code must already be registered when the file loads. |
| `match` | yes | list of criteria, or the literal `all` | Which rows the rule applies to. See below. |
| `description` | no | string, default `""` | Free text for humans. Not used in matching. |

There are no other keys. An unrecognised key is rejected, naming the rule and listing what
is allowed: in a file edited by hand, a key that is silently ignored is a setting that
quietly does nothing.

## Matching

Matching is **regex only**. There is no glob or wildcard alternative: one mechanism is
easier for non-developers to get right than two.

Each criterion is a mapping with both `column` and `pattern`. The pattern is a Python
regular expression applied with `re.search`, so it matches anywhere in the value unless
anchored with `^`/`$`. Values are compared as text (`str(value)`).

A rule applies to a row only when **every** criterion matches (AND). A criterion whose
column is absent from the row, or whose value is null, does not match.

`match: all` is the explicit way to say "every row, no column filtering".

Two shapes are rejected rather than treated as match-everything:

- `match: []` — an empty list is far more likely an accidentally deleted criterion or an
  unfilled template than a deliberate global rule, and getting it wrong disables checks
  across a whole dataset.
- a missing `match` key — same reason; it must never default to anything.

`match: al` and any other bare string is rejected as a typo.

## Precedence: last rule wins

For a given row, the state of a code starts at the check's `default_enabled`, then every
matching rule is applied in load order. The **last** matching rule decides. There is no
priority field, so ordering is entirely positional — which makes load order part of the
configuration:

| Loader | Order |
|---|---|
| one file | position in the file |
| `load_overrides_from_dir` / `-o` on a directory of files | **alphabetical filename**, then position within each file |
| `load_overrides_from_files` / repeated `-o` paths | the order the paths are given |

With directory loading, filenames carry precedence: name files `01_x.yaml`, `02_y.yaml`
when the ordering between them matters.

In `examples/rules/error_overrides.yaml` the third rule (`match: all`, disable) is listed after the first
(enable for legacy batch rows) and therefore wins on every row, including legacy batch
rows — that is the precedence demonstration, not a mistake.

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
| unknown code | `unknown code 'NO_SUCH_CODE'. Load the suite that defines it before loading overrides, or fix the code.` |
| duplicate name | `Duplicate override rule name 'same_name': defined in a.yaml and again in b.yaml.` |
| nested under a key | `override files must contain a flat top-level list of rules (no 'rules:' key), got dict.` |
| misspelled key | `unknown key(s) codez. Allowed: action, codes, description, match, name.` |

An "unknown code" that you know exists usually means its suite was not loaded by this
entry point — see [writing-checks.md](writing-checks.md#troubleshooting).

## Secrets

Rule files are matching patterns and code names only. Nothing in the format is a
credential, and none should be put there: patterns are echoed verbatim into the
`print_override_rules` table.
