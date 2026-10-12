"""`report.analysis.check_and_render` (ADR-0029 s7): the shared analyst-section check used by pack-cost and
cost-compare. Every cited number must be among the generated tables' numbers; the Markdown passes the egress scan."""

from __future__ import annotations

import pytest

from harness_bench.errors import BenchError
from harness_bench.report import analysis

TABLES = ("<p>12 outside a table</p><table><caption>t</caption><tr><th>Tokens</th><td>1,234,567</td>"
          "<td>0.25</td><td>40%</td></tr></table>")


def test_table_numbers_reads_only_the_tables_and_compares_by_value():
    found = analysis.table_numbers(TABLES)
    assert found == {"1234567", "0.25", "40"}
    assert analysis.canonical("1,500.0") == analysis.canonical("1500") == "1500"


def test_a_cited_number_in_the_tables_renders_under_the_heading():
    md = "# Where to cut\n\nCopilot pays **1,234,567** tokens per cell; a quarter (0.25) is one file, about 40%.\n"
    out = analysis.check_and_render(md, analysis.table_numbers(TABLES))
    assert '<section id="analysis">' in out
    assert "<h2>Analysis (written by an analyst, not generated)</h2>" in out
    assert "<strong>1,234,567</strong>" in out


def test_a_number_absent_from_the_tables_is_refused_and_listed():
    md = "Copilot pays 1,234,567 tokens; the hook costs 173 s and 9.56x more.\n"
    with pytest.raises(BenchError) as exc:
        analysis.check_and_render(md, analysis.table_numbers(TABLES))
    assert exc.value.code == "HB-USR-002"
    assert str(exc.value).endswith("9.56, 173")


def test_list_markers_and_frontmatter_are_not_citations():
    md = "---\nreview-by: \"2027-04-12\"\n---\n\n1. narrow the file (0.25)\n2. keep the rest\n"
    assert "<ol>" in analysis.check_and_render(md, {"0.25"})


def test_the_markdown_is_scanned_before_it_is_embedded():
    with pytest.raises(BenchError) as exc:
        analysis.check_and_render("Ask someone@example.org about 0.25.\n", {"0.25"})
    assert exc.value.code == "HB-SEC-001"
    assert "someone@example.org" not in str(exc.value)


def test_markup_in_the_markdown_is_escaped():
    out = analysis.check_and_render("A <script>alert(0.25)</script> line.\n", {"0.25"})
    assert "<script>" not in out and "&lt;script&gt;" in out
