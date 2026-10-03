--------------------------- MODULE run_lifecycle ---------------------------
(***************************************************************************)
(* The lifecycle of one harness-bench run (spec US-44; ADR-0006, ADR-0007). *)
(* Version 6 (native cells and R-21 cancel grace, ADR-0013; turns and turn   *)
(* snapshots, ADR-0015 section 7; crash-atomic archive writes, ADR-0015 5a;  *)
(* resume, ADR-0021 sections 2, 4 and 9: W1-K settled the two branches W1-J  *)
(* left provisional, the `BetweenSnapped` redo and the final ELSE of         *)
(* `ClassOf`, by the recorded `next` of each turn; R-100: a resume after a    *)
(* stop finishes the stop, so the invariant is NoLaunchAfterStop).          *)
(*                                                                         *)
(* One run engine process that can crash and be resumed; cells (each a    *)
(* native process tree in its own Job Object, `proc`) that can fail on    *)
(* their own and die asynchronously after a kill; a write-ahead intent    *)
(* log; a prompt_sent record that a worker queues and the engine persists *)
(* before the prompt goes out; kill first, record the outcome after the   *)
(* cell's process tree is gone; a control                                 *)
(* mailbox (stop, a decision answer); one decision request with a timeout; *)
(* archive-then-delete; and grading passes that the engine and a          *)
(* concurrent `bench grade` process run under a mutual-exclusion lock.    *)
(*                                                                         *)
(* BUG selects one seeded defect ("none" for the real design). Every       *)
(* invariant and property below has a variant that TLC must reject;       *)
(* tools/check_models.py asserts both directions.                          *)
(*                                                                         *)
(* The model lets a cell outlive an engine crash. With the Job Object's    *)
(* kill-on-close it cannot, so the checked behaviours are a superset of    *)
(* the engine's, and every safety result carries over.                     *)
(***************************************************************************)
EXTENDS Naturals, FiniteSets, TLC

CONSTANTS
    Cells,          \* the plan's cells
    Parallelism,    \* at most this many cells run at once
    MaxCrashes,     \* engine crashes explored
    Passes,         \* grading pass ids (each process mints its own)
    Graders,        \* processes that may grade: {"engine"} or {"engine", "bench"}
    NumTurns,       \* user turns per cell: 1, or 2 (ADR-0015 bounds a task to two turns)
    BUG             \* "none" or one seeded defect name

ASSUME Parallelism \in Nat \ {0}
ASSUME "engine" \in Graders /\ Graders \subseteq {"engine", "bench"}
ASSUME NumTurns \in 1..2

Controls   == {"stop", "answer"}
Outcomes   == {"none", "done", "timedout", "failed", "stopped", "crashfail", "crashbetween"}
Turns      == 1..NumTurns
NoCopy     == NumTurns            \* copying[c] when no copy is in progress (outside Arts)
Arts       == 0..(NumTurns - 1)   \* archive artifacts: 0 is the final archive, k is the turn-k snapshot
Reasons    == {"none", "timeout", "stop"}
NextKinds  == {"none", "snapshot", "final", "stop"}

VARIABLES
    engine,         \* "up" | "down"
    crashes,
    reconciling,    \* after a resume: no launch until reconciliation completes
    reconciled,     \* active cells reconciled in this incarnation
    intent,         \* [cell -> BOOLEAN]  ledger: cell.launch_intent
    launchEpoch,    \* [cell -> Nat]      incarnation that created the proc
    epoch,          \* engine incarnation
    proc,      \* [cell -> {"none","running","exited"}]  physical
    killRequested,  \* [cell -> BOOLEAN]  cancel requested, not yet confirmed
    killReason,     \* [cell -> Reasons]  why the engine killed it (process memory)
    grace,          \* [cell -> BOOLEAN]  cancel sent; TerminateJobObject not yet issued
    queued,         \* [cell -> 0..NumTurns] the turn whose prompt_sent the worker queued, not yet persisted (volatile; 0 none)
    promptSent,     \* [cell -> [turn -> BOOLEAN]]  ledger: cell.prompt_sent{turn} (fsynced, then acked to the worker)
    pendingSend,    \* [cell -> 0..NumTurns] the turn whose ack the worker holds and will send once (volatile; 0 none)
    prompts,        \* [cell -> [turn -> Nat]]  physical prompts delivered (history)
    turnEnded,      \* [cell -> [turn -> BOOLEAN]]  ledger: cell.turn_ended{turn}
    turnNext,       \* [cell -> [turn -> NextKinds]]  ledger: cell.turn_ended{turn}.next, the engine's decision (W0 rev 6.5)
    snapEv,         \* [cell -> [turn -> BOOLEAN]]  ledger: cell.turn_snapshot_archived{turn}
    copying,        \* [cell -> artifact | NoCopy]  the copy in progress on this incarnation (volatile)
    tmp,            \* [cell -> [artifact -> {"none","partial"}]]  a temporary sibling folder being filled
    fin,            \* [cell -> [artifact -> {"none","partial","complete"}]]  the final folder name on disk
    outcome,        \* [cell -> Outcomes] ledger: execution outcome
    wasStopped,     \* [cell -> BOOLEAN]  history: an outcome "stopped" was ever recorded
    archived,       \* [cell -> BOOLEAN]
    deleted,        \* [cell -> BOOLEAN]  workspace deleted
    controlFile,    \* [Controls -> BOOLEAN]
    controlApplied, \* [Controls -> BOOLEAN] ledger: control.applied{uuid}
    applyCount,     \* [Controls -> Nat]  history
    stopApplied,
    decision,       \* "none" | "open" | "resolved"
    resolutions,    \* history
    lock,           \* grade.lock holder: "free" | "engine" | "bench"
    passState,      \* [Passes -> {"idle","active","done","abandoned"}]
    passOwner,      \* [Passes -> {"none","engine","bench"}]
    graded,         \* [Passes -> SUBSET Cells]
    gradeCount,     \* [Passes -> [Cells -> Nat]]  history
    flags           \* history of forbidden events

tvars == <<turnEnded, turnNext, snapEv, copying, tmp, fin>>

vars == <<tvars, engine, crashes, reconciling, reconciled, intent, launchEpoch, epoch, proc,
          killRequested, killReason, grace, queued, promptSent, pendingSend, prompts, outcome,
          wasStopped, archived, deleted, controlFile, controlApplied, applyCount, stopApplied,
          decision, resolutions, lock, passState, passOwner, graded, gradeCount, flags>>

FlagNames == {"launchAfterStop", "launchWhileOpen", "gradeUnarchived", "archiveLive",
              "promptAfterOutcome", "launchBesideOrphan", "crashUnderStop"}

-----------------------------------------------------------------------------
Active(c)  == intent[c] /\ outcome[c] = "none"
Running    == {c \in Cells : proc[c] = "running"}
OrphanRunning == \E d \in Cells : proc[d] = "running" /\ launchEpoch[d] < epoch
Flag(f)    == flags' = [flags EXCEPT ![f] = TRUE]
Record(c, o) ==
    /\ outcome' = [outcome EXCEPT ![c] = o]
    /\ wasStopped' = [wasStopped EXCEPT ![c] = (@ \/ o = "stopped")]

AnyPrompted(c) == \E k \in Turns : promptSent[c][k]
\* A turn is in flight: its prompt went out, it has not ended, and the adapter is running.
InFlight(c) == \E k \in Turns : prompts[c][k] >= 1 /\ ~turnEnded[c][k] /\ proc[c] = "running"
\* ADR-0015 section 6 and ADR-0021 section 4: how resume classifies a prompted, non-terminal cell.
CrashedTurn(c) == \E k \in Turns : promptSent[c][k] /\ ~turnEnded[c][k]
\* ADR-0021 section 4, settled by W1-K. A cell is between turns only when the engine's recorded decision at turn k's end
\* was `snapshot` (a turn k+1 was to follow) and no prompt_sent{k+1} exists. A turn that ended with next = stop or final
\* is not between turns: no snapshot was taken and no turn k+1 was owed, so the class is crashfail, the final ELSE.
\* The ELSE therefore means one shape: every planned turn ended (or a turn ended with next = stop) and the outcome was
\* never recorded. It stays crashfail and is never read as "done" (the outcome needs exit status and extraction,
\* which a resume cannot recompute without guessing).
BetweenTurns(c) == \E k \in 1..(NumTurns - 1) : turnEnded[c][k] /\ (BUG = "between_ignores_next" \/ turnNext[c][k] = "snapshot")
                                               /\ ~promptSent[c][k + 1]
ClassOf(c) == IF CrashedTurn(c) THEN "crashfail" ELSE IF BetweenTurns(c) THEN "crashbetween" ELSE "crashfail"
\* The ledger holds the snapshot event of every turn the cell is waiting between (ADR-0021 section 4, snapshot row:
\* redo the copy first). Stated from the real predicate, so the seeded `between_ignores_next` reaches ClassOf alone.
BetweenSnapped(c) == \A k \in 1..(NumTurns - 1) :
                       (turnEnded[c][k] /\ turnNext[c][k] = "snapshot" /\ ~promptSent[c][k + 1]) => snapEv[c][k]

Init ==
    /\ engine = "up" /\ crashes = 0 /\ epoch = 1
    /\ reconciling = FALSE /\ reconciled = {}
    /\ intent = [c \in Cells |-> FALSE]
    /\ launchEpoch = [c \in Cells |-> 0]
    /\ proc = [c \in Cells |-> "none"]
    /\ killRequested = [c \in Cells |-> FALSE]
    /\ killReason = [c \in Cells |-> "none"]
    /\ grace = [c \in Cells |-> FALSE]
    /\ queued = [c \in Cells |-> 0]
    /\ promptSent = [c \in Cells |-> [k \in Turns |-> FALSE]]
    /\ pendingSend = [c \in Cells |-> 0]
    /\ prompts = [c \in Cells |-> [k \in Turns |-> 0]]
    /\ turnEnded = [c \in Cells |-> [k \in Turns |-> FALSE]]
    /\ turnNext = [c \in Cells |-> [k \in Turns |-> "none"]]
    /\ snapEv = [c \in Cells |-> [k \in Turns |-> FALSE]]
    /\ copying = [c \in Cells |-> NoCopy]
    /\ tmp = [c \in Cells |-> [a \in Arts |-> "none"]]
    /\ fin = [c \in Cells |-> [a \in Arts |-> "none"]]
    /\ outcome = [c \in Cells |-> "none"]
    /\ wasStopped = [c \in Cells |-> FALSE]
    /\ archived = [c \in Cells |-> FALSE]
    /\ deleted = [c \in Cells |-> FALSE]
    /\ controlFile = [k \in Controls |-> FALSE]
    /\ controlApplied = [k \in Controls |-> FALSE]
    /\ applyCount = [k \in Controls |-> 0]
    /\ stopApplied = FALSE
    /\ decision = "none" /\ resolutions = 0
    /\ lock = "free"
    /\ passState = [p \in Passes |-> "idle"]
    /\ passOwner = [p \in Passes |-> "none"]
    /\ graded = [p \in Passes |-> {}]
    /\ gradeCount = [p \in Passes |-> [c \in Cells |-> 0]]
    /\ flags = [f \in FlagNames |-> FALSE]

EngineReady == engine = "up" /\ ~reconciling

-----------------------------------------------------------------------------
(* Launch: intent -> proc -> prompt_sent queued -> persisted + acked -> prompt *)

WriteIntent(c) ==
    /\ EngineReady
    /\ ~intent[c] /\ outcome[c] = "none"
    /\ (BUG = "launch_after_stop" \/ ~stopApplied)
    /\ (BUG = "launch_while_open" \/ decision # "open")
    /\ intent' = [intent EXCEPT ![c] = TRUE]
    /\ IF stopApplied THEN Flag("launchAfterStop")
       ELSE IF decision = "open" THEN Flag("launchWhileOpen") ELSE UNCHANGED flags
    /\ UNCHANGED <<tvars, engine, crashes, reconciling, reconciled, launchEpoch, epoch, proc,
                   killRequested, killReason, queued, promptSent, pendingSend, prompts, outcome,
                   wasStopped, archived, deleted, controlFile, controlApplied, applyCount,
                   stopApplied, decision, resolutions, lock, passState, passOwner, graded,
                   gradeCount, grace>>

StartCell(c) ==
    /\ EngineReady
    /\ intent[c] /\ (BUG = "resend_turn_on_resume" \/ ~promptSent[c][1])
    /\ (BUG = "launch_after_outcome" \/ outcome[c] = "none")
    /\ (proc[c] = "none" \/ (BUG = "launch_after_outcome" /\ proc[c] = "exited"))
    /\ (BUG \in {"launch_after_stop", "stop_resume_launches"} \/ ~stopApplied)
    \* Parallelism is enforced where a proc starts, counting every running proc,
    \* including one that was killed and has not yet exited (the slot is held until confirmed).
    /\ (BUG = "exceed_parallelism" \/ Cardinality(Running) < Parallelism)
    /\ proc' = [proc EXCEPT ![c] = "running"]
    /\ launchEpoch' = [launchEpoch EXCEPT ![c] = epoch]
    /\ IF stopApplied THEN Flag("launchAfterStop")
       ELSE IF OrphanRunning THEN Flag("launchBesideOrphan") ELSE UNCHANGED flags
    /\ UNCHANGED <<tvars, engine, crashes, reconciling, reconciled, intent, epoch, killRequested,
                   killReason, queued, promptSent, pendingSend, prompts, outcome, wasStopped,
                   archived, deleted, controlFile, controlApplied, applyCount, stopApplied,
                   decision, resolutions, lock, passState, passOwner, graded, gradeCount, grace>>

\* The proc could not be created (image or create failure): recorded, never prompted.
StartFails(c) ==
    /\ EngineReady
    /\ Active(c) /\ proc[c] = "none" /\ ~AnyPrompted(c) /\ queued[c] = 0
    /\ Record(c, "failed")
    /\ UNCHANGED <<tvars, engine, crashes, reconciling, reconciled, intent, launchEpoch, epoch,
                   proc, killRequested, killReason, queued, promptSent, pendingSend,
                   prompts, archived, deleted, controlFile, controlApplied, applyCount,
                   stopApplied, decision, resolutions, lock, passState, passOwner, graded,
                   gradeCount, flags, grace>>

\* The worker queues prompt_sent{k} for the engine thread (volatile until persisted). Turn k > 1 waits for
\* turn k-1 to have ended and for its snapshot event to be durable (ADR-0015 section 2 (d)).
QueuePromptSent(c, k) ==
    /\ EngineReady
    /\ proc[c] = "running" /\ ~killRequested[c]
    /\ (BUG = "launch_after_outcome" \/ outcome[c] = "none")
    /\ ~promptSent[c][k] /\ queued[c] = 0 /\ pendingSend[c] = 0 /\ copying[c] = NoCopy
    /\ \/ k = 1
       \/ k > 1 /\ turnEnded[c][k - 1] /\ (BUG = "prompt_before_snapshot" \/ snapEv[c][k - 1])
    /\ queued' = [queued EXCEPT ![c] = k]
    /\ pendingSend' = IF BUG = "send_before_persist"
                        THEN [pendingSend EXCEPT ![c] = k] ELSE pendingSend
    /\ UNCHANGED <<tvars, engine, crashes, reconciling, reconciled, intent, launchEpoch, epoch,
                   proc, killRequested, killReason, promptSent, prompts, outcome,
                   wasStopped, archived, deleted, controlFile, controlApplied, applyCount,
                   stopApplied, decision, resolutions, lock, passState, passOwner, graded,
                   gradeCount, flags, grace>>

\* The engine thread appends and fsyncs prompt_sent, then acks the worker.
PersistPromptSent(c) ==
    /\ engine = "up"
    /\ queued[c] # 0
    /\ promptSent' = [promptSent EXCEPT ![c][queued[c]] = TRUE]
    /\ pendingSend' = [pendingSend EXCEPT ![c] = queued[c]]
    /\ queued' = [queued EXCEPT ![c] = 0]
    /\ UNCHANGED <<tvars, engine, crashes, reconciling, reconciled, intent, launchEpoch, epoch,
                   proc, killRequested, killReason, prompts, outcome, wasStopped,
                   archived, deleted, controlFile, controlApplied, applyCount, stopApplied,
                   decision, resolutions, lock, passState, passOwner, graded, gradeCount,
                   flags, grace>>

\* The worker sends the prompt once, only after the ack.
SendPrompt(c) ==
    /\ engine = "up"
    /\ pendingSend[c] # 0
    /\ proc[c] = "running" /\ ~killRequested[c]
    /\ prompts' = [prompts EXCEPT ![c][pendingSend[c]] = @ + 1]
    /\ pendingSend' = [pendingSend EXCEPT ![c] = 0]
    /\ IF outcome[c] # "none" THEN Flag("promptAfterOutcome") ELSE UNCHANGED flags
    /\ UNCHANGED <<tvars, engine, crashes, reconciling, reconciled, intent, launchEpoch, epoch,
                   proc, killRequested, killReason, queued, promptSent, outcome,
                   wasStopped, archived, deleted, controlFile, controlApplied, applyCount,
                   stopApplied, decision, resolutions, lock, passState, passOwner, graded,
                   gradeCount, grace>>

\* The adapter returns a stop reason and the worker records turn_ended{k} (ADR-0015 section 2 (a)), for every turn
\* that was sent, whatever its stop reason or a pending kill (w1-j rev 2: RV-SRE 1, RV-PAT F2, RV-DS 4). The record
\* says the turn ran; whether turn k+1 follows is the engine's rule, not this action's.
TurnEnd(c, k) ==
    /\ EngineReady
    /\ proc[c] = "running"
    /\ prompts[c][k] >= 1 /\ ~turnEnded[c][k]
    /\ turnEnded' = [turnEnded EXCEPT ![c][k] = TRUE]
    \* `next` is the engine's decision at the turn's end (W0 rev 6.5): a following turn (snapshot), the last planned
    \* turn (final), or a stop, budget kill or deadline that ends the cell (stop). It is recorded, not recomputed.
    /\ turnNext' = [turnNext EXCEPT ![c][k] = IF k = NumTurns THEN "final"
                                              ELSE IF killRequested[c] \/ stopApplied THEN "stop" ELSE "snapshot"]
    /\ UNCHANGED <<snapEv, copying, tmp, fin, engine, crashes, reconciling, reconciled, intent, launchEpoch, epoch,
                   proc, killRequested, killReason, queued, promptSent, pendingSend, prompts, outcome,
                   wasStopped, archived, deleted, controlFile, controlApplied, applyCount,
                   stopApplied, decision, resolutions, lock, passState, passOwner, graded,
                   gradeCount, flags, grace>>

\* Environment: the proc exits on its own (agent finished, or it failed before a prompt).
CellExits(c) ==
    /\ proc[c] = "running" /\ ~killRequested[c]
    /\ proc' = [proc EXCEPT ![c] = "exited"]
    /\ UNCHANGED <<tvars, engine, crashes, reconciling, reconciled, intent, launchEpoch, epoch,
                   killRequested, killReason, queued, promptSent, pendingSend, prompts,
                   outcome, wasStopped, archived, deleted, controlFile, controlApplied,
                   applyCount, stopApplied, decision, resolutions, lock, passState, passOwner,
                   graded, gradeCount, flags, grace>>

\* Environment: a requested kill takes effect (the engine retries until inspect confirms).
CellDies(c) ==
    /\ proc[c] = "running" /\ killRequested[c] /\ ~grace[c]
    /\ proc' = [proc EXCEPT ![c] = "exited"]
    /\ killRequested' = [killRequested EXCEPT ![c] = FALSE]
    /\ UNCHANGED <<tvars, engine, crashes, reconciling, reconciled, intent, launchEpoch, epoch,
                   killReason, queued, promptSent, pendingSend, prompts, outcome, wasStopped,
                   archived, deleted, controlFile, controlApplied, applyCount, stopApplied,
                   decision, resolutions, lock, passState, passOwner, graded, gradeCount,
                   flags, grace>>

\* The adapter may honour cancel and exit before the hard deadline.
GracefulExit(c) ==
    /\ proc[c] = "running" /\ killRequested[c] /\ grace[c]
    /\ proc' = [proc EXCEPT ![c] = "exited"]
    /\ killRequested' = [killRequested EXCEPT ![c] = FALSE]
    /\ grace' = [grace EXCEPT ![c] = FALSE]
    /\ UNCHANGED <<tvars, engine, crashes, reconciling, reconciled, intent, launchEpoch, epoch,
                   killReason, queued, promptSent, pendingSend, prompts, outcome, wasStopped,
                   archived, deleted, controlFile, controlApplied, applyCount, stopApplied,
                   decision, resolutions, lock, passState, passOwner, graded, gradeCount, flags>>

\* The engine's deadline issues the hard kill. Its timing is checked in code, not TLC.
EndGrace(c) ==
    /\ BUG # "no_escalate"
    /\ engine = "up"
    /\ proc[c] = "running" /\ killRequested[c] /\ grace[c]
    /\ grace' = [grace EXCEPT ![c] = FALSE]
    /\ UNCHANGED <<tvars, engine, crashes, reconciling, reconciled, intent, launchEpoch, epoch,
                   proc, killRequested, killReason, queued, promptSent, pendingSend, prompts,
                   outcome, wasStopped, archived, deleted, controlFile, controlApplied,
                   applyCount, stopApplied, decision, resolutions, lock, passState, passOwner,
                   graded, gradeCount, flags>>

\* The engine records how an exited proc's cell ended (never while it runs).
RecordExit(c) ==
    /\ EngineReady
    /\ Active(c) /\ ~killRequested[c] /\ copying[c] = NoCopy
    /\ \/ proc[c] = "exited"
       \/ BUG = "record_while_running" /\ proc[c] = "running"   \* seeded: records, never kills
    /\ Record(c, CASE killReason[c] = "stop"    -> "stopped"
                   [] killReason[c] = "timeout" -> "timedout"
                   [] prompts[c][NumTurns] >= 1 -> "done"
                   [] OTHER                     -> "failed")
    /\ UNCHANGED <<tvars, engine, crashes, reconciling, reconciled, intent, launchEpoch, epoch,
                   proc, killRequested, killReason, queued, promptSent, pendingSend,
                   prompts, archived, deleted, controlFile, controlApplied, applyCount,
                   stopApplied, decision, resolutions, lock, passState, passOwner, graded,
                   gradeCount, flags, grace>>

\* Budget or handshake deadline: kill first; the outcome is recorded after the proc is gone.
EngineKill(c) ==
    /\ BUG # "no_budget_kill"
    /\ EngineReady
    /\ Active(c) /\ proc[c] = "running" /\ ~killRequested[c]
    /\ killRequested' = [killRequested EXCEPT ![c] = TRUE]
    /\ killReason' = [killReason EXCEPT ![c] = "timeout"]
    /\ grace' = [grace EXCEPT ![c] = TRUE]
    /\ UNCHANGED <<tvars, engine, crashes, reconciling, reconciled, intent, launchEpoch, epoch,
                   proc, queued, promptSent, pendingSend, prompts, outcome, wasStopped,
                   archived, deleted, controlFile, controlApplied, applyCount, stopApplied,
                   decision, resolutions, lock, passState, passOwner, graded, gradeCount,
                   flags>>

-----------------------------------------------------------------------------
(* Stop: kill every running cell, then record stopped; cells never launched stay unstarted *)

StopCell(c) ==
    /\ EngineReady /\ stopApplied
    /\ Active(c) /\ copying[c] = NoCopy
    /\ ~(proc[c] = "running" /\ killReason[c] = "stop")
    /\ grace' = IF proc[c] = "running" /\ BUG # "record_without_kill"
                 THEN [grace EXCEPT ![c] = TRUE] ELSE grace
    /\ IF proc[c] = "running" /\ BUG = "record_without_kill"
         THEN /\ Record(c, "stopped")                        \* seeded: records, never kills
              /\ UNCHANGED <<tvars, killRequested, killReason>>
       ELSE IF proc[c] = "running"
         THEN /\ killRequested' = [killRequested EXCEPT ![c] = TRUE]
              /\ killReason' = [killReason EXCEPT ![c] = "stop"]
              /\ UNCHANGED <<tvars, outcome, wasStopped>>
         ELSE /\ Record(c, "stopped")
              /\ UNCHANGED <<tvars, killRequested, killReason>>
    /\ UNCHANGED <<tvars, engine, crashes, reconciling, reconciled, intent, launchEpoch, epoch,
                   proc, queued, promptSent, pendingSend, prompts, archived, deleted,
                   controlFile, controlApplied, applyCount, stopApplied, decision, resolutions,
                   lock, passState, passOwner, graded, gradeCount, flags>>

-----------------------------------------------------------------------------
(* Archive, then delete *)

\* Every archive write and every turn snapshot is a crash-atomic publish (ADR-0015 section 5a, the W0 `publish_dir`
\* helper): fill an exclusive temporary sibling, verify it, rename it to the final name, and only then append the
\* ledger event. Artifact 0 is the final archive; artifact k is the turn-k snapshot. The seeded `*_in_place`
\* defects fill the final name directly. A crash loses the volatile `copying` flag and leaves the temporary
\* sibling inert: W0 names it `<name>.tmp-<pid>-<uuid>`, so a leftover never collides with a later copy, and the
\* sweep (a file-level test, not a model action) only removes it.
InPlace(a) == (a = 0 /\ BUG = "archive_in_place") \/ (a > 0 /\ BUG = "snapshot_in_place")

\* A live worker, or the engine's reconciliation after the adapter is gone, may snapshot a cell between turns.
SnapAllowed(c) == Active(c) /\ ((launchEpoch[c] = epoch /\ ~reconciling) \/ (reconciling /\ proc[c] # "running"))

CopyBegin(c, a) ==
    /\ engine = "up" /\ copying[c] = NoCopy
    /\ tmp[c][a] = "none" /\ fin[c][a] = "none"           \* a final name that exists is HB-USR-002
    /\ IF a = 0
         THEN /\ ~archived[c]
              \* Archive only after the outcome is recorded and the proc is gone. The seeded bug archives as
              \* soon as a kill has been issued, without waiting for inspect to confirm the proc exited.
              /\ \/ outcome[c] # "none" /\ proc[c] # "running"
                 \/ BUG = "archive_live" /\ killRequested[c]
              /\ IF proc[c] = "running" THEN Flag("archiveLive") ELSE UNCHANGED flags
         ELSE /\ ~snapEv[c][a] /\ SnapAllowed(c)
              \* A snapshot is taken only when the engine decided a next turn follows (turn_ended.next = snapshot).
              \* The seeded bug snapshots a turn that ended with next = stop.
              /\ \/ BUG = "snapshot_when_stopping"
                 \/ turnNext[c][a] = "snapshot"
                 \/ BUG = "snapshot_in_flight" /\ turnNext[c][a] = "none"   \* the in-flight bug runs before any `next` exists
              \* The snapshot starts only while the adapter is idle: turn a has ended. The seeded bug
              \* snapshots while turn a is still in flight.
              /\ \/ turnEnded[c][a]
                 \/ BUG = "snapshot_in_flight" /\ prompts[c][a] >= 1 /\ proc[c] = "running"
              /\ UNCHANGED flags
    /\ copying' = [copying EXCEPT ![c] = a]
    /\ tmp' = IF InPlace(a) THEN tmp ELSE [tmp EXCEPT ![c][a] = "partial"]
    /\ fin' = IF InPlace(a) THEN [fin EXCEPT ![c][a] = "partial"] ELSE fin
    /\ UNCHANGED <<turnEnded, turnNext, snapEv, engine, crashes, reconciling, reconciled, intent, launchEpoch, epoch,
                   proc, killRequested, killReason, queued, promptSent, pendingSend,
                   prompts, outcome, wasStopped, archived, deleted, controlFile, controlApplied,
                   applyCount, stopApplied, decision, resolutions, lock, passState, passOwner,
                   graded, gradeCount, grace>>

\* Verified, then renamed (or, in place, the fill simply ends): the name now exists and is complete.
CopyPublish(c, a) ==
    /\ engine = "up" /\ copying[c] = a
    /\ IF InPlace(a) THEN fin[c][a] = "partial" ELSE tmp[c][a] = "partial"
    /\ fin' = [fin EXCEPT ![c][a] = "complete"]
    /\ tmp' = [tmp EXCEPT ![c][a] = "none"]
    /\ UNCHANGED <<turnEnded, turnNext, snapEv, copying, engine, crashes, reconciling, reconciled, intent, launchEpoch, epoch,
                   proc, killRequested, killReason, queued, promptSent, pendingSend,
                   prompts, outcome, wasStopped, archived, deleted, controlFile, controlApplied,
                   applyCount, stopApplied, decision, resolutions, lock, passState, passOwner,
                   graded, gradeCount, flags, grace>>

\* A snapshot copy fails after bounded retry (HB-CELL-117): the attempt ends, turn k+1 is never sent, and the
\* temporary sibling stays for the sweep.
SnapFail(c, k) ==
    /\ k \in Arts \ {0}
    /\ EngineReady /\ copying[c] = k /\ tmp[c][k] = "partial"
    /\ proc[c] = "running" /\ ~killRequested[c]
    /\ copying' = [copying EXCEPT ![c] = NoCopy]
    /\ tmp' = [tmp EXCEPT ![c][k] = "none"]
    /\ proc' = [proc EXCEPT ![c] = "exited"]
    /\ UNCHANGED <<turnEnded, turnNext, snapEv, fin, engine, crashes, reconciling, reconciled, intent, launchEpoch, epoch,
                   killRequested, killReason, queued, promptSent, pendingSend,
                   prompts, outcome, wasStopped, archived, deleted, controlFile, controlApplied,
                   applyCount, stopApplied, decision, resolutions, lock, passState, passOwner,
                   graded, gradeCount, flags, grace>>

\* cell.turn_snapshot_archived{k}: appended only after the snapshot folder is published.
SnapRecord(c, k) ==
    /\ k \in Arts \ {0}
    /\ engine = "up"
    /\ fin[c][k] = "complete" /\ ~snapEv[c][k]
    /\ snapEv' = [snapEv EXCEPT ![c][k] = TRUE]
    /\ copying' = [copying EXCEPT ![c] = NoCopy]
    /\ UNCHANGED <<turnEnded, turnNext, tmp, fin, engine, crashes, reconciling, reconciled, intent, launchEpoch, epoch,
                   proc, killRequested, killReason, queued, promptSent, pendingSend,
                   prompts, outcome, wasStopped, archived, deleted, controlFile, controlApplied,
                   applyCount, stopApplied, decision, resolutions, lock, passState, passOwner,
                   graded, gradeCount, flags, grace>>

\* cell.archived: appended only after the final folder is published. If a crash fell between the rename and
\* this append, the folder exists and the event is recorded on resume (W0 section 4, the recovery rule).
Archive(c) ==
    /\ engine = "up"
    /\ ~archived[c] /\ fin[c][0] = "complete"
    /\ archived' = [archived EXCEPT ![c] = TRUE]
    /\ copying' = [copying EXCEPT ![c] = NoCopy]
    /\ UNCHANGED <<turnEnded, turnNext, snapEv, tmp, fin, engine, crashes, reconciling, reconciled, intent, launchEpoch, epoch,
                   proc, killRequested, killReason, queued, promptSent, pendingSend,
                   prompts, outcome, wasStopped, deleted, controlFile, controlApplied,
                   applyCount, stopApplied, decision, resolutions, lock, passState, passOwner,
                   graded, gradeCount, flags, grace>>

DeleteWorkspace(c) ==
    /\ engine = "up"
    /\ ~deleted[c] /\ outcome[c] # "none"
    /\ (BUG = "delete_before_archive" \/ archived[c])
    /\ deleted' = [deleted EXCEPT ![c] = TRUE]
    /\ UNCHANGED <<tvars, engine, crashes, reconciling, reconciled, intent, launchEpoch, epoch,
                   proc, killRequested, killReason, queued, promptSent, pendingSend,
                   prompts, outcome, wasStopped, archived, controlFile, controlApplied,
                   applyCount, stopApplied, decision, resolutions, lock, passState, passOwner,
                   graded, gradeCount, flags, grace>>

-----------------------------------------------------------------------------
(* Control mailbox: control.applied is recorded before the file is removed *)

WriteControl(k) ==
    /\ ~controlFile[k] /\ ~controlApplied[k]
    /\ controlFile' = [controlFile EXCEPT ![k] = TRUE]
    /\ UNCHANGED <<tvars, engine, crashes, reconciling, reconciled, intent, launchEpoch, epoch,
                   proc, killRequested, killReason, queued, promptSent, pendingSend,
                   prompts, outcome, wasStopped, archived, deleted, controlApplied,
                   applyCount, stopApplied, decision, resolutions, lock, passState, passOwner,
                   graded, gradeCount, flags, grace>>

ApplyStop ==
    /\ BUG # "stop_ignored"
    /\ engine = "up"
    /\ controlFile["stop"]
    /\ (BUG = "apply_twice" \/ ~controlApplied["stop"])
    /\ controlApplied' = [controlApplied EXCEPT !["stop"] = TRUE]
    /\ applyCount' = [applyCount EXCEPT !["stop"] = @ + 1]
    /\ stopApplied' = TRUE
    /\ decision' = IF decision = "open" THEN "resolved" ELSE decision   \* superseded (stop)
    /\ resolutions' = IF decision = "open" THEN resolutions + 1 ELSE resolutions
    /\ UNCHANGED <<tvars, engine, crashes, reconciling, reconciled, intent, launchEpoch, epoch,
                   proc, killRequested, killReason, queued, promptSent, pendingSend,
                   prompts, outcome, wasStopped, archived, deleted, controlFile, lock,
                   passState, passOwner, graded, gradeCount, flags, grace>>

ApplyAnswer ==
    /\ engine = "up"
    /\ controlFile["answer"]
    /\ (BUG = "apply_twice" \/ ~controlApplied["answer"])
    /\ controlApplied' = [controlApplied EXCEPT !["answer"] = TRUE]
    /\ applyCount' = [applyCount EXCEPT !["answer"] = @ + 1]
    /\ IF decision = "open" \/ (BUG = "double_resolution" /\ decision = "resolved")
         THEN /\ decision' = "resolved" /\ resolutions' = resolutions + 1
         ELSE UNCHANGED <<tvars, decision, resolutions>>
    /\ UNCHANGED <<tvars, engine, crashes, reconciling, reconciled, intent, launchEpoch, epoch,
                   proc, killRequested, killReason, queued, promptSent, pendingSend,
                   prompts, outcome, wasStopped, archived, deleted, controlFile, stopApplied,
                   lock, passState, passOwner, graded, gradeCount, flags, grace>>

RemoveControl(k) ==
    /\ engine = "up"
    /\ controlFile[k] /\ controlApplied[k]
    /\ controlFile' = [controlFile EXCEPT ![k] = FALSE]
    /\ UNCHANGED <<tvars, engine, crashes, reconciling, reconciled, intent, launchEpoch, epoch,
                   proc, killRequested, killReason, queued, promptSent, pendingSend,
                   prompts, outcome, wasStopped, archived, deleted, controlApplied,
                   applyCount, stopApplied, decision, resolutions, lock, passState, passOwner,
                   graded, gradeCount, flags, grace>>

-----------------------------------------------------------------------------
(* One decision request with a timeout default *)

RaiseDecision ==
    /\ engine = "up" /\ decision = "none" /\ ~stopApplied
    /\ decision' = "open"
    /\ UNCHANGED <<tvars, engine, crashes, reconciling, reconciled, intent, launchEpoch, epoch,
                   proc, killRequested, killReason, queued, promptSent, pendingSend,
                   prompts, outcome, wasStopped, archived, deleted, controlFile,
                   controlApplied, applyCount, stopApplied, resolutions, lock, passState,
                   passOwner, graded, gradeCount, flags, grace>>

TimeoutDefault ==
    /\ BUG # "no_timeout"
    /\ engine = "up" /\ decision = "open"
    /\ decision' = "resolved" /\ resolutions' = resolutions + 1
    /\ UNCHANGED <<tvars, engine, crashes, reconciling, reconciled, intent, launchEpoch, epoch,
                   proc, killRequested, killReason, queued, promptSent, pendingSend,
                   prompts, outcome, wasStopped, archived, deleted, controlFile,
                   controlApplied, applyCount, stopApplied, lock, passState, passOwner,
                   graded, gradeCount, flags, grace>>

-----------------------------------------------------------------------------
(* Crash and resume: process memory (queue, acks, kill reasons) and the engine's lock are lost *)

Crash ==
    /\ engine = "up" /\ crashes < MaxCrashes
    /\ engine' = "down" /\ crashes' = crashes + 1
    /\ queued' = [c \in Cells |-> 0]
    /\ pendingSend' = [c \in Cells |-> 0]
    /\ copying' = [c \in Cells |-> NoCopy]
    /\ tmp' = [c \in Cells |-> [a \in Arts |-> "none"]]
    /\ killReason' = [c \in Cells |-> "none"]
    /\ grace' = [c \in Cells |-> FALSE]
    /\ lock' = IF lock = "engine" THEN "free" ELSE lock
    /\ passState' = [p \in Passes |->
                       IF passOwner[p] = "engine" /\ passState[p] = "active"
                         THEN "abandoned" ELSE passState[p]]
    /\ UNCHANGED <<turnEnded, turnNext, snapEv, fin, reconciling, reconciled, intent, launchEpoch, epoch, proc,
                   killRequested, promptSent, prompts, outcome, wasStopped, archived, deleted,
                   controlFile, controlApplied, applyCount, stopApplied, decision,
                   resolutions, passOwner, graded, gradeCount, flags>>

\* ADR-0021 section 2 as ruled by R-100 (DR-K1): a resume after a stop is not refused; it finishes the stop. It
\* launches nothing and records `stopped` for every intent-without-outcome cell (ReconcileRecord, under stopApplied).
\* `stopApplied` abstracts the three stop rows (run.stopped, control.applied{stop}, decision.resolved{option: stop})
\* as one step, the earliest of the three. The invariant is NoLaunchAfterStop, the guard WriteIntent already has.
Resume ==
    /\ engine = "down"
    /\ engine' = "up" /\ epoch' = epoch + 1
    /\ reconciling' = TRUE /\ reconciled' = {}
    /\ UNCHANGED <<tvars, crashes, intent, launchEpoch, proc, killRequested, killReason, queued,
                   promptSent, pendingSend, prompts, outcome, wasStopped, archived, deleted,
                   controlFile, controlApplied, applyCount, stopApplied, decision,
                   resolutions, lock, passState, passOwner, graded, gradeCount, grace, flags>>

\* Reconciliation step 1: kill every running proc carrying the run's label, whatever its outcome.
ReconcileKill(c) ==
    /\ engine = "up" /\ reconciling
    /\ proc[c] = "running" /\ ~killRequested[c]
    /\ killRequested' = [killRequested EXCEPT ![c] = TRUE]
    /\ UNCHANGED <<tvars, engine, crashes, reconciling, reconciled, intent, launchEpoch, epoch,
                   proc, killReason, queued, promptSent, pendingSend, prompts, outcome,
                   wasStopped, archived, deleted, controlFile, controlApplied, applyCount,
                   stopApplied, decision, resolutions, lock, passState, passOwner, graded,
                   gradeCount, flags, grace>>

\* Reconciliation step 2 (proc gone): prompted cells fail, never relaunched; unprompted
\* cells have their proc removed and may launch once. The recorded class is ADR-0015 section 6's
\* predicate (ClassOf); a cell between turns first has its snapshot redone (ADR-0021 section 4).
\* Seeded bugs: `relaunch_prompted` reopens every prompted cell; `resend_turn_on_resume` reopens a crashed
\* turn k > 1; `kill_between_turns` classifies by the old predicate (prompted and not terminal);
\* `crashed_turn_as_between` is the reverse error: a crashed turn classed as between turns.
ResendTurn(c) == BUG = "resend_turn_on_resume" /\ \E k \in Turns \ {1} : promptSent[c][k] /\ ~turnEnded[c][k]
ReconcileRecord(c) ==
    /\ engine = "up" /\ reconciling
    /\ Active(c) /\ c \notin reconciled /\ copying[c] = NoCopy
    /\ (BUG = "reconcile_no_wait" \/ proc[c] # "running")   \* seeded: records without confirming the kill
    /\ IF stopApplied /\ BUG # "stop_resume_launches"
         THEN \* R-100: the stop row chooses the branch; the engine's kill-reason rule for `stop` is `stopped`.
              \* A between-turns cell still has its snapshot redone first (C4).
              /\ (~AnyPrompted(c) \/ BUG = "between_without_snapshot" \/ BetweenSnapped(c))
              /\ Record(c, IF BUG = "stop_recorded_as_crash" THEN ClassOf(c) ELSE "stopped")
              /\ IF BUG = "stop_recorded_as_crash" THEN Flag("crashUnderStop") ELSE UNCHANGED flags
              /\ UNCHANGED <<proc, promptSent>>
         ELSE /\ UNCHANGED flags
              /\ IF AnyPrompted(c) /\ BUG # "relaunch_prompted" /\ ~ResendTurn(c)
                   THEN /\ (BUG = "between_without_snapshot" \/ BetweenSnapped(c))
                        /\ Record(c, IF BUG = "kill_between_turns" THEN "crashfail"
                                    ELSE IF BUG = "crashed_turn_as_between" /\ CrashedTurn(c) THEN "crashbetween"
                                    ELSE ClassOf(c))
                        /\ UNCHANGED <<proc, promptSent>>
                   ELSE /\ proc' = [proc EXCEPT ![c] = "none"]
                        /\ promptSent' = IF BUG = "relaunch_prompted"
                                           THEN [promptSent EXCEPT ![c] = [k \in Turns |-> FALSE]]
                                           ELSE IF ResendTurn(c)
                                           THEN [promptSent EXCEPT ![c] = [k \in Turns |-> promptSent[c][k] /\ turnEnded[c][k]]]
                                           ELSE promptSent
                        /\ UNCHANGED <<outcome, wasStopped>>
    /\ reconciled' = reconciled \cup {c}
    /\ UNCHANGED <<tvars, engine, crashes, reconciling, intent, launchEpoch, epoch, killRequested,
                   killReason, queued, pendingSend, prompts, archived, deleted, controlFile,
                   controlApplied, applyCount, stopApplied, decision, resolutions, lock,
                   passState, passOwner, graded, gradeCount, grace>>

\* Seeded bug "relaunch_stopped": reconciliation re-opens stopped cells.
ReopenStopped(c) ==
    /\ BUG = "relaunch_stopped"
    /\ engine = "up" /\ reconciling
    /\ outcome[c] = "stopped" /\ proc[c] # "running"
    /\ outcome' = [outcome EXCEPT ![c] = "none"]
    /\ proc' = [proc EXCEPT ![c] = "none"]
    /\ UNCHANGED <<tvars, engine, crashes, reconciling, reconciled, intent, launchEpoch, epoch,
                   killRequested, killReason, queued, promptSent, pendingSend, prompts,
                   wasStopped, archived, deleted, controlFile, controlApplied, applyCount,
                   stopApplied, decision, resolutions, lock, passState, passOwner, graded,
                   gradeCount, flags, grace>>

ReconcileDone ==
    /\ engine = "up" /\ reconciling
    /\ \A c \in Cells : (Active(c) => c \in reconciled)
                           /\ (BUG = "reconcile_no_wait" \/ proc[c] # "running")
    /\ reconciling' = FALSE
    /\ UNCHANGED <<tvars, engine, crashes, reconciled, intent, launchEpoch, epoch, proc,
                   killRequested, killReason, queued, promptSent, pendingSend, prompts,
                   outcome, wasStopped, archived, deleted, controlFile, controlApplied,
                   applyCount, stopApplied, decision, resolutions, lock, passState, passOwner,
                   graded, gradeCount, flags, grace>>

-----------------------------------------------------------------------------
(* Grading passes: each process mints its own pass; grade.lock gives mutual exclusion.         *)
(* The engine grades once per run, when every cell has ended and been archived (or was never   *)
(* launched because of a stop); a pass abandoned by a crash is restarted after the resume.     *)
(* `bench grade` may start a pass at any time.                                                  *)

RunFinished == \A c \in Cells : (outcome[c] # "none" /\ archived[c]) \/ (~intent[c] /\ stopApplied)
EngineGraded == \E q \in Passes : passOwner[q] = "engine" /\ passState[q] \in {"active", "done"}

GradeStart(p, g) ==
    /\ passState[p] = "idle"
    /\ (BUG = "no_lock" \/ lock = "free")
    /\ (g = "engine" => EngineReady /\ RunFinished /\ ~EngineGraded)
    /\ lock' = g
    /\ passState' = [passState EXCEPT ![p] = "active"]
    /\ passOwner' = [passOwner EXCEPT ![p] = g]
    /\ UNCHANGED <<tvars, engine, crashes, reconciling, reconciled, intent, launchEpoch, epoch,
                   proc, killRequested, killReason, queued, promptSent, pendingSend,
                   prompts, outcome, wasStopped, archived, deleted, controlFile,
                   controlApplied, applyCount, stopApplied, decision, resolutions, graded,
                   gradeCount, flags, grace>>

GradeCell(p, c) ==
    /\ passState[p] = "active"
    /\ (passOwner[p] = "engine" => engine = "up")
    /\ (BUG = "grade_unarchived" \/ archived[c])
    /\ outcome[c] # "none"
    /\ (BUG = "grade_twice" \/ c \notin graded[p])
    /\ graded' = [graded EXCEPT ![p] = @ \cup {c}]
    /\ gradeCount' = [gradeCount EXCEPT ![p][c] = @ + 1]
    /\ IF ~archived[c] THEN Flag("gradeUnarchived") ELSE UNCHANGED flags
    /\ UNCHANGED <<tvars, engine, crashes, reconciling, reconciled, intent, launchEpoch, epoch,
                   proc, killRequested, killReason, queued, promptSent, pendingSend,
                   prompts, outcome, wasStopped, archived, deleted, controlFile,
                   controlApplied, applyCount, stopApplied, decision, resolutions, lock,
                   passState, passOwner, grace>>

GradeEnd(p) ==
    /\ passState[p] = "active"
    /\ (passOwner[p] = "engine" => engine = "up")
    \* The engine's pass ends only when it has graded every archived cell.
    /\ (BUG = "grade_skipped" \/ passOwner[p] # "engine"
        \/ \A c \in Cells : archived[c] => c \in graded[p])
    /\ lock' = IF lock = passOwner[p] THEN "free" ELSE lock
    /\ passState' = [passState EXCEPT ![p] = "done"]
    /\ UNCHANGED <<tvars, engine, crashes, reconciling, reconciled, intent, launchEpoch, epoch,
                   proc, killRequested, killReason, queued, promptSent, pendingSend,
                   prompts, outcome, wasStopped, archived, deleted, controlFile,
                   controlApplied, applyCount, stopApplied, decision, resolutions, passOwner,
                   graded, gradeCount, flags, grace>>

-----------------------------------------------------------------------------
Next ==
    \/ \E c \in Cells : WriteIntent(c)
    \/ \E c \in Cells :
          \/ StartCell(c) \/ StartFails(c) \/ PersistPromptSent(c)
          \/ SendPrompt(c) \/ CellExits(c) \/ CellDies(c) \/ GracefulExit(c) \/ EndGrace(c) \/ RecordExit(c)
          \/ EngineKill(c) \/ StopCell(c) \/ Archive(c) \/ DeleteWorkspace(c)
          \/ \E k \in Turns : QueuePromptSent(c, k) \/ TurnEnd(c, k)
          \/ \E a \in Arts : CopyBegin(c, a) \/ CopyPublish(c, a) \/ SnapFail(c, a) \/ SnapRecord(c, a)
          \/ ReconcileKill(c) \/ ReconcileRecord(c) \/ ReopenStopped(c)
    \/ \E k \in Controls : WriteControl(k) \/ RemoveControl(k)
    \/ ApplyStop \/ ApplyAnswer \/ RaiseDecision \/ TimeoutDefault
    \/ Crash \/ Resume \/ ReconcileDone
    \/ \E p \in Passes : \E g \in Graders : GradeStart(p, g)
    \/ \E p \in Passes, c \in Cells : GradeCell(p, c)
    \/ \E p \in Passes : GradeEnd(p)

\* Fairness: the engine's own progress (including the budget deadline and its grading pass), and
\* the environment honouring kills (the engine retries a kill until inspect confirms; a kill that
\* never takes effect is an infrastructure fault).
Fairness ==
    /\ WF_vars(Resume) /\ WF_vars(ReconcileDone) /\ WF_vars(TimeoutDefault)
    /\ WF_vars(ApplyStop) /\ WF_vars(ApplyAnswer)
    /\ \A c \in Cells :
          /\ WF_vars(StopCell(c)) /\ WF_vars(CellDies(c)) /\ WF_vars(EndGrace(c)) /\ WF_vars(RecordExit(c))
          /\ WF_vars(ReconcileKill(c)) /\ WF_vars(ReconcileRecord(c)) /\ WF_vars(Archive(c))
          /\ \A a \in Arts : WF_vars(CopyBegin(c, a)) /\ WF_vars(CopyPublish(c, a)) /\ WF_vars(SnapRecord(c, a))
          /\ WF_vars(EngineKill(c))
    /\ \A p \in Passes :
          /\ WF_vars(GradeStart(p, "engine")) /\ WF_vars(GradeEnd(p))
          /\ \A c \in Cells : WF_vars(GradeCell(p, c))

Spec == Init /\ [][Next]_vars /\ Fairness

\* Cells and passes are interchangeable. Safety configuration only: TLC's symmetry reduction is
\* unsound for liveness, which is checked in a separate configuration.
Symmetry == Permutations(Cells) \cup Permutations(Passes)

-----------------------------------------------------------------------------
(* Safety invariants *)

TypeOK ==
    /\ engine \in {"up", "down"}
    /\ outcome \in [Cells -> Outcomes]
    /\ proc \in [Cells -> {"none", "running", "exited"}]
    /\ killReason \in [Cells -> Reasons]
    /\ grace \in [Cells -> BOOLEAN]
    /\ decision \in {"none", "open", "resolved"}
    /\ lock \in {"free", "engine", "bench"}
    /\ queued \in [Cells -> 0..NumTurns] /\ pendingSend \in [Cells -> 0..NumTurns]
    /\ promptSent \in [Cells -> [Turns -> BOOLEAN]] /\ turnEnded \in [Cells -> [Turns -> BOOLEAN]]
    /\ turnNext \in [Cells -> [Turns -> NextKinds]]
    /\ snapEv \in [Cells -> [Turns -> BOOLEAN]] /\ copying \in [Cells -> Arts \cup {NoCopy}]
    /\ tmp \in [Cells -> [Arts -> {"none", "partial"}]]
    /\ fin \in [Cells -> [Arts -> {"none", "partial", "complete"}]]

PromptOncePerTurn          == \A c \in Cells, k \in Turns : prompts[c][k] <= 1
\* ADR-0015 section 7. No turn k+1 prompt (ledger or wire) before turn k's snapshot event is durable.
SnapshotBeforeNextTurn     == \A c \in Cells, k \in Turns \ {1} :
                                (promptSent[c][k] \/ prompts[c][k] >= 1) => snapEv[c][k - 1]
\* No copy runs while a turn is in flight, so the working copy is quiescent apart from stray processes.
NoSnapshotInFlight         == \A c \in Cells : copying[c] # NoCopy => ~InFlight(c)
\* ADR-0015 section 7, stated from the ledger facts and independent of ClassOf (w1-j rev 2, RV-TA 2): a recorded
\* crash outcome is crashfail when a turn was sent and has not ended; a cell with no such turn that waits between
\* turns is crashbetween, and only such a cell is. Three implications, so a wrong ClassOf fails in either direction.
CrashedLit(c) == \E k \in Turns : promptSent[c][k] /\ ~turnEnded[c][k]
WaitingLit(c) == (\A k \in Turns : promptSent[c][k] => turnEnded[c][k])
                 /\ \E k \in 1..(NumTurns - 1) : turnEnded[c][k] /\ turnNext[c][k] = "snapshot" /\ ~promptSent[c][k + 1]
CrashedTurnPredicate       == \A c \in Cells : outcome[c] \in {"crashfail", "crashbetween"} =>
                                /\ (CrashedLit(c) => outcome[c] = "crashfail")
                                /\ (WaitingLit(c) => outcome[c] = "crashbetween")
                                /\ (outcome[c] = "crashbetween" => WaitingLit(c))
\* A final archive or snapshot name exists only after its copy was verified.
ArchiveExistsMeansComplete == \A c \in Cells, a \in Arts : fin[c][a] # "none" => fin[c][a] = "complete"
NoPromptAfterOutcome       == ~flags["promptAfterOutcome"]
NoArchiveWhileLive         == ~flags["archiveLive"]
NothingDeletedUnarchived   == \A c \in Cells : deleted[c] => archived[c]
GradedOncePerPass          == \A p \in Passes, c \in Cells : gradeCount[p][c] <= 1
GradedOnlyWhenArchived     == ~flags["gradeUnarchived"]
AtMostOneActivePass        == Cardinality({p \in Passes : passState[p] = "active"}) <= 1
ControlAppliedOnce         == \A k \in Controls : applyCount[k] <= 1
NoLaunchAfterStop          == ~flags["launchAfterStop"]
ParallelismBound           == Cardinality(Running) <= Parallelism
StoppedNeverRelaunched     == \A c \in Cells : wasStopped[c] => outcome[c] = "stopped"
DecisionResolvedOnce       == resolutions <= 1
NoLaunchWhileDecisionOpen  == ~flags["launchWhileOpen"]
NoLaunchBesideOrphan       == ~flags["launchBesideOrphan"]
NoOutcomeWhileRunning      == \A c \in Cells : outcome[c] # "none" => proc[c] # "running"
\* R-100 (DR-K1): a resume after a stop records `stopped` for every intent-without-outcome cell, never a crash class.
\* The flag is set only in ReconcileRecord, so a crash outcome recorded before the stop is not a violation.
StopResumeRecordsStopped   == ~flags["crashUnderStop"]
\* ADR-0021 section 4, the snapshot row and the between-turns row: a cell recorded crashbetween has the snapshot event
\* of the turn it was waiting after, and that turn's recorded decision was `snapshot`.
BetweenRecordedWithSnapshot == \A c \in Cells : outcome[c] = "crashbetween" =>
                                 \E k \in 1..(NumTurns - 1) : turnEnded[c][k] /\ turnNext[c][k] = "snapshot"
                                                              /\ ~promptSent[c][k + 1] /\ snapEv[c][k]
\* A turn-k snapshot exists only when the engine decided that a turn k+1 follows (turn_ended.next = snapshot).
SnapshotOnlyWhenNext       == \A c \in Cells, k \in Turns \ {NumTurns} : snapEv[c][k] => turnNext[c][k] = "snapshot"

\* Reachability witness (must be VIOLATED by the real design): every cell can end graded and
\* deleted, so safety does not pass merely because the run stalls early.
NotAllCellsFinished        == ~(\A c \in Cells : deleted[c] /\ \E p \in Passes : c \in graded[p])
NoGraceState               == \A c \in Cells : ~grace[c]
\* Witnesses for NumTurns = 2 (each must be VIOLATED): a cell completes both turns after the turn-1 snapshot, and a
\* resume classes a cell that was between turns, with its snapshot recorded.
NotAllTurnsDelivered       == ~(\E c \in Cells : outcome[c] = "done" /\ turnEnded[c][NumTurns] /\ (NumTurns = 1 \/ snapEv[c][1]))
NotCrashBetween            == ~(\E c \in Cells : outcome[c] = "crashbetween" /\ snapEv[c][1])

(* Liveness *)
DecisionEventuallyResolved == (decision = "open") ~> (decision = "resolved")
StopReachesTerminal        == controlFile["stop"] ~>
                                (stopApplied /\ \A c \in Cells :
                                   (intent[c] => outcome[c] # "none" /\ proc[c] # "running"))
EndedCellsGetArchived      == \A c \in Cells : (outcome[c] # "none") ~> archived[c]
PromptedCellsEnd           == \A c \in Cells : AnyPrompted(c) ~> outcome[c] # "none"
\* With GradedOncePerPass, "each cell is graded exactly once" (US-44) in the engine's pass.
ArchivedCellsGetGraded     == \A c \in Cells :
                                archived[c] ~> (\E p \in Passes : c \in graded[p] /\ passState[p] = "done")
=============================================================================
