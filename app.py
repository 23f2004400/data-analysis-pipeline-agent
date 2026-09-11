"""
Streamlit demo UI for the data-analysis-pipeline-agent.

Thin presentation layer only -- every agentic decision happens inside
agent.controller.run_pipeline(). This file's only job is to collect a CSV and
a question, call the pipeline once, and render its decision_trail so a judge
can see the branch-by-branch reasoning as it happened, not just a final number.

"""

import os
import time
from datetime import datetime

import streamlit as st
from fpdf import FPDF

from agent.controller import run_pipeline
from data.loader import REQUIRED_COLUMNS, load_groups

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SAMPLE_DIR = os.path.join(BASE_DIR, "data", "sample_datasets")

STEP_REVEAL_DELAY = 0.35  # seconds between steps during the live-reveal animation

# Preset questions are deliberately worded to classify as "two_group" under
# agent/question_classifier.py's real keyword rules (\bbetween\b, \bcompare\b,
# \bcomparison\b, \bvs\.?\b, \bversus\b, \bdifference\b) -- no "relationship",
# "among", "correlat", etc., which route elsewhere.
SAMPLE_PRESETS = {
    "Normal data": {
        "path": os.path.join(SAMPLE_DIR, "normal_equal_variance.csv"),
        "question": "Is there a difference between group A and group B?",
        "expect": "Student's t-test",
    },
    "Non-normal data": {
        "path": os.path.join(SAMPLE_DIR, "non_normal.csv"),
        "question": "How does group A compare to group B?",
        "expect": "Mann-Whitney U test",
    },
    "Unequal variance": {
        "path": os.path.join(SAMPLE_DIR, "unequal_variance.csv"),
        "question": "Is there a significant difference between group A and group B?",
        "expect": "Welch's t-test",
    },
    "Insufficient sample size": {
        "path": os.path.join(SAMPLE_DIR, "tiny_sample.csv"),
        "question": "Compare group A versus group B.",
        "expect": "Abort -- insufficient data",
    },
}

EXAMPLE_QUESTIONS = [
    "Is there a difference between Group A and Group B?",
    "How does Group A compare to Group B?",
    "Group A versus Group B -- is there a difference?",
]

STEP_ICONS = {
    "LOAD": "📂",
    "DETECT_COLUMNS": "🧩",
    "CLASSIFY": "🔎",
    "VALIDATE_SIZE": "🔢",
    "CHECK_NORMALITY": "📈",
    "CHECK_VARIANCE": "📊",
    "SELECT_TEST": "🧭",
    "EXECUTE": "⚙️",
    "REPORT": "✅",
}


# ---------------------------------------------------------------------------
# CSS
# ---------------------------------------------------------------------------

