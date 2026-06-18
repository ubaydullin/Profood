import sqlite3
import pandas as pd

conn = sqlite3.connect('salescrap.db')

with open("output.txt", "w", encoding="utf-8") as f:
    f.write("--- Top Items in 'Other' Category ---\n")
    df_other = pd.read_sql("SELECT item_name, competitor_name FROM parsed_promos WHERE item_category='Other' LIMIT 30", conn)
    f.write(df_other.to_string())

    f.write("\n\n--- Top Categories Overall ---\n")
    df_cats = pd.read_sql("SELECT item_category, count(*) as c FROM parsed_promos GROUP BY item_category ORDER BY c DESC LIMIT 10", conn)
    f.write(df_cats.to_string())

