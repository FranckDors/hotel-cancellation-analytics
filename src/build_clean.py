import duckdb
from datetime import datetime

con = duckdb.connect("warehouse.duckdb")

# ---- 1. Build the staging tables -------------------------------------------
sql_text = open("sql/02_staging.sql").read()
for stmt in sql_text.split(";"):
    lines = [l for l in stmt.splitlines() if l.strip() and not l.strip().startswith("--")]
    if lines:                       # skip chunks that are only comments
        con.execute(stmt)

# ---- 2. Create the results log ---------------------------------------------
con.execute("""
    CREATE OR REPLACE TABLE dq_results (
        check_name    VARCHAR,
        layer         VARCHAR,
        severity      VARCHAR,    -- 'error' = must be zero in clean, 'warn' = worth knowing
        status        VARCHAR,
        rows_checked  BIGINT,
        rows_failed   BIGINT,
        pct_failed    DOUBLE,
        run_timestamp TIMESTAMP,
        description   VARCHAR
    )
""")
now = datetime.now()

def record(name, layer, severity, checked, failed, description):
    if failed == 0:
        status = "PASS"
    elif layer == "raw":
        status = "FOUND"            # problems in raw data are expected
    else:
        status = "FAIL" if severity == "error" else "WARN"
    pct = round(100.0 * failed / checked, 3) if checked else 0.0
    con.execute("INSERT INTO dq_results VALUES (?,?,?,?,?,?,?,?,?)",
                [name, layer, severity, status, checked, failed, pct, now, description])

def run_check(name, layer, table, bad_condition, severity, description):
    checked = con.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
    failed = con.execute(f"SELECT COUNT(*) FROM {table} WHERE {bad_condition}").fetchone()[0]
    record(name, layer, severity, checked, failed, description)

MONTHS = "('January','February','March','April','May','June','July','August','September','October','November','December')"

# ---- 3. Checks on the RAW layer (we expect to find problems) ---------------
R = "raw.hotel_bookings"
run_check("missing_lead_time", "raw", R, "lead_time IS NULL OR TRIM(lead_time) IN ('', 'NULL', 'NA')", "error", "Lead time is blank")
run_check("negative_lead_time", "raw", R, "TRY_CAST(lead_time AS INTEGER) < 0", "error", "Lead time below zero")
run_check("invalid_cancel_flag", "raw", R, "is_canceled IS NULL OR is_canceled NOT IN ('0','1')", "error", "is_canceled is not 0 or 1")
run_check("bad_month_name", "raw", R, f"TRIM(arrival_date_month) NOT IN {MONTHS}", "error", "Month name not recognised")
run_check("children_missing", "raw", R, "children IS NULL OR TRIM(children) IN ('', 'NULL', 'NA')", "warn", "Children count missing")
run_check("country_missing", "raw", R, "country IS NULL OR TRIM(country) IN ('', 'NULL', 'NA')", "warn", "Country missing")
run_check("agent_missing", "raw", R, "agent IS NULL OR TRIM(agent) IN ('', 'NULL', 'NA')", "warn", "No agent (direct booking)")
run_check("zero_guests", "raw", R,
          "COALESCE(TRY_CAST(adults AS INTEGER),0) + COALESCE(TRY_CAST(TRY_CAST(children AS DOUBLE) AS INTEGER),0) + COALESCE(TRY_CAST(babies AS INTEGER),0) = 0",
          "error", "Booking with zero guests")
run_check("negative_adr", "raw", R, "TRY_CAST(adr AS DOUBLE) < 0", "error", "Negative average daily rate")
run_check("zero_nights", "raw", R,
          "COALESCE(TRY_CAST(stays_in_weekend_nights AS INTEGER),0) + COALESCE(TRY_CAST(stays_in_week_nights AS INTEGER),0) = 0",
          "warn", "Zero-night stay (could be day-use)")

# exact duplicate rows (no booking ID exists, so we report them instead of deleting)
total = con.execute(f"SELECT COUNT(*) FROM {R}").fetchone()[0]
distinct = con.execute(f"SELECT COUNT(*) FROM (SELECT DISTINCT * FROM {R})").fetchone()[0]
record("exact_duplicate_rows", "raw", "warn", total, total - distinct,
       "Identical rows (kept, since they may be separate real bookings)")

# ---- 4. Checks on the CLEAN layer (errors must be zero) --------------------
C = "staging.bookings_clean"
run_check("missing_key_fields", "clean", C, "is_canceled IS NULL OR lead_time IS NULL OR arrival_date IS NULL OR adr IS NULL", "error", "Key field missing")
run_check("negative_lead_time", "clean", C, "lead_time < 0", "error", "Lead time below zero")
run_check("invalid_cancel_flag", "clean", C, "is_canceled NOT IN (0, 1)", "error", "is_canceled is not 0 or 1")
run_check("zero_guests", "clean", C, "total_guests = 0", "error", "Booking with zero guests")
run_check("negative_adr", "clean", C, "adr < 0", "error", "Negative average daily rate")
run_check("duplicate_booking_id", "clean", C,
          "booking_id IN (SELECT booking_id FROM staging.bookings_clean GROUP BY booking_id HAVING COUNT(*) > 1)",
          "error", "booking_id not unique")
run_check("zero_nights", "clean", C, "is_zero_nights", "warn", "Zero-night stay (kept)")

# ---- 5. Row-count reconciliation -------------------------------------------
raw_n = con.execute("SELECT COUNT(*) FROM raw.hotel_bookings").fetchone()[0]
typed_n = con.execute("SELECT COUNT(*) FROM staging.bookings_typed").fetchone()[0]
clean_n = con.execute("SELECT COUNT(*) FROM staging.bookings_clean").fetchone()[0]
flagged = con.execute("""
    SELECT COUNT(*) FROM staging.bookings_typed
    WHERE is_zero_guests OR is_negative_adr OR is_missing_key_field
""").fetchone()[0]

record("raw_to_typed_rowcount", "reconciliation", "error", raw_n, abs(raw_n - typed_n),
       "Typing step must not add or lose rows")
record("typed_to_clean_rowcount", "reconciliation", "error", typed_n,
       abs((typed_n - clean_n) - flagged),
       "Rows removed must equal rows flagged as bad")

# ---- 6. Print the log -------------------------------------------------------
print(con.execute("""
    SELECT layer, check_name, severity, status, rows_failed, pct_failed
    FROM dq_results
    ORDER BY CASE layer WHEN 'raw' THEN 1 WHEN 'clean' THEN 2 ELSE 3 END, check_name
""").fetchdf().to_string(index=False))
print(f"\nraw rows: {raw_n:,} | clean rows: {clean_n:,} | removed: {typed_n - clean_n:,}")