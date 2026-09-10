# A rule naming a code that does not exist

One mistake, one message.

Input:    a rule file naming `NO_SUCH_CODE`
Expected: exit 1: a rule that can never apply is an error, not a no-op