def inject_css():
    st.markdown(
        """
        <style>
        :root {
            --bg: #0d1117;
            --surface: #161b26;
            --surface-2: #1c2333;
            --border: rgba(255,255,255,0.08);
            --text-primary: #e6e8eb;
            --text-secondary: #8b94a3;
            --accent: #7c8cfd;
            --accent-soft: rgba(124,140,253,0.14);
            --success: #34d399;
            --success-soft: rgba(52,211,153,0.12);
            --warning: #f59e0b;
            --warning-soft: rgba(245,158,11,0.12);
            --danger: #f87171;
            --danger-soft: rgba(248,113,113,0.10);
            --muted: #4b5563;
        }

        /* Hide Streamlit's native toolbar (Deploy/menu) -- it was overlapping
           our own header and clipping the title. This also frees up the
           vertical space it reserved. */
        header[data-testid="stHeader"] { display: none; }
        div[data-testid="stAppViewContainer"] { padding-top: 0rem; }
        div[data-testid="stToolbar"] { display: none; }

        .block-container { max-width: 1400px; padding-top: 2rem; }

        .app-header { display:flex; align-items:center; gap:0.7rem; }
        .app-header .icon { font-size: 3rem; }
        .app-title {
            font-size: 2rem !important; font-weight: 800 !important;
            color: var(--text-primary) !important; margin:0 !important; line-height:1.15 !important;
        }
        .app-subtitle {
            color: var(--text-secondary) !important; font-size: 1rem !important;
            font-weight:400 !important; margin:0.15rem 0 0 0 !important;
        }

        .panel-heading { position:relative; display:flex; align-items:center; gap:0.55rem; margin: 0.2rem 0 0.9rem 0; }
        .panel-heading .num {
            width: 26px; height:26px; border-radius:50%; background: var(--accent-soft);
            color: var(--accent); display:flex; align-items:center; justify-content:center;
            font-weight:700; font-size:0.85rem; flex-shrink:0;
        }
        .panel-heading .title { font-weight:600; font-size:1.05rem; color: var(--text-primary); }

        /* Decorative connecting arrow, reinforcing the pipeline flow between
           panels. Purely visual (absolute, overflowing into the column gap) --
           does not affect layout/flow, and is hidden on narrow/stacked screens. */
        .panel-heading.arrow::after {
            content: "→"; position:absolute; top:50%; right:-1.7rem;
            transform: translateY(-50%); color: var(--text-secondary);
            font-size: 1.2rem; font-weight:700;
        }
        @media (max-width: 900px) {
            .panel-heading.arrow::after { display:none; }
        }

        .panel-subtitle { color: var(--text-secondary); font-size:0.78rem; margin: -0.6rem 0 0.9rem 2.15rem; }
        .section-subtitle {
            color: var(--text-secondary) !important; font-size:0.78rem !important;
            margin: -0.55rem 0 0.6rem 0 !important;
        }

        .dataset-meta {
            background: var(--surface-2); border:1px solid var(--border); border-radius:10px;
            padding:0.55rem 0.75rem; margin-top:0.5rem; font-size:0.8rem; color: var(--text-secondary);
        }
        .dataset-meta b { color: var(--text-primary); }

        .step-card {
            border-radius: 10px; padding: 0.65rem 0.85rem; margin-bottom: 0.5rem;
            border: 1px solid var(--border); background: var(--surface);
            display:flex; gap:0.6rem; align-items:flex-start;
        }
        .step-card .step-icon { font-size:1.05rem; margin-top:0.05rem; }
        .step-card .step-body { flex:1; min-width:0; }
        .step-card .step-name {
            font-weight:700; font-size:0.78rem; letter-spacing:0.03em; color: var(--text-primary);
            font-family: 'Source Code Pro', 'Courier New', monospace;
        }
        .step-card .step-detail { color: var(--text-secondary); font-size:0.8rem; margin-top:0.2rem; line-height:1.4; }
        .step-card .badge {
            display:inline-block; font-size:0.62rem; font-weight:700; letter-spacing:0.05em;
            padding: 0.12rem 0.5rem; border-radius:999px; margin-left:0.5rem; vertical-align:middle;
        }

        .step-card.completed { border-color: rgba(52,211,153,0.22); }
        .step-card.completed .step-icon::after { content: ""; }
        .step-card.completed .step-name::before { content: "✓ "; color: var(--success); }

        .step-card.current { border-color: var(--accent); background: var(--accent-soft); }
        .step-card.current .step-name::before { content: "● "; color: var(--accent); }

        .step-card.pending { opacity: 0.42; }
        .step-card.pending .step-name::before { content: "○ "; color: var(--muted); }

        .step-card.select-test { border-color: var(--accent); background: var(--accent-soft); }
        .step-card.select-test .badge.decision { background: var(--accent); color:#0d1117; }

        .step-card.branch { border-color: var(--warning); background: var(--warning-soft); }
        .step-card.branch .badge.branch { background: var(--warning); color:#0d1117; }

        .step-card.terminal-abort { border-color: var(--danger); background: var(--danger-soft); }
        .step-card.terminal-abort .step-name::before { content: "⛔ "; color: var(--danger); }
        .step-card.terminal-abort .badge.term { background: var(--danger); color:#0d1117; }

        .step-card.terminal-clarify { border-color: var(--warning); background: var(--warning-soft); }
        .step-card.terminal-clarify .step-name::before { content: "❓ "; color: var(--warning); }
        .step-card.terminal-clarify .badge.term { background: var(--warning); color:#0d1117; }

        .step-card.terminal-invalid { border-color: var(--warning); background: var(--warning-soft); }
        .step-card.terminal-invalid .step-name::before { content: "⚠ "; color: var(--warning); }
        .step-card.terminal-invalid .badge.term { background: var(--warning); color:#0d1117; }

        .terminal-banner {
            border-radius:10px; padding:0.7rem 0.85rem; margin-top:0.4rem; font-size:0.85rem;
            border:1px solid var(--border); font-weight:600;
        }
        .terminal-banner.abort { background: var(--danger-soft); border-color: rgba(248,113,113,0.3); color: var(--danger); }
        .terminal-banner.clarify { background: var(--warning-soft); border-color: rgba(245,158,11,0.3); color: var(--warning); }

        .status-card {
            border-radius: 12px; padding: 0.95rem 1.05rem; margin-bottom:0.9rem;
            border:1px solid var(--border); display:flex; gap:0.75rem; align-items:flex-start;
        }
        .status-card.success { background: var(--success-soft); border-color: rgba(52,211,153,0.3); }
        .status-card.neutral { background: var(--surface-2); border-color: var(--border); }
        .status-card.abort { background: var(--danger-soft); border-color: rgba(248,113,113,0.3); }
        .status-card.clarify { background: var(--warning-soft); border-color: rgba(245,158,11,0.3); }
        .status-card .status-icon { font-size:1.4rem; }
        .status-card .status-title { font-weight:700; font-size:0.98rem; color: var(--text-primary); margin-bottom:0.15rem; }
        .status-card .status-desc { color: var(--text-secondary); font-size:0.83rem; line-height:1.4; }

        .stat-row { display:flex; gap:0.55rem; margin-bottom:0.9rem; flex-wrap:wrap; }
        .stat-tile {
            flex:1; min-width:100px; background: var(--surface); border:1px solid var(--border);
            border-radius:10px; padding:0.6rem 0.75rem;
        }
        .stat-tile .stat-label { color: var(--text-secondary); font-size:0.68rem; text-transform:uppercase; letter-spacing:0.04em; }
        .stat-tile .stat-value { color: var(--text-primary); font-size:1.1rem; font-weight:700; margin-top:0.15rem; word-break:break-word; }

        .reasoning-block p { color: var(--text-secondary); font-size:0.85rem; line-height:1.55; margin: 0 0 0.5rem 0; }

        .info-note {
            border-radius:10px; padding:0.7rem 0.85rem; background: var(--surface-2);
            border:1px solid var(--border); color: var(--text-secondary); font-size:0.78rem;
            margin-top:0.7rem; line-height:1.4;
        }
        .idle-note {
            border-radius:10px; padding:1.4rem 1rem; background: var(--surface);
            border:1px dashed var(--border); color: var(--text-secondary); font-size:0.85rem;
            text-align:center; margin-top:0.5rem;
        }

        .stButton > button { border-radius: 8px; }

        .input-footer {
            display:flex; justify-content:space-between; gap:0.4rem;
            margin-top:1.1rem; padding-top:0.9rem; border-top:1px solid var(--border);
        }
        .input-footer .footer-item { flex:1; text-align:center; }
        .input-footer .footer-icon { font-size:1.1rem; margin-bottom:0.2rem; }
        .input-footer .footer-text { color: var(--text-secondary); font-size:0.66rem; line-height:1.3; }
        </style>
        """,
        unsafe_allow_html=True,
    )


