# E6 — HumanEval-C# batch of 10

**Status: ready.** `prompt.md`, pinned source, `workspace/`, hidden xUnit tests, and an oracle that fails on the base tree and passes on `oracle/reference/` are all present. `uv run bench validate` accepts the folder.

## Upstream Problems

The 10 problems are drawn from MultiPL-E at commit `3025a531af7450e7df8b96fe0440e9804480bbad`, translated from OpenAI HumanEval into C#:

| Index | Upstream ID | Original Name | C# Method Signature | Assertions |
| --- | --- | --- | --- | --- |
| 1 | `HumanEval/0` | `HumanEval_0_has_close_elements` | `public static bool HasCloseElements(List<float> numbers, float threshold)` | 7 |
| 2 | `HumanEval/1` | `HumanEval_1_separate_paren_groups` | `public static List<string> SeparateParenGroups(string paren_string)` | 4 |
| 3 | `HumanEval/2` | `HumanEval_2_truncate_number` | `public static float TruncateNumber(float number)` | 3 |
| 4 | `HumanEval/3` | `HumanEval_3_below_zero` | `public static bool BelowZero(List<long> operations)` | 6 |
| 5 | `HumanEval/4` | `HumanEval_4_mean_absolute_deviation` | `public static float MeanAbsoluteDeviation(List<float> numbers)` | 3 |
| 6 | `HumanEval/5` | `HumanEval_5_intersperse` | `public static List<long> Intersperse(List<long> numbers, long delimeter)` | 3 |
| 7 | `HumanEval/6` | `HumanEval_6_parse_nested_parens` | `public static List<long> ParseNestedParens(string paren_string)` | 3 |
| 8 | `HumanEval/7` | `HumanEval_7_filter_by_substring` | `public static List<string> FilterBySubstring(List<string> strings, string substring)` | 4 |
| 9 | `HumanEval/8` | `HumanEval_8_sum_product` | `public static Tuple<long, long> SumProduct(List<long> numbers)` | 5 |
| 10 | `HumanEval/9` | `HumanEval_9_rolling_max` | `public static List<long> RollingMax(List<long> numbers)` | 4 |

Total upstream assertions ported to xUnit tests: **42**.

## Source Pin

- `repo`: `https://github.com/nuprl/MultiPL-E`
- `commit`: `3025a531af7450e7df8b96fe0440e9804480bbad` (full SHA verified via `git ls-remote` for `3025a53`)

## Licence

MultiPL-E is licensed under the BSD 3-Clause License with Machine Learning Restriction:
- `license`: `BSD 3-Clause License with Machine Learning Restriction`
- `copyright`: `Copyright (c) 2022, Northeastern University, Oberlin College, Roblox Inc, Stevens Institute of Technology, University of Massachusetts Amherst, and Wellesley College.`
- Full license text copied to `tasks/E6/LICENSE`.
- HumanEval inheritance: MultiPL-E does not separately state an in-tree license for the HumanEval dataset problems it translates. Upstream OpenAI HumanEval was published under the MIT license.

## Workspace & Tests Architecture

- `workspace/`: holds `E6.csproj` (a .NET 10.0 class library) and `Problem.cs` containing the 10 static method stubs throwing `NotImplementedException`. In accordance with US-8, no test code exists in the workspace.
- `tests/`: holds an xUnit test project `tests/E6.Tests.csproj` referencing `../E6.csproj`, with 42 `[Fact]` test methods in `tests/ProblemTests.cs` (one test per upstream assertion).
- `oracle/`: holds `reference/Problem.cs` with the passing implementation, `grade_e6.py` for verification, and `evidence.md` with execution proofs.
