"""
Streamlit demo UI for the data-analysis-pipeline-agent.

Thin presentation layer only -- every agentic decision happens inside
agent.controller.run_pipeline(). This file's only job is to collect a CSV and
a question, call the pipeline once, and render its decision_trail so a judge
can see the branch-by-branch reasoning as it happened, not just a final number.
"""

import os

import streamlit as st

from agent.controller import run_pipeline

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SAMPLE_DIR = os.path.join(BASE_DIR, "data", "sample_datasets")

# Preset questions are deliberately worded to classify as "two_group" under
# agent/question_classifier.py's keyword rules (no "relationship"/"among"/etc.)
# so the demo is guaranteed not to hit the needs_clarification branch.
PRESETS = {
    "Normal data, equal variance": {
        "path": os.path.join(SAMPLE_DIR, "normal_equal_variance.csv"),
        "question": "Is there a difference between group A and group B?",
        "expect": "Student's t-test",
    },
    "Non-normal data": {
        "path": os.path.join(SAMPLE_DIR, "non_normal.csv"),
        "question": "How does group A compare to group B?",
        "expect": "Mann-Whitney U test",
    },
    "Normal data, unequal variance": {
        "path": os.path.join(SAMPLE_DIR, "unequal_variance.csv"),
        "question": "Is there a significant difference between group A and group B?",
        "expect": "Welch's t-test",
    },
    "Tiny sample (n < 5 per group)": {
        "path": os.path.join(SAMPLE_DIR, "tiny_sample.csv"),
        "question": "Compare group A versus group B.",
        "expect": "Abort -- insufficient data",
    },
}

STEP_ICONS = {
    "LOAD": "📂",
    "CLASSIFY": "🔎",
    "VALIDATE_SIZE": "🔢",
    "CHECK_NORMALITY": "📈",
    "CHECK_VARIANCE": "📊",
    "SELECT_TEST": "🧭",
    "EXECUTE": "⚙️",
    "REPORT": "✅",
}


def _describe(entry):
    """Turn one decision_trail record into a human-readable 'checked' line.

    Never dump the raw dict -- interpret it per step so the trail reads like
    an explanation, not a debug log.
    """
    step = entry["step"]
    res = entry["result"]

    if step == "LOAD":
        if "error" in res:
            return f"Failed to load dataset: {res['error']}"
        return f"Loaded {res['n_a']} values for group_a and {res['n_b']} for group_b."
    if step == "CLASSIFY":
        return f"Question classified as **{res['question_type']}**."
    if step == "VALIDATE_SIZE":
        return res["reason"]
    if step == "CHECK_NORMALITY":
        return (
            f"Shapiro-Wilk p-values: group_a={res['p_value_a']:.4f}, "
            f"group_b={res['p_value_b']:.4f}. {res['reason']}"
        )
    if step == "CHECK_VARIANCE":
        return f"Levene's test p-value: {res['p_value']:.4f}. {res['reason']}"
    if step == "SELECT_TEST":
        return res["reason"]
    if step == "EXECUTE":
        return (
            f"Ran {res['test_used']}: statistic={res['statistic']:.4f}, "
            f"p-value={res['p_value']:.4f}."
        )
    if step == "REPORT":
        return "All steps completed; result compiled below."
    return str(res)


def render_trail(decision_trail):
    st.subheader("Agent reasoning trail")
    for entry in decision_trail:
        step = entry["step"]
        checked = _describe(entry)
        decision = entry["decision"]
        icon = STEP_ICONS.get(step, "•")

        is_select_test = step == "SELECT_TEST"
        is_normality_branch = step == "CHECK_NORMALITY" and not entry["result"].get("passed", True)

        if is_select_test:
            with st.container(border=True):
                st.markdown(f"### {icon} {step}  &nbsp; 🔀 `DECISION POINT`")
                st.markdown(f"**Checked:** {checked}")
                st.success(f"**Decision:** {decision}")
        elif is_normality_branch:
            with st.container(border=True):
                st.markdown(f"### {icon} {step}  &nbsp; ⚡ `BRANCH TRIGGERED`")
                st.markdown(f"**Checked:** {checked}")
                st.warning(f"**Decision:** {decision}")
        else:
            with st.container(border=True):
                st.markdown(f"#### {icon} {step}")
                st.markdown(f"**Checked:** {checked}")
                st.markdown(f"**Decision:** {decision}")


