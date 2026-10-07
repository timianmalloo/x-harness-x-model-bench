"""Task readiness: what `bench validate` says about a property task (W1-E section 8; grade class).

A property task is `ready` only because a discrimination record, made by the real engine and grader, shows its hidden
check discriminates. This module recomputes every verdict from the record and the current task files; it trusts nothing
the record says about itself (not even `readiness_failures`).

The readers `hidden_test_disagreements`, `comparable_cells` and `unbiased_failures` return `list[str]` or raise
`BenchError("HB-USR-002", <reason>)`; `discriminate` converts a raise into an HB-RDY-011 item whose detail is the reason.
They never return a bare None.
"""

import ast
import hashlib
import json
import logging
import re
import sys
import tempfile
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from pathlib import Path

import yaml

from harness_bench import atomic, config, egress, identity, plan, views, workspace
from harness_bench.errors import BenchError
from harness_bench.grade import _changes, _env, diffstats, runner
from harness_bench.grade import property as prop
from harness_bench.synthetic_agent import (
    OverlayError,
    apply_overlay,
    overlay_files,
    safe_relpath,
)

ROLES = ("reference", "naive")
CORRECTNESS_SCORES = ("pass_at_1", "partial_credit")  # recorded in `scores`, no expected value (R-90 condition 1)
FLIPPED = ("blocked", "passed")  # a case outcome outside this pair is a flip (W1-E section 7)
MAX_VARIANTS_BYTES = 64 * 1024
MAX_CLAUSE_CHARS = 200
VARIANT_NAME = re.compile(r"[a-z0-9]{1,16}")
OVERLAY_COMPONENT = re.compile(r"[A-Za-z0-9._-]+")
_NAME_LEN = 16
_PROPERTY_PASS = "property_check_pass"


@dataclass(frozen=True)
class Failure:
    code: str  # "HB-RDY-003"
    item: str  # "exploit_probes_blocked"
    detail: str  # "reference expected 1.0000, observed 0.0000"


def record_key(root: Path, task_id: str) -> tuple[str, str]:
    """(task version hash, engine identity hash) of the key a record of `task_id` has today. The identity is the
    manifest of this one task with no `builds/*` key (W0 section 6)."""
    tv = plan.task_version_hash(root / "tasks" / task_id)
    return tv, identity.identity_hash(identity.manifest(root, [task_id], builds=None))


def record_dir(root: Path, task_id: str) -> Path:
    return root / "bench" / "discrimination" / task_id


def record_name(task_version: str, identity_hash: str, platform: str) -> str:
    """The one definition of a discrimination record's file name; `campaign.verify` derives the expected name from a body with it."""
    return f"{task_version[:_NAME_LEN]}-{identity_hash[:_NAME_LEN]}-{platform}.json"


def record_path(root: Path, task_id: str) -> Path:
    """`bench/discrimination/<task>/<tv16>-<id16>-<platform>.json` for the current key."""
    tv, ih = record_key(root, task_id)
    return record_dir(root, task_id) / record_name(tv, ih, sys.platform)


def recorded_metrics(root: Path, task: Mapping) -> dict[str, dict]:
    """Catalog entries of the property grader's narrowed set for this task (R-90 condition 1), in catalog order."""
    catalog = config.load_yaml(root / "bench" / "metrics.yaml")
    return runner.applicable(catalog, list(task["graders"]), task["property"]["name"]).get("property", {})


def scales(root: Path) -> dict[str, int]:
    return runner._scales(config.load_yaml(root / "bench" / "metrics.yaml"))


def is_check_based(task: Mapping) -> bool:
    return task["property"]["name"] in config.CHECK_PROPERTIES


def normal(value, scale: int | None):
    """A score or expected value through the one normaliser: `("na", reason)` or `grade.property.at_scale`'s result.
    ValueError names what is wrong."""
    if isinstance(value, Mapping):
        if set(value) != {"na"} or not isinstance(value["na"], str):
            raise ValueError(f"{value!r} is not {{na: <reason>}}")
        return ("na", value["na"])
    return prop.at_scale(value, scale)


def expected_na(root: Path, tasks: Iterable[str]) -> Mapping[str, frozenset[str]]:
    """Per task, the metric ids whose `expected.reference` is `{na: <reason>}` (X-C's `pilot pass` hands it to `gates.pilot`). The
    reference role only: a naive-only NA says nothing about real cells (W0 section 8). Raises HB-USR-002 for a `task.yaml` that is absent,
    unparseable or holds a malformed NA."""
    out: dict[str, frozenset[str]] = {}
    for task_id in tasks:
        path = root / "tasks" / task_id / "task.yaml"
        try:
            reference = (config.load_yaml(path).get("expected") or {}).get("reference") or {}
            for value in reference.values():
                if isinstance(value, Mapping):
                    normal(value, None)  # the one normaliser: a malformed NA raises ValueError
            out[task_id] = frozenset(metric for metric, value in reference.items() if isinstance(value, Mapping))
        except (OSError, yaml.YAMLError, ValueError, AttributeError) as exc:
            raise BenchError("HB-USR-002", f"task {task_id}: {path.name} cannot be read for its expected NA metrics ({exc}). Fix the file.") from exc
    return out


def show(value) -> str:
    return f"NA ({value['na']})" if isinstance(value, Mapping) and "na" in value else str(value)


def score_failures(root: Path, task_id: str, body: Mapping) -> list[Failure]:
    """HB-RDY-003: every metric of the narrowed set, per role, equals the task's declared `expected` by exact equality
    after both sides pass through `normal`. Pure in the record body and the current files."""
    task = config.load_yaml(root / "tasks" / task_id / "task.yaml")
    table, out = scales(root), []
    for role in ROLES:
        declared = (task.get("expected") or {}).get(role) or {}
        for metric in recorded_metrics(root, task):
            if metric not in declared:
                continue  # a missing expected is HB-RDY-005 (contract), not a record defect
            observed = (body.get("scores") or {}).get(role, {}).get(metric, {"na": "not recorded"})
            try:
                ok = normal(observed, table.get(metric)) == normal(declared[metric], table.get(metric))
                why = ""
            except ValueError as exc:
                ok, why = False, f" ({exc})"
            if not ok:
                out.append(Failure("HB-RDY-003", metric, f"{role} expected {show(declared[metric])}, observed {show(observed)}{why}"))
    return out


