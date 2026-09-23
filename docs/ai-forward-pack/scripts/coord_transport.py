#!/usr/bin/env python3
"""Bounded POSIX ACP / Agy session IO. Native harness policy remains authoritative.

This is a lifecycle adapter, not an editor proxy or an approval broker. Only
locally selected operational fields leave this module; wire bodies are discarded.
"""
import copy
import json
import math
import os
from pathlib import Path
import re
import selectors
import signal
import stat
import subprocess
import sys
import threading
import time

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))
from platform_process import (  # noqa: E402
    WindowsJob as _WindowsJob,
    release_windows_gate,
    spawn_windows_gate,
    terminate_owned_process,
    wait_after_termination,
)


MAX_INPUT_BYTES = 16 * 1024 * 1024
POLL_SECONDS = 0.1
CLEANUP_SECONDS = 4.0


def file_root_identities(paths, missing_path=None):
    """Validate explicit file access; content may append without changing identity.

    Only preparation may defer its exact future session log until worktree registration.
    """
    if not isinstance(paths, list) or len(paths) > 3:
        raise ValueError("invalid_file_roots")
    identities = []
    seen = set()
    for value in paths:
        if not isinstance(value, str) or not value or len(value) > 4096 or "\0" in value or value in seen:
            raise ValueError("invalid_file_roots")
        seen.add(value)
        path = Path(value)
        if not path.is_absolute() or str(path.resolve()) != value:
            raise ValueError("invalid_file_roots")
        try:
            info = path.lstat()
        except FileNotFoundError:
            if value == missing_path and path.parent.is_dir():
                continue
            raise ValueError("invalid_file_roots") from None
        if not stat.S_ISREG(info.st_mode):
            raise ValueError("invalid_file_roots")
        identities.append({"path": value, "device": info.st_dev, "inode": info.st_ino})
    return identities


class _Failure(Exception):
    def __init__(self, code, outcome="failed"):
        super().__init__(code)
        self.code = code
        self.outcome = outcome


def _identifier(value):
    return isinstance(value, str) and re.fullmatch(r"[A-Za-z0-9._:/+-]{1,256}", value) is not None


def _signal_group(process, sig):
    # macOS can return EPERM for an unreaped zombie. Reap before signalling,
    # and retry once if exit raced the first poll. Still signal live descendants.
    process.poll()
    for attempt in range(2):
        try:
            os.killpg(process.pid, sig)
            return None
        except ProcessLookupError:
            return None
        except PermissionError:
            if attempt == 0 and process.poll() is not None:
                continue
            return "group_signal_failed"
        except OSError:
            return "group_signal_failed"
    return "group_signal_failed"


