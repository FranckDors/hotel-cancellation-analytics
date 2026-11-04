import duckdb
con = duckdb.connect("warehouse.duckdb")
print(con.execute("""
    SELECT hotel,
           COUNT(*) AS bookings,
           ROUND(100.0 * AVG(is_canceled), 1) AS cancel_pct
    FROM staging.bookings_clean
    GROUP BY hotel
""").fetchdf())