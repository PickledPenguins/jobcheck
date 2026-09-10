"""The example checks: two suites plus an always-on base check.

Deliberately *outside* the package. They demonstrate the framework and drive the
checks; they are not part of what installs, so nothing here can end up registered
in someone else's registry.

Load them the way an adopter loads their own::

    load_suites(["hard_checks", "soft_checks"], package="example_suites")
"""
