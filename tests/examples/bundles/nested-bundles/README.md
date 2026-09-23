# A bundle inside a bundle, with a prerequisite across the two

Nesting is not limited to one level, and the dependency graph is validated once
the outermost call returns -- so `TOTAL_IS_A_NUMBER`, registered by the inner
bundle, may depend on `TOTAL_PRESENT`, which the outer bundle loads.

The check files live in this directory rather than under `examples/`: they exist
to be collected by a bundle, and putting them beside it is what makes the
`base_dir` the bundles use readable.

Level:    moderate
Input:    `tests/examples/bundles/nested-bundles/outer_bundle.py`, which loads one check file and one more bundle
Expected: four loaded files -- the two check files, the inner bundle, then the outer one -- and both checks registered, the dependent on layer 1; exit 0
