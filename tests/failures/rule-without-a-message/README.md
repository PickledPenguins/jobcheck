# A rule with no message

One mistake, one message.

Input:    `tests/failures/rule-without-a-message/rules.yaml`, a rule with every key but `message`
Expected: exit 2: `'message' must be the text saying why the rule exists` -- a rule nobody can justify is a rule nobody dares delete
