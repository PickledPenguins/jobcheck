# Pattern is not a valid regular expression

Input:    `python3 examples/main.py -o tests/failures/invalid-regex/rules.yaml`
Expected: stderr `invalid regex '([unclosed' for column 'email': unterminated character set at position 1`; exit 1
