import duckdb
con = duckdb.connect("warehouse.duckdb")

def show(title, sql):
    print(f"\n=== {title} ===")
    print(con.execute(sql).fetchdf().to_string(index=False))

show("Does the high-risk rule work?", """
    SELECT is_high_risk_booking, COUNT(*) AS bookings,
           ROUND(100.0 * AVG(is_canceled), 1) AS cancel_pct
    FROM mart.bookings_enriched GROUP BY 1 ORDER BY 1""")

show("Do repeat guests cancel less?", """
    SELECT is_repeat_guest_safe, COUNT(*) AS bookings,
           ROUND(100.0 * AVG(is_canceled), 1) AS cancel_pct
    FROM mart.bookings_enriched GROUP BY 1 ORDER BY 1""")

show("Cancel rate by lead time", """
    SELECT lead_time_bucket, COUNT(*) AS bookings,
           ROUND(100.0 * AVG(is_canceled), 1) AS cancel_pct
    FROM mart.bookings_enriched GROUP BY 1 ORDER BY MIN(lead_time)""")

show("Direct vs agent bookings", """
    SELECT has_agent, COUNT(*) AS bookings,
           ROUND(100.0 * AVG(is_canceled), 1) AS cancel_pct
    FROM mart.bookings_enriched GROUP BY 1 ORDER BY 1""")

show("Top 10 agents by cancellations", """
    SELECT agent_id, bookings, cancellations,
           ROUND(100.0 * cancel_rate, 1) AS cancel_pct,
           ROUND(100.0 * share_of_all_cancellations, 1) AS pct_of_all_cancels,
           is_high_cancel_agent
    FROM mart.agent_summary ORDER BY cancellations DESC LIMIT 10""")

show("How many high-cancel agents?", """
    SELECT is_high_cancel_agent, COUNT(*) AS agents, SUM(bookings) AS bookings
    FROM mart.agent_summary GROUP BY 1 ORDER BY 1""")