# ---------------------------------------------------------------------------
# decision_trail -> human-readable text (never dump the raw dict)
# ---------------------------------------------------------------------------

def _describe(entry):
    step = entry["step"]
    res = entry["result"]

    if step == "LOAD":
        if "error" in res:
            return f"Failed to load dataset: {res['error']}"
        if "n_rows" in res:
            columns = res.get("columns") or []
            return f"Loaded {res['n_rows']} rows with columns: {', '.join(columns)}."
        # Fallback for the older fixed group_a/group_b LOAD shape, in case
        # any code path still produces it.
        n_a, n_b = res.get("n_a"), res.get("n_b")
        if n_a is not None and n_b is not None:
            return f"Loaded {n_a} values for group_a and {n_b} for group_b."
        return "Dataset loaded."
    if step == "DETECT_COLUMNS":
        if "error" in res:
            return f"Could not read the detected columns: {res['error']}"
        mode = res.get("mode")
        if mode == "direct":
            cols = res.get("numeric_columns") or []
            return f"Exactly 2 numeric columns found ({', '.join(cols)}); using them directly."
        if mode == "grouped":
            return (
                f"Auto-selected '{res.get('group_col')}' as the grouping column and "
                f"'{res.get('value_col')}' as the value column ({res.get('reason', '')})."
            )
        if mode == "ambiguous":
            candidates = res.get("candidates") or []
            detail = f"Could not determine which columns to compare ({res.get('reason', '')})."
            if candidates:
                detail += f" Candidates: {', '.join(candidates)}."
            return detail
        return res.get("reason", "Column detection completed.")
    if step == "CLASSIFY":
        return f"Question classified as '{res['question_type']}'."
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
        if res.get("status") == "invalid_result":
            return f"Ran {res['test_used']}, but the result was undefined: {res['reason']}"
        return (
            f"Ran {res['test_used']}: statistic={res['statistic']:.4f}, "
            f"p-value={res['p_value']:.4f}."
        )
    if step == "REPORT":
        return "All steps completed; result compiled below."
    return str(res)


