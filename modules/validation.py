from utils.utils import is_select_sql


def validate_select_sql(sql: str) -> bool:
    return is_select_sql(sql)

