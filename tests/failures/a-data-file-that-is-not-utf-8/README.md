# A file that is not UTF-8

A spreadsheet saved as Latin-1 is the usual way one arrives. One mistake, one message, and no traceback.

Input:    a Latin-1 file with an accented name
Expected: exit 2 naming the path and the byte that is not UTF-8
