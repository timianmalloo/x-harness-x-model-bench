"""Analyze mutation killer coverage, unreferenced ceremony tests, and consolidation groups."""

from __future__ import annotations

import glob
import json
import xml.etree.ElementTree as ET
from collections import defaultdict
from dataclasses import dataclass


@dataclass
class SuiteTest:
    ring: str
    classname: str
    name: str
    time: float
    full_id: str
    base_id: str
    file_path: str


def load_suite() -> list[SuiteTest]:
    tests = []
    for path, ring in [
        ("C:/Projects/ci-opt-profile/default.xml", "default"),
        ("C:/Projects/ci-opt-profile/slow.xml", "slow"),
    ]:
        root = ET.parse(path).getroot()
        for tc in root.findall(".//testcase"):
            cls = tc.attrib["classname"]
            name = tc.attrib["name"]
            t = float(tc.attrib.get("time", 0.0))
            file_path = cls.replace(".", "/") + ".py"
            full_id = f"{file_path}::{name}"
            base_name = name.split("[")[0]
            base_id = f"{file_path}::{base_name}"
            tests.append(
                SuiteTest(
                    ring=ring,
                    classname=cls,
                    name=name,
                    time=t,
                    full_id=full_id,
                    base_id=base_id,
                    file_path=file_path,
                )
            )
    return tests


def load_mutants() -> dict[str, list[dict]]:
    mutants_by_file = {}
    for p in glob.glob("tests/mutations/*.json"):
        norm_path = p.replace("\\", "/")
        with open(p, encoding="utf-8") as fp:
            mutants_by_file[norm_path] = json.load(fp)
    return mutants_by_file


def analyze():
    suite = load_suite()
    mutants_by_file = load_mutants()

    # Map mutant -> list of test patterns
    # Map test full_id -> set of mutant identifiers (file::name)
    all_mutants = []
    test_pattern_to_mutants = defaultdict(set)
    for mfile, mlist in mutants_by_file.items():
        for m in mlist:
            m_id = f"{mfile}::{m['name']}"
            all_mutants.append((m_id, m))
            for t_pattern in m.get("tests", []):
                test_pattern_to_mutants[t_pattern].add(m_id)

    # For each test in suite, find all mutants it matches
    test_to_mutants = defaultdict(set)
    for st in suite:
        # Match full_id, base_id, or whole file
        if st.full_id in test_pattern_to_mutants:
            test_to_mutants[st.full_id].update(test_pattern_to_mutants[st.full_id])
        if st.base_id in test_pattern_to_mutants:
            test_to_mutants[st.full_id].update(test_pattern_to_mutants[st.base_id])
        if st.file_path in test_pattern_to_mutants:
            test_to_mutants[st.full_id].update(test_pattern_to_mutants[st.file_path])

    # Unreferenced tests (named by 0 mutants)
    unreferenced = [st for st in suite if len(test_to_mutants[st.full_id]) == 0]
    referenced = [st for st in suite if len(test_to_mutants[st.full_id]) > 0]

    # Consolidation groups: groups of tests named for EXACTLY the same non-empty set of mutants
    signature_to_tests = defaultdict(list)
    for st in referenced:
        sig = frozenset(test_to_mutants[st.full_id])
        signature_to_tests[sig].append(st)

    duplicate_groups = {sig: tlist for sig, tlist in signature_to_tests.items() if len(tlist) > 1}

    return suite, all_mutants, unreferenced, referenced, duplicate_groups, test_to_mutants


def main():
    suite, all_mutants, unreferenced, referenced, duplicate_groups, _test_to_mutants = analyze()

    print(f"Total suite tests: {len(suite)}")
    print(f"Total mutants in tests/mutations/*.json: {len(all_mutants)}")
    print(f"Tests named by at least 1 mutant: {len(referenced)} ({len(referenced)/len(suite)*100:.1f}%)")
    print(f"Tests named by NO mutant (ceremony candidates): {len(unreferenced)} ({len(unreferenced)/len(suite)*100:.1f}%)")
    print(f"Summed time of unreferenced tests: {sum(t.time for t in unreferenced):.2f}s")

    # Unreferenced by file
    unref_by_file = defaultdict(list)
    for t in unreferenced:
        unref_by_file[t.file_path].append(t)

    print("\nTop files by unreferenced test count:")
    for fp, tlist in sorted(unref_by_file.items(), key=lambda x: len(x[1]), reverse=True)[:15]:
        total_t = sum(x.time for x in tlist)
        print(f"  {fp}: {len(tlist)} tests ({total_t:.2f}s)")

    # Unreferenced among tests >= 5s
    unref_5s = [t for t in unreferenced if t.time >= 5.0]
    print(f"\nUnreferenced tests >= 5s: {len(unref_5s)} tests, sum={sum(t.time for t in unref_5s):.2f}s")
    for t in unref_5s:
        print(f"  [{t.ring.upper()}] {t.time:6.2f}s | {t.full_id}")

    # Duplicate groups
    print(f"\nConsolidation groups (multiple tests killing exactly same mutant set): {len(duplicate_groups)} groups")
    total_tests_in_dups = sum(len(g) for g in duplicate_groups.values())
    total_time_in_dups = sum(sum(t.time for t in g) for g in duplicate_groups.values())
    print(f"Total tests in consolidation groups: {total_tests_in_dups} ({total_time_in_dups:.2f}s)")

    # Largest consolidation groups
    print("\nTop consolidation groups by test count:")
    for sig, tlist in sorted(duplicate_groups.items(), key=lambda x: len(x[1]), reverse=True)[:10]:
        total_t = sum(t.time for t in tlist)
        print(f"  Group of {len(tlist)} tests ({total_t:.2f}s) killing {len(sig)} mutants:")
        for t in tlist[:4]:
            print(f"    - {t.time:5.2f}s | {t.full_id}")
        if len(tlist) > 4:
            print(f"    ... and {len(tlist)-4} more")


if __name__ == "__main__":
    main()
