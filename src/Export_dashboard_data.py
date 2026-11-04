from pathlib import Path
import shutil
import duckdb, pandas as pd

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "app" / "exports"
OUT.mkdir(parents=True, exist_ok=True)

con = duckdb.connect(str(ROOT / "warehouse.duckdb"), read_only=True)

# 1. Bookings and cancel rate per year
con.execute("""
    SELECT arrival_year, COUNT(*) AS bookings,
           ROUND(100.0 * AVG(is_canceled), 1) AS cancel_pct
    FROM mart.bookings_enriched GROUP BY 1 ORDER BY 1
""").fetchdf().to_csv(OUT / "overview_by_year.csv", index=False)

# 2. Cancel rate for each driver, overall and by year (groups of 200+ bookings only)
DRIVERS = ["lead_time_bucket", "distribution_channel", "deposit_type",
           "market_segment", "hotel", "customer_type"]
frames = []
for d in DRIVERS:
    by_year = f"""
        SELECT '{d}' AS driver, CAST({d} AS VARCHAR) AS category,
               CAST(arrival_year AS VARCHAR) AS year, COUNT(*) AS bookings,
               ROUND(100.0 * AVG(is_canceled), 1) AS cancel_pct
        FROM mart.bookings_enriched GROUP BY {d}, arrival_year"""
    overall = f"""
        SELECT '{d}' AS driver, CAST({d} AS VARCHAR) AS category,
               'All' AS year, COUNT(*) AS bookings,
               ROUND(100.0 * AVG(is_canceled), 1) AS cancel_pct
        FROM mart.bookings_enriched GROUP BY {d}"""
    frames += [con.execute(by_year).fetchdf(), con.execute(overall).fetchdf()]
rates = pd.concat(frames)
rates[rates["bookings"] >= 200].to_csv(OUT / "driver_rates.csv", index=False)

# 3. Agent summary (all agents)
con.execute("SELECT * FROM mart.agent_summary ORDER BY bookings DESC") \
   .fetchdf().to_csv(OUT / "agent_summary.csv", index=False)

# 4. Data quality log
con.execute("""
    SELECT layer, check_name, severity, status, rows_checked, rows_failed, pct_failed, description
    FROM dq_results
    ORDER BY CASE layer WHEN 'raw' THEN 1 WHEN 'clean' THEN 2
                        WHEN 'reconciliation' THEN 3 ELSE 4 END, check_name
""").fetchdf().to_csv(OUT / "dq_results.csv", index=False)
con.close()

# 5. Copy files made by the notebooks
for src in [ROOT / "docs" / "model_metrics.csv", ROOT / "docs" / "agent_segments_pca.png"]:
    if src.exists():
        shutil.copy(src, OUT / src.name)

print("Exported:", sorted(p.name for p in OUT.iterdir()))