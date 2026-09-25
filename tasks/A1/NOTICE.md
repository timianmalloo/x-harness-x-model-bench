# A1 licence note

A1 is built from two upstream sources. Each part of this folder keeps its upstream licence.

| Part of this folder | Upstream | Licence (as read from upstream on 2026-09-25) |
| --- | --- | --- |
| The problem text in `prompt.md` (after the `---`), `oracle/clarifications.yaml` (question, reply, type) | ClarifyCodeBench, `github.com/fangz-cs/ClarifyCodeBench` at `5e2d5b5ce6259daa034cebb69f65e5e4c6dec3e9`, `data/ClarifyCodeBench.jsonl`, `task_199` | **Annotations: MIT**, "Copyright (c) 2026 Zheng Fang and the ClarifyCodeBench authors" (`LICENSE`). The same repository says the underlying problems and hidden tests are "governed by the **LiveCodeBench** license" (`README.md` § License; `data/README.md` § License). The underspecified text is a deletion-only edit of the LiveCodeBench problem, so the problem text falls under both. |
| `tests/a1_cases.json` (43 input/output cases) | LiveCodeBench, Hugging Face dataset `livecodebench/code_generation_lite` at revision `0fe84c3912ea0c4d4a78037083943e8f0c4dd505`, `test6.jsonl` (sha256 `bb4c364f…fd1f5`, equal to its LFS oid), problem `abc396_c` | The dataset card declares `license: cc` and names no Creative Commons variant (`README.md` front matter at that revision). The LiveCodeBench code repository, `github.com/LiveCodeBench/LiveCodeBench` at `28fef95ea8c9f7a547c8329f2cd3d32b92c1fa24`, is **MIT**, "Copyright (c) 2024 LiveCodeBench" (`LICENSE`). |
| The stdio comparison rule in `tests/test_a1_hidden.py` | Ported from LiveCodeBench `lcb_runner/evaluation/testing_util.py` (`get_stripped_lines`, `grade_stdio`) at `28fef95` | MIT (as above). |
| `workspace/`, `oracle/reference/`, `oracle/heldout_questions.yaml`, `oracle/README.md`, this file | Authored for this bench | The bench repository's terms. |

The problem was first published by AtCoder (ABC 396, problem C, "Buy Balls", 2025-03-08). **Not checked:**
AtCoder's own terms for its statements and test data. The licence chain above is taken as LiveCodeBench states it.

**Open:** the dataset card's `cc` does not name a variant (BY, BY-SA, BY-NC, ...). That matters only if this
folder is redistributed outside the bench repository. Confirm the variant with LiveCodeBench before then.

Citations the upstreams ask for:

- Fang, Z. et al. *ClarifyCodeBench: Evaluating LLMs on Clarifying Ambiguous Requirements for Code Generation.* arXiv:2607.00711, 2026.
- Jain, N. et al. *LiveCodeBench: Holistic and Contamination Free Evaluation of Large Language Models for Code.* arXiv:2403.07974, 2024.