def declared_cases(root: Path, task_id: str) -> list[str]:
    spec = config.load_yaml(root / "tasks" / task_id / "oracle" / "check" / "cases.yaml")
    return [str(c["id"]) for c in spec.get("cases") or []]


def host_failures(root: Path, task_id: str, task: Mapping, body: Mapping) -> list[Failure]:
    """R-HOST (O1), only for a check-based property: the digest shows the real probe host ran every declared case, for
    every role. A check-less property has no host, so a `probe` in its record is itself a failure."""
    probe = body.get("probe")
    if not is_check_based(task):
        return [Failure("HB-RDY-001", task_id, "probe on a check-less task: it has no real host, so its record carries no probe")] \
            if probe is not None else []
    if not isinstance(probe, Mapping):
        return [Failure("HB-RDY-001", task_id, "record lacks real-host probe evidence")]
    cases, out = declared_cases(root, task_id), []
    for role in ROLES:
        digest = probe.get(role)
        if not isinstance(digest, Mapping):
            out.append(Failure("HB-RDY-001", task_id, f"probe evidence of the {role} role is missing"))
        elif (digest.get("deliverable") != "ran" or sorted(digest.get("cases") or {}) != sorted(cases)
              or digest.get("hosts_ready") != len(cases)):
            out.append(Failure("HB-RDY-001", task_id, f"probe of the {role} role does not show a real-host run of every case "
                                                      f"(deliverable {digest.get('deliverable')!r}, hosts_ready {digest.get('hosts_ready')!r}, "
                                                      f"{len(digest.get('cases') or {})} of {len(cases)} cases)"))
    return out


def variant_failures(declared: Mapping[str, dict], body: Mapping, *, check_based: bool) -> list[Failure]:
    """The variant compare (O2): assertions (1) hidden tests pass (check-based task), (1') for a check-less task hidden
    tests pass unless property_check_pass is a declared flip (R-109), (2) the deliverable ran (check-based), (3) the
    flipped set equals the declared one, (4) the deciding clauses equal the declared ones. One failure per variant. A
    declared variant absent from the record is HB-RDY-001."""
    recorded, out = body.get("variants") or {}, []
    for name, entry in declared.items():
        got = recorded.get(name)
        if not isinstance(got, Mapping):
            out.append(Failure("HB-RDY-001", name, "declared variant is absent from the record"))
            continue
        why = []
        if got.get("hidden_tests_pass") != 1:
            if check_based:
                why.append("hidden tests do not pass (1)")
            elif "property_check_pass" not in entry["flips"]:
                why.append("hidden tests do not pass and the primary is not a declared flip (1')")
        if "deliverable" in got and got["deliverable"] != "ran":
            why.append(f"deliverable {got['deliverable']!r}, not 'ran' (2)")
        if sorted(got.get("flips") or []) != sorted(entry["flips"]):
            why.append(f"flips observed {sorted(got.get('flips') or [])}, declared {sorted(entry['flips'])} (3)")
        if (got.get("clauses") or {}) != entry["clauses"]:
            why.append(f"clauses observed {got.get('clauses') or {}}, declared {entry['clauses']} (4)")
        if why:
            out.append(Failure("HB-RDY-003", name, "; ".join(why)))
    return out


def body_failures(root: Path, task_id: str, body: Mapping) -> list[Failure]:
    """Every record item recomputed from the body and the current files (HB-RDY-001 host rule, 003 scores, 003 variants)."""
    task = config.load_yaml(root / "tasks" / task_id / "task.yaml")
    out = score_failures(root, task_id, body) + host_failures(root, task_id, task, body)
    try:
        declared = variants(root, task_id)
    except BenchError as exc:
        return [*out, Failure("HB-RDY-005", "variants.py", exc.message)]
    return out + variant_failures(declared, body, check_based=is_check_based(task))


def _read_record(path: Path) -> dict | None:
    try:
        body = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return body if isinstance(body, dict) else None


def _name_parts(name: str) -> tuple[str, str, str] | None:
    stem = name.removesuffix(".json")
    if stem == name or len(stem) < 2 * _NAME_LEN + 3 or stem[_NAME_LEN] != "-" or stem[2 * _NAME_LEN + 1] != "-":
        return None
    return stem[:_NAME_LEN], stem[_NAME_LEN + 1:2 * _NAME_LEN + 1], stem[2 * _NAME_LEN + 2:]


CONTAINER_RUNTIMES = frozenset({"docker", "podman", "nerdctl", "buildah", "ctr", "colima", "lima"})  # simplify: named, extend on a find
LINUX_ONLY = frozenset({"strace", "ltrace", "gdb", "valgrind", "perf", "bwrap", "firejail", "unshare", "iptables", "systemctl"})
CASE_ID = re.compile(r"[a-z0-9][a-z0-9_-]{0,31}")
ENTRY = re.compile(r"[A-Za-z0-9_][A-Za-z0-9_.-]*\.py")
APP_KINDS = frozenset({"callable", "wsgi"})  # what E1 builds (the grader's own set)
_EXPECTED_LINE = re.compile(r"^(\s+)([A-Za-z0-9_]+):\s*(.*)$")