class _Wire:
    """One bounded input frame and output buffer; no transcript or message queue."""

    def __init__(self, deadline, output_limit, cancelled, result):
        self.process = None
        self.deadline = deadline
        self.output_limit = output_limit
        self.cancelled = cancelled
        self.result = result
        self.selector = selectors.DefaultSelector()
        self.incoming = bytearray()
        self.outgoing = bytearray()
        self.stdout_eof = False
        self.safe_shutdown_output = False

    def attach(self, process):
        self.process = process
        for stream, label in ((process.stdout, "stdout"), (process.stderr, "stderr")):
            os.set_blocking(stream.fileno(), False)
            self.selector.register(stream, selectors.EVENT_READ, label)
        os.set_blocking(process.stdin.fileno(), False)

    def check(self):
        if time.monotonic() >= self.deadline:
            raise _Failure("deadline_exceeded")
        try:
            cancelled = self.cancelled()
        except Exception:
            raise _Failure("callback_failed") from None
        if cancelled:
            raise _Failure("cancelled", "cancelled")

    def queue(self, message):
        self.safe_shutdown_output = False
        payload = (json.dumps(message, ensure_ascii=False, separators=(",", ":")) + "\n").encode("utf-8")
        if len(payload) + len(self.outgoing) > MAX_INPUT_BYTES:
            raise _Failure("input_limit_exceeded")
        if not self.outgoing:
            self.selector.register(self.process.stdin, selectors.EVENT_WRITE, "stdin")
        self.outgoing.extend(payload)

    def pump(self, timeout):
        for key, _ in self.selector.select(timeout):
            if key.data == "stdin":
                try:
                    count = os.write(key.fd, memoryview(self.outgoing)[:65536])
                except BlockingIOError:
                    continue
                except BrokenPipeError:
                    raise _Failure("early_eof") from None
                del self.outgoing[:count]
                if not self.outgoing:
                    self.selector.unregister(key.fileobj)
                continue
            remaining = self.output_limit - self.result["stdout_bytes"] - self.result["stderr_bytes"]
            if remaining < 0:
                raise _Failure("output_limit_exceeded")
            try:
                data = os.read(key.fd, min(65536, max(1, remaining + 1)))
            except BlockingIOError:
                continue
            if not data:
                self.selector.unregister(key.fileobj)
                if key.data == "stdout":
                    self.stdout_eof = True
                continue
            self.result[key.data + "_bytes"] += len(data)
            if len(data) > remaining:
                raise _Failure("output_limit_exceeded")
            if key.data == "stdout":
                self.incoming.extend(data)

    def receive(self):
        while True:
            self.check()
            newline = self.incoming.find(b"\n")
            if newline >= 0:
                line = bytes(self.incoming[:newline])
                del self.incoming[:newline + 1]
                try:
                    value = json.loads(line.decode("utf-8"))
                except (ValueError, UnicodeError, RecursionError):
                    raise _Failure("protocol_error") from None
                if not isinstance(value, dict):
                    raise _Failure("protocol_error")
                return value
            if self.stdout_eof:
                raise _Failure("protocol_error" if self.incoming else "early_eof")
            self.pump(min(POLL_SECONDS, max(0, self.deadline - time.monotonic())))

    def flush_input(self):
        while self.outgoing:
            self.check()
            self.pump(min(POLL_SECONDS, max(0, self.deadline - time.monotonic())))

    def cleanup(self, session_id, graceful):
        """Always kill our group, even if the direct child has already exited."""
        if self.process is None:
            self.selector.close()
            return None
        cleanup_end = min(time.monotonic() + CLEANUP_SECONDS, self.deadline + CLEANUP_SECONDS)
        error = None
        if graceful and session_id and (not self.outgoing or self.safe_shutdown_output):
            try:
                self.queue({"jsonrpc": "2.0", "method": "session/cancel", "params": {"sessionId": session_id}})
                grace_end = min(cleanup_end, time.monotonic() + .2)
                while time.monotonic() < grace_end:
                    self.pump(min(.05, max(0, grace_end - time.monotonic())))
            except (OSError, _Failure):
                pass  # Best effort; group termination below is unconditional.
        error = _signal_group(self.process, signal.SIGTERM)
        try:
            self.process.wait(timeout=max(0, min(.2, cleanup_end - time.monotonic())))
        except subprocess.TimeoutExpired:
            pass
        error = _signal_group(self.process, signal.SIGKILL) or error
        try:
            self.process.wait(timeout=max(0, cleanup_end - time.monotonic()))
        except subprocess.TimeoutExpired:
            error = "process_reap_failed"
        finally:
            self.selector.close()
            for stream in (self.process.stdin, self.process.stdout, self.process.stderr):
                stream.close()
        return error


