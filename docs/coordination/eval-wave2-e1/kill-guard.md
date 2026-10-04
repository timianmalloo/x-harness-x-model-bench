---
id: brief-eval-kill-guard
title: "Brief KILL-GUARD: the PreToolUse guard refuses process kills by name or pattern (class PROC-A)"
type: plan
status: proposed
owner: "@timianmalloo"
links:
  - { to: coordination-eval-wave2-e1-briefs, rel: implements }
  - { to: defect-classes, rel: relates-to }
review-by: "2026-10-17"
summary: "tools/heredoc_guard.py gains a fourth verdict: a kill by process name, pattern or command line (Stop-Process -Name, a pipeline into Stop-Process, taskkill /IM or /FI, pkill, killall) is refused; a kill by PID passes. The hook is also wired for the PowerShell tool. Claude Sonnet, one short session."
---

# KILL-GUARD: no kill by name or pattern

**Session** `x-killg-e1e4` · **branch** `build/eval-kill-guard` · **harness** Claude Code Agent tool, `model: sonnet` (served `claude-sonnet-5-5`, R-91) · **budget** 40 calls · 60k · 1 session · 45 min · **fallback** a fresh Sonnet session from this brief.

**Why** (class **PROC-A**, `docs/lessons/defect-classes.md`): on 2026-10-03 X-F's F2 session ran a machine-wide `Stop-Process` on every process whose command line matched `pytest`. It killed three other worktrees' `mutate_check` runs and left their mutants applied. The README rule (E1 README §2) is the instruction; this hook makes the Claude Code form of it impossible. Codex, Agy and Grok workers are not covered by this hook (PROC-A's upgrade trigger).

## Owned paths
`tools/heredoc_guard.py` (a fourth verdict and its message), `tests/test_heredoc_guard.py` (new parametrized tests only), `.claude/settings.json` (one hunk: the same guard command under a `PowerShell` matcher beside the `Bash` one). `.claude/settings.json` is a binding file for every Claude worker: the Leader merges it and names it in the operator report.

## Work (red first; E1 README §2)
1. **Refuse** (exit 2, message starting `PROC-A:` and saying "kill only PIDs you started: Stop-Process -Id <pid>, taskkill /PID <pid>, kill <pid>"):
   - `Stop-Process -Name …`, `Stop-Process -ProcessName …`, `spps -Name …`;
   - any pipeline into `Stop-Process` or `spps` whose source is not `Get-Process -Id …` (for example `Get-Process python | Stop-Process`, `Get-CimInstance Win32_Process | Where-Object CommandLine -match pytest | ForEach-Object { Stop-Process -Id $_.ProcessId }`; the second shape is a pattern kill through a PID; refuse a `Stop-Process` inside a `ForEach-Object` fed by `Where-Object` on `CommandLine`, `Name` or `ProcessName`);
   - `Invoke-CimMethod … -MethodName Terminate` and `wmic process where … (delete|call terminate)`;
   - `taskkill` with `/IM` or `/FI`; `pkill`; `killall`.
2. **Pass:** `Stop-Process -Id 1234`, `Stop-Process -Id $proc.Id`, `taskkill /PID 1234 /T /F`, `kill 1234`, `kill $pid`, `Get-Process -Id 1234 | Stop-Process`, and any of the refused words inside a quoted argument (a commit message is data, as the CLN-C test shows).
3. **Wire PowerShell.** Add the guard under a `PowerShell` matcher. `assume:` the PowerShell tool's PreToolUse payload carries the command at `tool_input.command`, as Bash's does; confirm by a test that feeds a payload with `"tool_name": "PowerShell"` and, after the merge, by the Leader running `Stop-Process -Name notepad -WhatIf` in a fresh Claude Code session and seeing the refusal; if false, the PowerShell half is a no-op (the guard passes any payload it cannot read) and the report says so.
4. The existing verdicts (heredoc, pipe, force) are unchanged; every existing test passes untouched.

## Tests
- `test_a_kill_by_name_or_pattern_is_blocked` (parametrized over item 1's shapes, including the observed instance's shape: a command-line match on `pytest` piped to `Stop-Process`). Red first: the skeleton adds the `"kill"` message key only, so the test fails on `returncode == 2`.
- `test_a_kill_by_pid_passes` (item 2).
- `test_a_powershell_payload_is_read` (the PowerShell `tool_name`, a refused command, exit 2).
- A mutant in `tests/mutations/` for the guard if a set exists, else none (state which).

## Acceptance items
1. The three tests red then green (SHA, node, failing assertion).
2. `uv run pytest -q tests/test_heredoc_guard.py` green; the module docstring names PROC-A beside EDIT-B, E2E-E and CLN-C.
3. The report says whether item 3's `assume:` was confirmed or is left to the Leader's post-merge check.

## Exit
E1 README §3 join gate. Report per E1 README §4.
