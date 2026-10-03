# S2 spike: verified reads of bottle's signed-cookie code

Pin: `bottlepy/bottle` @ `cbd569c447b3fd53f194cef9a306146ce6a07a59`, file `bottle.py`. Read on 2026-10-03 in a fresh clone at that commit. Status: **Verified** (the lines were opened and read).

| line | what it holds |
| --- | --- |
| `bottle.py:2978` | `cookie_encode` serialises its data with `pickle.dumps` before signing. |
| `bottle.py:1803` | The `set_cookie` docstring warns that a leaked signing secret allows code execution on the server when a cookie is unpickled. |
| `bottle.py:1190` | `get_cookie` (with a secret) calls `pickle.loads` on the signed payload after the signature check. |

Consequence for W1-I section 12, open item 2: the "Inferred" label on `:2978` and `:1803` becomes Verified, and `:1190` is a third read site. Signed-cookie deserialisation is part of bottle's session mechanism, so S2's probe class is being redesigned (an Owner matter) to avoid it. No probe, variant or run exists for S2; the spike is stopped.