class _ThreadedWire:
    def __init__(self, deadline, output_limit, cancelled, result):
        self.process = None
        self.deadline = deadline
        self.output_limit = output_limit
        self.cancelled = cancelled
        self.result = result
        self.incoming = bytearray()
        self.outgoing = bytearray()
        self.stdout_eof = False
        self.safe_shutdown_output = False
        self._closed = False
        self._writer_broken = False
        self._output_error = None
        self._condition = threading.Condition()
        self._threads = []

    def attach(self, process):
        self.process = process
        self._threads = [
            threading.Thread(target=self._read_stdout, daemon=True),
            threading.Thread(target=self._read_stderr, daemon=True),
            threading.Thread(target=self._write_stdin, daemon=True),
        ]
        for thread in self._threads:
            thread.start()

    def _consume_budget(self, label, data):
        with self._condition:
            remaining = self.output_limit - self.result["stdout_bytes"] - self.result["stderr_bytes"]
            self.result[label + "_bytes"] += len(data)
            if len(data) > remaining:
                self._output_error = "output_limit_exceeded"
                self._condition.notify_all()
                return False
            if label == "stdout":
                self.incoming.extend(data)
            self._condition.notify_all()
            return True

    def _read_stdout(self):
        while True:
            with self._condition:
                if self._closed:
                    return
                remaining = self.output_limit - self.result["stdout_bytes"] - self.result["stderr_bytes"]
                size = min(65536, max(1, remaining + 1))
            try:
                data = self.process.stdout.read(size)
            except OSError:
                data = b""
            if not data:
                with self._condition:
                    self.stdout_eof = True
                    self._condition.notify_all()
                return
            if not self._consume_budget("stdout", data):
                return

    def _read_stderr(self):
        while True:
            with self._condition:
                if self._closed:
                    return
                remaining = self.output_limit - self.result["stdout_bytes"] - self.result["stderr_bytes"]
                size = min(65536, max(1, remaining + 1))
            try:
                data = self.process.stderr.read(size)
            except OSError:
                return
            if not data:
                with self._condition:
                    self._condition.notify_all()
                return
            if not self._consume_budget("stderr", data):
                return

    def _write_stdin(self):
        while True:
            with self._condition:
                while not self.outgoing and not self._closed:
                    self._condition.wait()
                if self._closed:
                    return
                chunk = bytes(memoryview(self.outgoing)[:65536])
            try:
                count = self.process.stdin.write(chunk)
                self.process.stdin.flush()
                if count is None:
                    count = len(chunk)
            except (BrokenPipeError, OSError):
                with self._condition:
                    self._writer_broken = True
                    self._condition.notify_all()
                return
            with self._condition:
                del self.outgoing[:count]
                if not self.outgoing:
                    self._condition.notify_all()

    def check(self):
        if time.monotonic() >= self.deadline:
            raise _Failure("deadline_exceeded")
        with self._condition:
            if self._output_error is not None:
                raise _Failure(self._output_error)
            if self._writer_broken:
                raise _Failure("early_eof")
        try:
            cancelled = self.cancelled()
        except Exception:
            raise _Failure("callback_failed") from None
        if cancelled:
            raise _Failure("cancelled", "cancelled")

    def queue(self, message):
        self.safe_shutdown_output = False
        payload = (json.dumps(message, ensure_ascii=False, separators=(",", ":")) + "\n").encode("utf-8")
        with self._condition:
            if len(payload) + len(self.outgoing) > MAX_INPUT_BYTES:
                raise _Failure("input_limit_exceeded")
            self.outgoing.extend(payload)
            self._condition.notify_all()

    def pump(self, timeout):
        with self._condition:
            self._condition.wait(timeout)

    def receive(self):
        while True:
            self.check()
            with self._condition:
                newline = self.incoming.find(b"\n")
                if newline >= 0:
                    line = bytes(self.incoming[:newline])
                    del self.incoming[:newline + 1]
                elif self.stdout_eof:
                    raise _Failure("protocol_error" if self.incoming else "early_eof")
                else:
                    line = None
            if line is None:
                self.pump(min(POLL_SECONDS, max(0, self.deadline - time.monotonic())))
                continue
            try:
                value = json.loads(line.decode("utf-8"))
            except (ValueError, UnicodeError, RecursionError):
                raise _Failure("protocol_error") from None
            if not isinstance(value, dict):
                raise _Failure("protocol_error")
            return value

    def flush_input(self):
        while True:
            self.check()
            with self._condition:
                if not self.outgoing:
                    return
            self.pump(min(POLL_SECONDS, max(0, self.deadline - time.monotonic())))

    def cleanup(self, session_id, graceful):
        if self.process is None:
            return None
        cleanup_end = min(time.monotonic() + CLEANUP_SECONDS, self.deadline + CLEANUP_SECONDS)
        error = None
        if graceful and session_id and (not self.outgoing or self.safe_shutdown_output):
            try:
                self.queue({"jsonrpc": "2.0", "method": "session/cancel", "params": {"sessionId": session_id}})
                grace_end = min(cleanup_end, time.monotonic() + .2)
                while time.monotonic() < grace_end:
                    with self._condition:
                        if self._writer_broken:
                            break
                        if self.process.poll() is not None and not self.outgoing:
                            break
                    self.pump(min(.05, max(0, grace_end - time.monotonic())))
            except _Failure:
                pass
        error = terminate_owned_process(self.process, self.windows_job)
        returncode, waited_error = wait_after_termination(
            self.process, self.windows_job, lambda: terminate_owned_process(self.process, self.windows_job)
        )
        _ = returncode
        error = waited_error or error
        with self._condition:
            self._closed = True
            self._condition.notify_all()
        for stream in (self.process.stdin, self.process.stdout, self.process.stderr):
            try:
                stream.close()
            except OSError:
                pass
        for thread in self._threads:
            thread.join(timeout=max(0, cleanup_end - time.monotonic()))
        self.windows_job.close()
        return error


