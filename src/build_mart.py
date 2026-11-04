import duckdb
from datetime import datetime

con = duckdb.connect("warehouse.duckdb")

# 1. Build the mart tables
sql_text = open("sql/03_marts.sql").read()
for stmt in sql_text.split(";"):
    lines = [l for l in stmt.splitlines() if l.strip() and not l.strip().startswith("--")]
    if lines:
        con.execute(stmt)

# 2. Add mart checks to dq_results (replace any older mart rows first)
con.execute("DELETE FROM dq_results WHERE layer = 'mart'")
now = datetime.now()

def record(name, checked, failed, description):
    status = "PASS" if failed == 0 else "FAIL"
    pct = round(100.0 * failed / checked, 3) if checked else 0.0
    con.execute("INSERT INTO dq_results VALUES (?,?,?,?,?,?,?,?,?)",
                [name, "mart", "error", status, checked, failed, pct, now, description])

clean_n = con.execute("SELECT COUNT(*) FROM staging.bookings_clean").fetchone()[0]
mart_n = con.execute("SELECT COUNT(*) FROM mart.bookings_enriched").fetchone()[0]
record("clean_to_mart_rowcount", clean_n, abs(clean_n - mart_n),
       "Mart booking table must have the same rows as clean")

agent_total = con.execute("SELECT COALESCE(SUM(bookings), 0) FROM mart.agent_summary").fetchone()[0]
direct_n = con.execute("SELECT COUNT(*) FROM staging.bookings_clean WHERE agent_id IS NULL").fetchone()[0]
record("agent_bookings_reconcile", clean_n, abs(clean_n - (agent_total + direct_n)),
       "Agent bookings plus direct bookings must equal all clean bookings")

n_agents = con.execute("SELECT COUNT(*) FROM mart.agent_summary").fetchone()[0]
bad_rate = con.execute(
    "SELECT COUNT(*) FROM mart.agent_summary WHERE cancel_rate < 0 OR cancel_rate > 1").fetchone()[0]
record("agent_cancel_rate_in_range", n_agents, bad_rate, "Cancel rate must be between 0 and 1")

print(con.execute("""
    SELECT layer, check_name, status, rows_failed
    FROM dq_results WHERE layer IN ('reconciliation', 'mart')
    ORDER BY layer, check_name
""").fetchdf().to_string(index=False))
print(f"\nmart bookings: {mart_n:,} | agents: {n_agents:,}")