# schema/sql_templates.py

ICU_LAB_SUMMARY_SQL = """
SELECT
  COUNT(*) AS n_points,
  AVG(le.valuenum) AS mean_val,
  MIN(le.valuenum) AS min_val,
  MAX(le.valuenum) AS max_val
FROM `physionet-data.mimiciv_3_1_icu.icustays` icu
JOIN `physionet-data.mimiciv_3_1_hosp.labevents` le
  ON le.hadm_id = icu.hadm_id
WHERE le.itemid IN UNNEST(@itemids)
  AND le.valuenum IS NOT NULL
  AND le.charttime BETWEEN icu.intime AND icu.outtime
"""
