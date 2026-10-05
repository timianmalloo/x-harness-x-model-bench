"""The browser ring (design phase4-report.md section 12; ruling R-81 DR-R-9).

Playwright drives the generated `report.html` over `file://` in headless Chromium -- the only way to
observe what a real DOM does with `report.js` (CSP enforcement, focus, `performance.mark`, network
requests). This ring runs at readiness, never in the offline gate: the `browser` marker is excluded
from `addopts` and from CI's own `-m` selector (`pyproject.toml`, `.github/workflows/ci.yml`), the
same way `slow`, `workstation` and `gate` are. Run with `uv run pytest -m browser`.

Scope (R4's own done-when): UIA-1 (offline load, zero requests, zero console errors, the section ids
the page renders) and UIA-8's functional keyboard path (sort, isolate, pack switch, popover open plus
Esc, cell card). The 320 px reflow and sticky-bar-focus measurement (UIA-3) and axe (UIA-2) are R9's
scope (design section 15), named `Not in scope` in this slice's brief -- so "the focus ring is
visible" is operationalized here as "focus lands on, and returns to, the expected element", not a
pixel-level render check.
"""

from pathlib import Path

import pytest
from archived_runs import GOOD, make_root, make_run

from harness_bench import views
from harness_bench.grade import runner
from harness_bench.report import html

pytestmark = pytest.mark.browser

sync_playwright = pytest.importorskip("playwright.sync_api").sync_playwright


@pytest.fixture
def report_path(tmp_path):
    root = make_root(tmp_path)
    run_dir = make_run(
        root, tmp_path, {"a": GOOD, "b": GOOD, "c": GOOD},
        combos={"a": "combo-a", "b": "combo-b", "c": "combo-a"},
    )
    runner.run_pass(run_dir, root)
    view = views.load(run_dir)
    return html.write(run_dir, view)


@pytest.fixture
def browser_page(report_path):
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        yield page, report_path
        browser.close()


def test_offline_zero_requests(browser_page):
    """UIA-1 / US-40 c1: the `report-ready` mark fires, the page makes no network request beyond its
    own load, no console error is raised, and every section the generator rendered is in the DOM."""
    page, report_path = browser_page
    requests = []
    console_errors = []
    page.on("request", lambda req: requests.append(req.url))
    page.on("console", lambda msg: console_errors.append(msg.text) if msg.type == "error" else None)
    page.on("pageerror", lambda exc: console_errors.append(str(exc)))

    page.goto(report_path.as_uri())
    page.wait_for_function("() => performance.getEntriesByName('report-ready').length > 0")

    assert page.evaluate("performance.getEntriesByName('report-ready').length") > 0
    assert len(requests) == 1 and requests[0] == report_path.as_uri()
    assert console_errors == []
    ids = page.eval_on_selector_all("main > section[id]", "els => els.map(e => e.id)")
    # "controls" (R4 join review): the control bar's own publication-scan unit (US-47 c3) -- chrome,
    # not one of the report's eleven IA sections, but still a real <section> in the DOM.
    # "pack-improvement": always present and always last (design pack-improvement-section.md section 2).
    assert set(ids) == {"header", "controls", "validity", "leaderboard", "pack-effect", "cost-frontier", "areas",
                        "scenarios", "context-growth", "summaries", "runs", "pack-improvement"}