def _provenance_missing(text: str) -> list[tuple[str, str]]:
    """(role, metric) of every `expected` value line in the raw task.yaml whose `#` comment has fewer than three words (GLD-A:
    a presence check; whether the value is independent of the grader's output stays a review item)."""
    out, role, inside = [], "", False
    for line in text.splitlines():
        if line.startswith("expected:"):
            inside = True
            continue
        if not inside:
            continue
        if line and not line[0].isspace():
            break
        m = _EXPECTED_LINE.match(line)
        if not m:
            continue
        indent, key, rest = len(m.group(1)), m.group(2), m.group(3)
        if indent <= 2 and not rest.strip():
            role = key
        elif indent > 2 and role:
            comment = rest.partition(" #")[2] if " #" in rest else ""
            if len(comment.split()) < 3:
                out.append((role, key))
    return out


def _timeouts_failures(expected: Mapping, prop_name: str, cases_path: Path, add) -> None:
    """CR47-7: `expected.<role>.timeouts` lists the case ids whose outcome is `timeout` by design. It is no metric, so every
    metric compare skips it; it is refused on a check-less task, on the reference role (its primary 1 needs every case passed),
    and for an id that is not a declared case."""
    for role in ROLES:
        declared = (expected.get(role) or {}).get("timeouts")
        if declared is None:
            continue
        item = f"expected.{role}.timeouts"
        if prop_name not in config.CHECK_PROPERTIES:
            add(item, "a check-less task has no case to time out")
        elif role == "reference":
            add(item, "the reference's primary 1 requires every case passed")
        elif not isinstance(declared, list):
            add(item, "must be a list of case ids")
        else:
            try:
                known = {str(c.get("id")) for c in config.load_yaml(cases_path).get("cases") or []}
            except (OSError, ValueError, AttributeError):
                continue  # an unreadable cases.yaml is reported by its own item
            unknown = sorted(str(c) for c in declared if str(c) not in known)
            if unknown:
                add(item, f"{unknown} is not a declared case")


def _container_items(spec: Mapping) -> list[str]:
    names = [str(t) for t in spec.get("toolchain") or []]
    deliverable = spec.get("deliverable") or {}
    for key in ("build", "start"):
        argv = deliverable.get(key)
        if isinstance(argv, list) and argv:
            names.append(str(argv[0]))
    stems = {Path(n.replace("\\", "/")).name.lower().removesuffix(".exe") for n in names}
    return sorted(stems & (CONTAINER_RUNTIMES | LINUX_ONLY))


def _case_failures(spec: Mapping, add) -> None:
    try:
        prop.check_segment("entry", str(spec.get("entry")), ENTRY)
    except ValueError as exc:
        add("cases.yaml", str(exc))
    for case in spec.get("cases") or []:
        try:
            prop.check_segment("case id", str(case.get("id")), CASE_ID)
        except ValueError as exc:
            add("cases.yaml", str(exc))
    for env_name in spec.get("env") or []:
        if (env_name not in _env.TOOLCHAIN_ENV and not str(env_name).startswith(_env.CHECK_PREFIX)) or _env.denied(str(env_name)):
            add("cases.yaml env", f"{env_name!r} is neither a toolchain name nor HB_CHECK_*")
    for rel in (spec.get("app") or {}).get("paths") or []:
        try:
            safe_relpath(str(rel))
        except OverlayError as exc:
            add("cases.yaml app.paths", f"{rel!r} is not a relative path inside the deliverable ({exc})")
    interface = spec.get("interface")
    if interface == "loopback":  # W0 s3: exactly one of shape (a) (start + config, no app) or shape (b) (an app, no start)
        deliverable = spec.get("deliverable") or {}
        shape_a = bool(deliverable.get("start") and deliverable.get("config")) and not spec.get("app")
        shape_b = bool(spec.get("app")) and not deliverable.get("start")
        if shape_a == shape_b:
            add("cases.yaml interface", "loopback declares exactly one of shape (a) (deliverable.start and deliverable.config, no app) or shape (b) (an app, no deliverable.start)")
        elif shape_a:
            add("cases.yaml interface", "loopback shape (a) (the deliverable listens) is not built")
        elif (spec.get("app") or {}).get("kind") != "callable":
            add("cases.yaml app.kind", f"{(spec.get('app') or {}).get('kind')!r} is not callable (loopback shape (b))")
        return
    if interface != "in-process":
        add("cases.yaml interface", f"{interface!r} is neither in-process nor loopback")
    if (spec.get("app") or {}).get("kind") not in APP_KINDS:
        add("cases.yaml app.kind", f"{(spec.get('app') or {}).get('kind')!r} is not callable or wsgi")


def _check_simplicity_reference_size(root: Path, d: Path, p: Mapping, add) -> None:
    """Recompute size_reference_lines for a simplicity task (W1-L s8.1, s15; HB-RDY-009)."""
    frozen = p.get("size_reference_lines")
    if frozen is None:
        add("property.size_reference_lines", "missing", "HB-RDY-005")
        return
    # assume: the upstream cache root is root / ".tools" / "upstream" (discriminate.run's default); confirm: discriminate.run line 254; breaks if false: cache miss on discrimination run.
    upstream_root = (root / ".tools" / "upstream").resolve()
    sources_root = (root / ".tools" / "sources").resolve()
    try:
        tv = plan.task_version_hash(d)
        base_repo = workspace.task_source(d, tv, sources_root, upstream_root)
    except (BenchError, OSError) as exc:
        add("property.size_reference_lines", f"value not checked: base tree cannot be built ({exc})", "HB-RDY-009")
        return

    ref_dir = d / "oracle" / "solutions" / "reference"
    radius = config.load_yaml(d / "task.yaml").get("blast_radius") or []
    try:
        with tempfile.TemporaryDirectory() as tmp_dir:
            final = Path(tmp_dir) / "final"
            _changes.copy_tree(base_repo, final)
            apply_overlay(ref_dir, final)
            computed = diffstats.measure(base_repo, final, radius)["inside_lines"]
    except (OSError, OverlayError) as exc:
        add("property.size_reference_lines", f"value not checked: reference overlay cannot be applied ({exc})", "HB-RDY-009")
        return

    if frozen != computed:
        add("property.size_reference_lines", f"frozen value {frozen} differs from computed {computed}", "HB-RDY-009")


