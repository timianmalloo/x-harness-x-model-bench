# E6 oracle evidence

Grading copy matches `src/harness_bench/grade/correctness.py`: the tree under test (`tasks/E6/workspace` or `oracle/reference` working copy), with `tasks/E6/tests/` overlaid, executed in its disposable working directory.

Oracle runner: `dotnet` (`src/harness_bench/grade/correctness.py`)
Command: `cmd /c run.cmd --logger trx;LogFileName=e6.trx`
Underlying execution: `dotnet test tests/E6.Tests.csproj -p:RestoreSources=. -p:NuGetAudit=false --logger trx;LogFileName=e6.trx` with the host NuGet global packages cache at `%USERPROFILE%\.nuget\packages` (or `NUGET_PACKAGES` when set).

Runner script: `tasks/E6/oracle/grade_e6.py`

## Fail on the base workspace

Grading call:
`correctness.grade(ws_base, task_dir, oracle, out_base, tmp, timeout=120.0)`

Result:
```python
Result(passed=0, partial_credit=Decimal('0'), reason=None, evidence='out_base/oracle.log')
```

Command:
```
cmd /c run.cmd --logger trx;LogFileName=e6.trx
```

Exit code: **1**

Summary from TRX / test runner:
`Failed!  - Failed: 42, Passed: 0, Skipped: 0, Total: 42, Duration: 32 ms - E6.Tests.dll (net10.0)`

All 42 tests failed with `System.NotImplementedException`:

1. `ProblemTests.Test_0_1_HasCloseElements`
2. `ProblemTests.Test_0_2_HasCloseElements`
3. `ProblemTests.Test_0_3_HasCloseElements`
4. `ProblemTests.Test_0_4_HasCloseElements`
5. `ProblemTests.Test_0_5_HasCloseElements`
6. `ProblemTests.Test_0_6_HasCloseElements`
7. `ProblemTests.Test_0_7_HasCloseElements`
8. `ProblemTests.Test_1_1_SeparateParenGroups`
9. `ProblemTests.Test_1_2_SeparateParenGroups`
10. `ProblemTests.Test_1_3_SeparateParenGroups`
11. `ProblemTests.Test_1_4_SeparateParenGroups`
12. `ProblemTests.Test_2_1_TruncateNumber`
13. `ProblemTests.Test_2_2_TruncateNumber`
14. `ProblemTests.Test_2_3_TruncateNumber`
15. `ProblemTests.Test_3_1_BelowZero`
16. `ProblemTests.Test_3_2_BelowZero`
17. `ProblemTests.Test_3_3_BelowZero`
18. `ProblemTests.Test_3_4_BelowZero`
19. `ProblemTests.Test_3_5_BelowZero`
20. `ProblemTests.Test_3_6_BelowZero`
21. `ProblemTests.Test_4_1_MeanAbsoluteDeviation`
22. `ProblemTests.Test_4_2_MeanAbsoluteDeviation`
23. `ProblemTests.Test_4_3_MeanAbsoluteDeviation`
24. `ProblemTests.Test_5_1_Intersperse`
25. `ProblemTests.Test_5_2_Intersperse`
26. `ProblemTests.Test_5_3_Intersperse`
27. `ProblemTests.Test_6_1_ParseNestedParens`
28. `ProblemTests.Test_6_2_ParseNestedParens`
29. `ProblemTests.Test_6_3_ParseNestedParens`
30. `ProblemTests.Test_7_1_FilterBySubstring`
31. `ProblemTests.Test_7_2_FilterBySubstring`
32. `ProblemTests.Test_7_3_FilterBySubstring`
33. `ProblemTests.Test_7_4_FilterBySubstring`
34. `ProblemTests.Test_8_1_SumProduct`
35. `ProblemTests.Test_8_2_SumProduct`
36. `ProblemTests.Test_8_3_SumProduct`
37. `ProblemTests.Test_8_4_SumProduct`
38. `ProblemTests.Test_8_5_SumProduct`
39. `ProblemTests.Test_9_1_RollingMax`
40. `ProblemTests.Test_9_2_RollingMax`
41. `ProblemTests.Test_9_3_RollingMax`
42. `ProblemTests.Test_9_4_RollingMax`

## Pass on the reference solution

Grading call:
`correctness.grade(ref_ws, task_dir, oracle, out_ref, tmp, timeout=120.0)`

Result:
```python
Result(passed=1, partial_credit=Decimal('1'), reason=None, evidence='out_ref/oracle.log')
```

Command:
```
cmd /c run.cmd --logger trx;LogFileName=e6.trx
```

Exit code: **0**

Summary from TRX / test runner:
`Passed!  - Failed: 0, Passed: 42, Skipped: 0, Total: 42, Duration: 28 ms - E6.Tests.dll (net10.0)`

No failing tests. 42 / 42 passed (100% partial credit, passed=1).

## Validate

- `uv run bench validate`: exit code 0 (`ok: bom, metrics, example matrix and every task folder are valid`)
- `uv run pytest -q -p no:cacheprovider`: exit code 0 (852 passed, 1 skipped, 8 deselected)
- `uv run ruff check src tests tools`: exit code 0 (`All checks passed!`)