def _card_classes(entry, is_last, overall_status):
    """Return (css_classes, badge_html) for one decision_trail entry."""
    step = entry["step"]
    res = entry["result"]
    classes = ["step-card", "completed"]
    badge = ""

    if is_last and overall_status != "success":
        if step == "LOAD" and "error" in res:
            classes = ["step-card", "terminal-abort"]
            badge = '<span class="badge term">STOPPED</span>'
        elif step == "DETECT_COLUMNS" and "error" in res:
            classes = ["step-card", "terminal-abort"]
            badge = '<span class="badge term">STOPPED</span>'
        elif step == "DETECT_COLUMNS" and res.get("mode") == "ambiguous":
            classes = ["step-card", "terminal-clarify"]
            badge = '<span class="badge term">STOPPED</span>'
        elif step == "VALIDATE_SIZE" and not res.get("passed", True):
            classes = ["step-card", "terminal-abort"]
            badge = '<span class="badge term">STOPPED</span>'
        elif step == "CLASSIFY" and res.get("question_type") != "two_group":
            classes = ["step-card", "terminal-clarify"]
            badge = '<span class="badge term">STOPPED</span>'
        elif step == "SELECT_TEST" and res.get("action") == "abort":
            classes = ["step-card", "terminal-abort"]
            badge = '<span class="badge term">STOPPED</span>'
        elif step == "EXECUTE" and res.get("status") == "invalid_result":
            classes = ["step-card", "terminal-invalid"]
            badge = '<span class="badge term">INVALID RESULT</span>'
        return classes, badge

    if step == "SELECT_TEST" and res.get("action") == "run_test":
        classes = ["step-card", "completed", "select-test"]
        badge = '<span class="badge decision">DECISION POINT</span>'
    elif step == "CHECK_NORMALITY" and not res.get("passed", True):
        classes = ["step-card", "completed", "branch"]
        badge = '<span class="badge branch">BRANCH TRIGGERED</span>'

    return classes, badge


def _step_card_html(entry, is_last, overall_status):
    step = entry["step"]
    icon = STEP_ICONS.get(step, "•")
    classes, badge = _card_classes(entry, is_last, overall_status)
    detail = _describe(entry)
    return (
        f'<div class="{" ".join(classes)}">'
        f'<div class="step-icon">{icon}</div>'
        f'<div class="step-body">'
        f'<div class="step-name">{step}{badge}</div>'
        f'<div class="step-detail">{detail}</div>'
        f"</div></div>"
    )


def _pending_card_html(step):
    icon = STEP_ICONS.get(step, "•")
    return (
        f'<div class="step-card pending">'
        f'<div class="step-icon">{icon}</div>'
        f'<div class="step-body"><div class="step-name">{step}</div></div>'
        f"</div>"
    )


def _current_card_html(step):
    icon = STEP_ICONS.get(step, "•")
    return (
        f'<div class="step-card current">'
        f'<div class="step-icon">{icon}</div>'
        f'<div class="step-body"><div class="step-name">{step}</div>'
        f'<div class="step-detail">Running…</div></div></div>'
    )


def _terminal_banner_html(status, n_steps):
    if status == "aborted":
        return (
            f'<div class="terminal-banner abort">⛔ Stopped after {n_steps} step'
            f'{"s" if n_steps != 1 else ""} — insufficient data, no test was run.</div>'
        )
    if status == "needs_clarification":
        return (
            f'<div class="terminal-banner clarify">❓ Stopped after {n_steps} step'
            f'{"s" if n_steps != 1 else ""} — question needs clarification.</div>'
        )
    if status == "invalid_result":
        return (
            f'<div class="terminal-banner clarify">⚠️ Stopped after {n_steps} step'
            f'{"s" if n_steps != 1 else ""} — the test produced an undefined result.</div>'
        )
    return ""


def render_pipeline_frame(container, decision_trail, revealed_count, total, status):
    """Render one animation frame: steps [0, revealed_count) as completed/terminal,
    steps[revealed_count] (if any) as current, the rest as pending placeholders
    for whatever steps are still queued to reveal in THIS run's own trail --
    never for steps the backend already skipped, since those never appear here."""
    html_parts = []
    for i, entry in enumerate(decision_trail):
        if i < revealed_count:
            is_last_revealed = i == revealed_count - 1
            html_parts.append(
                _step_card_html(entry, is_last=is_last_revealed and i == total - 1, overall_status=status)
            )
        elif i == revealed_count:
            html_parts.append(_current_card_html(entry["step"]))
        else:
            html_parts.append(_pending_card_html(entry["step"]))
    container.markdown("".join(html_parts), unsafe_allow_html=True)


def render_pipeline_final(container, decision_trail, status):
    html_parts = [
        _step_card_html(entry, is_last=(i == len(decision_trail) - 1), overall_status=status)
        for i, entry in enumerate(decision_trail)
    ]
    container.markdown("".join(html_parts), unsafe_allow_html=True)