def contract_failures(root: Path, task_id: str) -> list[Failure]:
    """HB-RDY-005..008 for one task: what needs no run (EV-1, W1-E section 8.2). Loopback shapes are not built in E1."""
    d = root / "tasks" / task_id
    text = (d / "task.yaml").read_text(encoding="utf-8")
    task = config.load_yaml(d / "task.yaml")
    p = task.get("property")
    if not isinstance(p, dict):
        return []
    out: list[Failure] = []

    def add(item: str, detail: str, code: str = "HB-RDY-005") -> None:
        out.append(Failure(code, item, detail))

    name = p.get("name")
    if name not in config.PROPERTY_NAMES:
        return [Failure("HB-RDY-005", "property.name", f"{name!r} is not one of {', '.join(config.PROPERTY_NAMES)}")]
    if not isinstance(p.get("latent_requirement"), str) or not p["latent_requirement"].strip():
        add("property.latent_requirement", "missing")
    terms = p.get("latent_terms")
    if not isinstance(terms, list) or not terms or not all(isinstance(t, str) and t for t in terms):
        add("property.latent_terms", "must be a non-empty list of terms")
        terms = []
    evidence = p.get("evidence_paths")
    if not isinstance(evidence, list) or not evidence:
        add("property.evidence_paths", "at least one path is required")
    elif (task.get("source") or {}).get("workspace_from") != "source":
        # assume: a `workspace_from: source` base tree is the upstream clone, which this check does not open; confirm: the
        # E2 discrimination run builds it; breaks if false: a wrong evidence path of such a task is found one step late.
        out.extend(Failure("HB-RDY-005", "property.evidence_paths", f"{rel} is not in the base tree")
                   for rel in evidence if not (d / "workspace" / str(rel)).exists())
    if p.get("primary_metric") != _PROPERTY_PASS:  # simplify: the catalog's one primary is named here, not derived
        add("property.primary_metric", f"must be {_PROPERTY_PASS}")
    graders = task.get("graders") or []
    if not {"correctness", "property"} <= set(graders):
        add("graders", "must name correctness and property")
    radius = (p.get("ceilings") or {}).get("outside_radius_lines")
    if name == "simplicity":
        if isinstance(radius, bool) or not isinstance(radius, int):
            add("property.ceilings.outside_radius_lines", "a simplicity task needs an integer outside_radius_lines")
        _check_simplicity_reference_size(root, d, p, add)
    catalog = config.load_yaml(root / "bench" / "metrics.yaml")
    narrowed = runner.applicable(catalog, ["correctness", "property"], name).get("property", {})
    expected = task.get("expected") or {}
    for role in ROLES:
        declared = expected.get(role) or {}
        out.extend(Failure("HB-RDY-005", f"expected.{role}.{metric}", "missing (or {na: <reason>})") for metric in narrowed if metric not in declared)
        want = {"reference": 1, "naive": 0}[role]
        got = declared.get(_PROPERTY_PASS)
        if got is not None and not isinstance(got, Mapping) and got != want:
            add(f"expected.{role}.{_PROPERTY_PASS}", f"the primary must be {want} for the {role} role (EV-7), not {got!r}")
    _timeouts_failures(expected, name, d / "oracle" / "check" / "cases.yaml", add)
    out.extend(Failure("HB-RDY-005", f"expected.{role}.{metric}", "no provenance comment of at least three words (GLD-A)")
               for role, metric in _provenance_missing(text) if metric in narrowed)
    check_dir = d / "oracle" / "check"
    if name in config.CHECK_PROPERTIES:
        if not (check_dir / "cases.yaml").is_file():
            add("oracle/check", f"a {name} task needs oracle/check/ with cases.yaml")
        else:
            try:
                spec = config.load_yaml(check_dir / "cases.yaml")
                if not (check_dir / str(spec.get("entry"))).is_file():
                    add("oracle/check", f"the entry {spec.get('entry')!r} is not in oracle/check/")
                _case_failures(spec, add)
                out.extend(Failure("HB-RDY-008", "cases.yaml", f"declares {c}, a container runtime or Linux-only tool") for c in _container_items(spec))
            except (OSError, ValueError, AttributeError) as exc:
                add("oracle/check/cases.yaml", f"unreadable ({type(exc).__name__})")
    elif check_dir.exists():
        add("oracle/check", f"a {name} task has no hidden check; oracle/check/ would be a dead oracle")
    for role in ROLES:
        folder = d / "oracle" / "solutions" / role
        if not folder.is_dir():
            add(f"oracle/solutions/{role}", "missing")
            continue
        try:
            overlay_files(folder)
        except OverlayError as exc:
            add(f"oracle/solutions/{role}", f"overlay refused: {exc}")
    try:
        variants(root, task_id)
    except BenchError as exc:
        add("oracle/variants.py", exc.message)
    prompt = (d / "prompt.md").read_text(encoding="utf-8") if (d / "prompt.md").is_file() else ""
    for term in terms:
        rx = re.compile(r"(?<![A-Za-z0-9])" + re.escape(term) + r"(?![A-Za-z0-9])", re.IGNORECASE)
        out.extend(Failure("HB-RDY-006", term, f"prompt line {i} states the latent term {term!r}")
                   for i, line in enumerate(prompt.splitlines(), 1) if rx.search(line))
    return out


def pair_failures(tasks: Mapping[str, Mapping]) -> dict[str, list[Failure]]:
    """HB-RDY-007 (DR-T1), per property that has a task past `stub`: two tasks, at different bases (a base is the source's
    repo and commit). A stub with no `source` conflicts with nothing."""
    out: dict[str, list[Failure]] = {}
    by_property: dict[str, list[str]] = {}
    for tid, t in sorted(tasks.items()):
        by_property.setdefault(str((t.get("property") or {}).get("name")), []).append(tid)
    for name, ids in by_property.items():
        live = [i for i in ids if tasks[i].get("status") != "stub"]
        if not live:
            continue
        if len(ids) < 2:
            out.setdefault(live[0], []).append(Failure("HB-RDY-007", name, f"the {name} property has one task; the pair rule needs two"))
            continue
        seen: dict[tuple, str] = {}
        for tid in live:
            src = tasks[tid].get("source") or {}
            base = (src.get("repo"), src.get("commit"))
            if base in seen:
                out.setdefault(tid, []).append(Failure("HB-RDY-007", name, f"{tid} and {seen[base]} share one base {base[0]}@{str(base[1])[:12]}"))
            seen.setdefault(base, tid)
    return out