class _Session:
    def __init__(self, wire, result, emit, before_prompt, roots, next_prompt=None,
                 permission_handler=None, max_turns=8):
        self.wire = wire
        self.result = result
        self.emit = emit
        self.before_prompt = before_prompt
        self.roots = roots
        self.sequence = 0
        self.turn = 0
        self.last_progress = float("-inf")
        self.creating_session_id = None
        self.creating_updates = 0
        self.grok_reload_compat = False
        self.next_prompt = next_prompt
        self.permission_handler = permission_handler
        self.max_turns = max_turns

    def event(self, event, **fields):
        try:
            self.emit({"event": event, **fields})
        except Exception:
            raise _Failure("callback_failed") from None

    def admit(self):
        self.wire.check()
        try:
            admitted = self.before_prompt(max(0, self.wire.deadline - time.monotonic()))
        except Exception:
            raise _Failure("callback_failed") from None
        if self.roots:
            try:
                unchanged = file_root_identities([row["path"] for row in self.roots]) == self.roots
            except (OSError, ValueError):
                unchanged = False
            if not unchanged:
                raise _Failure("file_roots_changed", "blocked")
        self.wire.check()  # A slow admission check is charged to this attempt.
        if not admitted:
            raise _Failure("dispatch_refused", "cancelled")
        self.turn += 1
        # Conservative retry floor: even a failed observer after this point
        # cannot claim that a prompt was never admitted for dispatch.
        self.result["prompts_started"] += 1
        self.event("prompt_started", turn=self.turn)

    def callback(self, callback, *args):
        self.wire.check()
        try:
            value = callback(*args, max(0, self.wire.deadline - time.monotonic()))
        except Exception:
            raise _Failure("callback_failed") from None
        self.wire.check()
        return value

    def wait(self):
        self.wire.check()
        self.wire.pump(min(POLL_SECONDS, max(0, self.wire.deadline - time.monotonic())))
        self.wire.check()
        if self.wire.stdout_eof:
            raise _Failure("early_eof")

    def prompts(self, initial):
        yield from initial
        if self.next_prompt is None:
            return
        self.event("waiting")
        while True:
            prompt = self.callback(self.next_prompt)
            if prompt is False:
                self.event("input_closed")
                return
            if self.turn >= self.max_turns:
                raise _Failure("turn_limit_exceeded", "blocked")
            if prompt is None:
                self.wait()
                continue
            if not isinstance(prompt, str) or not prompt:
                raise _Failure("invalid_dynamic_prompt", "blocked")
            if len(prompt) > MAX_INPUT_BYTES:
                raise _Failure("input_limit_exceeded", "blocked")
            yield prompt
            self.event("waiting")

    def progress(self, count=1):
        self.result["progress_updates"] += count
        now = time.monotonic()
        if now - self.last_progress >= 1:
            self.last_progress = now
            self.event("progress", turn=self.turn, progress_updates=self.result["progress_updates"])

    def permission(self, message):
        params = message.get("params")
        if (not self.result["session_id"] or not isinstance(params, dict)
                or params.get("sessionId") != self.result["session_id"]):
            raise _Failure("protocol_error")
        options = params.get("options", [])
        tool_call = params.get("toolCall")
        if not isinstance(options, list) or not isinstance(tool_call, dict):
            raise _Failure("protocol_error")
        choices = {}
        for option in options:
            if (not isinstance(option, dict) or not _identifier(option.get("optionId"))
                    or option.get("kind") not in ("allow_once", "allow_always", "reject_once", "reject_always")
                    or option["optionId"] in choices):
                raise _Failure("protocol_error")
            choices[option["optionId"]] = option["kind"]
        self.result["permission_requests"] += 1
        action_id = "permission-" + str(self.result["permission_requests"])
        if self.permission_handler is None or self.result["permission_denials"]:
            selected = next((key for key, kind in choices.items() if kind == "reject_once"), None)
        else:
            request = {"sessionId": params["sessionId"], "requestId": message["id"],
                       "requestSequence": self.result["permission_requests"],
                       "toolCall": tool_call, "options": options}
            try:
                self.event("permission_pending", action_id=action_id)
                while True:
                    selected = self.callback(self.permission_handler, copy.deepcopy(request))
                    if selected is not None:
                        if (not isinstance(selected, str) or choices.get(selected) not in
                                ("allow_once", "reject_once", "reject_always")):
                            raise _Failure("permission_decision_invalid", "blocked")
                        break
                    self.wait()
            except _Failure:
                # The pending native request must not inherit an approval if
                # cancellation, deadline, callback or protocol handling fails.
                if not self.wire.outgoing:
                    self.wire.queue({"jsonrpc": "2.0", "id": message["id"],
                                     "result": {"outcome": {"outcome": "cancelled"}}})
                    # Cleanup may flush only this rejection, never a prompt or
                    # approval left queued when authority/callback handling failed.
                    self.wire.safe_shutdown_output = True
                raise
        outcome = {"outcome": "selected", "optionId": selected} if selected is not None else {"outcome": "cancelled"}
        self.wire.queue({"jsonrpc": "2.0", "id": message["id"], "result": {"outcome": outcome}})
        allowed = selected is not None and choices[selected] == "allow_once"
        self.result["permission_allowed" if allowed else "permission_denials"] += 1
        self.event("permission_allowed" if allowed else "permission_denied",
                   permission_requests=self.result["permission_requests"], action_id=action_id)

    def rpc(self, method, params):
        self.sequence += 1
        request_id = self.sequence
        self.wire.queue({"jsonrpc": "2.0", "id": request_id, "method": method, "params": params})
        while True:
            message = self.wire.receive()
            if message.get("jsonrpc") != "2.0":
                raise _Failure("protocol_error")
            if "method" in message:
                if (not isinstance(message["method"], str) or "result" in message or "error" in message
                        or ("params" in message and not isinstance(message["params"], (dict, list)))):
                    raise _Failure("protocol_error")
                if "id" in message:
                    if type(message["id"]) not in (str, int):
                        raise _Failure("protocol_error")
                    if message["method"] == "session/request_permission":
                        if method == "session/load":
                            # Replay identity is not yet a successfully loaded
                            # session; do not expose an approval callback here.
                            raise _Failure("protocol_error")
                        self.permission(message)
                    else:
                        self.wire.queue({"jsonrpc": "2.0", "id": message["id"], "error": {
                            "code": -32601, "message": "Method not supported"}})
                elif message["method"] == "session/update":
                    update = message.get("params")
                    if (not isinstance(update, dict) or not isinstance(update.get("update"), dict)
                            or not _identifier(update.get("sessionId"))
                            or not _identifier(update["update"].get("sessionUpdate"))):
                        raise _Failure("protocol_error")
                    if method == "session/new" and self.result["session_id"] is None:
                        # Grok 1.0.34 emits updates before the creation response.
                        # Retain identity/count only; the response grants authority.
                        if self.creating_session_id not in (None, update["sessionId"]):
                            raise _Failure("protocol_error")
                        self.creating_session_id = update["sessionId"]
                        self.creating_updates += 1
                    elif self.result["session_id"] and update["sessionId"] == self.result["session_id"]:
                        self.progress()
                    else:
                        raise _Failure("protocol_error")
                elif message["method"].startswith("_"):
                    # ACP v1 extension notifications are optional, one-way data.
                    # Count without retaining names/payloads or emitting per-item events;
                    # the same wire deadline and byte limit still bound every receive.
                    self.result["extension_notifications"] += 1
                else:
                    raise _Failure("protocol_error")
                continue
            # Grok 1.0.34 injects its own skills watcher acknowledgement into ACP.
            # This exact, measured exception never completes our pending request.
            if (self.grok_reload_compat and method == "session/prompt" and self.result["session_id"]
                    and message == {"jsonrpc": "2.0", "id": "skills-reload", "result": {"result": {"reloaded": 1}}}
                    and type(message["result"]["result"]["reloaded"]) is int):
                self.result["compatibility_responses"] += 1
                continue
            if type(message.get("id")) is not int or message["id"] != request_id:
                raise _Failure("protocol_error")
            if "error" in message:
                error = message["error"]
                if not isinstance(error, dict) or type(error.get("code")) is not int:
                    raise _Failure("protocol_error")
                if error["code"] == -32000:  # ACP schema: authentication required.
                    raise _Failure("authentication_required", "blocked")
                raise _Failure("authentication_failed" if method == "authenticate" else "remote_error")
            if not isinstance(message.get("result"), dict):
                raise _Failure("protocol_error")
            return message["result"]

    def acp(self, cwd, prompts, additional_roots, session_id, require_loaded_cwd, mode_id, expected_model):
        info = self.rpc("initialize", {"protocolVersion": 1, "clientCapabilities": {},
                                      "clientInfo": {"name": "ai-forward-coordination", "version": "1"}})
        if type(info.get("protocolVersion")) is not int or info["protocolVersion"] != 1:
            raise _Failure("protocol_error")
        if session_id is not None:
            capabilities = info.get("agentCapabilities", {})
            if not isinstance(capabilities, dict) or capabilities.get("loadSession") is not True:
                raise _Failure("unsupported_session_load", "blocked")
        agent = info.get("agentInfo", {})
        if additional_roots:
            capabilities = info.get("agentCapabilities", {})
            sessions = capabilities.get("sessionCapabilities", {}) if isinstance(capabilities, dict) else {}
            if (not isinstance(agent, dict) or agent.get("name") != "@agentclientprotocol/codex-acp"
                    or not isinstance(sessions, dict) or not isinstance(sessions.get("additionalDirectories"), dict)):
                raise _Failure("unsupported_file_roots", "blocked")
        version = agent.get("version") if isinstance(agent, dict) else None
        self.result["reported_version"] = version if _identifier(version) else None
        if self.result["reported_version"]:
            self.result["reported_version_source"] = "agentInfo.version"
        metadata = info.get("_meta", {})
        if isinstance(metadata, dict) and metadata.get("grokShell") is True:
            if self.result["reported_version"] is None and _identifier(metadata.get("agentVersion")):
                self.result["reported_version"] = metadata["agentVersion"]
                self.result["reported_version_source"] = "grok._meta.agentVersion"
            self.grok_reload_compat = (metadata.get("agentVersion") == "1.0.34"
                                       and self.result["reported_version"] == "1.0.34")
        auth = info.get("authMethods", [])
        if not isinstance(auth, list):
            raise _Failure("protocol_error")
        if any(isinstance(item, dict) and item.get("id") == "cached_token" for item in auth):
            self.rpc("authenticate", {"methodId": "cached_token", "_meta": {"headless": True}})
        params = {"cwd": os.fspath(cwd), "mcpServers": []}
        if additional_roots:
            params["additionalDirectories"] = additional_roots
        if session_id is None:
            created = self.rpc("session/new", params)
            if (not _identifier(created.get("sessionId"))
                    or self.creating_session_id not in (None, created["sessionId"])):
                raise _Failure("protocol_error")
            self.result["session_id"] = created["sessionId"]
            models = created.get("models", {})
            current_model = models.get("currentModelId") if isinstance(models, dict) else None
            self.result["selected_model"] = current_model if _identifier(current_model) else None
            if expected_model is not None:
                self.rpc("session/set_model", {"sessionId": created["sessionId"], "modelId": expected_model})
                self.result["selected_model_set"] = True
                self.event("session_model_selected", requested_model=expected_model)
            self.event("session_created", selected_model=self.result["selected_model"])
            if mode_id is not None:
                modes = created.get("modes", {})
                available = modes.get("availableModes") if isinstance(modes, dict) else None
                if (not isinstance(available, list) or sum(isinstance(mode, dict)
                        and mode.get("id") == mode_id for mode in available) != 1):
                    raise _Failure("unsupported_session_mode", "blocked")
                self.rpc("session/set_mode", {"sessionId": created["sessionId"], "modeId": mode_id})
                self.event("session_mode_selected")
        else:
            # Known identity correlates replay updates; loading is not ownership
            # transfer or proof of attaching an arbitrary terminal process.
            self.result["session_id"] = session_id
            params["sessionId"] = session_id
            loaded = self.rpc("session/load", params)
            metadata = loaded.get("_meta", {})
            if (("sessionId" in loaded and loaded["sessionId"] != session_id)
                    or not isinstance(metadata, dict)
                    or ("sessionId" in metadata and metadata["sessionId"] != session_id)):
                raise _Failure("protocol_error")
            detail = metadata.get("x.ai/sessionDetail", {})
            if (not isinstance(detail, dict)
                    or ("sessionId" in detail and detail["sessionId"] != session_id)
                    or ("cwd" in detail and detail["cwd"] != os.fspath(cwd))):
                raise _Failure("protocol_error")
            self.result["loaded_cwd_verified"] = (detail.get("sessionId") == session_id
                                                   and detail.get("cwd") == os.fspath(cwd))
            if require_loaded_cwd and not self.result["loaded_cwd_verified"]:
                raise _Failure("unverified_session_cwd", "blocked")
            self.event("session_loaded", loaded_cwd_verified=self.result["loaded_cwd_verified"])
        if self.creating_updates:
            self.progress(self.creating_updates)
        self.creating_session_id = None
        self.creating_updates = 0
        for prompt in self.prompts(prompts):
            if self.result["permission_denials"]:
                raise _Failure("permission_denied", "blocked")
            self.admit()
            response = self.rpc("session/prompt", {"sessionId": self.result["session_id"],
                                                    "prompt": [{"type": "text", "text": prompt}]})
            if self.result["permission_denials"]:
                raise _Failure("permission_denied", "blocked")
            if response.get("stopReason") != "end_turn":
                raise _Failure("incomplete")
            self.result["turns_completed"] += 1
            self.event("turn_completed", turn=self.turn)

    def native_denial(self, count):
        self.result["native_denials"] += count
        self.event("native_permission_denied", native_denials=self.result["native_denials"],
                   action_id="native-denial-" + str(self.result["native_denials"]))
        raise _Failure("permission_denied", "blocked")

    def agy(self, prompts):
        # Observed Agy 1.2.7 wire: init.conversation_id; result.result.status.
        for prompt in self.prompts(prompts):
            if self.turn:
                # Native results have no observed per-turn id. Reject output
                # already waiting at the boundary; it cannot answer an unsent
                # prompt. This is sequencing, not malicious-provider protection.
                self.wire.check()
                self.wire.pump(0)
                if self.wire.incoming:
                    raise _Failure("protocol_error")
            self.admit()
            self.wire.queue({"event": "user", "message": {"content": prompt}})
            self.wire.flush_input()
            while True:
                message = self.wire.receive()
                if message.get("event") == "init":
                    session_id = message.get("conversation_id")
                    if not _identifier(session_id) or self.result["session_id"] not in (None, session_id):
                        raise _Failure("protocol_error")
                    self.result["session_id"] = session_id
                    self.event("session_created")
                elif message.get("event") == "step_update":
                    step = message.get("step_update")
                    if (not isinstance(step, dict) or ("conversation_id" in step
                            and (not self.result["session_id"] or step["conversation_id"] != self.result["session_id"]))):
                        raise _Failure("protocol_error")
                    self.progress()
                    if step.get("state") == "ERROR":
                        if not self.result["session_id"] or step.get("conversation_id") != self.result["session_id"]:
                            raise _Failure("protocol_error")
                        info = step.get("tool_info", {})
                        if not isinstance(info, dict) or not isinstance(info.get("error", {}), dict):
                            raise _Failure("protocol_error")
                        error = info.get("error", {})
                        detail = error.get("message", "")
                        # This narrow signature is from Agy 1.2.7's native TOOL_ERROR,
                        # not assistant prose. Other error steps also stop dispatch.
                        if (step.get("step_type") == "tool" and error.get("type") == "TOOL_ERROR"
                                and isinstance(detail, str) and detail.startswith("permission check failed for ")):
                            self.native_denial(1)
                        raise _Failure("native_tool_error")
                elif message.get("event") == "result":
                    response = message.get("result")
                    if (not isinstance(response, dict) or not self.result["session_id"]
                            or response.get("conversation_id") != self.result["session_id"]):
                        raise _Failure("protocol_error")
                    denied = response.get("denied_actions", [])
                    if (not isinstance(denied, list) or any(not isinstance(item, dict)
                            or not _identifier(item.get("action")) for item in denied)):
                        raise _Failure("protocol_error")
                    if denied:
                        self.native_denial(len(denied))
                    if response.get("status") != "SUCCESS":
                        raise _Failure("incomplete")
                    self.result["turns_completed"] += 1
                    self.event("turn_completed", turn=self.turn)
                    break
                else:
                    raise _Failure("protocol_error")