def _pipeline_chip(result, animating):
    """Distinct 'Running...' pill while the reveal animation is in progress,
    separate from the final ABORTED/CLARIFY/DONE badge shown once it settles."""
    if animating:
        return '<span class="badge" style="background:var(--accent-soft);color:var(--accent);">● RUNNING…</span>'
    if result is None:
        return ""
    if result["status"] == "success":
        return '<span class="badge" style="background:var(--success-soft);color:var(--success);">✓ DONE</span>'
    if result["status"] == "aborted":
        return '<span class="badge" style="background:var(--danger-soft);color:var(--danger);">⛔ ABORTED</span>'
    if result["status"] == "invalid_result":
        return '<span class="badge" style="background:var(--warning-soft);color:var(--warning);">⚠ INVALID</span>'
    return '<span class="badge" style="background:var(--warning-soft);color:var(--warning);">❓ CLARIFY</span>'


def _pipeline_heading_html(chip):
    return (
        '<div class="panel-heading arrow"><div class="num">2</div>'
        f'<div class="title">Agent Pipeline</div>{chip}</div>'
        '<div class="panel-subtitle">Watching the agent work, step by step</div>'
    )


# ---------------------------------------------------------------------------
# Report export (new, lightweight -- not part of the existing backend)
# ---------------------------------------------------------------------------

def _pdf_safe(text):
    """fpdf2's core fonts only support latin-1; never let a stray character
    (e.g. from a user-typed question) crash report generation mid-demo."""
    return str(text).encode("latin-1", errors="replace").decode("latin-1")


def _mc(pdf, h, text):
    """multi_cell wrapper that always resets the cursor to the left margin
    afterward. Without this, fpdf2's default new_x="RIGHT" leaves the cursor
    near the page's right edge, so the *next* full-width multi_cell computes
    its available width from that leftover position instead of the full page
    width -- eventually shrinking to zero and raising FPDFException."""
    pdf.multi_cell(0, h, _pdf_safe(text), new_x="LMARGIN", new_y="NEXT")


def build_report_pdf(result, dataset_label, question):
    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()

    pdf.set_font("Helvetica", "B", 16)
    _mc(pdf, 9, "Data Analysis Pipeline Agent -- Run Report")
    pdf.ln(2)

    pdf.set_font("Helvetica", "", 10)
    pdf.set_text_color(110, 110, 110)
    for line in [
        f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        f"Dataset: {dataset_label}",
        f"Question: {question}",
        f"Status: {result['status']}",
    ]:
        _mc(pdf, 6, line)
    pdf.set_text_color(0, 0, 0)
    pdf.ln(3)

    if result["status"] == "success":
        pdf.set_font("Helvetica", "B", 13)
        _mc(pdf, 8, "Result")
        pdf.set_font("Helvetica", "", 11)
        for line in [
            f"Test used: {result['test_used']}",
            f"Test statistic: {result['statistic']:.4f}",
            f"p-value: {result['p_value']:.4f}",
            f"Significant (alpha=0.05): {'Yes' if result['significant'] else 'No'}",
        ]:
            _mc(pdf, 6, line)
        pdf.ln(3)

    pdf.set_font("Helvetica", "B", 13)
    _mc(pdf, 8, "Reasoning")
    pdf.set_font("Helvetica", "", 11)
    _mc(pdf, 6, result["reasoning"])
    pdf.ln(3)

    pdf.set_font("Helvetica", "B", 13)
    _mc(pdf, 8, "Agent Reasoning Trail")
    pdf.set_font("Helvetica", "", 10)
    for i, entry in enumerate(result["decision_trail"], start=1):
        _mc(pdf, 6, f"{i}. {entry['step']} -- {_describe(entry)} Decision: {entry['decision']}")

    return bytes(pdf.output())


# ---------------------------------------------------------------------------
# Dataset preview (uses the existing data/loader.py, does not modify it)
# ---------------------------------------------------------------------------

def preview_dataset(source):
    """Returns (n_a, n_b, error) for a path string or an uploaded file object."""
    try:
        if hasattr(source, "seek"):
            source.seek(0)
        group_a, group_b = load_groups(source)
        if hasattr(source, "seek"):
            source.seek(0)
        return len(group_a), len(group_b), None
    except ValueError as exc:
        return None, None, str(exc)


# ---------------------------------------------------------------------------
# Page setup
# ---------------------------------------------------------------------------

st.set_page_config(page_title="Data Analysis Pipeline Agent", page_icon="🧪", layout="wide")
inject_css()

# Flush any pending question text (e.g. from an example-chip click) into
# question_input's session_state BEFORE that widget is instantiated further
# down. Streamlit raises StreamlitAPIException if a widget-bound session_state
# key is written to after the widget has already been created in the same
# run -- so chip clicks set "_pending_question" instead of writing directly
# to "question_input", and this block is what actually applies it, always
# ahead of the st.text_area(key="question_input", ...) call below.
if "_pending_question" in st.session_state:
    st.session_state["question_input"] = st.session_state.pop("_pending_question")