def _find_record(root: Path, task_id: str, baseline: Mapping | None) -> tuple[Path | None, dict | None, list[Failure]]:
    """(the record's path, its body, []) when the key names one that matches its body, else (None, None, the failure)."""
    tv, ih = record_key(root, task_id)
    if baseline is not None:
        ih = identity.identity_hash(identity.for_task(dict(baseline), task_id))
    folder = record_dir(root, task_id)
    names = sorted(p.name for p in folder.glob("*.json") if not atomic.is_temp_name(p.name)) if folder.is_dir() else []
    here = [n for n in names if (parts := _name_parts(n)) and parts[0] == tv[:_NAME_LEN] and parts[2] == sys.platform]
    if not here:
        present = ", ".join(names) or "none"
        return None, None, [Failure("HB-RDY-001", task_id, f"no discrimination record for task version {tv[:_NAME_LEN]} on {sys.platform}; present: {present}")]
    match = [n for n in here if _name_parts(n)[1] == ih[:_NAME_LEN]]  # type: ignore[index]
    if not match:
        return None, None, [Failure("HB-RDY-002", task_id, f"record identity {_name_parts(here[0])[1]} differs from the current {ih[:_NAME_LEN]}")]  # type: ignore[index]
    body = _read_record(folder / match[0])
    p_tv, p_ih, p_platform = _name_parts(match[0])  # type: ignore[misc]
    if (body is None or body.get("task") != task_id or body.get("platform") != p_platform
            or str(body.get("task_version", ""))[:_NAME_LEN] != p_tv or str(body.get("identity_hash", ""))[:_NAME_LEN] != p_ih):
        return None, None, [Failure("HB-RDY-001", task_id, f"record name {match[0]} does not match its body")]
    return folder / match[0], body, []


def record_failures(root: Path, task_id: str, *, baseline: Mapping | None = None) -> list[Failure]:
    """HB-RDY-001..004, 010, 011 for one task: what the discrimination record must show. With a campaign `baseline`
    manifest the identity compared is `identity_hash(identity.for_task(baseline, task))` (W0 section 6)."""
    _path, body, failures = _find_record(root, task_id, baseline)
    if body is None:
        return failures
    task = config.load_yaml(root / "tasks" / task_id / "task.yaml")
    if body.get("expected") != task.get("expected"):
        return [Failure("HB-RDY-001", task_id, "record expected differs from task.yaml (a tamper tell)")]
    return body_failures(root, task_id, body)


def run_scores(run_dir: Path, grading_id: str, cell_roles: Mapping[str, str], keep: set[str]) -> tuple[dict, dict]:
    """(role -> metric -> value or {na: reason}, role -> the `property.json` pointer of its property_check_pass row) read
    from one completed grading pass; `cell_roles` maps a cell id to its role. The one reader of a pass for the record, used
    by `discriminate` to write it and by `reconcile` to compare it."""
    scores: dict[str, dict] = {role: {} for role in cell_roles.values()}
    pointers: dict[str, str] = {}
    for row in views.rows(run_dir, "scores"):
        if row["grading_id"] == grading_id and row["cell_id"] in cell_roles:
            role = cell_roles[row["cell_id"]]
            if row["metric_id"] in keep:
                scores[role][row["metric_id"]] = row["value"] if row["value"] is not None else {"na": row["reason"]}
            if row["metric_id"] == _PROPERTY_PASS and row["evidence"]:
                pointers[role] = row["evidence"]
    return {role: dict(sorted(s.items())) for role, s in scores.items()}, pointers


def probe_digest(found: Mapping) -> dict:
    return {"deliverable": found["deliverable"], "cases": dict(sorted(found["cases"].items())), "hosts_ready": found["hosts_ready"]}


def _newest_link(runs: Path, stem: str) -> dict | None:
    """The link whose `record_stem` is `stem` with the newest wall-clock `recorded_at` (ties: the larger run id). `mono_ns` is
    informational and never orders (RV-PAT 2): a monotonic clock restarts with the machine."""
    links = []
    for path in sorted(runs.glob("*/discrimination-link.json")) if runs.is_dir() else []:
        try:
            link = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if isinstance(link, dict) and link.get("record_stem") == stem:
            links.append(link)
    return max(links, key=lambda link: (link.get("recorded_at", ""), link.get("run_id", "")), default=None)


