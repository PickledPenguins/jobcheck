# See the rules as written, one row each

The registry table is one row per check code, so a rule touching eight codes appears eight times and its own shape is lost. `--rules-table` prints the rules themselves -- name, action, how many codes each hits, what it matches -- which is what answers "what did this file actually say".

Level:    simple
Input:    the built-in demo frame and `examples/rules/error_overrides.yaml` (3 rules)
Expected: a rules table above the registry table; exit 0
