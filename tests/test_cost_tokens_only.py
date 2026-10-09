"""Tokens are the only cost axis on every rendered surface (R-115, X-NOPRICE).

A report and a CLI table rendered from a run whose `cost_usd` carries a value show no `$`, no "USD" and no
"cost_usd" label in the rendered text; and `bench/prices.yaml` parses with `entries == []`, the guard that no
USD number can be computed into a record before the price list is retired (a price entry is the only path to one).
"""

from html.parser import HTMLParser
from pathlib import Path

import yaml
from archived_runs import CODEX_MODEL, GOOD, make_root, make_run, set_prices

from harness_bench import views
from harness_bench.grade import runner
from harness_bench.report import cli_table, html

ROOT = Path(__file__).resolve().parents[1]
_LABEL_ATTRS = {"title", "aria-label", "alt"}


class _Visible(HTMLParser):
    """The rendered text: text nodes outside script and style, plus the title, aria-label and alt attribute values."""

    def __init__(self) -> None:
        super().__init__()
        self.parts: list[str] = []
        self._skip = 0

    def handle_starttag(self, tag, attrs):
        if tag in {"script", "style"}:
            self._skip += 1
        self.parts.extend(v for k, v in attrs if k in _LABEL_ATTRS and v)

    def handle_endtag(self, tag):
        if tag in {"script", "style"}:
            self._skip -= 1

    def handle_data(self, data):
        if not self._skip:
            self.parts.append(data)


def _visible_text(page: str) -> str:
    p = _Visible()
    p.feed(page)
    return "\n".join(p.parts)


def _priced_view(tmp_path):
    root = make_root(tmp_path)
    set_prices(root, [{"model": CODEX_MODEL, "effective": "2026-09-01", "source": "s", "input": "1.25", "output": 10,
                       "cache_read": "0.125", "cache_write": 0}])
    run_dir = make_run(root, tmp_path, {"a": GOOD})
    runner.run_pass(run_dir, root)
    view = views.load(run_dir)
    assert view.cells[0].scores["cost_usd"].value is not None  # the fixture carries a cost value
    return view


def _assert_no_usd(text: str) -> None:
    assert "$" not in text
    assert "usd" not in text.lower()


def test_the_cli_table_shows_no_usd_for_a_valued_cost(tmp_path):
    out, _ = cli_table.render(_priced_view(tmp_path), plain=True)
    _assert_no_usd(out)


def test_the_html_report_shows_no_usd_for_a_valued_cost(tmp_path):
    _assert_no_usd(_visible_text(html.render(_priced_view(tmp_path), archive_present=True)))


def test_the_price_list_has_no_entries():
    assert yaml.safe_load((ROOT / "bench" / "prices.yaml").read_text(encoding="utf-8"))["entries"] == []
