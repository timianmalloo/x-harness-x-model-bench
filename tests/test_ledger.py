"""Hash-chained append-only segments (ADR-0006, design: Data model)."""

import errno
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


def test_a_failed_write_poisons_the_writer(tmp_path):  # SRE-5: nothing is appended after a torn write
    w = ledger.SegmentWriter.create(tmp_path / "events", "engine-1")
    w.append({"kind": "a"})
    real = w._file

    class Torn:  # the disk fills halfway through the line
        def write(self, data):
            real.write(data[: len(data) // 2])
            real.flush()
            raise OSError(errno.ENOSPC, "No space left on device")

        def __getattr__(self, name):
            return getattr(real, name)

    w._file = Torn()
    with pytest.raises(OSError) as first:
        w.append({"kind": "b"})
    assert first.value.errno == errno.ENOSPC  # the first failure keeps its cause
    w._file = real  # space is back: the writer must still refuse
    for later in (lambda: w.append({"kind": "c"}), w.seal):
        with pytest.raises(BenchError) as e:
            later()
        assert e.value.code == "HB-LED-002"
    w.close()
    report = ledger.verify_segment(tmp_path / "events" / "engine-1.jsonl")
    assert (report.error, report.lines, report.torn_tail) == (None, 1, True)  # the half line stays a torn tail


@pytest.mark.parametrize(("tamper", "detail"), [("rewrite", "chain break at line 2"), ("insert", "chain break at line 3"),
                                                ("delete_middle", "chain break at line 3"), ("cut_sealed_tail", "")])
def test_tampering_is_detected(tmp_path, tamper, detail):  # bytes, never text: text mode on Windows writes \r\n (T2-10)
    path = _write(tmp_path, n=4, seal=True)
    lines = path.read_bytes().splitlines(keepends=True)
    if tamper == "rewrite":
        lines[1] = lines[1].replace(b'"c1"', b'"cX"')
    elif tamper == "insert":
        lines.insert(2, lines[1])
    elif tamper == "delete_middle":
        del lines[2]
    elif tamper == "cut_sealed_tail":
        del lines[-1]
    path.write_bytes(b"".join(lines))
    report = ledger.verify_segment(path)
    assert report.detail == detail
    if tamper == "cut_sealed_tail":
        assert not report.sealed and report.error is None  # the recorded head exposes it (test_verify)
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


def test_an_unparseable_last_line_of_an_unsealed_segment_is_a_torn_tail(tmp_path):  # newline-ended: still the tail
    path = _write(tmp_path)
    with path.open("ab") as f:
        f.write(b'{"kind":"hal\n')
    report = ledger.verify_segment(path)
    assert (report.error, report.torn_tail, report.lines) == (None, True, 3)


def test_stamp_records_utc_milliseconds_and_a_monotonic_clock(monkeypatch):
    monkeypatch.setattr(ledger.time, "time", lambda: 1_790_000_007.25)  # whole seconds not a multiple of 1000
    monkeypatch.setattr(ledger.time, "monotonic_ns", lambda: 42)
    assert ledger.stamp({"kind": "x"}) == {"kind": "x", "recorded_at": "2026-09-21T14:13:27.250Z", "mono_ns": 42}


def test_a_torn_line_that_is_not_the_tail_is_a_break(tmp_path):
    path = _write(tmp_path)
    lines = path.read_bytes().splitlines(keepends=True)
    lines[2] = b'{"kind":"hal\n'
    lines.append(b'{"kind":"more')  # a torn tail after it does not make it the tail
    path.write_bytes(b"".join(lines))
    report = ledger.verify_segment(path)
    assert (report.error, report.detail, report.lines) == ("HB-LED-002", "line 3 does not parse", 0)


def test_a_long_segment_verifies(tmp_path):  # seq and count past the small-int cache: compared by value
    w = ledger.SegmentWriter.create(tmp_path / "runs" / "r" / "events", "engine-1")  # parents are created
    for i in range(300):
        w.append({"kind": "x", "i": i})
    w.seal()
    w.close()
    report = ledger.verify_segment(tmp_path / "runs" / "r" / "events" / "engine-1.jsonl")
    assert (report.error, report.sealed, report.lines) == (None, True, 300)


# the structural rules a re-hashing forger must still meet (the chain is keyless) --------------------


def _append_raw(path, row: dict) -> None:
    with path.open("ab") as f:
        f.write(ledger.canonical(row) + b"\n")


def test_a_segment_has_one_writer_until_it_closes(tmp_path):
    path = _write(tmp_path)
    first = ledger.SegmentWriter.reopen(path)
    try:
        with pytest.raises(BenchError) as e:
            ledger.SegmentWriter.reopen(path)
        assert e.value.code == "HB-LED-002" and "already has a writer" in e.value.message
    finally:
        first.close()
    ledger.SegmentWriter.reopen(path).close()  # released on close
    path.unlink()  # and its handle is closed: Windows refuses to delete an open file


def test_a_sealed_segment_is_never_reopened(tmp_path):
    path = _write(tmp_path, seal=True)
    with pytest.raises(BenchError) as e:
        ledger.SegmentWriter.reopen(path)
    assert e.value.code == "HB-LED-002" and "is sealed" in e.value.message


@pytest.mark.parametrize(("count", "head", "seq", "detail"), [  # each forged value both below and above the true one
    (2, None, 4, "seal does not match the segment"),
    (4, None, 4, "seal does not match the segment"),
    (3, "0" * 64, 4, "seal does not match the segment"),
    (3, "f" * 64, 4, "seal does not match the segment"),
    (3, None, 3, "chain break at line 4"),
    (3, None, 5, "chain break at line 4"),
])
def test_a_re_hashed_seal_must_still_match_its_segment(tmp_path, count, head, seq, detail):
    path = _write(tmp_path, n=3)
    last = ledger.read_segment(path)[-1]["hash"]
    _append_raw(path, ledger._chain({"kind": ledger.SEAL, "count": count, "head_hash": head or last}, seq, last))
    report = ledger.verify_segment(path)
    assert (report.error, report.detail) == ("HB-LED-002", detail)


@pytest.mark.parametrize("extra", [b'{"kind":"cell.prompt_se', b"\n", b"garbage\n"])  # T2-8: newline-ended too
def test_bytes_after_the_seal_are_a_break_not_a_torn_tail(tmp_path, extra):
    path = _write(tmp_path, seal=True)
    with path.open("ab") as f:
        f.write(extra)
    report = ledger.verify_segment(path)
    assert report.error == "HB-LED-002" and report.detail.startswith("bytes after the seal") and not report.torn_tail


def test_a_chained_line_after_the_seal_is_a_break(tmp_path):
    path = _write(tmp_path, n=2, seal=True)
    seal = json.loads(path.read_bytes().splitlines()[-1])
    _append_raw(path, ledger._chain({"kind": "cell.prompt_sent"}, 4, seal["hash"]))
    report = ledger.verify_segment(path)
    assert (report.error, report.detail) == ("HB-LED-002", "bytes after the seal (line 4)")


@pytest.mark.parametrize("sort_keys", [True, False])  # spaced (sorts after the canonical bytes) or unsorted (before)
def test_a_line_not_in_canonical_form_is_a_break(tmp_path, sort_keys):
    path = _write(tmp_path)
    lines = path.read_bytes().splitlines(keepends=True)
    row = json.loads(lines[1])
    reordered = {"seq": row["seq"], **row} if not sort_keys else row
    lines[1] = (json.dumps(reordered, sort_keys=True) if sort_keys else json.dumps(reordered, separators=(",", ":"))).encode() + b"\n"
    path.write_bytes(b"".join(lines))
    report = ledger.verify_segment(path)
    assert (report.error, report.detail, report.lines) == ("HB-LED-002", "line 2 is not in canonical form", 0)


def test_a_float_in_a_stored_line_is_a_break_not_a_crash(tmp_path):
    path = _write(tmp_path, n=2)
    rows = ledger.read_segment(path)
    body = {"kind": "x", "v": 1, "seq": 3, "prev_hash": rows[1]["hash"]}
    line = ledger.canonical(body)[:-1] + b',"hash":"0"}'
    with path.open("ab") as f:
        f.write(line.replace(b'"v":1', b'"v":1.5') + b"\n")
    report = ledger.verify_segment(path)
    assert report.error == "HB-LED-002" and report.detail.startswith("line 3: $.v: float is not allowed")


def test_canonical_rejects_a_non_string_key():
    with pytest.raises(TypeError, match="keys must be strings"):
        ledger.canonical({"v": {1: "x"}})


def test_a_record_may_not_forge_a_seal_or_its_chain_fields(tmp_path):  # T2-7: a caller's kind is never the seal's
    w = ledger.SegmentWriter.create(tmp_path / "events", "engine-1")
    try:
        for record in ({"kind": ledger.SEAL, "count": 0, "head_hash": w.head_hash}, {"kind": "x", "seq": 1}):
            with pytest.raises(ValueError):
                w.append(record)
    finally:
        w.close()
    assert ledger.verify_segment(tmp_path / "events" / "engine-1.jsonl").error is None


def test_a_seal_kind_built_at_runtime_is_still_refused(tmp_path):  # compared by value, not by identity (T12)
    kind = "".join(list(ledger.SEAL))  # an equal string that is not the constant's object
    assert kind == ledger.SEAL and kind is not ledger.SEAL
    w = ledger.SegmentWriter.create(tmp_path / "events", "engine-1")
    try:
        with pytest.raises(ValueError):
            w.append({"kind": kind, "count": 0, "head_hash": w.head_hash})
    finally:
        w.close()


# a break names the line it found, counted from 1 (T12) ------------------------------------

def test_an_unparseable_middle_line_of_a_newline_ended_segment_is_a_break(tmp_path):  # only the last line is the tail
    path = _write(tmp_path)
    lines = path.read_bytes().splitlines(keepends=True)
    lines[1] = b'{"kind":"hal\n'
    path.write_bytes(b"".join(lines))
    report = ledger.verify_segment(path)
    assert (report.error, report.detail, report.torn_tail) == ("HB-LED-002", "line 2 does not parse", False)


def test_a_first_line_not_in_canonical_form_is_line_1(tmp_path):
    path = _write(tmp_path)
    lines = path.read_bytes().splitlines(keepends=True)
    lines[0] = json.dumps(json.loads(lines[0]), sort_keys=True).encode() + b"\n"
    path.write_bytes(b"".join(lines))
    report = ledger.verify_segment(path)
    assert (report.error, report.detail) == ("HB-LED-002", "line 1 is not in canonical form")


def test_a_float_in_the_second_line_names_line_2(tmp_path):
    path = _write(tmp_path, n=1)
    first = ledger.read_segment(path)[0]
    body = {"kind": "x", "v": 1, "seq": 2, "prev_hash": first["hash"]}
    line = ledger.canonical(body)[:-1] + b',"hash":"0"}'
    with path.open("ab") as f:
        f.write(line.replace(b'"v":1', b'"v":1.5') + b"\n")
    report = ledger.verify_segment(path)
    assert report.error == "HB-LED-002" and report.detail.startswith("line 2: $.v: float is not allowed")


def test_a_torn_tail_past_the_small_int_cache_is_still_the_tail(tmp_path):  # the last index is compared by value
    w = ledger.SegmentWriter.create(tmp_path / "events", "engine-1")
    for i in range(300):
        w.append({"kind": "x", "i": i})
    w.close()
    path = tmp_path / "events" / "engine-1.jsonl"
    with path.open("ab") as f:
        f.write(b'{"kind":"hal\n')
    report = ledger.verify_segment(path)
    assert (report.error, report.torn_tail, report.lines) == (None, True, 300)


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
@given(n=st.integers(min_value=1, max_value=6), data=st.data())
def test_any_cut_or_insert_is_detected(tmp_path_factory, n, data):  # D2
    tmp = tmp_path_factory.mktemp("cut")
    path = _write(tmp, n=n, seal=True)
    raw = path.read_bytes()
    if data.draw(st.booleans()):  # cut raw[i:j], at least one byte
        i = data.draw(st.integers(min_value=0, max_value=len(raw) - 1))
        tampered = raw[:i] + raw[data.draw(st.integers(min_value=i + 1, max_value=len(raw))):]
    else:  # insert at least one byte at i
        i = data.draw(st.integers(min_value=0, max_value=len(raw)))
        tampered = raw[:i] + data.draw(st.binary(min_size=1, max_size=40)) + raw[i:]
    path.write_bytes(tampered)
    report = ledger.verify_segment(path)
    # a cut or insert breaks the chain, or leaves an unsealed prefix (then the recorded head exposes it: test_verify)
    assert report.error == "HB-LED-002" or not report.sealed


RECORDS = st.lists(st.dictionaries(st.sampled_from(["a", "b", "kind", "x"]),
                                   st.one_of(st.integers(-10**12, 10**12), st.text(max_size=20)),
                                   min_size=1, max_size=4).filter(lambda r: r.get("kind") != ledger.SEAL), min_size=1, max_size=8)


@settings(max_examples=100, deadline=None)
@given(records=RECORDS, seal=st.booleans())
def test_append_then_verify_round_trips(tmp_path_factory, records, seal):  # D2
    tmp = tmp_path_factory.mktemp("rt")
    with ledger.SegmentWriter.create(tmp / "f", "s") as w:
        for r in records:
            w.append(dict(r))
        head = w.seal() if seal else w.head_hash
    report = ledger.verify_segment(tmp / "f" / "s.jsonl")
    assert (report.error, report.sealed, report.torn_tail, report.lines, report.head_hash) == (None, seal, False, len(records), head)
    rows = ledger.read_segment(tmp / "f" / "s.jsonl")
    assert [{k: v for k, v in row.items() if k not in ledger.CHAIN_FIELDS} for row in rows] == records


@settings(max_examples=150, deadline=None)
@given(n=st.integers(min_value=0, max_value=5), data=st.data())
def test_a_torn_tail_is_handled_at_any_offset(tmp_path_factory, n, data):  # D2: a crash mid-write, at any byte
    tmp = tmp_path_factory.mktemp("torn")
    path = _write(tmp, n=n)
    raw = path.read_bytes()
    k = data.draw(st.integers(min_value=0, max_value=len(raw)))
    kept = raw[:k]
    path.write_bytes(kept)
    whole = kept.count(b"\n")  # lines that were written in full
    torn = not kept.endswith(b"\n") and kept != b""
    report = ledger.verify_segment(path)
    assert (report.error, report.lines, report.torn_tail) == (None, whole, torn)
    with ledger.SegmentWriter.reopen(path) as w:  # the owner cuts the torn line back and records the repair
        assert w.repaired == torn
        w.append({"kind": "after"})
    rows = ledger.read_segment(path)
    assert [r["kind"] for r in rows] == ["cell.launch_intent"] * whole + [ledger.TAIL_REPAIRED] * torn + ["after"]
    assert ledger.verify_segment(path).torn_tail is False
