"""The model gateway's judge path (design phase3-gateway-judges; ADR-0009; W3-GW-I).

Slice 1 is the offline half: render a blinded, delimited request (`request`, `scrub`), validate an answer against
the one schema file (`schema`), key and keep verdict sets write-once (`store`), and reach a backend only through
`egress.check(...).release(...)` (`pipeline`). Every backend is behind the `backend.Backend` protocol; slice 1
ships only `backend.ReplayBackend`, which replays recorded answers and opens no process, file handle to a
network, socket or listener. Slice 2 adds `backend.Headless` (the pinned CLI, request on stdin, reached only inside the release).
"""
