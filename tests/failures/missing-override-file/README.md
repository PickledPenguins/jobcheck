# Override file path does not exist

Input:    `python3 examples/main.py -o no_such_file.yaml`
Expected: stderr a FileNotFoundError naming the path; exit 1