def test_keyboard_path(browser_page):
    """UIA-8: sort, isolate (the last-combo refusal), the pack switch, an evidence popover's open plus
    Esc-close-and-focus-return, and a Runs cell card, each driven by the keyboard alone."""
    page, report_path = browser_page
    page.goto(report_path.as_uri())

    # 1. Sort: Enter on the Gated column's sort button orders the leaderboard and marks aria-sort.
    sort_btn = page.locator('#leaderboard-table button.sort[data-sort-key="gated"]')
    sort_btn.focus()
    assert page.evaluate("document.activeElement.dataset.sortKey") == "gated"
    page.keyboard.press("Enter")
    aria_sort = sort_btn.evaluate("btn => btn.closest('th').getAttribute('aria-sort')")
    assert aria_sort == "descending"

    # 2. Evidence popover: focusing an .ev button opens its popover (section 7); Esc closes it and
    # returns focus to the button that owned it (1.4.13). Done before isolating combos below, since
    # that hides rows and a real browser refuses focus to a display:none element (TEST-A: interact
    # with what is actually visible at the time).
    ev_btn = page.locator(".ev").first
    ev_btn.focus()
    pop_id = ev_btn.get_attribute("aria-describedby")
    assert pop_id
    assert page.locator(f"#{pop_id}").is_visible()
    page.keyboard.press("Escape")
    assert ev_btn.get_attribute("aria-describedby") is None
    assert page.locator(f"#{pop_id}").is_hidden()
    assert page.evaluate("document.activeElement.classList.contains('ev')")

    # 3. Cell card: a Runs row's <details> opens via Enter on its native <summary> -- no JS involved,
    # proving the page still works when a reader tabs straight to it. Also before isolating combos.
    summary = page.locator("#runs details summary").first
    details = page.locator("#runs details").first
    summary.focus()
    page.keyboard.press("Enter")
    assert details.get_attribute("open") is not None

    # 4. Isolate: toggle every combo off but one; the last one refuses (UIA-14): it stays pressed and
    # visible, aria-disabled, and its aria-describedby resolves to visible reason text.
    combo_buttons = page.locator("#legend .tg")
    count = combo_buttons.count()
    for i in range(count - 1):
        combo_buttons.nth(i).focus()
        page.keyboard.press("Enter")
    last = combo_buttons.nth(count - 1)
    last.focus()
    page.keyboard.press("Enter")
    assert last.get_attribute("aria-pressed") == "true"
    assert last.get_attribute("aria-disabled") == "true"
    reason_id = last.get_attribute("aria-describedby")
    assert reason_id is not None
    reason_text = page.locator(f"#{reason_id}").inner_text()
    assert reason_text == "At least one combo must stay visible."

    # 5. Pack switch: Enter on "on" (when it is not itself disabled) marks <main> pack-on.
    on_btn = page.locator('#pack-switch .tg[data-pack="on"]')
    if on_btn.get_attribute("aria-disabled") != "true":
        on_btn.focus()
        page.keyboard.press("Enter")
        assert "pack-on" in (page.locator("main").get_attribute("class") or "")


# --- X-H2: report section 3 (EVU-5, EVX-2) -----------------------------------------------------------

AXE = Path(__file__).parent / "vendor" / "axe-core" / "axe.min.js"


@pytest.fixture
def campaign_page(tmp_path):
    from test_campaign_section import (
        make_world,  # the real-ledger campaign world of tests/test_campaign_section.py
    )

    world = make_world(tmp_path / "campaign")
    run_dir = tmp_path / "campaign-run"
    run_dir.mkdir()
    path = html.write(run_dir, world.view, campaign_obj=world.obj)
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": 1280, "height": 800})
        page.goto(path.as_uri())
        yield page
        browser.close()


@pytest.mark.parametrize("scheme", ["light", "dark"])
def test_evu_5_axe_light_and_dark(campaign_page, scheme):
    """EVU-5: axe-core (WCAG 2.2 AA) reports zero violations for the verdict section in both colour schemes. The vendored
    source runs through `evaluate` (the page's CSP refuses an injected script tag)."""
    campaign_page.emulate_media(color_scheme=scheme)
    campaign_page.evaluate(AXE.read_text(encoding="utf-8"))
    found = campaign_page.evaluate(
        "axe.run(document.querySelector('#property-verdicts'),"
        " {runOnly: ['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa', 'wcag22aa']}).then(r =>"
        " ({violations: r.violations.map(v => v.id + ': ' + v.nodes.length), passes: r.passes.length}))")
    assert found["passes"] > 0, "axe ran no rule on the section"  # a run that checked nothing is not a pass
    assert found["violations"] == []


def test_evx_2_the_first_verdict_row_is_visible_after_the_header_jump_link(campaign_page):
    """EVX-2: at 1280x800, activating the jump link shows the first verdict row without further scrolling."""
    campaign_page.click("nav a[href='#property-verdicts']")
    box = campaign_page.locator("#property-verdicts tbody tr").first.bounding_box()
    assert box is not None and 0 <= box["y"] and box["y"] + box["height"] <= 800