def run_session(transport, argv, cwd, env, prompts, deadline_seconds, output_limit,
                emit, cancelled, before_prompt=None, additional_roots=None, *,
                next_prompt=None, permission_handler=None, max_turns=8, session_id=None,
                require_loaded_cwd=False, mode_id=None, expected_model=None):
    """Run admitted turns in one owned process group; return metadata, never bodies.

    Callbacks are caller-owned, fast/bounded functions. Admission is charged to the
    same attempt deadline. The caller must bind native permissions and trust before
    launch. next_prompt returns text, None (wait), or False (close). A permission
    handler returns an offered once/reject option ID or None (wait), after checking
    current authority. It receives a stable requestSequence across polls; native
    request IDs alone may be reused. Arbitrary blocking callbacks cannot be preempted.
    No capabilities or instructions are inferred from a successful result.
    session_id requests negotiated ACP loading, not generic live-terminal attach.
    mode_id selects a literal advertised fresh-session mode before any prompt.
    """
    started = time.monotonic()
    result = {"outcome": "failed", "code": "invalid_input", "session_id": None,
              "turns_completed": 0, "stdout_bytes": 0, "stderr_bytes": 0,
              "duration_seconds": 0.0, "permission_requests": 0,
              "cleanup_error": None, "reported_version": None, "progress_updates": 0,
              "reported_version_source": None, "compatibility_responses": 0}
    result.update(extension_notifications=0, native_denials=0, prompts_started=0,
                  permission_allowed=0, permission_denials=0, loaded_cwd_verified=False,
                  selected_model=None, selected_model_set=False)
    wire = None
    try:
        if os.name not in ("posix", "nt"):
            raise _Failure("unsupported_platform", "blocked")
        if (transport not in ("acp", "agy") or not isinstance(argv, (list, tuple)) or not argv
                or any(not isinstance(arg, str) or "\0" in arg for arg in argv)
                or not isinstance(prompts, (list, tuple)) or not 1 <= len(prompts) <= 8
                or type(max_turns) is not int or not 1 <= max_turns <= 8 or len(prompts) > max_turns
                or (next_prompt is not None and not callable(next_prompt))
                or (permission_handler is not None and not callable(permission_handler))
                or (session_id is not None and not _identifier(session_id))
                or (mode_id is not None and (not _identifier(mode_id) or session_id is not None or transport != "acp"))
                or (expected_model is not None and (transport != "acp" or session_id is not None or not _identifier(expected_model)))
                or type(require_loaded_cwd) is not bool
                or (require_loaded_cwd and (session_id is None or transport != "acp"))
                or any(not isinstance(prompt, str) or not prompt for prompt in prompts)
                or type(deadline_seconds) not in (int, float) or not math.isfinite(deadline_seconds)
                or not 0 < deadline_seconds <= 3600 or type(output_limit) is not int
                or not 0 < output_limit <= MAX_INPUT_BYTES):
            raise _Failure("invalid_input", "blocked")
        if transport == "agy" and permission_handler is not None:
            raise _Failure("unsupported_permission_handler", "blocked")
        if session_id is not None:
            if transport != "acp":
                raise _Failure("unsupported_session_load", "blocked")
            if additional_roots is not None:
                raise _Failure("unsupported_file_roots", "blocked")
        if any(len(prompt) > MAX_INPUT_BYTES for prompt in prompts):
            raise _Failure("input_limit_exceeded", "blocked")
        try:
            roots = file_root_identities(additional_roots) if additional_roots is not None else []
            if additional_roots is not None and transport != "acp":
                raise ValueError("invalid_file_roots")
        except (OSError, ValueError):
            raise _Failure("invalid_file_roots", "blocked") from None
        deadline = started + deadline_seconds
        wire = (_ThreadedWire if os.name == "nt" else _Wire)(deadline, output_limit, cancelled, result)
        wire.check()
        try:
            if os.name == "nt":
                process = spawn_windows_gate(argv, cwd=cwd, env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                wire.windows_job = _WindowsJob(process)
                if not wire.windows_job.handle:
                    error = wire.windows_job.error or "Windows Job Object containment is unavailable"
                    terminate_owned_process(process, wire.windows_job)
                    wait_after_termination(process, wire.windows_job)
                    for stream in (process.stdin, process.stdout, process.stderr):
                        stream.close()
                    wire.windows_job.close()
                    raise _Failure("spawn_failed")
                gate_error = release_windows_gate(process)
                if gate_error:
                    terminate_owned_process(process, wire.windows_job)
                    wait_after_termination(process, wire.windows_job)
                    for stream in (process.stdin, process.stdout, process.stderr):
                        stream.close()
                    wire.windows_job.close()
                    raise _Failure("spawn_failed")
            else:
                process = subprocess.Popen(argv, cwd=cwd, env=env, stdin=subprocess.PIPE,
                                           stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                           bufsize=0, start_new_session=True)
        except (OSError, ValueError, TypeError):
            raise _Failure("spawn_failed") from None
        wire.attach(process)
        session = _Session(wire, result, emit, before_prompt or (lambda remaining: True), roots,
                           next_prompt, permission_handler, max_turns)
        if transport == "acp":
            session.acp(cwd, prompts, additional_roots, session_id, require_loaded_cwd, mode_id, expected_model)
        else:
            session.agy(prompts)
        wire.check()
        result.update(outcome="complete", code="complete")
    except _Failure as failure:
        result.update(outcome=failure.outcome, code=failure.code)
    except (OSError, ValueError, UnicodeError, RecursionError):
        result.update(outcome="failed", code="io_error")
    finally:
        if wire is not None:
            # A loaded backend is shared, and session/cancel has no turn identity.
            # Detach our client; never cancel another live client's current turn.
            graceful = transport == "acp" and result["code"] != "complete" and session_id is None
            result["cleanup_error"] = wire.cleanup(result["session_id"], graceful)
        # A rejected request cannot become success or a less informative timeout.
        if result["permission_denials"] or result["native_denials"]:
            result.update(outcome="blocked", code="permission_denied")
        if result["cleanup_error"] and result["outcome"] == "complete":
            result.update(outcome="failed", code="cleanup_failed")
        result["duration_seconds"] = round(time.monotonic() - started, 6)
    return result
