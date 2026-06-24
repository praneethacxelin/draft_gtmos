import sqlite3

conn = sqlite3.connect("gtmdb.db")
cursor = conn.cursor()

try:
    cursor.execute("SELECT id, product_name, status FROM strategies")
    rows = cursor.fetchall()
    print("STRATEGIES:")
    for row in rows:
        print(row)
except Exception as e:
    print("Error querying strategies:", e)

try:
    cursor.execute("SELECT count(*) FROM outreach_events")
    print("Outreach events count:", cursor.fetchone()[0])
except Exception as e:
    print("Error querying outreach events:", e)

conn.close()
