# B1 oracle

Reference spec: `reference/docs/specs/p0-conventions-and-spine.md`. It is not in the workspace.

`rubric.md` is the judge rubric for the /specify definition of done named in `task.yaml`. `evidence.md` records the fail-on-base and pass-on-reference unittest runs.

Hidden tests are `../tests/test_b1_hidden.py`, overlaid by the correctness grader (`runner: unittest`). They check that the spec file exists and that the required sections have bodies. They do not score the prose. The judge does.
