# Problem & Solution Brief

**Project:** data-analysis-pipeline-agent
**Event:** Agentic AI Hackathon, Tech Zephyr 4.0, IIT Bhubaneswar

## Problem statement

Comparing two groups of numeric data (e.g. treatment vs. control, before vs. after)
requires choosing the *correct* statistical test — and that choice depends on
properties of the data itself, not the analyst's preference. In practice, most
people either skip the assumption checks (normality, equal variance) and default to
a Student's t-test regardless of whether it's valid, or don't know the checks exist
at all. An invalid test silently produces an unreliable p-value with no warning.

## Target users

Students, researchers, and data analysts who need a statistically defensible
two-group comparison without first having to know — or manually verify — which
assumption checks apply and which test each outcome implies.

## Why this problem requires an agentic solution

This is not a summarization or Q&A task where a single LLM call over the data
would suffice, and it is not a task a fixed script can solve correctly, because
**the correct action depends on intermediate results that are only known at
runtime**: whether Shapiro-Wilk rejects normality, and whether Levene's rejects
equal variance. A different result at either check provably changes which test
runs next, or whether a test runs at all:

- n < 5 per group → abort before running any checks
- normality fails → skip the variance check, use Mann-Whitney U
- normality passes, variance fails → Welch's t-test
- normality passes, variance passes → Student's t-test

A hardcoded script would have to pick one test and stick with it, right or wrong.
This system observes the outcome of each check and decides its next action
accordingly — an observe → decide → act → evaluate → adapt loop, not a fixed
pipeline with cosmetic branching.

## Proposed solution

An agent that takes a raw two-group CSV and a plain-English question, and:
1. Validates sample size before doing anything else, aborting cleanly if the data
   can't support any test.
2. Classifies the question deterministically (keyword-based, no LLM, no external
   API) to confirm it's a two-group comparison — asking for clarification rather
   than guessing if it isn't.
3. Runs Shapiro-Wilk and (conditionally) Levene's tests, and selects the
   statistically appropriate test based on the live results.
4. Executes that test and returns the result alongside a full, inspectable
   decision trail — so the reasoning is auditable, not a black box.

The entire pipeline runs offline: `core/` is pure deterministic Python (scipy),
and the only optional network dependency ever considered (an LLM-assisted
classifier) was deliberately dropped in favor of full determinism and demo
reliability.

## Expected impact

Removes the most common source of invalid statistical conclusions in informal
data analysis — running the wrong test — by making assumption-checking automatic
and non-optional, while remaining fully transparent about *why* a given test was
chosen so the result can be defended, not just trusted.
