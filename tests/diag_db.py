import sqlite3

conn = sqlite3.connect('data/fundy_records.db')
c = conn.cursor()

c.execute('SELECT COUNT(*) FROM funding_records')
print(f'Total records: {c.fetchone()[0]}')

c.execute("SELECT COUNT(*) FROM funding_records WHERE institution IS NULL OR institution = ''")
print(f'Empty institution: {c.fetchone()[0]}')

c.execute("SELECT COUNT(*) FROM funding_records WHERE details IS NULL OR details = ''")
print(f'Empty details: {c.fetchone()[0]}')

c.execute('SELECT site_name, COUNT(*) FROM funding_records GROUP BY site_name')
print('\n--- Site distribution ---')
for r in c.fetchall():
    print(f'  {r[0]}: {r[1]} records')

c.execute("SELECT institution, recruit_period, substr(details,1,80), url FROM funding_records ORDER BY date DESC LIMIT 5")
print('\n--- Recent 5 samples ---')
for i, r in enumerate(c.fetchall(), 1):
    print(f'\n  [{i}] institution: [{r[0]}]')
    print(f'      recruit_period: [{r[1]}]')
    print(f'      details(80ch): [{r[2]}]')
    print(f'      url: ...{r[3][-50:]}')

conn.close()
