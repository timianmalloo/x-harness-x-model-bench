"""These fixture trees hold `test_*.py` files meant to be copied into a grading working copy and run there by
the formal grader's own pytest subprocess (bugs_confirmed, DR-FM2) -- never collected by this repo's own suite."""

collect_ignore_glob = ["**/test_*.py"]
