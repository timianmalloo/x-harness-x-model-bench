# Hooks — the controls that run at the tool seam

Native ownership is an explicit project opt-in. `coord hook --config --host
claude|codex|copilot|grok|agy` emits a reviewable entry; it changes no settings or trust.
Grok can keep it in a separate `.grok/hooks/coord-ownership.json`. Agy uses a local
`ownership-guard` named section; both sync and installer refresh source-managed names
while preserving project-owned names, and reject malformed current JSON without overwrite.
Fresh pack installations do not enable ownership guards automatically.

The separate Codex Stop entry requires its own native review; approving apply_patch
does not approve Stop. Stop facts in the existing coordination log record the script's
requested refusal, allowed closure or bounded loop guard, with no request bodies.
They do not alone prove the host honored that response. Grok1.0.34 advertises blocking
Stop metadata although its current web documentation calls Stop passive; qualify the
actual host. Regardless of native continuation limits, the runner refuses final readiness
for open or unreadable worker Owner decisions after verifying independent work receipts.

Agy ownership success returns no permission override. Its `TargetFile` must be absolute:
the observed hook cwd is the workspace's `.agents` directory. Relative targets fail closed.
The native file-edit mode and the ownership guard are separate policy layers.

Prose that says "check whether you already have it" is a memoir (`continuous-improvement.md` CI6). The
hooks here are the same rule as a **control**: a host runs them at a fixed lifecycle point regardless
of what the model decides.

