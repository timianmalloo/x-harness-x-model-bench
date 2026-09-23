--------------------------- MODULE run_lifecycle ---------------------------
(***************************************************************************)
(* The lifecycle of one harness-bench run (spec US-44; ADR-0006, ADR-0007). *)
(* Version 2 (after the design gate).                                      *)
(*                                                                         *)
(* One run engine process that can crash and be resumed; cell containers   *)
(* that outlive a crash, can fail on their own, and die asynchronously    *)
(* after a kill; a write-ahead intent log; a prompt_sent record that a    *)
(* worker queues and the engine persists before the prompt goes out; kill *)
(* first, record the outcome after the container is gone; a control       *)
(* mailbox (stop, a decision answer); one decision request with a timeout; *)
(* archive-then-delete; and grading passes that the engine and a          *)
(* concurrent `bench grade` process run under a mutual-exclusion lock.    *)
(*                                                                         *)
(* BUG selects one seeded defect ("none" for the real design). Every       *)
(* invariant and property below has a variant that TLC must reject;       *)
(* tools/check_models.py asserts both directions.                          *)
(***************************************************************************)
EXTENDS Naturals, FiniteSets, TLC

CONSTANTS
    Cells,          \* the plan's cells
    COORD,          \* the coordinator session (never a cell)
    Parallelism,    \* at most this many cell containers run at once
    MaxCrashes,     \* engine crashes explored
    Passes,         \* grading pass ids (each process mints its own)
    Graders,        \* processes that may grade: {"engine"} or {"engine", "bench"}
    BUG             \* "none" or one seeded defect name

ASSUME COORD \notin Cells
ASSUME Parallelism \in Nat \ {0}
ASSUME "engine" \in Graders /\ Graders \subseteq {"engine", "bench"}

AllCells   == Cells \cup {COORD}
Launchable == IF BUG = "coordinator_cell" THEN AllCells ELSE Cells
Controls   == {"stop", "answer"}
Outcomes   == {"none", "done", "timedout", "failed", "stopped", "crashfail"}
Reasons    == {"none", "timeout", "stop"}

VARIABLES
    engine,         \* "up" | "down"
    crashes,
    reconciling,    \* after a resume: no launch until reconciliation completes
    reconciled,     \* active cells reconciled in this incarnation
    intent,         \* [cell -> BOOLEAN]  ledger: cell.launch_intent
    launchEpoch,    \* [cell -> Nat]      incarnation that created the container
    epoch,          \* engine incarnation
    container,      \* [cell -> {"none","running","exited"}]  physical
    killRequested,  \* [cell -> BOOLEAN]  docker kill issued, container not yet gone
    killReason,     \* [cell -> Reasons]  why the engine killed it (process memory)
    queued,         \* [cell -> BOOLEAN]  worker queued prompt_sent, not yet persisted (volatile)
    promptSent,     \* [cell -> BOOLEAN]  ledger: cell.prompt_sent (fsynced, then acked to the worker)
    pendingSend,    \* [cell -> BOOLEAN]  worker holds the ack and will send once (volatile)
    prompts,        \* [cell -> Nat]      physical prompts delivered (history)
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
    graded,         \* [Passes -> SUBSET AllCells]
    gradeCount,     \* [Passes -> [AllCells -> Nat]]  history
    flags           \* history of forbidden events

vars == <<engine, crashes, reconciling, reconciled, intent, launchEpoch, epoch, container,
          killRequested, killReason, queued, promptSent, pendingSend, prompts, outcome,
          wasStopped, archived, deleted, controlFile, controlApplied, applyCount, stopApplied,
          decision, resolutions, lock, passState, passOwner, graded, gradeCount, flags>>

FlagNames == {"launchAfterStop", "launchWhileOpen", "gradeUnarchived", "archiveLive",
              "promptAfterOutcome", "launchBesideOrphan"}

-----------------------------------------------------------------------------
Active(c)  == intent[c] /\ outcome[c] = "none"
Running    == {c \in AllCells : container[c] = "running"}
OrphanRunning == \E d \in AllCells : container[d] = "running" /\ launchEpoch[d] < epoch
Flag(f)    == flags' = [flags EXCEPT ![f] = TRUE]
Record(c, o) ==
    /\ outcome' = [outcome EXCEPT ![c] = o]
    /\ wasStopped' = [wasStopped EXCEPT ![c] = (@ \/ o = "stopped")]