header_left, header_right = st.columns([3, 1])
with header_left:
    st.markdown(
        '<div class="app-header"><div class="icon">🧪</div>'
        '<div><div class="app-title">Data Analysis Pipeline Agent</div>'
        '<div class="app-subtitle">From data to statistically validated insights — fully offline, zero API calls.</div>'
        "</div></div>",
        unsafe_allow_html=True,
    )
with header_right:
    hcol1, hcol2 = st.columns(2)
    with hcol1:
        with st.popover("❓ Help"):
            st.markdown(
                "1. Pick a dataset (upload or sample).\n"
                "2. Ask a two-group comparison question.\n"
                "3. Click **Run Agent** and watch it check assumptions live.\n\n"
                "The agent picks the test itself — it does not run one fixed test."
            )
    with hcol2:
        new_analysis_clicked = st.button("🔄 New Analysis", use_container_width=True)

if new_analysis_clicked:
    for key in list(st.session_state.keys()):
        del st.session_state[key]
    st.rerun()

st.divider()

col_input, col_pipeline, col_results = st.columns([1, 1.05, 1.15], gap="medium")

# ---------------------------------------------------------------------------
# PANEL 1 -- INPUT
# ---------------------------------------------------------------------------

with col_input:
    st.markdown(
        '<div class="panel-heading arrow"><div class="num">1</div><div class="title">Input</div></div>'
        '<div class="panel-subtitle">Upload your data and ask a question</div>',
        unsafe_allow_html=True,
    )

    st.markdown("**Your Dataset**")
    st.markdown(
        '<p class="section-subtitle">Choose how you want to provide your data.</p>',
        unsafe_allow_html=True,
    )
    data_mode = st.segmented_control(
        "Data source mode",
        options=["Upload CSV", "Use sample dataset"],
        default="Use sample dataset",
        key="data_mode",
        label_visibility="collapsed",
    )

    csv_source = None
    dataset_label = None

    if data_mode == "Upload CSV":
        uploaded = st.file_uploader(
            f"CSV with columns: {', '.join(REQUIRED_COLUMNS)}", type=["csv"], key="uploaded_file"
        )
        if uploaded is not None:
            csv_source = uploaded
            dataset_label = uploaded.name
            n_a, n_b, err = preview_dataset(uploaded)
            if err:
                st.error(f"Could not read this file: {err}")
                csv_source = None
            else:
                rows_text = f"{n_a} rows" if n_a == n_b else f"{n_a} rows (group_a), {n_b} rows (group_b)"
                st.markdown(
                    f'<div class="dataset-meta">📄 <b>{uploaded.name}</b><br>'
                    f"{rows_text} · {len(REQUIRED_COLUMNS)} columns ({', '.join(REQUIRED_COLUMNS)})</div>",
                    unsafe_allow_html=True,
                )
        if st.session_state.get("_last_source") != "upload":
            st.session_state["question_input"] = ""
            st.session_state["_last_source"] = "upload"
    else:
        sample_choice = st.selectbox(
            "Sample dataset", list(SAMPLE_PRESETS.keys()), key="sample_choice", label_visibility="collapsed"
        )
        preset = SAMPLE_PRESETS[sample_choice]
        csv_source = preset["path"]
        dataset_label = os.path.basename(preset["path"])
        n_a, n_b, err = preview_dataset(csv_source)
        if err:
            st.error(f"Could not read this file: {err}")
            csv_source = None
        else:
            rows_text = f"{n_a} rows" if n_a == n_b else f"{n_a} rows (group_a), {n_b} rows (group_b)"
            st.markdown(
                f'<div class="dataset-meta">📄 <b>{dataset_label}</b><br>'
                f"{rows_text} · {len(REQUIRED_COLUMNS)} columns ({', '.join(REQUIRED_COLUMNS)})<br>"
                f"Expected outcome: <b>{preset['expect']}</b></div>",
                unsafe_allow_html=True,
            )
        if st.session_state.get("_last_source") != sample_choice:
            st.session_state["question_input"] = preset["question"]
            st.session_state["_last_source"] = sample_choice

    st.markdown("**Your Question**")
    st.markdown(
        '<p class="section-subtitle">Ask a plain-English comparison question.</p>',
        unsafe_allow_html=True,
    )
    question = st.text_area(
        "Comparison question",
        key="question_input",
        placeholder="What would you like to compare?",
        height=90,
        max_chars=500,
        label_visibility="collapsed",
    )
    st.caption(f"{len(question)}/500")

    st.caption("Try an example:")
    chip_cols = st.columns(len(EXAMPLE_QUESTIONS))
    for chip_col, example_q in zip(chip_cols, EXAMPLE_QUESTIONS):
        with chip_col:
            if st.button(example_q, key=f"chip_{example_q}", use_container_width=True):
                st.session_state["_pending_question"] = example_q
                st.rerun()

    run_disabled = csv_source is None
    run_clicked = st.button("▶️ Run Agent →", type="primary", disabled=run_disabled, use_container_width=True)
    if run_disabled:
        st.caption("Choose or upload a valid dataset to enable Run Agent.")

    st.markdown(
        '<div class="input-footer">'
        '<div class="footer-item"><div class="footer-icon">🎓</div>'
        '<div class="footer-text">No statistical<br>knowledge required</div></div>'
        '<div class="footer-item"><div class="footer-icon">⚡</div>'
        '<div class="footer-text">Fast and accurate<br>analysis</div></div>'
        '<div class="footer-item"><div class="footer-icon">🛡️</div>'
        '<div class="footer-text">Clear, step-by-step<br>explanations</div></div>'
        "</div>",
        unsafe_allow_html=True,
    )

