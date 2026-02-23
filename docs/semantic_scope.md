# Semantic Scope Specification (v1.2)

This document defines the supported analytical semantics for the
Mode 2 (System-Enforced) execution path.

Mode 2 operates as a **closed-world analytical system**.
Any request that falls outside this specification MUST be explicitly refused.

Refusal is a correct and expected outcome.

---

## 1. Data Scope

The system operates exclusively on **ICU-aligned laboratory analytics**
derived from MIMIC-IV.

Supported source tables:
- `icustays`  
  Used to define ICU admission windows and identifiers:
  `stay_id`, `hadm_id`, `subject_id`, `intime`, `outtime`
- `labevents`  
  Used to provide laboratory measurements (`valuenum`, `charttime`)

All analyses are anchored to `stay_id` and restricted to measurements
whose `charttime` lies within the ICU window
`[icustays.intime, icustays.outtime]`.

Other MIMIC-IV tables (e.g., diagnoses, procedures, medications) are
intentionally excluded to isolate analytical validity, evidence
sufficiency, and temporal alignment from broader clinical modeling
complexity.

---

## 2. Supported Semantics (v1.3)

| Dimension              | Allowed Values                                                |
|-----------------------|----------------------------------------------------------------|
| Metric                | Any numeric laboratory measurement in `labevents`             |
| Time window           | icu                                                            |
| Operation             | summary, compare                                               |
| Phase types           | discovery, reduction, measurement                              |
| Reduction rules       | pick_max_value                                                 |
| Evidence rule         | n_points ≥ 2 per ICU stay                                      |
| Demographics (derived)| age_at_icu, sex                                                |
| Demographic filters   | Explicit numeric or categorical boundaries only                |

Any value outside this set MUST result in refusal.

---

## 3. Identifiers and Temporal Authority

### ICU Identifier
- `stay_id` is the atomic unit of analysis.
- All measurements, demographics, and summaries are derived per `stay_id`.

### ICU Time Window
- ICU window is defined as:
- icu_intime = icustays.intime
- icu_outtime = icustays.outtime
- Measurements outside this window are invalid and must not be used.

---

## 4. Laboratory Measurements

### Supported Metrics
All numeric laboratory measurements present in the MIMIC-IV
`labevents` table are supported.

A laboratory measurement is considered valid if:
- `valuenum` is non-null and numeric
- the measurement occurs within the ICU window
- the measurement maps to a valid `itemid` in `labevents`

### Derived Lab Statistics
The following descriptive statistics may be computed per ICU stay
or per cohort:
- minimum value
- maximum value
- mean value
- number of valid measurements (`n_points`)

### Evidence Sufficiency
- At least **2 valid measurements** are required per ICU stay
  to produce a summary.
- If `n_points < 2`, the request MUST be refused as evidentially invalid.

---

## 5. Demographics (Derived Only)

Demographics are supported **only as derived attributes of ICU stays**.
Raw demographic tables are not directly exposed.

### Supported Derived Attributes
- `age_at_icu`
- Computed from date of birth and ICU admission time
- `sex`

These attributes are:
- deterministic
- stable per ICU stay
- non-interpretive

---

## 6. Demographic Stratification Rules

Demographic comparisons are supported **only when cohort boundaries
are explicitly specified by the user**.

### Allowed Examples
- `age_at_icu > 50`
- `age_at_icu < 30`
- `sex = 'M'`
- `sex = 'F'`

### Disallowed Examples
- “elderly patients”
- “young patients”
- “older vs younger”
- percentile-based or relative thresholds (e.g., top 10%)

If demographic boundaries are implicit, relative, or inferred by the LLM,
the request MUST be refused.

---

## 7. Supported Phase Types

The system supports the following phase types:

- **discovery**
- Identifies ICU stays satisfying a condition (e.g., creatinine > X)
- **reduction**
- Deterministically selects a single example from candidates
- **measurement**
- Computes statistics for a known ICU stay or cohort

---

## 8. Supported Phase Compositions

Only the following phase sequences are allowed:

- `measurement`
- `discovery → measurement`
- `discovery → reduction → measurement`

Iterative, recursive, or unbounded compositions
(e.g., `discovery → discovery`) are not supported and MUST be refused.

---

## 9. Reduction Rules

The following deterministic reduction rules are supported:

- `pick_max_value`
- Selects the ICU stay with the maximum observed value
  for the target metric

Reduction rules are:
- deterministic
- reproducible
- system-enforced

The LLM must never select examples.

---

## 10. Refusal Policy

A request MUST be refused if:

- It references unsupported metrics, operations, or time windows
- It requires demographic categories without explicit boundaries
- It violates evidence sufficiency (`n_points < 2`)
- It requires unsupported phase composition
- It is semantically undefined under this specification

Refusal is an expected and correct outcome in Mode 2.

---

## 11. Out of Scope (v1.2)

The following are intentionally not supported:

- Diagnoses (ICD codes)
- Procedures or ventilation events
- Medications or dosing information
- Predictive modeling or risk scoring
- LLM-defined thresholds or cohort boundaries
- Percentile-based or relative cohort definitions
- Arbitrary SQL or user-defined joins

These exclusions preserve deterministic enforcement and analytical validity.

---

## 12. Design Rationale

This semantic scope intentionally prioritizes:
- determinism
- reproducibility
- enforceability
- explicit failure over silent invalid analysis

The scope may be expanded in future versions only where these guarantees
can be preserved.

