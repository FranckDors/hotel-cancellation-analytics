import urllib.request
import duckdb

URL = "https://raw.githubusercontent.com/rfordatascience/tidytuesday/main/data/2020/2020-02-11/hotels.csv"

# 1. Download the CSV file
urllib.request.urlretrieve(URL, "data/hotels.csv")

# 2. Open (or create) the database file
con = duckdb.connect("warehouse.duckdb")

# 3. Load the file into a "raw" table, exactly as it arrived
con.execute("CREATE SCHEMA IF NOT EXISTS raw")
con.execute("""
    CREATE OR REPLACE TABLE raw.hotel_bookings AS
    SELECT * FROM read_csv_auto('data/hotels.csv', all_varchar=true)
""")

# 4. Check it worked
print(con.execute("SELECT COUNT(*) FROM raw.hotel_bookings").fetchone())
print(con.execute("SELECT hotel, COUNT(*) FROM raw.hotel_bookings GROUP BY hotel").fetchall())