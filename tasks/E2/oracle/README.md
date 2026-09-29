# E2 Oracle

The oracle is Terminal-Bench 2.0's own `count-dataset-tokens` test, `tests/test_outputs.py`,
unmodified except the one native-path edit (`tasks/E2/README.md`): it asserts `answer.txt` (in the
grading copy's working directory) contains the substring `79586`, the correct total deepseek-token
count over the `deepseek_reasoning` and `deepseek_solution` fields of the science-domain
(chemistry, biology, physics) rows of `ryanmarten/OpenThoughts-1k-sample` (HuggingFace `metadata`
config, `train` split), tokenized with the `Qwen/Qwen2.5-1.5B-Instruct` tokenizer.

## Runner

`task.yaml`'s `oracle.command` invokes the pinned Python (3.13, matching the upstream
`python:3.13-slim-bookworm` base image) through `uv run --python 3.13` directly — never `cmd.exe` —
with forward-slash paths and a bare `--junitxml=e2.xml` report name:

```
uv run --python 3.13 --with pytest==8.4.1 pytest tests/test_outputs.py --junitxml=e2.xml -rA
```

`oracle.runner: pytest` is not yet dispatched by `src/harness_bench/grade/correctness.py`
(`grade()` recognises only `"unittest"` and `"dotnet"`; see `tasks/E2/README.md`). The proof in
`evidence.md` was therefore run directly with the command above (`cwd` = the grading copy's working
directory: the base workspace or the reference solution's working copy, with `tasks/E2/tests/`
overlaid, exactly as `grade/correctness.py`'s own `grade()` builds its grading copy for `unittest`
and `dotnet` today), not through `harness_bench.grade.correctness.grade`.

## Reference Solution

`oracle/reference/solve.sh` is the upstream `solution/solve.sh`, edited only for the same
native-path substitution (`tasks/E2/README.md`). It installs `datasets==4.0.0`,
`transformers==4.56.0` and `jinja2==3.1.6` (pinned, matching upstream), downloads the tokenizer and
dataset from HuggingFace (internet required, matching upstream's `allow_internet = true`), and
writes the token count to `answer.txt`.

## Verification

`oracle/evidence.md` records two runs of the exact `oracle.command` above, on this host:

1. against the base tree (`tasks/E2/workspace/`, empty — no `answer.txt` exists) — must fail;
2. against a working copy with `oracle/reference/solve.sh` run first (producing a correct
   `answer.txt`) — must pass.

An oracle that passes the base tree measures nothing (`new-bench-task` stage 5); this is the check
that rules that out.
