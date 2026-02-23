# policy/rules.py

# Currently supported lab metrics (expand later)
ALLOWED_METRICS = {
    "creatinine"
}

# Evidence sufficiency rules
MIN_POINTS = {
    "summary": 2
}

# Lab → itemid mapping (partial, expand later)
LAB_ITEMIDS = {
    "creatinine": [50912, 52546]
}
