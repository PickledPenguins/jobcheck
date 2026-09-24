# See the rules as written, one row each

The registry table is one row per check code, so a rule touching eight codes appears eight times and its own shape is lost. `--rules-table` prints the rules themselves -- name, action, how many codes each hits, what it matches -- which is what answers "what did this file actually say".

It is also where a rule that can never apply is reported. The shipped file shadows one on purpose, as the precedence demonstration: the narrow enable is listed before an unconditional disable of the same code, so the disable is the last match on every row and the enable never decides anything. Reversing the two is the shape that works, and reports nothing.

Level:    simple
Input:    the built-in demo frame and `examples/rules/error_overrides.yaml` (3 rules, one of them shadowed)
Expected: a rules table above the registry table, with a warning naming the shadowed rule; exit 0
