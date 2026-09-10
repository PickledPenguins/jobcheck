# Showing columns from the data next to the row key

`--data-columns` copies fields from the frame into the report, in the order
given, immediately after the key. They carry the context needed to judge a
failure without going back to the source file.

Input:    `python3 examples/main.py --data-columns source_system record_type --report table`
Expected: the failure table with source_system and record_type after `row`; exit 0
