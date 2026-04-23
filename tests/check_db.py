import sqlite3

conn = sqlite3.connect('fundy_records.db')
cursor = conn.cursor()
cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
tables = [row[0] for row in cursor.fetchall()]
print("Tables:", tables)

for t in tables:
    if 'record' in t or 'fund' in t:
        cursor.execute(f'SELECT COUNT(*) FROM {t}')
        print(f"Total in {t}:", cursor.fetchone()[0])
conn.close()