def reconcile(root: Path, task_id: str, runs: Path, *, baseline: Mapping | None = None) -> tuple[str, list[Failure]]:
    """(`reconciled: yes` or `reconciled: no (<reason>)`, HB-RDY-004 failures) of the current record against the newest run
    that made it (ADR-0016 section 4, R-98 condition 3). The reason is one of seven; a `no` neither fails nor passes. Only
    a score or `probe` difference fails, and it is never degraded to a pass."""
    path, body, _ = _find_record(root, task_id, baseline)
    if path is None or body is None:
        return "reconciled: no (no link)", []
    link = _newest_link(runs, path.stem)
    if link is None:
        return "reconciled: no (no link)", []
    run_dir = runs / str(link.get("run_id"))
    if not run_dir.is_dir():
        return "reconciled: no (run folder absent)", []
    if link.get("grading_id") not in views.completed_passes(run_dir):
        return "reconciled: no (no completed grading pass)", []
    if hashlib.sha256(path.read_bytes()).hexdigest() != link.get("record_sha256"):
        return "reconciled: no (record hash differs from the link)", []
    try:
        stored = plan.load_confirmed(run_dir)
        is_discrimination = plan.kind_of(stored) == "discrimination"
    except (BenchError, OSError, ValueError, KeyError):
        is_discrimination = False
    if not is_discrimination:
        return "reconciled: no (run is not a discrimination run)", []
    if (stored.get("tasks", {}).get(task_id) or {}).get("version_hash") != body.get("task_version"):
        return "reconciled: no (run task version differs)", []
    declared = sorted(f"synthetic-v-{n}" for n in body.get("variants") or {})
    if (sorted(c["combo"] for c in stored["cells"]) != sorted(["synthetic-reference", "synthetic-naive", *declared])
            or any(c["harness"] != "synthetic" for c in stored["cells"])):
        return "reconciled: no (run combos are not the synthetic ones)", []
    roles = {c["combo"]: ("reference" if c["combo"].endswith("reference") else "naive" if c["combo"].endswith("naive")
                          else f"variant:{c['combo'].removeprefix('synthetic-v-')}") for c in stored["cells"]}
    scores, pointers = run_scores(run_dir, link["grading_id"], {c["cell_id"]: roles[c["combo"]] for c in stored["cells"]}, set(body["scores"]["reference"]))
    failures = []
    for role in ROLES:
        for metric, value in sorted(body["scores"][role].items()):
            if scores[role].get(metric) != value:
                failures.append(Failure("HB-RDY-004", metric, f"copy {show(value)}, run {show(scores[role].get(metric, {'na': 'not recorded'}))}"))
    for role in ROLES if "probe" in body else ():
        try:
            run_probe = probe_digest(property_evidence(run_dir, pointers[role]))
        except (KeyError, OSError, ValueError, IndexError):
            failures.append(Failure("HB-RDY-004", f"probe.{role}", "the run holds no readable check evidence"))
            continue
        copy = body["probe"].get(role) or {}
        if run_probe["deliverable"] != copy.get("deliverable") or run_probe["hosts_ready"] != copy.get("hosts_ready"):
            failures.append(Failure("HB-RDY-004", f"probe.{role}", f"copy {copy}, run {run_probe}"))
        failures.extend(Failure("HB-RDY-004", f"probe.{role}.cases.{c}", f"copy {copy.get('cases', {}).get(c)}, run {out}")
                        for c, out in sorted(run_probe["cases"].items()) if (copy.get("cases") or {}).get(c) != out)
    return ("reconciled: yes", []) if not failures else ("", failures)


def pass_rule_problems(root: Path, task_id: str) -> list[Failure]:
    """HB-RDY-005 per metric id of `formal.pass_rule.all_of` that the formal grader does not record for this task (the set
    `formal.pass_at_1` checks in its order 2: `runner.applicable`'s `formal` set); [] for a task with no pass rule (W1-G 4.3, FM1)."""
    task = config.load_yaml(root / "tasks" / task_id / "task.yaml")
    rule = (task.get("formal") or {}).get("pass_rule")
    names = rule.get("all_of") if isinstance(rule, dict) else None
    if not names:
        return []
    catalog = config.load_yaml(root / "bench" / "metrics.yaml")
    prop_name = (task.get("property") or {}).get("name") if isinstance(task.get("property"), dict) else None
    recorded = runner.applicable(catalog, list(task.get("graders") or []), prop_name).get("formal", {})
    return [Failure("HB-RDY-005", "formal.pass_rule.all_of", f"{m!r} is not a metric the formal grader records for this task")
            for m in names if m not in recorded]


log = logging.getLogger("harness_bench.readiness")


def problems(root: Path, *, baseline: Mapping | None = None, runs: Path | None = None) -> list[str]:
    """The lines `bench validate` prints, `x <code> <task>: <item>: <detail>`, plus non-failing `note:` lines (a skipped temp
    in `bench/discrimination/<task>/`, which is never deleted here, and one `reconciled:` line per ready task). A `stub` is
    skipped; a `draft` gets its contract items; a `ready` task gets the contract, the record and the reconciliation."""
    runs = runs or root / "runs"
    tasks = {}
    rule_only: dict[str, Mapping] = {}
    for path in sorted((root / "tasks").glob("*/task.yaml")):
        task = config.load_yaml(path)
        if isinstance(task.get("property"), dict):
            tasks[path.parent.name] = task
        elif task.get("status") != "stub" and (task.get("formal") or {}).get("pass_rule"):
            rule_only[path.parent.name] = task  # no property block: the pass-rule branch only, never a record or contract check
    pairs = pair_failures(tasks)
    lines: list[str] = []
    reconciled = ""
    for tid, task in tasks.items():
        if task.get("status") == "stub":
            continue
        failures = contract_failures(root, tid) + pairs.get(tid, []) + pass_rule_problems(root, tid)
        folder = record_dir(root, tid)
        if folder.is_dir():
            lines += [f"note: {tid}: skipped temp {p.name} (the writer's sweep removes it)" for p in sorted(folder.iterdir()) if atomic.is_temp_name(p.name)]
        if task.get("status") == "ready":
            failures += record_failures(root, tid, baseline=baseline)
            if not any(f.code in ("HB-RDY-001", "HB-RDY-002") for f in failures):
                line, drift = reconcile(root, tid, runs, baseline=baseline)
                failures += drift
                if line:
                    lines.append(f"note: {tid}: {line}")
                    reconciled = line.split(": ", 1)[1].split(" ")[0]
        lines += [f"x {f.code} {tid}: {f.item}: {f.detail}" for f in failures]
    for tid in rule_only:
        lines += [f"x {f.code} {tid}: {f.item}: {f.detail}" for f in pass_rule_problems(root, tid)]
    log.info("readiness.validated", extra={"detail": f"reconciled={reconciled or 'null'} tasks={len(tasks)}"})
    return lines


# --- the readers over a graded run (O3, O4) ------------------------------------------------------------------------


