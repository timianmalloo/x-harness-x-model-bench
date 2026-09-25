import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location("check_models", ROOT / "tools" / "check_models.py")
check_models = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(check_models)


def test_corrupted_tla_jar_is_deleted_and_refused(tmp_path, monkeypatch):
    jar = tmp_path / "tla2tools.jar"
    jar.write_bytes(b"not the pinned jar")
    monkeypatch.setattr(check_models, "JAR", jar)
    with pytest.raises(SystemExit, match="sha256 mismatch"):
        check_models.ensure_jar()
    assert not jar.exists()


def test_every_checked_property_has_a_seeded_variant():
    checked = set()
    for cfg in (ROOT / "models").glob("run_lifecycle.*.cfg"):
        in_list = False
        for line in cfg.read_text(encoding="utf-8").splitlines():
            word = line.strip()
            if word in ("INVARIANTS", "PROPERTIES"):
                in_list = True
            elif not word or not line.startswith(" "):
                in_list = False
            elif in_list:
                checked.add(word)
    targets = {target for _, target in check_models.VARIANTS.values()}
    assert checked - {"TypeOK"} <= targets, f"no seeded variant for {sorted(checked - {'TypeOK'} - targets)}"


def test_variant_config_checks_only_its_target():
    safety = (ROOT / "models" / "run_lifecycle.safety.cfg").read_text(encoding="utf-8")
    cfg = check_models.only_invariant(safety, "AtMostOnePrompt")
    listed = cfg.split("INVARIANTS", 1)[1].split("CHECK_DEADLOCK", 1)[0].split()
    assert listed == ["AtMostOnePrompt"]


def test_substitute_refuses_a_missing_line():
    with pytest.raises(SystemExit, match="config drift"):
        check_models.substitute("Cells = {c1}", {"Cells = {c1, c2, c3}": "Cells = {c1, c2}"})


def test_every_seeded_variant_targets_a_declared_property():
    tla = (ROOT / "models" / "run_lifecycle.tla").read_text(encoding="utf-8")
    for bug, (_, target) in check_models.VARIANTS.items():
        assert f'"{bug}"' in tla, f"variant {bug} is not seeded in the model"
        assert f"\n{target} " in tla or f"\n{target}==" in tla, f"{target} is not defined in the model"


def test_grace_variant_and_both_reachability_witnesses_are_checked():
    assert check_models.VARIANTS["no_escalate"] == ("prop", "StopReachesTerminal")
    assert check_models.WITNESSES == {"witness": "NotAllCellsFinished", "grace-witness": "NoGraceState"}


def test_an_unregistered_seeded_bug_is_rejected_by_the_reverse_check():
    tla = (ROOT / "models" / "run_lifecycle.tla").read_text(encoding="utf-8")
    assert check_models.unregistered_variants(tla) == set()
    assert check_models.unregistered_variants(tla + '\nProbe == BUG = "unregistered_grace_bug"\n') == {
        "unregistered_grace_bug"}
