"""The example tests: two suites plus an always-on base test.

Deliberately *outside* the package. They demonstrate the framework and drive the
tests; they are not part of what installs, so nothing here can end up registered
in someone else's registry.

Load them the way an adopter loads their own::

    load_suites(["hard_tests", "soft_tests"], package="example_suites")
"""
