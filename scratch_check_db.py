import sqlite3

conn = sqlite3.connect("artifacts/fastapi-server/gtmdb.db")
cursor = conn.cursor()

# Get table names
cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
print("Tables:", [r[0] for r in cursor.fetchall()])

# Get strategies
cursor.execute("SELECT id, product_name, status, description FROM strategies;")
print("Strategies:")
for row in cursor.fetchall():
    print(row)
    
conn.close()
