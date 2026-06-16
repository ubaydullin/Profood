import sqlite3

conn = sqlite3.connect("salescrap.db")
c = conn.cursor()
c.execute(
    "SELECT competitor_name, restaurant_url FROM parsed_promos WHERE competitor_name LIKE '%Pizza_Hut%' LIMIT 1"
)
print(c.fetchone())
