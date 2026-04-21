# 🧠 Authority Allocation in Hybrid LLM Systems

A research-driven AI system exploring how **authority distribution between LLMs and deterministic components** affects reliability in structured question answering.

Built on clinical ICU data (MIMIC-IV), this project focuses on **reducing silent failure in LLM systems** through modular architecture, validation, and controlled execution.

---

## 🚀 Overview

LLM-based systems often fail silently — producing outputs that look correct but are:

- logically incorrect  
- unsupported by data  
- structurally invalid downstream  
- inconsistent in refusal behavior  

This project investigates:

> **How should authority be distributed across system components to maximize reliability?**

Instead of treating LLMs as black boxes, the system decomposes reasoning into **explicit, controllable modules**.

---

## 🏗️ System Architecture

The system is a **modular hybrid pipeline**:

Question
↓
Intent Extraction (LLM)
↓
Request Gate (LLM / Deterministic)
↓
Discovery SQL → Execute
↓
Final SQL Generation (LLM)
↓
Artifact Validation (Deterministic)
↓
SQL Execution
↓
Reducer (Deterministic / Hybrid)
↓
Post Validation
↓
Renderer


Each module has **explicit authority assignment**, enabling controlled experimentation.

---

## ⚙️ Core Design Principle

> Not “use LLM everywhere” —  
> but **decide where LLMs should and should NOT have authority**

---

## 🔬 Experimental Setup

To isolate system behavior, only selected modules are varied.

### Fixed Components
- Intent extraction  
- Discovery pipeline  
- Database execution  
- Renderer  
- Logging + benchmark  

### Experimental Components
- Request Gate  
- SQL Generation  
- Validation  
- Reducer  

---

## 🧪 Implemented Systems

### System 0 (S0)
- Request Gate: Deterministic  
- SQL Generation: LLM  
- Validator: Deterministic  
- Reducer: Deterministic  

### System 1 (S1)
- Request Gate: **LLM**  
- SQL Generation: LLM  
- Validator: Deterministic  
- Reducer: Deterministic  

---

## 📊 Key Results

| Metric | S0 | S1 |
|------|----|----|
| Answerable Success | 34 / 60 | 33 / 60 |
| Correct Refusal | 20 / 35 | **35 / 35** |
| False Compliance | 15 | **0** |

### 🔍 Insight

- LLM-based request gating **eliminates unsafe compliance**
- Minimal impact on answerable queries
- Major failures shift **downstream (SQL → reducer interface)**

---

## ⚠️ Core Problem Identified

Even when SQL is valid:

> Outputs can still fail during deterministic reduction due to **contract mismatch**

👉 Structural correctness ≠ system correctness  

This highlights the importance of **cross-module compatibility**, not just individual module quality.

---

## 🧠 Discovery-Guided SQL Generation

Instead of direct prompting:

1. Extract measure terms  
2. Query metadata candidates  
3. Inject discovery context into SQL generation  

This improves:
- grounding  
- schema correctness  
- reliability under constrained tables  

---

## 🛡️ Reliability & Safety Mechanisms

- Allowed-table enforcement  
- ICU time-window constraints  
- Deterministic SQL validation  
- Explicit refusal for unsupported queries  
- Controlled execution boundaries  
- Post-generation validation  

The system is designed to **fail safely**, not just produce answers.

---

## 📈 Benchmark & Evaluation Framework

### Benchmark Design
- 19 questions × 5 trials = 95 runs per system  
- Categories:
  - SQL-heavy queries  
  - reducer-sensitive queries  
  - validation-sensitive queries  
  - out-of-scope requests  
  - adversarial prompts  

### Metrics

#### Raw Metrics
- execution success  
- refusal count  
- failure stage  
- token usage  
- latency  

#### Derived Metrics
- answerable success rate  
- correct refusal rate  
- false compliance rate  
- validation pass rate  
- unsafe request detection  
- determinism (SQL / output / policy)  

---

## 🔍 Observability & Logging

Structured experiment logging includes:

- authority configuration  
- SQL traces  
- validation traces  
- reducer traces  
- failure stage  
- token + latency metrics  

This enables analysis of **where and why failures occur**, not just outcomes.

---

## 🚧 Next Step: Hybrid Reducer

Current bottleneck:
- SQL outputs don’t always match deterministic reducer expectations  

### Planned Solution

Hybrid reducer design:

1. Summarize SQL output structure  
2. LLM generates reduction plan  
3. Deterministic execution applies plan  

This keeps:
- execution safe  
- reasoning flexible  

---

## 🧰 Tech Stack

- Python  
- SQL (MIMIC-IV)  
- OpenAI API  
- Pydantic (structured outputs)  
- Custom modular pipeline  
- JSON-based logging & evaluation system  

---

## 🎯 What This Project Demonstrates

- Hybrid LLM system design  
- Reliability engineering for AI systems  
- Structured query generation (text-to-SQL)  
- Validation and guardrail design  
- Experimental framework for AI behavior  
- Observability in multi-stage pipelines  

---

## 📌 Positioning

This project is best described as:

- **AI Systems Engineering**
- **LLM + Deterministic Hybrid Architecture**
- **Reliability & Evaluation Framework for GenAI**

Not focused on:
- pure model training  
- generic chatbot applications  

---

## 👤 Author

Shotitouch Tuangcharoentip  
AI / Full-Stack Engineer | LLM Systems | MS ML Stevens Institute of Technology
