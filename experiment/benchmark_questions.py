IN_SCOPE_QUESTIONS = [

    # ----------------------------
    # Level 1 – Single aggregation
    # Tests:
    # - Basic lab resolution (d_labitems join)
    # - ICU window enforcement
    # - Single aggregate computation (median)
    # - Case robustness (Q2)
    # ----------------------------

    ("Q1", "What is the median creatinine during ICU stay?", False),

    # Case-insensitive robustness (label matching via LOWER())
    ("Q2", "What is the median CREATININE during icu stay?", False),

    # Tests AVG aggregation instead of median
    ("Q3", "What is the average serum creatinine in the ICU?", False),

    # ----------------------------
    # Level 2 – Grouped aggregation
    # Tests:
    # - GROUP BY stay_id
    # - Per-stay aggregation
    # - Deterministic ordering when selecting highest value
    # ----------------------------

    # Tests MAX + ordering + returning stay_id
    ("Q4", "Which ICU stay had the highest potassium value?", False),

    # Tests GROUP BY stay_id + AVG
    ("Q5", "For each ICU stay, what is the average glucose level?", False),

    # Tests COUNT DISTINCT stay_id with existence condition
    ("Q6", "How many ICU stays had at least one lactate measurement?", False),

    # Tests multi-metric aggregation in same query (parallel medians)
    ("Q7", "What are the median sodium and potassium levels during ICU stay?", False),

    # ----------------------------
    # Refusal robustness
    # Tests:
    # - Out-of-scope lab handling
    # - REFUSE correctness
    # ----------------------------

    ("Q8", "What is the median unicorn_lab during ICU stay?", True),

    # ----------------------------
    # Level 3 – Window function (single-stage)
    # Tests:
    # - FIRST_VALUE / ORDER BY logic
    # - ICU window correctness
    # - Deterministic row selection
    # ----------------------------

    ("Q9", "What is the first creatinine value recorded during ICU stay?", False),

    # Tests:
    # - Window functions (FIRST_VALUE + LAST_VALUE)
    # - Derived metric (last - first)
    # - No outer aggregation yet
    ("Q10", "What is the difference between the last and first creatinine value during ICU stay?", False),

    # ----------------------------
    # Level 4 – Per-stay multi-stage computation
    # Tests:
    # - Partitioning by stay_id
    # - Returning multiple derived columns
    # - Proper window decomposition via CTE
    # ----------------------------

    ("Q11", "For each ICU stay, what are the first and last creatinine values recorded during the ICU stay?", False),

    # Tests:
    # - Window functions
    # - Derived percentage computation
    # - Division safety (exclude first_value = 0)
    # - Proper decomposition under 'no window + group mix' rule
    ("Q12", "For each ICU stay, what is the percentage change between the first and last creatinine values during the ICU stay?", False),

    # ----------------------------
    # Level 5 – Nested aggregation (highest complexity)
    # Tests:
    # - Multi-stage CTE decomposition
    # - Per-stay derived metric
    # - Outer aggregation (AVG across stays)
    # - Strict separation of window and GROUP BY logic
    # - Token-length + structural coordination stress
    # ----------------------------

    ("Q13", "What is the average percentage change between the first and last creatinine values across all ICU stays?", False),
]

OUT_OF_SCOPE_QUESTIONS = [
    ("O1", "What is the median creatinine during the entire hospital admission?", True),
    ("O2", "What was the creatinine level before ICU admission?", True),
    ("O3", "What medications were given during ICU stay?", True),
]