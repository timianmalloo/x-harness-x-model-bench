"""A minimal WSGI deliverable with a factory: it writes `notes.db` into its state dir, then echoes the query."""

import html
import os
from urllib.parse import unquote


def create_app(state_dir, escape=True):
    open(os.path.join(state_dir, "notes.db"), "w").close()

    def app(environ, start_response):
        text = unquote(environ["QUERY_STRING"])
        body = (html.escape(text) if escape else text).encode()
        start_response("200 OK", [("Content-Type", "text/html")])
        return [body]

    return app
