---
id: note-20261003-spike-s-lb-loopback
title: "Spike S-LB - does a loopback-only listener raise a Windows Defender Firewall prompt or rule?"
type: decision-note
status: proposed
owner: "@timianmalloo"
tags: [spike, windows, firewall, loopback, adr-0018, e4]
links:
  - { to: arch-evaluation-campaign, rel: relates-to }
  - { to: design-eval-seam-contracts, rel: relates-to }
review-by: "2026-10-17"
summary: >-
  Method and operator procedure for spike S-LB. The script tools/spikes/s_lb_loopback.py was written and compiled but
  NOT run (no operator present; a bind could raise a firewall dialog nobody sees). Every result row is "not run,
  operator required". Until the table is filled and passes, ADR-0018 section 3 keeps its assume: and phase E1 admits
  in-process probes only.
---

# Spike S-LB: loopback firewall behaviour on Windows

**Question.** ADR-0018 §3 carries: "*assume:* binding `127.0.0.1` raises no Windows Defender Firewall prompt and loopback traffic is not filtered. **Confirm:** spike S-LB. **Breaks if false:** an unattended grading pass shows a modal dialog (the bind still succeeds); mitigation: a pre-created allow rule for the pinned interpreter, checked in preflight." The loopback fake (X-LB) and the E4 resilience tasks wait on this.

**Procedure and pass rule (architecture, quoted).** "A stdlib script, run once per platform with the operator present: (1) copy the interpreter to a fresh path so no existing firewall rule matches; (2) bind `127.0.0.1:0`, connect from a second process, exchange one request; (3) record whether a dialog appeared and diff `Get-NetFirewallRule` (Windows) or `socketfilterfw --listapps` (macOS) before and after; (4) positive control: the same with `0.0.0.0`, which must produce a prompt or a rule, so the probe is shown able to see one. Pass = no prompt and no new rule for the loopback bind, and the positive control fires." macOS is out of scope for this dispatch.

## Method (what the script does; written 2026-10-03, not run)

`tools/spikes/s_lb_loopback.py`, stdlib only, `--mode loopback|positive-control|report`.

1. **Fresh interpreter.** Copies `python.exe` and the top-level DLLs of `sys.base_prefix` to `%TEMP%\slb-*\py\`, a path no rule names. The copy runs with `PYTHONHOME=sys.base_prefix` so it finds the standard library.
2. **Bind and exchange.** The copy is the **server**: it binds `(host, 0)` (`127.0.0.1`, or `0.0.0.0` for the control), prints the port, accepts one connection, uppercases `ping` to `PING`. A **second process** (the original interpreter) is the client and connects to `127.0.0.1:<port>`. `exchange_ok` is true only if the client read `PING`. The server stays bound for `--settle` seconds (default 15) so a late dialog or rule can appear.
3. **Dialog and rule diff.** `Get-NetFirewallRule` joined to `Get-NetFirewallApplicationFilter` is snapshotted before the bind and after the settle. `new_rules` is the rows present only after. The operator answers one prompt, "Did a Windows Defender Firewall dialog appear? [y/n]", recorded as `dialog_seen` (or pass `--dialog yes|no` to script the answer).
4. **Positive control.** The same run with `0.0.0.0`.
5. **Verdict (`--mode report`).** Reads `<out>/loopback.json` and `<out>/positive-control.json`. `PASS` only if loopback has `dialog_seen` false, `new_rules` empty and `exchange_ok`, and the control has a dialog or a new rule. Any value not recorded (snapshot unreadable, no tty and no `--dialog`, exchange failed) gives `INCONCLUSIVE`, never a guessed pass. A fired loopback gives `FAIL loopback fired`.

Each run mode prints one JSON document and writes `<out>/<mode>.json` (default `%TEMP%\slb-out`). The result also carries a `cleanup` line.

**Checked offline (no socket):** `python -m py_compile` exit 0; `--mode report` on hand-written files gives `PASS` for (no dialog, no rules, control fired) and `INCONCLUSIVE` for `dialog_seen: null`; omitting `--mode` is an argparse error. The bind paths were not exercised.

## Operator procedure (Windows 11, operator at the screen)

Run from the repo root, in a normal (non-elevated) terminal. Reading firewall rules works without elevation; removing rules does not.

```
python tools/spikes/s_lb_loopback.py --mode loopback
python tools/spikes/s_lb_loopback.py --mode positive-control
python tools/spikes/s_lb_loopback.py --mode report
```

What to expect:

- **loopback:** a ~15 s pause, then the question about a dialog. **Expected: no dialog.** Answer `n`. Output: `dialog_seen: false`, `new_rules: []`, `exchange_ok: true`. If a dialog does appear, answer `y` and press either button; that is the failure the spike looks for.
- **positive-control:** **expected: a "Windows Defender Firewall has blocked some features of this app" dialog** naming the copied `python.exe` under `%TEMP%\slb-*\py\`. **Either button works** (the spike needs the dialog seen, not a choice); Cancel is the safer one. Answer `y` to the question. A new rule may also appear in `new_rules`. If no dialog and no rule appear, the probe cannot see one and the run is `INCONCLUSIVE`: check that the profile has the firewall on (`Get-NetFirewallProfile`).
- **report:** prints `{"verdict": "PASS"}`, `FAIL loopback fired`, or `INCONCLUSIVE ...`.
- **Cleanup:** if the control created rules, remove them from an elevated shell using the `cleanup` line in `positive-control.json`, then delete the `slb-*` folder under `%TEMP%`.

Then paste the three JSON outputs and the verdict into the table below, with host build (`[Environment]::OSVersion`), interpreter version and firewall profile.

## Results (empty until the operator runs it)

| Run | dialog_seen | new_rules | exchange_ok | Result |
| --- | --- | --- | --- | --- |
| loopback `127.0.0.1:0` | not run, operator required | not run, operator required | not run, operator required | not run, operator required |
| positive control `0.0.0.0:0` | not run, operator required | not run, operator required | not run, operator required | not run, operator required |
| report verdict | - | - | - | not run, operator required |

**On PASS:** retire the `assume:` in ADR-0018 §3 (cite this note) and admit `interface: loopback` for E4. **On FAIL:** adopt ADR-0018's stated mitigation (a pre-created allow rule for the pinned interpreter, checked in preflight) and raise a decision request.

**Gate:** no lens review; the operator's run is the evidence (B-2). **Limits:** one host, one firewall profile, one interpreter path; a managed enterprise host with group-policy rules may differ.