# ---------------------------------------------------------------------------
# Run the agent (real backend call; UI only animates the reveal of results
# that already exist -- the pipeline itself is not actually streaming)
# ---------------------------------------------------------------------------

if run_clicked:
    if not question.strip():
        st.session_state["result"] = None
        st.session_state["_run_error"] = "Please enter a comparison question before running the agent."
    else:
        st.session_state["_run_error"] = None
        st.session_state["dataset_label"] = dataset_label
        st.session_state["question_asked"] = question
        try:
            st.session_state["result"] = run_pipeline(csv_source, question)
            st.session_state["_animate"] = True
        except Exception as exc:  # a live demo must never hard-crash on stage
            st.session_state["result"] = None
            st.session_state["_run_error"] = f"Unexpected error while running the pipeline: {exc}"

result = st.session_state.get("result")
run_error = st.session_state.get("_run_error")

# ---------------------------------------------------------------------------
# PANEL 2 -- AGENT PIPELINE
# ---------------------------------------------------------------------------

with col_pipeline:
    heading_slot = st.empty()
    animating_now = result is not None and st.session_state.get("_animate")
    heading_slot.markdown(_pipeline_heading_html(_pipeline_chip(result, animating_now)), unsafe_allow_html=True)

    pipeline_slot = st.empty()
    progress_slot = st.empty()

    if run_error:
        pipeline_slot.markdown(
            f'<div class="idle-note">⚠️ {run_error}</div>', unsafe_allow_html=True
        )
    elif result is None:
        pipeline_slot.markdown(
            '<div class="idle-note">Run the agent to see its reasoning trail here.</div>',
            unsafe_allow_html=True,
        )
    else:
        trail = result["decision_trail"]
        total = len(trail)

        if st.session_state.get("_animate"):
            for revealed in range(total + 1):
                render_pipeline_frame(pipeline_slot, trail, revealed, total, result["status"])
                pct = min(revealed, total) / total
                if result["status"] == "success" or revealed < total:
                    progress_slot.progress(pct, text=f"{min(revealed, total)} / {total} steps")
                time.sleep(STEP_REVEAL_DELAY)
            st.session_state["_animate"] = False
            heading_slot.markdown(_pipeline_heading_html(_pipeline_chip(result, False)), unsafe_allow_html=True)

        render_pipeline_final(pipeline_slot, trail, result["status"])

        if result["status"] == "success":
            progress_slot.progress(1.0, text=f"{total} / {total} steps — complete")
        else:
            progress_slot.markdown(_terminal_banner_html(result["status"], total), unsafe_allow_html=True)

    st.markdown(
        '<div class="info-note">💡 <b>Why these checks?</b> The agent inspects your '
        "data's characteristics (sample size, normality, variance) and picks the "
        "statistically appropriate test automatically -- you never have to guess.</div>",
        unsafe_allow_html=True,
    )

# ---------------------------------------------------------------------------
# PANEL 3 -- RESULTS
# ---------------------------------------------------------------------------