st.set_page_config(page_title="Data Analysis Pipeline Agent", page_icon="🧪", layout="centered")

st.title("🧪 Data Analysis Pipeline Agent")
st.caption(
    "Give it a dataset and a plain-English comparison question. It runs the "
    "assumption checks itself and picks the correct statistical test based on "
    "what those checks reveal -- it does not run one fixed test."
)

st.divider()

# ---------------------------------------------------------------------------
# 1. Data source
# ---------------------------------------------------------------------------

st.subheader("1. Choose a dataset")

source_choice = st.radio(
    "Data source",
    ["Upload your own CSV"] + list(PRESETS.keys()),
    index=1,
    label_visibility="collapsed",
)

uploaded_file = None
csv_source = None

if source_choice == "Upload your own CSV":
    uploaded_file = st.file_uploader(
        "CSV with two numeric columns named group_a and group_b", type=["csv"]
    )
    csv_source = uploaded_file
    if st.session_state.get("_last_source") != "upload":
        st.session_state["question_input"] = ""
        st.session_state["_last_source"] = "upload"
else:
    preset = PRESETS[source_choice]
    csv_source = preset["path"]
    st.caption(f"Expected outcome for the demo question below: **{preset['expect']}**")
    if st.session_state.get("_last_source") != source_choice:
        st.session_state["question_input"] = preset["question"]
        st.session_state["_last_source"] = source_choice

st.subheader("2. Ask your comparison question")
question = st.text_input(
    "Comparison question",
    key="question_input",
    placeholder="e.g. Is there a difference between group A and group B?",
    label_visibility="collapsed",
)

run_disabled = source_choice == "Upload your own CSV" and uploaded_file is None
run_clicked = st.button("▶️ Run Agent", type="primary", disabled=run_disabled)
if run_disabled:
    st.caption("Upload a CSV to enable the Run Agent button.")

st.divider()

# ---------------------------------------------------------------------------
# 3. Run + render
# ---------------------------------------------------------------------------

if run_clicked:
    if not question.strip():
        st.warning("Please enter a comparison question before running the agent.")
    else:
        with st.spinner("Running assumption checks and selecting a test..."):
            try:
                st.session_state["result"] = run_pipeline(csv_source, question)
            except Exception as exc:  # a live demo must never hard-crash on stage
                st.session_state["result"] = None
                st.error(f"Unexpected error while running the pipeline: {exc}")

result = st.session_state.get("result")

if result is not None:
    render_trail(result["decision_trail"])

    st.divider()

    if result["status"] == "aborted":
        st.error("🛑 **Insufficient data — pipeline aborted before running any test**")
        st.markdown(result["reasoning"])
    elif result["status"] == "needs_clarification":
        st.warning(
            "🤔 **Could not confidently classify this as a two-group comparison.** "
            'Please rephrase your question — e.g. "Is there a difference between '
            'group A and group B?"'
        )
        st.markdown(result["reasoning"])
    elif result["status"] == "success":
        st.subheader("Final result")
        with st.container(border=True):
            col1, col2, col3 = st.columns(3)
            col1.metric("Test used", result["test_used"])
            col2.metric("p-value", f"{result['p_value']:.4f}")
            col3.metric("Significant?", "Yes" if result["significant"] else "No")
            st.markdown(f"**Test statistic:** {result['statistic']:.4f}")
            st.markdown("**Reasoning:**")
            st.markdown(result["reasoning"])