Init ==
    /\ engine = "up" /\ crashes = 0 /\ epoch = 1
    /\ reconciling = FALSE /\ reconciled = {}
    /\ intent = [c \in AllCells |-> FALSE]
    /\ launchEpoch = [c \in AllCells |-> 0]
    /\ container = [c \in AllCells |-> "none"]
    /\ killRequested = [c \in AllCells |-> FALSE]
    /\ killReason = [c \in AllCells |-> "none"]
    /\ queued = [c \in AllCells |-> FALSE]
    /\ promptSent = [c \in AllCells |-> FALSE]
    /\ pendingSend = [c \in AllCells |-> FALSE]
    /\ prompts = [c \in AllCells |-> 0]
    /\ outcome = [c \in AllCells |-> "none"]
    /\ wasStopped = [c \in AllCells |-> FALSE]
    /\ archived = [c \in AllCells |-> FALSE]
    /\ deleted = [c \in AllCells |-> FALSE]
    /\ controlFile = [k \in Controls |-> FALSE]
    /\ controlApplied = [k \in Controls |-> FALSE]
    /\ applyCount = [k \in Controls |-> 0]
    /\ stopApplied = FALSE
    /\ decision = "none" /\ resolutions = 0
    /\ lock = "free"
    /\ passState = [p \in Passes |-> "idle"]
    /\ passOwner = [p \in Passes |-> "none"]
    /\ graded = [p \in Passes |-> {}]
    /\ gradeCount = [p \in Passes |-> [c \in AllCells |-> 0]]
    /\ flags = [f \in FlagNames |-> FALSE]

EngineReady == engine = "up" /\ ~reconciling

-----------------------------------------------------------------------------
(* Launch: intent -> container -> prompt_sent queued -> persisted + acked -> prompt *)