with col_results:
    results_ready = result is not None and not st.session_state.get("_animate")

    result_status_chip = ""
    if results_ready:
        if result["status"] == "success":
            result_status_chip = '<span class="badge" style="background:var(--success-soft);color:var(--success);">✓ COMPLETE</span>'
        elif result["status"] == "aborted":
            result_status_chip = '<span class="badge" style="background:var(--danger-soft);color:var(--danger);">⛔ ABORTED</span>'
        elif result["status"] == "invalid_result":
            result_status_chip = '<span class="badge" style="background:var(--warning-soft);color:var(--warning);">⚠ INVALID RESULT</span>'
        else:
            result_status_chip = '<span class="badge" style="background:var(--warning-soft);color:var(--warning);">❓ NEEDS INPUT</span>'

    st.markdown(
        f'<div class="panel-heading"><div class="num">3</div>'
        f'<div class="title">Results</div>{result_status_chip}</div>'
        '<div class="panel-subtitle">Statistical output with reasoning</div>',
        unsafe_allow_html=True,
    )

    if not results_ready:
        st.markdown(
            '<div class="idle-note">Results will appear here once the agent finishes.</div>',
            unsafe_allow_html=True,
        )
    else:
        status = result["status"]

        if status == "success":
            sig = result["significant"]
            title = "Significant Difference Detected" if sig else "No Significant Difference Detected"
            desc = (
                f"The {result['test_used']} found a statistically significant difference "
                f"between group A and group B (p = {result['p_value']:.4f})."
                if sig
                else f"The {result['test_used']} did not find a statistically significant "
                f"difference between group A and group B (p = {result['p_value']:.4f})."
            )
            icon = "✅" if sig else "➖"
            st.markdown(
                f'<div class="status-card success"><div class="status-icon">{icon}</div>'
                f'<div><div class="status-title">{title}</div>'
                f'<div class="status-desc">{desc}</div></div></div>',
                unsafe_allow_html=True,
            )

            # NOTE: effect size (e.g. Cohen's d / rank-biserial correlation) is not
            # computed by core/test_executor.py yet, so it is intentionally omitted
            # here rather than fabricated -- see README "Future work".
            st.markdown(
                '<div class="stat-row">'
                f'<div class="stat-tile"><div class="stat-label">Test used</div>'
                f'<div class="stat-value">{result["test_used"]}</div></div>'
                f'<div class="stat-tile"><div class="stat-label">p-value</div>'
                f'<div class="stat-value">{result["p_value"]:.4f}</div></div>'
                f'<div class="stat-tile"><div class="stat-label">Statistic</div>'
                f'<div class="stat-value">{result["statistic"]:.4f}</div></div>'
                "</div>",
                unsafe_allow_html=True,
            )
        elif status == "aborted":
            st.markdown(
                '<div class="status-card abort"><div class="status-icon">⛔</div>'
                '<div><div class="status-title">Insufficient Data — Pipeline Aborted</div>'
                '<div class="status-desc">No statistical test was run because the data '
                "could not support one. See the reasoning below.</div></div></div>",
                unsafe_allow_html=True,
            )
        elif status == "invalid_result":
            st.markdown(
                f'<div class="status-card clarify"><div class="status-icon">⚠️</div>'
                f'<div><div class="status-title">Result Undefined — No Conclusion Possible</div>'
                f'<div class="status-desc">{result["test_used"]} produced a mathematically '
                "undefined result (this typically happens when one or both groups have "
                "zero variance, e.g. identical values). This is not the same as "
                '"no significant difference" -- no conclusion can be drawn here. See the '
                "reasoning below for details.</div></div></div>",
                unsafe_allow_html=True,
            )
        else:
            st.markdown(
                '<div class="status-card clarify"><div class="status-icon">❓</div>'
                '<div><div class="status-title">Question Needs Clarification</div>'
                '<div class="status-desc">The question could not be confidently classified '
                "as a two-group comparison. Try rephrasing using words like "
                '"compare", "difference", "between", or "versus".</div></div></div>',
                unsafe_allow_html=True,
            )

        with st.expander("📄 Detailed Results", expanded=True):
            sentences = [s.strip().rstrip(".") for s in result["reasoning"].split(". ") if s.strip()]
            html = "".join(f"<p>{s}.</p>" for s in sentences)
            st.markdown(f'<div class="reasoning-block">{html}</div>', unsafe_allow_html=True)

        with st.expander("🧭 Agent Reasoning Trail", expanded=False):
            rows = [
                {"Step": entry["step"], "Summary": _describe(entry)}
                for entry in result["decision_trail"]
            ]
            st.dataframe(rows, use_container_width=True, hide_index=True)

        st.markdown("---")
        action_col1, action_col2 = st.columns(2)
        with action_col1:
            if st.button("🔄 Ask a new question", use_container_width=True):
                for key in list(st.session_state.keys()):
                    del st.session_state[key]
                st.rerun()
        with action_col2:
            report_pdf = build_report_pdf(
                result,
                st.session_state.get("dataset_label", "unknown"),
                st.session_state.get("question_asked", ""),
            )
            st.download_button(
                "⬇️ Download Report",
                data=report_pdf,
                file_name=f"agent_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf",
                mime="application/pdf",
                use_container_width=True,
            )
