"""Hash-chained append-only segments (ADR-0006, design: Data model)."""

import json

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from harness_bench import ledger
from harness_bench.errors import BenchError


def _write(tmp_path, n=3, seal=False):
    w = ledger.SegmentWriter.create(tmp_path / "events", "engine-1")
    for i in range(n):
        w.append({"kind": "cell.launch_intent", "cell_id": f"c{i}"})
    if seal:
        w.seal()
    w.close()
    return tmp_path / "events" / "engine-1.jsonl"


# canonical form ---------------------------------------------------------------------------

def test_canonical_is_sorted_compact_utf8():
    assert ledger.canonical({"b": 1, "a": "é"}) == '{"a":"é","b":1}'.encode()


@pytest.mark.parametrize("bad", [1.5, True, float("nan"), {"x": [1, 2.0]}, b"bytes"])
def test_canonical_rejects_floats_bools_and_bytes(bad):
    with pytest.raises(TypeError):
        ledger.canonical({"v": bad})


# append / verify ------------------------------------------------------------------------------

def test_appended_lines_chain_and_verify(tmp_path):
    path = _write(tmp_path)
    report = ledger.verify_segment(path)
    assert report.lines == 3 and not report.sealed and report.error is None
    rows = ledger.read_segment(path)
    assert [r["seq"] for r in rows] == [1, 2, 3]
    assert rows[1]["prev_hash"] == rows[0]["hash"]


def test_first_line_is_bound_to_its_segment_id(tmp_path):
    path = _write(tmp_path)
    other = tmp_path / "events" / "engine-2.jsonl"
    other.write_bytes(path.read_bytes())  # the same bytes under another segment id
    assert ledger.verify_segment(other).error == "HB-LED-002"


def test_seal_records_count_and_head(tmp_path):
    path = _write(tmp_path, seal=True)
    report = ledger.verify_segment(path)
    assert report.sealed and report.lines == 3
    last = json.loads(path.read_text(encoding="utf-8").splitlines()[-1])
    assert last["kind"] == "segment.sealed" and last["count"] == 3 and last["head_hash"] == report.head_hash


def test_append_after_seal_is_refused(tmp_path):
    w = ledger.SegmentWriter.create(tmp_path / "events", "s")
    w.append({"kind": "x"})
    w.seal()
    with pytest.raises(BenchError) as e:
        w.append({"kind": "y"})
    assert e.value.code == "HB-LED-002"


@pytest.mark.parametrize("tamper", ["rewrite", "insert", "delete_middle", "cut_sealed_tail"])
def test_tampering_is_detected(tmp_path, tamper):
    path = _write(tmp_path, n=4, seal=True)
    lines = path.read_text(encoding="utf-8").splitlines(keepends=True)
    if tamper == "rewrite":
        lines[1] = lines[1].replace('"c1"', '"cX"')
    elif tamper == "insert":
        lines.insert(2, lines[1])
    elif tamper == "delete_middle":
        del lines[2]
    elif tamper == "cut_sealed_tail":
        del lines[-1]
    path.write_text("".join(lines), encoding="utf-8")
    report = ledger.verify_segment(path)
    if tamper == "cut_sealed_tail":
        assert not report.sealed  # a completed run then fails on the unsealed segment (engine rule)
    else:
        assert report.error == "HB-LED-002"


# torn tail ------------------------------------------------------------------------------------

def test_reader_ignores_a_torn_tail_of_an_unsealed_segment(tmp_path):
    path = _write(tmp_path)
    with path.open("ab") as f:
        f.write(b'{"kind":"cell.prompt_sent","se')
    report = ledger.verify_segment(path)
    assert report.error is None and report.torn_tail and report.lines == 3
    assert len(ledger.read_segment(path)) == 3


def test_owner_reopen_repairs_the_torn_tail_and_records_it(tmp_path):
    path = _write(tmp_path)
    with path.open("ab") as f:
        f.write(b'{"kind":"half')
    w = ledger.SegmentWriter.reopen(path)
    assert w.repaired
    w.append({"kind": "cell.prompt_sent"})
    w.close()
    rows = ledger.read_segment(path)
    assert [r["kind"] for r in rows][-2:] == ["ledger.tail_repaired", "cell.prompt_sent"]
    assert ledger.verify_segment(path).error is None


def test_a_torn_line_that_is_not_the_tail_is_a_break(tmp_path):
    path = _write(tmp_path)
    text = path.read_text(encoding="utf-8").splitlines(keepends=True)
    text[1] = '{"kind":"hal\n'
    path.write_text("".join(text), encoding="utf-8")
    assert ledger.verify_segment(path).error == "HB-LED-002"


# property: any byte change, cut or insert is detected -------------------------------------

@settings(max_examples=150, deadline=None)
@given(n=st.integers(min_value=1, max_value=6), data=st.data())
def test_any_single_byte_change_is_detected(tmp_path_factory, n, data):
    tmp = tmp_path_factory.mktemp("prop")
    path = _write(tmp, n=n, seal=True)
    raw = bytearray(path.read_bytes())
    i = data.draw(st.integers(min_value=0, max_value=len(raw) - 1))
    new = data.draw(st.integers(min_value=0, max_value=255).filter(lambda b: b != raw[i]))
    raw[i] = new
    path.write_bytes(bytes(raw))
    report = ledger.verify_segment(path)
    # a changed byte either breaks the chain or turns the seal line into a torn tail (unsealed)
    assert report.error == "HB-LED-002" or not report.sealed


@settings(max_examples=100, deadline=None)
@given(records=st.lists(st.dictionaries(st.sampled_from(["a", "b", "kind", "x"]),
                                        st.one_of(st.integers(-10**12, 10**12), st.text(max_size=20)),
                                        min_size=1, max_size=4), min_size=1, max_size=8))
def test_round_trip_preserves_every_record(tmp_path_factory, records):
    tmp = tmp_path_factory.mktemp("rt")
    w = ledger.SegmentWriter.create(tmp / "f", "s")
    for r in records:
        w.append(dict(r))
    w.close()
    rows = ledger.read_segment(tmp / "f" / "s.jsonl")
    assert [{k: v for k, v in row.items() if k not in ("seq", "prev_hash", "hash")} for row in rows] == records