WriteIntent(c) ==
    /\ EngineReady
    /\ ~intent[c] /\ outcome[c] = "none"
    /\ (BUG = "launch_after_stop" \/ ~stopApplied)
    /\ (BUG = "launch_while_open" \/ decision # "open")
    /\ intent' = [intent EXCEPT ![c] = TRUE]
    /\ IF stopApplied THEN Flag("launchAfterStop")
       ELSE IF decision = "open" THEN Flag("launchWhileOpen") ELSE UNCHANGED flags
    /\ UNCHANGED <<engine, crashes, reconciling, reconciled, launchEpoch, epoch, container,
                   killRequested, killReason, queued, promptSent, pendingSend, prompts, outcome,
                   wasStopped, archived, deleted, controlFile, controlApplied, applyCount,
                   stopApplied, decision, resolutions, lock, passState, passOwner, graded,
                   gradeCount>>

CreateContainer(c) ==
    /\ EngineReady
    /\ intent[c] /\ ~promptSent[c]
    /\ (BUG = "launch_after_outcome" \/ outcome[c] = "none")
    /\ (container[c] = "none" \/ (BUG = "launch_after_outcome" /\ container[c] = "exited"))
    /\ (BUG = "launch_after_stop" \/ ~stopApplied)
    \* Parallelism is enforced where a container starts, counting every running container,
    \* including one that was killed and has not yet exited (the slot is held until confirmed).
    /\ (BUG = "exceed_parallelism" \/ Cardinality(Running) < Parallelism)
    /\ container' = [container EXCEPT ![c] = "running"]
    /\ launchEpoch' = [launchEpoch EXCEPT ![c] = epoch]
    /\ IF stopApplied THEN Flag("launchAfterStop")
       ELSE IF OrphanRunning THEN Flag("launchBesideOrphan") ELSE UNCHANGED flags
    /\ UNCHANGED <<engine, crashes, reconciling, reconciled, intent, epoch, killRequested,
                   killReason, queued, promptSent, pendingSend, prompts, outcome, wasStopped,
                   archived, deleted, controlFile, controlApplied, applyCount, stopApplied,
                   decision, resolutions, lock, passState, passOwner, graded, gradeCount>>

\* The container could not be created (image or create failure): recorded, never prompted.
CreateFails(c) ==
    /\ EngineReady
    /\ Active(c) /\ container[c] = "none" /\ ~promptSent[c] /\ ~queued[c]
    /\ Record(c, "failed")
    /\ UNCHANGED <<engine, crashes, reconciling, reconciled, intent, launchEpoch, epoch,
                   container, killRequested, killReason, queued, promptSent, pendingSend,
                   prompts, archived, deleted, controlFile, controlApplied, applyCount,
                   stopApplied, decision, resolutions, lock, passState, passOwner, graded,
                   gradeCount, flags>>

\* The worker queues prompt_sent for the engine thread (volatile until persisted).
QueuePromptSent(c) ==
    /\ EngineReady
    /\ container[c] = "running" /\ ~killRequested[c]
    /\ (BUG = "launch_after_outcome" \/ outcome[c] = "none")
    /\ ~promptSent[c] /\ ~queued[c]
    /\ queued' = [queued EXCEPT ![c] = TRUE]
    /\ pendingSend' = IF BUG = "send_before_persist"
                        THEN [pendingSend EXCEPT ![c] = TRUE] ELSE pendingSend
    /\ UNCHANGED <<engine, crashes, reconciling, reconciled, intent, launchEpoch, epoch,
                   container, killRequested, killReason, promptSent, prompts, outcome,
                   wasStopped, archived, deleted, controlFile, controlApplied, applyCount,
                   stopApplied, decision, resolutions, lock, passState, passOwner, graded,
                   gradeCount, flags>>

\* The engine thread appends and fsyncs prompt_sent, then acks the worker.
PersistPromptSent(c) ==
    /\ engine = "up"
    /\ queued[c]
    /\ promptSent' = [promptSent EXCEPT ![c] = TRUE]
    /\ queued' = [queued EXCEPT ![c] = FALSE]
    /\ pendingSend' = [pendingSend EXCEPT ![c] = TRUE]
    /\ UNCHANGED <<engine, crashes, reconciling, reconciled, intent, launchEpoch, epoch,
                   container, killRequested, killReason, prompts, outcome, wasStopped,
                   archived, deleted, controlFile, controlApplied, applyCount, stopApplied,
                   decision, resolutions, lock, passState, passOwner, graded, gradeCount,
                   flags>>

\* The worker sends the prompt once, only after the ack.
SendPrompt(c) ==
    /\ engine = "up"
    /\ pendingSend[c]
    /\ container[c] = "running" /\ ~killRequested[c]
    /\ prompts' = [prompts EXCEPT ![c] = @ + 1]
    /\ pendingSend' = [pendingSend EXCEPT ![c] = FALSE]
    /\ IF outcome[c] # "none" THEN Flag("promptAfterOutcome") ELSE UNCHANGED flags
    /\ UNCHANGED <<engine, crashes, reconciling, reconciled, intent, launchEpoch, epoch,
                   container, killRequested, killReason, queued, promptSent, outcome,
                   wasStopped, archived, deleted, controlFile, controlApplied, applyCount,
                   stopApplied, decision, resolutions, lock, passState, passOwner, graded,
                   gradeCount>>

\* Environment: the container exits on its own (agent finished, or it failed before a prompt).
ContainerExits(c) ==
    /\ container[c] = "running" /\ ~killRequested[c]
    /\ container' = [container EXCEPT ![c] = "exited"]
    /\ UNCHANGED <<engine, crashes, reconciling, reconciled, intent, launchEpoch, epoch,
                   killRequested, killReason, queued, promptSent, pendingSend, prompts,
                   outcome, wasStopped, archived, deleted, controlFile, controlApplied,
                   applyCount, stopApplied, decision, resolutions, lock, passState, passOwner,
                   graded, gradeCount, flags>>

\* Environment: a requested kill takes effect (the engine retries until inspect confirms).
ContainerDies(c) ==
    /\ container[c] = "running" /\ killRequested[c]
    /\ container' = [container EXCEPT ![c] = "exited"]
    /\ killRequested' = [killRequested EXCEPT ![c] = FALSE]
    /\ UNCHANGED <<engine, crashes, reconciling, reconciled, intent, launchEpoch, epoch,
                   killReason, queued, promptSent, pendingSend, prompts, outcome, wasStopped,
                   archived, deleted, controlFile, controlApplied, applyCount, stopApplied,
                   decision, resolutions, lock, passState, passOwner, graded, gradeCount,
                   flags>>

\* The engine records how an exited container's cell ended (never while it runs).
RecordExit(c) ==
    /\ EngineReady
    /\ Active(c) /\ ~killRequested[c]
    /\ \/ container[c] = "exited"
       \/ BUG = "record_while_running" /\ container[c] = "running"   \* seeded: records, never kills
    /\ Record(c, CASE killReason[c] = "stop"    -> "stopped"
                   [] killReason[c] = "timeout" -> "timedout"
                   [] prompts[c] >= 1           -> "done"
                   [] OTHER                     -> "failed")
    /\ UNCHANGED <<engine, crashes, reconciling, reconciled, intent, launchEpoch, epoch,
                   container, killRequested, killReason, queued, promptSent, pendingSend,
                   prompts, archived, deleted, controlFile, controlApplied, applyCount,
                   stopApplied, decision, resolutions, lock, passState, passOwner, graded,
                   gradeCount, flags>>

\* Budget or handshake deadline: kill first; the outcome is recorded after the container is gone.
EngineKill(c) ==
    /\ BUG # "no_budget_kill"
    /\ EngineReady
    /\ Active(c) /\ container[c] = "running" /\ ~killRequested[c]
    /\ killRequested' = [killRequested EXCEPT ![c] = TRUE]
    /\ killReason' = [killReason EXCEPT ![c] = "timeout"]
    /\ UNCHANGED <<engine, crashes, reconciling, reconciled, intent, launchEpoch, epoch,
                   container, queued, promptSent, pendingSend, prompts, outcome, wasStopped,
                   archived, deleted, controlFile, controlApplied, applyCount, stopApplied,
                   decision, resolutions, lock, passState, passOwner, graded, gradeCount,
                   flags>>

-----------------------------------------------------------------------------
(* Stop: kill every running cell, then record stopped; cells never launched stay unstarted *)

StopCell(c) ==
    /\ EngineReady /\ stopApplied
    /\ Active(c)
    /\ ~(container[c] = "running" /\ killReason[c] = "stop")
    /\ IF container[c] = "running" /\ BUG = "record_without_kill"
         THEN /\ Record(c, "stopped")                        \* seeded: records, never kills
              /\ UNCHANGED <<killRequested, killReason>>
       ELSE IF container[c] = "running"
         THEN /\ killRequested' = [killRequested EXCEPT ![c] = TRUE]
              /\ killReason' = [killReason EXCEPT ![c] = "stop"]
              /\ UNCHANGED <<outcome, wasStopped>>
         ELSE /\ Record(c, "stopped")
              /\ UNCHANGED <<killRequested, killReason>>
    /\ UNCHANGED <<engine, crashes, reconciling, reconciled, intent, launchEpoch, epoch,
                   container, queued, promptSent, pendingSend, prompts, archived, deleted,
                   controlFile, controlApplied, applyCount, stopApplied, decision, resolutions,
                   lock, passState, passOwner, graded, gradeCount, flags>>

-----------------------------------------------------------------------------
(* Archive, then delete *)

\* Archive only after the outcome is recorded and the container is gone. The seeded bug archives as
\* soon as a kill has been issued, without waiting for inspect to confirm the container exited.
Archive(c) ==
    /\ engine = "up"
    /\ ~archived[c]
    /\ \/ outcome[c] # "none" /\ container[c] # "running"
       \/ BUG = "archive_live" /\ killRequested[c]
    /\ archived' = [archived EXCEPT ![c] = TRUE]
    /\ IF container[c] = "running" THEN Flag("archiveLive") ELSE UNCHANGED flags
    /\ UNCHANGED <<engine, crashes, reconciling, reconciled, intent, launchEpoch, epoch,
                   container, killRequested, killReason, queued, promptSent, pendingSend,
                   prompts, outcome, wasStopped, deleted, controlFile, controlApplied,
                   applyCount, stopApplied, decision, resolutions, lock, passState, passOwner,
                   graded, gradeCount>>

DeleteWorkspace(c) ==
    /\ engine = "up"
    /\ ~deleted[c] /\ outcome[c] # "none"
    /\ (BUG = "delete_before_archive" \/ archived[c])
    /\ deleted' = [deleted EXCEPT ![c] = TRUE]
    /\ UNCHANGED <<engine, crashes, reconciling, reconciled, intent, launchEpoch, epoch,
                   container, killRequested, killReason, queued, promptSent, pendingSend,
                   prompts, outcome, wasStopped, archived, controlFile, controlApplied,
                   applyCount, stopApplied, decision, resolutions, lock, passState, passOwner,
                   graded, gradeCount, flags>>

-----------------------------------------------------------------------------
(* Control mailbox: control.applied is recorded before the file is removed *)

WriteControl(k) ==
    /\ ~controlFile[k] /\ ~controlApplied[k]
    /\ controlFile' = [controlFile EXCEPT ![k] = TRUE]
    /\ UNCHANGED <<engine, crashes, reconciling, reconciled, intent, launchEpoch, epoch,
                   container, killRequested, killReason, queued, promptSent, pendingSend,
                   prompts, outcome, wasStopped, archived, deleted, controlApplied,
                   applyCount, stopApplied, decision, resolutions, lock, passState, passOwner,
                   graded, gradeCount, flags>>

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
    /\ UNCHANGED <<engine, crashes, reconciling, reconciled, intent, launchEpoch, epoch,
                   container, killRequested, killReason, queued, promptSent, pendingSend,
                   prompts, outcome, wasStopped, archived, deleted, controlFile, lock,
                   passState, passOwner, graded, gradeCount, flags>>

ApplyAnswer ==
    /\ engine = "up"
    /\ controlFile["answer"]
    /\ (BUG = "apply_twice" \/ ~controlApplied["answer"])
    /\ controlApplied' = [controlApplied EXCEPT !["answer"] = TRUE]
    /\ applyCount' = [applyCount EXCEPT !["answer"] = @ + 1]
    /\ IF decision = "open" \/ (BUG = "double_resolution" /\ decision = "resolved")
         THEN /\ decision' = "resolved" /\ resolutions' = resolutions + 1
         ELSE UNCHANGED <<decision, resolutions>>
    /\ UNCHANGED <<engine, crashes, reconciling, reconciled, intent, launchEpoch, epoch,
                   container, killRequested, killReason, queued, promptSent, pendingSend,
                   prompts, outcome, wasStopped, archived, deleted, controlFile, stopApplied,
                   lock, passState, passOwner, graded, gradeCount, flags>>

RemoveControl(k) ==
    /\ engine = "up"
    /\ controlFile[k] /\ controlApplied[k]
    /\ controlFile' = [controlFile EXCEPT ![k] = FALSE]
    /\ UNCHANGED <<engine, crashes, reconciling, reconciled, intent, launchEpoch, epoch,
                   container, killRequested, killReason, queued, promptSent, pendingSend,
                   prompts, outcome, wasStopped, archived, deleted, controlApplied,
                   applyCount, stopApplied, decision, resolutions, lock, passState, passOwner,
                   graded, gradeCount, flags>>

-----------------------------------------------------------------------------
(* One decision request with a timeout default *)

RaiseDecision ==
    /\ engine = "up" /\ decision = "none" /\ ~stopApplied
    /\ decision' = "open"
    /\ UNCHANGED <<engine, crashes, reconciling, reconciled, intent, launchEpoch, epoch,
                   container, killRequested, killReason, queued, promptSent, pendingSend,
                   prompts, outcome, wasStopped, archived, deleted, controlFile,
                   controlApplied, applyCount, stopApplied, resolutions, lock, passState,
                   passOwner, graded, gradeCount, flags>>

TimeoutDefault ==
    /\ BUG # "no_timeout"
    /\ engine = "up" /\ decision = "open"
    /\ decision' = "resolved" /\ resolutions' = resolutions + 1
    /\ UNCHANGED <<engine, crashes, reconciling, reconciled, intent, launchEpoch, epoch,
                   container, killRequested, killReason, queued, promptSent, pendingSend,
                   prompts, outcome, wasStopped, archived, deleted, controlFile,
                   controlApplied, applyCount, stopApplied, lock, passState, passOwner,
                   graded, gradeCount, flags>>

-----------------------------------------------------------------------------
(* Crash and resume: process memory (queue, acks, kill reasons) and the engine's lock are lost *)

Crash ==
    /\ engine = "up" /\ crashes < MaxCrashes
    /\ engine' = "down" /\ crashes' = crashes + 1
    /\ queued' = [c \in AllCells |-> FALSE]
    /\ pendingSend' = [c \in AllCells |-> FALSE]
    /\ killReason' = [c \in AllCells |-> "none"]
    /\ lock' = IF lock = "engine" THEN "free" ELSE lock
    /\ passState' = [p \in Passes |->
                       IF passOwner[p] = "engine" /\ passState[p] = "active"
                         THEN "abandoned" ELSE passState[p]]
    /\ UNCHANGED <<reconciling, reconciled, intent, launchEpoch, epoch, container,
                   killRequested, promptSent, prompts, outcome, wasStopped, archived, deleted,
                   controlFile, controlApplied, applyCount, stopApplied, decision,
                   resolutions, passOwner, graded, gradeCount, flags>>

Resume ==
    /\ engine = "down"
    /\ engine' = "up" /\ epoch' = epoch + 1
    /\ reconciling' = TRUE /\ reconciled' = {}
    /\ UNCHANGED <<crashes, intent, launchEpoch, container, killRequested, killReason, queued,
                   promptSent, pendingSend, prompts, outcome, wasStopped, archived, deleted,
                   controlFile, controlApplied, applyCount, stopApplied, decision,
                   resolutions, lock, passState, passOwner, graded, gradeCount, flags>>

\* Reconciliation step 1: kill every running container carrying the run's label, whatever its outcome.
ReconcileKill(c) ==
    /\ engine = "up" /\ reconciling
    /\ container[c] = "running" /\ ~killRequested[c]
    /\ killRequested' = [killRequested EXCEPT ![c] = TRUE]
    /\ UNCHANGED <<engine, crashes, reconciling, reconciled, intent, launchEpoch, epoch,
                   container, killReason, queued, promptSent, pendingSend, prompts, outcome,
                   wasStopped, archived, deleted, controlFile, controlApplied, applyCount,
                   stopApplied, decision, resolutions, lock, passState, passOwner, graded,
                   gradeCount, flags>>

\* Reconciliation step 2 (container gone): prompted cells fail, never relaunched; unprompted
\* cells have their container removed and may launch once.
ReconcileRecord(c) ==
    /\ engine = "up" /\ reconciling
    /\ Active(c) /\ c \notin reconciled
    /\ (BUG = "reconcile_no_wait" \/ container[c] # "running")   \* seeded: records without confirming the kill
    /\ IF promptSent[c] /\ BUG # "relaunch_prompted"
         THEN /\ Record(c, "crashfail")
              /\ UNCHANGED <<container, promptSent>>
         ELSE /\ container' = [container EXCEPT ![c] = "none"]
              /\ promptSent' = IF BUG = "relaunch_prompted"
                                 THEN [promptSent EXCEPT ![c] = FALSE] ELSE promptSent
              /\ UNCHANGED <<outcome, wasStopped>>
    /\ reconciled' = reconciled \cup {c}
    /\ UNCHANGED <<engine, crashes, reconciling, intent, launchEpoch, epoch, killRequested,
                   killReason, queued, pendingSend, prompts, archived, deleted, controlFile,
                   controlApplied, applyCount, stopApplied, decision, resolutions, lock,
                   passState, passOwner, graded, gradeCount, flags>>

\* Seeded bug "relaunch_stopped": reconciliation re-opens stopped cells.
ReopenStopped(c) ==
    /\ BUG = "relaunch_stopped"
    /\ engine = "up" /\ reconciling
    /\ outcome[c] = "stopped" /\ container[c] # "running"
    /\ outcome' = [outcome EXCEPT ![c] = "none"]
    /\ container' = [container EXCEPT ![c] = "none"]
    /\ UNCHANGED <<engine, crashes, reconciling, reconciled, intent, launchEpoch, epoch,
                   killRequested, killReason, queued, promptSent, pendingSend, prompts,
                   wasStopped, archived, deleted, controlFile, controlApplied, applyCount,
                   stopApplied, decision, resolutions, lock, passState, passOwner, graded,
                   gradeCount, flags>>

ReconcileDone ==
    /\ engine = "up" /\ reconciling
    /\ \A c \in AllCells : (Active(c) => c \in reconciled)
                           /\ (BUG = "reconcile_no_wait" \/ container[c] # "running")
    /\ reconciling' = FALSE
    /\ UNCHANGED <<engine, crashes, reconciled, intent, launchEpoch, epoch, container,
                   killRequested, killReason, queued, promptSent, pendingSend, prompts,
                   outcome, wasStopped, archived, deleted, controlFile, controlApplied,
                   applyCount, stopApplied, decision, resolutions, lock, passState, passOwner,
                   graded, gradeCount, flags>>

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
    /\ UNCHANGED <<engine, crashes, reconciling, reconciled, intent, launchEpoch, epoch,
                   container, killRequested, killReason, queued, promptSent, pendingSend,
                   prompts, outcome, wasStopped, archived, deleted, controlFile,
                   controlApplied, applyCount, stopApplied, decision, resolutions, graded,
                   gradeCount, flags>>

GradeCell(p, c) ==
    /\ passState[p] = "active"
    /\ (passOwner[p] = "engine" => engine = "up")
    /\ (BUG = "grade_unarchived" \/ archived[c])
    /\ outcome[c] # "none"
    /\ (BUG = "grade_twice" \/ c \notin graded[p])
    /\ graded' = [graded EXCEPT ![p] = @ \cup {c}]
    /\ gradeCount' = [gradeCount EXCEPT ![p][c] = @ + 1]
    /\ IF ~archived[c] THEN Flag("gradeUnarchived") ELSE UNCHANGED flags
    /\ UNCHANGED <<engine, crashes, reconciling, reconciled, intent, launchEpoch, epoch,
                   container, killRequested, killReason, queued, promptSent, pendingSend,
                   prompts, outcome, wasStopped, archived, deleted, controlFile,
                   controlApplied, applyCount, stopApplied, decision, resolutions, lock,
                   passState, passOwner>>

GradeEnd(p) ==
    /\ passState[p] = "active"
    /\ (passOwner[p] = "engine" => engine = "up")
    \* The engine's pass ends only when it has graded every archived cell.
    /\ (BUG = "grade_skipped" \/ passOwner[p] # "engine"
        \/ \A c \in Cells : archived[c] => c \in graded[p])
    /\ lock' = IF lock = passOwner[p] THEN "free" ELSE lock
    /\ passState' = [passState EXCEPT ![p] = "done"]
    /\ UNCHANGED <<engine, crashes, reconciling, reconciled, intent, launchEpoch, epoch,
                   container, killRequested, killReason, queued, promptSent, pendingSend,
                   prompts, outcome, wasStopped, archived, deleted, controlFile,
                   controlApplied, applyCount, stopApplied, decision, resolutions, passOwner,
                   graded, gradeCount, flags>>

-----------------------------------------------------------------------------
Next ==
    \/ \E c \in Launchable : WriteIntent(c)
    \/ \E c \in AllCells :
          \/ CreateContainer(c) \/ CreateFails(c) \/ QueuePromptSent(c) \/ PersistPromptSent(c)
          \/ SendPrompt(c) \/ ContainerExits(c) \/ ContainerDies(c) \/ RecordExit(c)
          \/ EngineKill(c) \/ StopCell(c) \/ Archive(c) \/ DeleteWorkspace(c)
          \/ ReconcileKill(c) \/ ReconcileRecord(c) \/ ReopenStopped(c)
    \/ \E k \in Controls : WriteControl(k) \/ RemoveControl(k)
    \/ ApplyStop \/ ApplyAnswer \/ RaiseDecision \/ TimeoutDefault
    \/ Crash \/ Resume \/ ReconcileDone
    \/ \E p \in Passes : \E g \in Graders : GradeStart(p, g)
    \/ \E p \in Passes, c \in AllCells : GradeCell(p, c)
    \/ \E p \in Passes : GradeEnd(p)

\* Fairness: the engine's own progress (including the budget deadline and its grading pass), and
\* the environment honouring kills (the engine retries a kill until inspect confirms; a kill that
\* never takes effect is an infrastructure fault).
Fairness ==
    /\ WF_vars(Resume) /\ WF_vars(ReconcileDone) /\ WF_vars(TimeoutDefault)
    /\ WF_vars(ApplyStop) /\ WF_vars(ApplyAnswer)
    /\ \A c \in AllCells :
          /\ WF_vars(StopCell(c)) /\ WF_vars(ContainerDies(c)) /\ WF_vars(RecordExit(c))
          /\ WF_vars(ReconcileKill(c)) /\ WF_vars(ReconcileRecord(c)) /\ WF_vars(Archive(c))
          /\ WF_vars(EngineKill(c))
    /\ \A p \in Passes :
          /\ WF_vars(GradeStart(p, "engine")) /\ WF_vars(GradeEnd(p))
          /\ \A c \in AllCells : WF_vars(GradeCell(p, c))

Spec == Init /\ [][Next]_vars /\ Fairness

\* Cells and passes are interchangeable. Safety configuration only: TLC's symmetry reduction is
\* unsound for liveness, which is checked in a separate configuration.
Symmetry == Permutations(Cells) \cup Permutations(Passes)

-----------------------------------------------------------------------------
(* Safety invariants *)

TypeOK ==
    /\ engine \in {"up", "down"}
    /\ outcome \in [AllCells -> Outcomes]
    /\ container \in [AllCells -> {"none", "running", "exited"}]
    /\ killReason \in [AllCells -> Reasons]
    /\ decision \in {"none", "open", "resolved"}
    /\ lock \in {"free", "engine", "bench"}

CoordinatorNeverACell      == ~intent[COORD]
AtMostOnePrompt            == \A c \in AllCells : prompts[c] <= 1
NoPromptAfterOutcome       == ~flags["promptAfterOutcome"]
NoArchiveWhileLive         == ~flags["archiveLive"]
NothingDeletedUnarchived   == \A c \in AllCells : deleted[c] => archived[c]
GradedOncePerPass          == \A p \in Passes, c \in AllCells : gradeCount[p][c] <= 1
GradedOnlyWhenArchived     == ~flags["gradeUnarchived"]
AtMostOneActivePass        == Cardinality({p \in Passes : passState[p] = "active"}) <= 1
ControlAppliedOnce         == \A k \in Controls : applyCount[k] <= 1
NoLaunchAfterStop          == ~flags["launchAfterStop"]
ParallelismBound           == Cardinality(Running) <= Parallelism
StoppedNeverRelaunched     == \A c \in AllCells : wasStopped[c] => outcome[c] = "stopped"
DecisionResolvedOnce       == resolutions <= 1
NoLaunchWhileDecisionOpen  == ~flags["launchWhileOpen"]
NoLaunchBesideOrphan       == ~flags["launchBesideOrphan"]
NoOutcomeWhileRunning      == \A c \in AllCells : outcome[c] # "none" => container[c] # "running"

\* Reachability witness (must be VIOLATED by the real design): every cell can end graded and
\* deleted, so safety does not pass merely because the run stalls early.
NotAllCellsFinished        == ~(\A c \in Cells : deleted[c] /\ \E p \in Passes : c \in graded[p])

(* Liveness *)
DecisionEventuallyResolved == (decision = "open") ~> (decision = "resolved")
StopReachesTerminal        == controlFile["stop"] ~>
                                (stopApplied /\ \A c \in AllCells :
                                   (intent[c] => outcome[c] # "none" /\ container[c] # "running"))
EndedCellsGetArchived      == \A c \in Cells : (outcome[c] # "none") ~> archived[c]
PromptedCellsEnd           == \A c \in Cells : promptSent[c] ~> (outcome[c] # "none")
\* With GradedOncePerPass, "each cell is graded exactly once" (US-44) in the engine's pass.
ArchivedCellsGetGraded     == \A c \in Cells :
                                archived[c] ~> (\E p \in Passes : c \in graded[p] /\ passState[p] = "done")
=============================================================================
