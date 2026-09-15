# A misspelled key in a rule

One mistake, one message.

Input:    `tests/failures/misspelled-key/rules.yaml`, whose rule says `codez:`
Expected: exit 1: `unknown key(s) codez` and the list of allowed keys -- a key that was silently ignored would be a setting that does nothing
