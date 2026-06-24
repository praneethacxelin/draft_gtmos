import sqlite3

conn = sqlite3.connect("gtmdb.db")
cursor = conn.cursor()

# Get column names for strategies table
cursor.execute("PRAGMA table_info(strategies)")
columns = [row[1] for row in cursor.fetchall()]
print("strategies columns:", columns)

# Get column names for other tables as well to see if they match db.py
for table in ["strategies", "contacts", "accounts", "signals", "pattern_clusters", "sequences", "sequence_steps", "instantly_campaigns", "outreach_events"]:
    try:
        cursor.execute(f"PRAGMA table_info({table})")
        cols = [row[1] for row in cursor.fetchall()]
        print(f"{table} columns:", cols)
    except Exception as e:
        print(f"Error reading info for {table}: {e}")

conn.close()
