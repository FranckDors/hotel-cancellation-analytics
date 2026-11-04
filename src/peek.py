import duckdb
con = duckdb.connect("warehouse.duckdb")
print(con.execute("""
    SELECT agent, COUNT(*) AS bookings
    FROM raw.hotel_bookings
    GROUP BY agent
    ORDER BY bookings DESC
    LIMIT 5
""").fetchdf())