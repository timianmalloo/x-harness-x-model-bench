# Reported bugs

## double-claim-before-release

The lease fold accepts a second `claim` with no intervening `release`, so `AtMostOneHolder`
can be violated with no detection.

Test: tests/test_bug.py::test_at_most_one_holder
