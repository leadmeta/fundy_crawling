import sqlite3, json

conn = sqlite3.connect('data/fundy_records.db')
cur = conn.cursor()

# Check a gov24 record that has good data from API
cur.execute('''
SELECT id, title, SUBSTR(details, 1, 200), LENGTH(details) 
FROM funding_records 
WHERE site_name LIKE '%24%' AND details NOT LIKE '%MyGOV%' AND LENGTH(details) > 100 
LIMIT 3
''')
print('=== Good gov24 records ===')
for r in cur.fetchall():
    print(f'Title: {r[1][:50]} | len={r[3]}')
    print(f'  Details: {r[2][:150]}')
    print()

# Check a gov24 record with garbage
cur.execute('''
SELECT id, title, SUBSTR(details, 1, 100), LENGTH(details) 
FROM funding_records 
WHERE site_name LIKE '%24%' AND details LIKE '%MyGOV%' 
LIMIT 2
''')
print('=== Garbage gov24 records ===')
for r in cur.fetchall():
    print(f'Title: {r[1][:50]} | len={r[3]}')
    print()

# Check what a processed garbage record looks like
cur.execute('''
SELECT p.id, p.status, p.extracted_json
FROM processed_funding_records p
JOIN funding_records f ON p.id = f.id
WHERE f.details LIKE '%MyGOV%'
LIMIT 2
''')
print('=== Processed garbage records ===')
for r in cur.fetchall():
    print(f'ID: {r[0][:16]} | Status: {r[1]}')
    if r[2]:
        d = json.loads(r[2])
        ft = d.get('funding_type', 'N/A')
        tt = d.get('target_types', [])
        red = d.get('recruit_end_date', 'N/A')
        print(f'  funding_type: {ft} target_types: {tt}')
        print(f'  recruit_end_date: {red}')
    print()

conn.close()
