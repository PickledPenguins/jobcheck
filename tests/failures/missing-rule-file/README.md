# A rule file that is not there

One mistake, one message.

Input:    `no_such_file.yaml`
Expected: exit 1 with a `ValueError` naming the path and the absolute path it was resolved to
