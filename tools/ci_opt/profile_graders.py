"""Profile representative default-ring grader tests with cProfile and report cumulative function shares."""

from __future__ import annotations

import pstats
from dataclasses import dataclass
from pathlib import Path


@dataclass
class FunctionStat:
    filename: str
    line: int
    name: str
    cumtime: float
    selftime: float
    ncalls: int
    share: float


def profile_summary(pstats_path: str | Path, test_func_name: str, top_n: int = 10) -> tuple[float, list[FunctionStat]]:
    p = pstats.Stats(str(pstats_path))
    test_key = next((k for k in p.stats if test_func_name in k[2]), None)
    if not test_key:
        raise ValueError(f"Function {test_func_name} not found in {pstats_path}")

    test_cum = p.stats[test_key][3]

    # Map callers to find functions in the subtree of test_key
    root_wrappers = {"<frozen runpy>", "pytest", "_pytest", "pluggy"}
    callees: dict[tuple, dict[tuple, tuple]] = {}
    for child, v in p.stats.items():
        for parent, cinfo in v[4].items():
            callees.setdefault(parent, {})[child] = cinfo

    tree_nodes: set[tuple] = set()

    def get_tree(node: tuple) -> None:
        tree_nodes.add(node)
        for child in callees.get(node, {}):
            if child not in tree_nodes and not any(w in child[0] for w in root_wrappers):
                get_tree(child)

    get_tree(test_key)

    rows: list[FunctionStat] = []
    for node in tree_nodes:
        if node == test_key:
            continue
        callers = [ci for parent, ci in p.stats[node][4].items() if parent in tree_nodes]
        if not callers:
            continue
        tot_calls = sum(ci[1] for ci in callers)
        tot_cum = sum(ci[3] for ci in callers)
        tot_self = sum(ci[2] for ci in callers)
        fname = node[0].replace("C:\\Projects\\x-harness-x-model-bench-w3-ciopt2\\", "")
        rows.append(
            FunctionStat(
                filename=fname,
                line=node[1],
                name=node[2],
                cumtime=tot_cum,
                selftime=tot_self,
                ncalls=tot_calls,
                share=(tot_cum / test_cum) * 100 if test_cum else 0.0,
            )
        )

    rows.sort(key=lambda x: x.cumtime, reverse=True)
    return test_cum, rows[:top_n]


def main() -> None:
    targets = [
        ("C:/Projects/bench-test/prof_arch.pstats", "test_the_d1_reference_plus_using_newtonsoft_json_is_0"),
        ("C:/Projects/bench-test/prof_drift.pstats", "test_a_pack_commit_stand_in_outside_the_blast_radius_is_not_scope_creep"),
        ("C:/Projects/bench-test/prof_mutation.pstats", "test_no_tests_written_when_only_source_changed_is_na"),
    ]

    for pfile, func_name in targets:
        print("\n==================================================")
        print(f"Profiling: {func_name}")
        print(f"Profile: {pfile}")
        print("==================================================")
        total_t, stats = profile_summary(pfile, func_name, 10)
        print(f"Total test execution time: {total_t:.3f} s\n")
        print(f"{'#':2s} | {'CumTime':8s} | {'Share':6s} | {'SelfTime':8s} | {'Calls':6s} | {'Function'}")
        print("-" * 80)
        for i, st in enumerate(stats, 1):
            fn_repr = f"{st.filename}:{st.line}({st.name})"
            print(f"{i:2d} | {st.cumtime:7.3f}s | {st.share:5.1f}% | {st.selftime:7.3f}s | {st.ncalls:6d} | {fn_repr}")


if __name__ == "__main__":
    import sys
    for _stream in (sys.stdout, sys.stderr):
        if hasattr(_stream, "reconfigure"):
            try:
                _stream.reconfigure(encoding="utf-8", errors="replace")
            except (ValueError, OSError):
                pass
    main()
