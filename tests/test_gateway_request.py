"""The judge request `judge-request/1` (design phase3-gateway-judges sections 7.1, 7.2; T-GW-01, 02, 06, 33).

Offline and pure: no backend, no file outside tmp_path. Artifacts are synthetic bytes written here.
"""

import hashlib
import json

from harness_bench.gateway import request, scrub

ARTIFACTS = (("docs/architecture.md", b"# Queue\nThe queue is a binary heap. Claude wrote this note.\n"),
             ("priority_queue.py", b"def push(q, x):\n    q.append(x)\n"))


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _artifact_sha256(artifacts) -> str:
    """The design's recipe for several files: sha256 of the canonical list of (path, sha256 of the raw bytes)."""
    body = {"artifacts": [[path, _sha(raw)] for path, raw in artifacts]}
    return _sha(json.dumps(body, sort_keys=True, separators=(",", ":")).encode())


def test_t_gw_01_render_is_deterministic_and_the_nonce_comes_from_the_raw_bytes():
    first = request.render("Preamble.", "1. Item one.\n2. Item two.\n", 2, ARTIFACTS, scrub.FAMILY_WORDS)
    second = request.render("Preamble.", "1. Item one.\n2. Item two.\n", 2, ARTIFACTS, scrub.FAMILY_WORDS)
    raw_hash = _artifact_sha256(ARTIFACTS)
    scrubbed = tuple((p, scrub.scrub(r.decode(), scrub.FAMILY_WORDS).encode()) for p, r in ARTIFACTS)
    assert first.text.encode() == second.text.encode()
    assert (first.artifact_sha256, first.nonce) == (raw_hash, raw_hash[:12])
    assert first.nonce != _artifact_sha256(scrubbed)[:12]  # hashed before the scrub (step 1 before step 3)
    assert f"<<<DATA {raw_hash[:12]} docs/architecture.md>>>\n# Queue\nThe queue is a binary heap. [redacted] wrote " \
           f"this note.\n<<<END DATA {raw_hash[:12]}>>>" in first.text
    assert "Claude" not in first.text
