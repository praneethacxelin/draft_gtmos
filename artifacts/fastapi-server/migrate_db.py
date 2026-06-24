import sqlite3

conn = sqlite3.connect("gtmdb.db")
cursor = conn.cursor()

def add_column_if_missing(table, column, col_type):
    cursor.execute(f"PRAGMA table_info({table})")
    columns = [row[1] for row in cursor.fetchall()]
    if column not in columns:
        print(f"Adding column {column} to table {table}...")
        try:
            cursor.execute(f"ALTER TABLE {table} ADD COLUMN {column} {col_type}")
            conn.commit()
            print("Successfully added!")
        except Exception as e:
            print(f"Error adding column {column}: {e}")
    else:
        print(f"Column {column} already exists in table {table}.")

# Add missing columns
add_column_if_missing("strategies", "roi_json", "JSON")
add_column_if_missing("strategies", "last_signal_scan", "TIMESTAMP")
add_column_if_missing("strategies", "daily_signal_summary", "JSON")

add_column_if_missing("contacts", "source", "VARCHAR DEFAULT 'discovery'")
add_column_if_missing("contacts", "source_ref", "VARCHAR")

add_column_if_missing("accounts", "location", "VARCHAR")
add_column_if_missing("accounts", "founded_year", "INTEGER")

conn.close()
print("Migration check complete.")
