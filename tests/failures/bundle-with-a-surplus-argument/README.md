# A second path handed to the bundle entry point

A bundle is one file that names the rest, so this entry point takes one path. A second argument used to be dropped silently, leaving a user who meant to load two bundles with a run that quietly loaded one. It is an error now, and the same parser is what makes `--help` answer rather than be read as a path.

Input:    two bundle paths on one command line
Expected: argparse names the unrecognized argument; nothing is loaded; exit 2
