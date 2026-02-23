import re

def clean_sql(text: str) -> str:
    if not text:
        return ""

    t = text.strip()

    # Remove markdown fences if present
    if t.startswith("```"):
        parts = t.split("```")
        if len(parts) > 1:
            t = parts[1].strip()

    # Remove leading language tags like: "sql", "SQL:", "Sql"
    t = re.sub(r"^\s*(sql\s*:?\s*)", "", t, flags=re.IGNORECASE)

    # Remove BOM / weird leading chars
    t = t.lstrip("\ufeff").strip()

    return t


def is_select_sql(sql: str) -> bool:
    s = sql.strip().lower()
    # allow WITH ... SELECT
    return s.startswith("select") or s.startswith("with")