| File | Host | Deploys to | Purpose |
|---|---|---|---|
| `reread-guard.py` | Claude Code, Copilot CLI, Grok Build, Antigravity | `docs/ai-forward-pack/hooks/reread-guard.py` | Counts identical reads per turn; on the third, and on any paged tool output viewed whole, adds a warning to the model's context. Warns, never blocks (a real third read exists). Fail-open on every error path. `--host claude\|copilot\|grok\|agy`. |
| `copilot.ai-forward-hooks.json` | Copilot CLI | `.github/hooks/ai-forward.json` | Copilot's hook config (`version: 1`, camelCase events, `bash`/`powershell` per platform, `timeoutSec`). Loaded from the repo automatically. Personal alternative: `~/.copilot/hooks/`. |
| `grok.ai-forward-hooks.json` | Grok Build | `.grok/hooks/ai-forward.json` | Grok's hook config (PascalCase events, `matcher: Read` which aliases to `read_file`). Project hooks require folder trust (`/hooks-trust` or `--trust`). |
| `agy.ai-forward-hooks.json` | Antigravity (`agy`) | `.agents/hooks.json` | Antigravity hook config: five named sections — `reread-guard` (`PreToolUse`, matcher `view_file`), `session-start` and `mail-doorbell` (`PreInvocation`), `heartbeat` (`PostToolUse` under a `matcher: ""` + `hooks` wrapper, and `Stop`), `owner-review-gate` (`Stop`). Shape per event follows the host's docs: tool events need the wrapper, lifecycle events take handlers directly. **Correction to revision 83:** `enabled` defaults to true, so the missing flag was not why nothing fired in the S1 session; the causes were the bare `PostToolUse` handler (loaded, never fired), the doorbell's string `injectSteps` (rejected by protojson), and a session that hung inside its ack command before any `Stop`. Headless probes on 2026-09-20 showed `PreInvocation` (run-start marker) and `Stop` (heartbeat rows) firing once the folder was a registered project (`--new-project` or `--add-dir`); a plain `agy -p` in an unregistered folder loaded only the user-level file. |
| `coord_identity.py` | Claude Code, Copilot CLI, Grok Build, Antigravity | `docs/ai-forward-pack/hooks/coord_identity.py` | Shared identity validator for the hook layer: parent `$AGENT_SESSION` must match `[A-Za-z0-9_.-]` in the bounded hook length, and Copilot child events derive one canonical id from the native session/agent pair only when both parts are valid and bounded. Invalid ids are refused silently with no writes; ids are never truncated into collisions. |
| `session-start.py` | Claude Code, Copilot CLI, Grok Build, Antigravity | `docs/ai-forward-pack/hooks/session-start.py` | Runs on session start (`SessionStart`/`SubagentStart`, Copilot `sessionStart`, or `PreInvocation` invocationNum 1): records the audit start marker at the session seam (`audit-log.py start`, keyed to `$AGENT_SESSION` when the harness environment carries it, else a harness slot an `append` uses only when it has no marker of its own — `duration_source: session-start-hook`). Copilot child events never reuse the parent's `$AGENT_SESSION`; if a stable native child id is absent, Copilot `subagentStart` is a no-op rather than guessing from `agentName`. Prints nothing; exits 0 on every path. Closes DC-190. |
| `mail-doorbell.py` | Claude Code, Copilot CLI, Grok Build, Antigravity | `docs/ai-forward-pack/hooks/mail-doorbell.py` | The message layer's doorbell (design-message-layer section 8): folds the caller's inbox (`$AGENT_SESSION`) and, when unacknowledged mail newer than five minutes exists, emits a **count and a pointer, never a body** in the host's shape - Claude/Grok `additionalContext` at `PreToolUse`/`UserPromptSubmit`, Antigravity `injectSteps` at `PreInvocation`, Copilot `additionalContext` at `preToolUse` and `decision: block` + `reason` at `agentStop`/`subagentStop` (only when count > 0 and `stop_hook_active` is unset). Copilot child events derive the same canonical child identity as the other hooks instead of reusing the parent's `$AGENT_SESSION`. When Copilot also loads `.claude/settings.json`, the Claude-form invocation is skipped to avoid duplicate doorbells. The inbox is truth; the doorbell is a hint. Exits 0 and prints nothing on every other path. Per-harness execution status: `.agents/harness-status.json` (`verified` only when executed on this machine). |
| `owner-review-gate.py` | Claude Code, Grok Build, Copilot CLI (Antigravity: unsupported) | `docs/ai-forward-pack/hooks/owner-review-gate.py` | The Owner review gate (design-owner-review, D6): at the **stop seam** it resolves the session to `$AGENT_SESSION`, reads P1's request store through P1's reader, and refuses the stop when that session still holds an unresolved **decision request it sent** — Claude/Grok `Stop`/`SubagentStop`: **exit 2** with one reason line on stderr (count + ids, never a body); Copilot `agentStop`/`subagentStop`: `{"decision":"block","reason":…}` with exit 0. Copilot child events derive the same canonical child identity as the other hooks instead of reusing the parent's `$AGENT_SESSION`; duplicate Claude-form invocations are skipped when Copilot also loads `.claude/settings.json`. Exits 0 and prints nothing on every path it cannot evaluate (no `AGENT_SESSION`, non-JSON stdin, `stop_hook_active`, no store, malformed store, `COORD_ROOT` outside the repo). Per-host status below. |
| `heartbeat.py` | Claude Code, Copilot CLI, Grok Build, Antigravity | `docs/ai-forward-pack/hooks/heartbeat.py` | The progress heartbeat (spec-liveness-and-track, D7): on every tool call (`PostToolUse` on Claude Code and Antigravity, Claude-format `PreToolUse` on Grok, Copilot `postToolUse`) it adds one call and any file a write-class tool named to a machine-local accumulator in the git common dir; at most once per 100 s (D13's renew cadence) - or on the stop-class event (`Stop` / `agentStop` / `subagentStop`) - it writes ONE `kind: heartbeat` row with the deltas (calls, distinct files, tokens `not recorded`) into `$AGENT_SESSION`'s ledger via `coord-core.py heartbeat_tick`. A zero-delta row on Stop is deliberate: `coord track` renders it `stalled`, never `live`. A beat from the session holding `refs/coord/leader` renews the designation (F-1). Copilot child events derive the same canonical child identity as the other hooks instead of reusing the parent's `$AGENT_SESSION`; duplicate Claude-form invocations are skipped when Copilot also loads `.claude/settings.json`. Counts, never paths; prints nothing; exits 0 on every path. Claude Code executed here against the documented contract; Grok, Antigravity and Copilot are **observed-only** until a live session shows the event fire (CO12). |
| `claude-code.settings.hooks.json` | Claude Code | merge into `.claude/settings.json` | The `hooks` object for `PreToolUse` (matcher `Read` for the guard; unmatched for the doorbell), `UserPromptSubmit`, `SessionStart`, `SubagentStart`, and (P3) `PostToolUse` + `Stop` for the heartbeat. Committed project settings run in sub-agents too. |

**Stop-class events per host (the owner review gate).** A host is `enforced` only once a live session
has shown the hook refuse a stop here (CO12); until then it is `observed-only`, and a host with no
stop event is `unsupported`.

| Host | Event | Block form | Status (2026-09-19) |
|---|---|---|---|
| Claude Code | `Stop`, `SubagentStop` | exit 2, reason on stderr | **enforced** — 2026-09-19, Claude Code 2.1.278: a headless `claude -p` session in a linked worktree with an open decision request had its stop refused; the model reported the refusal and touched nothing (Ruling 2 in `docs/notes/rulings.md`) |
| Grok Build | `Stop` (Claude-format hooks) | exit 2, reason on stderr | observed-only — the S1 Grok session reported "refused stop: not seen" while its decision request was open |
| Copilot CLI | `agentStop`, `subagentStop` | exit 0 + `{"decision":"block","reason"}` | observed-only |
| Antigravity | `Stop` (handlers directly under the key; payload `executionNum`, `terminationReason`, `fullyIdle`) | exit 0 + `{"decision":"continue"}` on stdout, at most twice per stop sequence, reason on stderr | **enforced** — 2026-09-20, 1.2.7: a headless session with an open decision request reported "Termination was blocked … has an unresolved decision request that must be ruled or expired before stopping" twice, then stopped (Ruling 5) |

**Codex push.** `codex queue --thread <id> --message <pointer>` **verified** — 2026-09-20, codex-cli 0.155.1: two pointers queued by the coordinator arrived in the operator's Codex thread as user-role turns and are quoted verbatim in `note-20260920-s1-codex-coordination-surface`; the first ("run mail read --ack") produced exactly that and a stop, the second ("then execute the brief") completed the track — the pointer must name the action after the read.

**Heartbeat per host.** Claude Code **enforced** — 2026-09-19, 2.1.278: host-fired `PostToolUse` and `Stop` rows in the session ledger, the first Stop carrying `calls: 3` for a three-call turn, in an interactive session and again headless. Grok Build **enforced** — 2026-09-20, Grok Build 1.0.34: a host-fired `PreToolUse` heartbeat row with `"host": "grok"` in `.agents/log/s1-grok.jsonl` during the S1 three-harness test (`note-20260920-s1-grok-hooks-surface-freshness`). Antigravity **enforced** — 2026-09-20, 1.2.7: headless probes wrote `Stop` rows with `calls 2` once the `PostToolUse` handler took the documented `matcher`/`hooks` form (the S1 session's rows were absent because the handler was in the direct form). Copilot CLI stays observed-only. `coord mail dispatch --harness claude-code` **verified** the same day (`.agents/harness-status.json`, machine-local).

**Contracts these are written to** (established from the hosts' own documentation and a captured event
stream, not assumed — class RIG-D): Claude Code hooks receive `{"hook_event_name","session_id",
"tool_name","tool_input"}` on stdin, and exit 0 with `hookSpecificOutput.systemMessage` to warn (exit 2
would block). Copilot CLI hooks receive `{"sessionId","toolName","toolArgs"}` and return
`{"additionalContext": …}`; on `preToolUse` any non-zero exit other than 2 **denies** the call, so the
guard exits 0 on every path including its own failures.

**Interpreter (Windows and macOS).** The Claude Code, Grok Build and Antigravity commands resolve the
interpreter **at run time**: `py=$(python3 -c 'import sys;print(sys.executable)' 2>/dev/null); [ -x "$py" ] || py=$(python -c …); "$py" <script>`.
`python3` wins where it is real Python (Linux, macOS); on python.org Windows `python3` is a Store alias
that exits 9009 without printing a path, so the fallback `python` is taken. Nothing machine-specific is
written into the tracked config (class PLAT-B), and no one edits the command per machine (class
PLAT-A). Cost: one extra interpreter start (~25 ms) per hook. The form needs a POSIX `sh`, which
Claude Code uses on every platform (Git Bash on Windows); for Grok Build and Antigravity on Windows it is
**observed-only** until a live session shows the hook firing there — the Antigravity command additionally
anchors the script at `$(git rev-parse --show-toplevel)` because its hook cwd is not documented. The
Copilot config keeps its `bash`/`powershell` arms, which are the same resolution done by the host.

Measured origin: the profiled TheTerrace session viewed `public.html` four times in three minutes,
a 43 KB paged output whole twice, and one sub-agent read the same mockup six times — none of it errored.
