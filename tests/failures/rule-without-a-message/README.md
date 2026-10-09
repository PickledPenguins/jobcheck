# A rule with no message

One mistake, one message.

Input:    `tests/failures/rule-without-a-message/rules.yaml`, a rule with every key but `message`
Expected: exit 2: `'message' must be a non-empty string`
