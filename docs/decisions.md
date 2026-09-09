# Design decisions log

Running log of non-obvious decisions made during the build, so the reasoning isn't
lost between sessions. Newest entries at the bottom. Format: decision, then why.

---

### Offline-first design
**Decision:** The entire pipeline — sample size gate, assumption checks, test
selection, test execution — runs with zero external API calls. The *only* place an
external API is ever touched is one optional LLM call in
`agent/question_classifier.py`, used to map the user's plain-English question to a
group/value column pair, and that call has a mandatory offline (keyword-based)
fallback.
**Why:** The demo cannot depend on internet or API uptime during judging. A single
dropped connection must never take down the core agentic behavior the judges are
scoring — only the (non-essential) natural-language convenience layer.

### No framework dependency
**Decision:** No vector database, no RAG, no multi-agent framework (LangChain
agents, CrewAI, AutoGen, etc.) anywhere in the system.
**Why:** The hackathon explicitly states these are not mandatory, and none of them
solve a problem this pipeline actually has. The agentic behavior comes entirely from
branching on live intermediate statistical results — a plain Python orchestration
loop expresses that correctly and is far easier for judges to read and for a
2-person team to debug under deadline pressure. Adding a framework here would be
complexity with no corresponding capability gain.

### Sample-size gate runs before assumption checks
**Decision:** `validate_sample_size` is always the first call in the orchestration
loop, before `check_normality` or `check_equal_variance` ever run. If it fails, the
pipeline aborts immediately with "insufficient data" and no other `core/` function
is invoked.
**Why:** Shapiro-Wilk and Levene's are not meaningful (and can error or emit
garbage) on very small samples. Gating first avoids computing statistics on data
that can't support them, and keeps the abort path cheap and unambiguous — it's a
data-sufficiency check, not a statistical judgment call, so it shouldn't be tangled
into the same decision step as normality/variance.

### `core/` built against a contract, not against current file state
**Decision:** `agent/` orchestration code is written strictly against the shapes
defined in [docs/contract.md](contract.md), independent of whether `core/` currently
contains real implementations, placeholder mocks, or nothing at all.
**Why:** Teammate owns `core/` and its state varies by timing during a compressed
hackathon schedule. Coupling `agent/` development to `core/`'s current contents
would create a serial bottleneck between two people who should be able to work in
parallel. The contract is the interface; either side can stub the other out.

### `select_test` kept as pure decision logic, no statistics inside it
**Decision:** `test_selector.select_test` only inspects the dicts returned by the
assumption checks and returns a test name + reason — it never computes a statistic
itself.
**Why:** This function is the literal encoding of the agentic branch logic. Keeping
it free of any computation makes it trivially easy to unit test (feed it fixed
`passed: True/False` combinations, assert the right branch) and makes the decision
point auditable in isolation from the math that feeds it.

---

## Milestone 2: Agent Orchestration

### LLM classifier rejected in favor of keyword matching
**Decision:** `agent/question_classifier.py` uses pure deterministic regex/keyword
matching (`classify_question`) with zero external calls of any kind — not even the
optional LLM call originally scoped for this module in [CLAUDE.md](../CLAUDE.md).
**Why:** For demo reliability and Q&A defensibility. A judge asking "what does this
actually do" deserves an answer that's fully traceable to explicit rules, not "the
LLM decided" — and a live demo can't be allowed to fail because of a dropped
connection or a rate limit on stage. Keyword matching also makes the classifier
trivial to unit test exhaustively (see `tests/test_agent.py`), which an LLM call
is not. If an LLM-assisted classifier is added later for handling messier
phrasing, it must sit *in front of* this keyword matcher as an optional enhancement
— this function remains the guaranteed-available fallback, never the other way
around.

### `core/` placeholders are real implementations, not dummy stubs
**Decision:** Since `core/` had not been delivered by teammate as of this
milestone, the four contract functions (`validate_sample_size`, `check_normality`,
`check_equal_variance`, `select_test`, `run_test`) were implemented using real
scipy statistics (Shapiro-Wilk, Levene's, Student's/Welch's t-test, Mann-Whitney U)
rather than fixed dummy return values. Each file's docstring marks it as a
placeholder pending teammate's own implementation.
**Why:** The task required building `tests/test_agent.py` against 4 sample
datasets that must each drive the pipeline down a *different* branch
(student_t / welch_t / mann_whitney / aborted). Fixed dummy data can't produce
differentiated, meaningful branch outcomes — only real statistics can. This also
means Milestone 2 already demonstrates genuine end-to-end agentic behavior, not
just wiring; teammate's real `core/` can drop in later with zero changes to
`agent/controller.py` as long as the contract in
[docs/contract.md](contract.md) holds.

### Sample datasets generated deterministically, verified against expected branch
**Decision:** The 4 sample CSVs in `data/sample_datasets/` were generated with a
fixed `numpy` random seed and each one's Shapiro-Wilk/Levene's outcome was checked
by hand before being committed, to guarantee `normal_equal_variance.csv` truly
produces `student_t`, `non_normal.csv` truly produces `mann_whitney`,
`unequal_variance.csv` truly produces `welch_t`, and `tiny_sample.csv` (n=4 per
group) truly aborts.
**Why:** These files are the test fixtures for the entire branch-logic contract.
If a dataset only *coincidentally* landed on the intended branch, a scipy version
bump or a re-generation could silently flip a test's meaning. Verifying the
p-values at generation time makes the fixtures deliberately, not accidentally,
correct.

### Native `bool` required on every `passed` field
**Decision:** All boolean fields returned by `core/` functions (`passed`,
`significant`) are explicitly wrapped in `bool(...)` before being returned.
**Why:** scipy comparisons (e.g. `p_value >= alpha`) return `numpy.bool_`, not
Python `bool`. Left unwrapped, this leaks numpy types into `decision_trail` and
the final result dict, which is harmless in Python but is exactly the kind of
inconsistency that breaks JSON serialization later (Streamlit UI, saved run logs)
and looks unprofessional in a judge's console output. Caught during Milestone 2
by inspecting a live trace — see [docs/contract.md](contract.md) for the
resulting contract note.