def _rows(run_dir: Path, grading_id: str) -> dict[str, dict[str, dict]]:
    """cell id -> metric id -> score row of one completed grading pass. HB-USR-002 with the reason when it cannot be read."""
    try:
        if grading_id not in views.completed_passes(run_dir):
            raise BenchError("HB-USR-002", f"grading pass {grading_id} is absent or not completed in {run_dir.name}")
        rows = [r for r in views.rows(run_dir, "scores") if r.get("grading_id") == grading_id]
    except (BenchError, OSError, ValueError, KeyError) as exc:
        reason = exc.message if isinstance(exc, BenchError) else f"{type(exc).__name__}: {exc}"
        raise BenchError("HB-USR-002", f"the scores of pass {grading_id} cannot be read: {reason}") from exc
    if not rows:
        raise BenchError("HB-USR-002", f"the scores ledger holds no rows for pass {grading_id}")
    out: dict[str, dict[str, dict]] = {}
    for r in rows:
        out.setdefault(r["cell_id"], {})[r["metric_id"]] = r
    return out


def _property_doc(run_dir: Path, cell: str, row: Mapping | None) -> dict | None:
    """The cell's `property.json` through the pointer its score row holds; None when it is not there or not JSON."""
    pointer = (row or {}).get("evidence")
    if not pointer:
        return None
    try:
        doc = json.loads((run_dir / pointer).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return doc if isinstance(doc, dict) else None


def unbiased_failures(run_dir: Path, grading_id: str) -> list[str]:
    """Cell ids with a grading span whose `unbiased_ok` is false. Raises BenchError("HB-USR-002", <reason>) when it cannot run."""
    out = []
    for cell, metrics in sorted(_rows(run_dir, grading_id).items()):
        row = metrics.get(_PROPERTY_PASS)
        if row is None:
            continue
        doc = _property_doc(run_dir, cell, row)
        if doc is None:
            if row["value"] is not None:
                raise BenchError("HB-USR-002", f"cell {cell} has a {_PROPERTY_PASS} value but no readable property.json")
            continue
        if any(not span.get("unbiased_ok") for span in doc.get("spans") or []):
            out.append(cell)
    return out


def comparable_cells(run_dir: Path, grading_id: str) -> tuple[list[str], list[str]]:
    """(cells where the hidden tests and `pass_at_1` disagree, cells where either side is NA), each sorted. Raises like the
    readers. A cell with no `property_check_pass` row (a task with no property grader) is not examined."""
    disagree, not_comparable = [], []
    for cell, metrics in sorted(_rows(run_dir, grading_id).items()):
        row = metrics.get(_PROPERTY_PASS)
        if row is None:
            continue
        doc = _property_doc(run_dir, cell, row)
        if doc is None and row["value"] is not None:
            raise BenchError("HB-USR-002", f"cell {cell} has a {_PROPERTY_PASS} value but no readable property.json")
        hidden = ((doc or {}).get("hidden_tests_pass") or {}).get("value")
        passed = (metrics.get("pass_at_1") or {}).get("value")
        if hidden is None or passed is None:
            not_comparable.append(cell)
        elif (hidden == 1) != (passed == 1):
            disagree.append(cell)
    return disagree, not_comparable


def hidden_test_disagreements(run_dir: Path, grading_id: str) -> list[str]:
    """Cell ids where the hidden tests and `pass_at_1` disagree; `[]` means every comparable cell agreed. Not-comparable
    cells are left out (the discriminate path turns them into HB-RDY-011 items through `comparable_cells`). Raises
    BenchError("HB-USR-002", <reason>) when it cannot run; the caller converts (R-96's third state, never a bare None)."""
    return comparable_cells(run_dir, grading_id)[0]


def property_evidence(run_dir: Path, pointer: str) -> dict:
    """What one cell's check recorded, for the probe digest and the variant compare: `deliverable`, `cases` (id ->
    outcome), `hosts_ready` (the `end: ready` lines of `hosts.jsonl`), `hidden` (the hidden-test value) and `clauses`
    (`clauses.json`, at most 64 KiB, or None). ValueError / OSError name what could not be read.

    Every evidence file is read through the `check.*` pointers `property.json` holds, each relative to `run_dir`. A pointer
    that is absent or null, or a file that is missing, is a ValueError naming it (fail closed, HB-RDY-011); only
    `check.clauses` may be null, which reads as `clauses: None`."""
    doc_path = run_dir / pointer
    doc = json.loads(doc_path.read_text(encoding="utf-8"))
    pointers = doc.get("check") or {}

    def resolve(key: str, nullable: bool = False) -> Path | None:
        if key not in pointers:
            raise ValueError(f"property.json has no check.{key} pointer")
        rel = pointers[key]
        if rel is None and nullable:
            return None
        if not isinstance(rel, str):
            raise ValueError(f"check.{key} is not a path")  # noqa: TRY004 (the readers raise ValueError, W0 rev 6)
        target = (run_dir / rel).resolve()
        if not target.is_relative_to(run_dir.resolve()) or not target.is_file():
            raise ValueError(f"check.{key} {rel!r} does not resolve to a file in the run")
        return target

    result = json.loads(resolve("deliverable").read_text(encoding="utf-8").splitlines()[0])
    cases_doc = json.loads(resolve("cases").read_text(encoding="utf-8").splitlines()[0])
    hosts = [json.loads(line) for line in resolve("hosts").read_text(encoding="utf-8").splitlines() if line.strip()]
    clauses = None
    clauses_file = resolve("clauses", nullable=True)
    if clauses_file is not None:
        if clauses_file.stat().st_size > MAX_VARIANTS_BYTES:
            raise ValueError("clauses.json is over 64 KiB")
        text = clauses_file.read_text(encoding="utf-8")
        # Untrusted grader output: the scan every other reader uses (egress.check, as report/judges.py), before the parse.
        verdict = egress.check(text, destination="readiness", operator=egress.Operator.from_os())
        if verdict.withheld:
            raise ValueError(f"clauses.json is withheld by the egress scan ({', '.join(verdict.classes)})")
        clauses = json.loads(text)
        if not isinstance(clauses, dict) or not all(isinstance(k, str) and isinstance(v, str) for k, v in clauses.items()):
            raise ValueError("clauses.json is not a {case id: clause text} object")
    return {"deliverable": result["deliverable"], "cases": {c["id"]: c["outcome"] for c in cases_doc["cases"]},
            "hosts_ready": sum(1 for h in hosts if h.get("end") == "ready"),
            "hidden": (doc.get("hidden_tests_pass") or {}).get("value"), "clauses": clauses}


# --- the variants file: data, never code (W1-E section 7; W0 section 2) -----------------------------------------------


def _bad(task_id: str, why: str) -> BenchError:
    return BenchError("HB-RDY-005", f"{task_id}: oracle/variants.py {why}")


def apply_edit(task_id: str, name: str, edit: dict, raw: bytes, where: str) -> str:
    """The one definition of "a variant edit applies" (DM7, APPLY-A): the file's text with CRLF read as LF, `old` exactly once,
    else HB-RDY-005 naming the variant and the file. Returns the replaced text; the applier writes it, never the unchanged bytes."""
    text = raw.decode("utf-8").replace("\r\n", "\n")
    if not edit["old"] or text.count(edit["old"]) != 1:
        raise _bad(task_id, f"variant {name} edit does not apply (`old` must occur exactly once in {where})")
    return text.replace(edit["old"], edit["new"], 1)


def variants(root: Path, task_id: str) -> dict[str, dict]:
    """The task's declared defect variants `{name: {flips, clauses, edits}}`, read as data: one top-level `VARIANTS`
    assignment through `ast.literal_eval`; the file is never imported or executed. HB-RDY-005 on any defect: over 64 KiB,
    a parse or recursion error, none or more than one assignment (an annotated or augmented one included), a non-literal,
    a name that fails the charset or `check_segment`, a `clauses` text over 200 characters, an `edits[].file` that fails
    the overlay path rule (before any read), or an `old` that does not occur exactly once in the reference file."""
    path = root / "tasks" / task_id / "oracle" / "variants.py"
    if not path.is_file():
        return {}
    if path.stat().st_size > MAX_VARIANTS_BYTES:
        raise _bad(task_id, f"is over {MAX_VARIANTS_BYTES} bytes")
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"))
    except (SyntaxError, RecursionError, MemoryError, ValueError) as exc:
        raise _bad(task_id, f"does not parse ({type(exc).__name__})") from exc
    targets = [n for n in tree.body if isinstance(n, ast.Assign) and any(isinstance(t, ast.Name) and t.id == "VARIANTS" for t in n.targets)]
    extras = [n for n in tree.body if isinstance(n, ast.AnnAssign | ast.AugAssign) and isinstance(n.target, ast.Name) and n.target.id == "VARIANTS"]
    if len(targets) != 1 or extras:
        raise _bad(task_id, "must hold exactly one plain top-level `VARIANTS = {...}` assignment")
    try:
        value = ast.literal_eval(targets[0].value)
    except (ValueError, TypeError, SyntaxError, RecursionError, MemoryError) as exc:
        raise _bad(task_id, f"VARIANTS is not a literal ({type(exc).__name__})") from exc
    if not isinstance(value, dict):
        raise _bad(task_id, "VARIANTS is not a mapping")
    for name, entry in value.items():
        _check_variant(root, task_id, name, entry)
    return value


def _check_variant(root: Path, task_id: str, name, entry) -> None:
    try:
        prop.check_segment("variant name", name if isinstance(name, str) else repr(name), VARIANT_NAME)
    except ValueError as exc:
        raise _bad(task_id, str(exc)) from exc
    if not isinstance(entry, dict) or set(entry) != {"flips", "clauses", "edits"}:
        raise _bad(task_id, f"variant {name} must have exactly the keys flips, clauses and edits")
    flips, clauses, edits = entry["flips"], entry["clauses"], entry["edits"]
    if not isinstance(flips, list) or not all(isinstance(f, str) for f in flips):
        raise _bad(task_id, f"variant {name} flips is not a list of strings")
    if not isinstance(clauses, dict) or not all(isinstance(k, str) and isinstance(v, str) and len(v) <= MAX_CLAUSE_CHARS
                                                for k, v in clauses.items()):
        raise _bad(task_id, f"variant {name} clauses must map strings to texts of at most {MAX_CLAUSE_CHARS} characters")
    if not isinstance(edits, list) or not edits:
        raise _bad(task_id, f"variant {name} edits is not a non-empty list")
    task_path = root / "tasks" / task_id / "task.yaml"
    has_turns = bool(config.load_yaml(task_path).get("turns")) if task_path.is_file() else False
    reference = root / "tasks" / task_id / "oracle" / "solutions" / "reference"
    for edit in edits:
        if not isinstance(edit, dict) or set(edit) != {"file", "old", "new"} or not all(isinstance(v, str) for v in edit.values()):
            raise _bad(task_id, f"variant {name} has an edit that is not {{file, old, new}} strings")
        file_str = edit["file"]
        if has_turns and not re.match(r"^turn-\d+/", file_str):
            raise _bad(task_id, f"variant {name} edit file must start with turn-<n>/ for a task with turns ({file_str})")
        try:
            rel = safe_relpath(file_str)
            for part in rel.parts:
                prop.check_segment("overlay component", part, OVERLAY_COMPONENT)
        except (OverlayError, ValueError) as exc:
            raise _bad(task_id, f"variant {name} edit file: {exc}") from exc
        target = reference / rel
        if edit["old"] == "":
            if target.is_file():
                raise _bad(task_id, f"variant {name} create edit cannot replace file already in reference overlay ({rel.as_posix()})")
        else:
            apply_edit(task_id, name, edit, target.read_bytes() if target.is_file() else b"", f"reference/{rel.as_posix()}")
