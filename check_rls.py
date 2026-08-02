import psycopg2

conn = psycopg2.connect('postgresql://postgres:123@localhost:5432/medical_test')
cur = conn.cursor()
cur.execute('SELECT version_num FROM alembic_version')
print('Alembic version:', cur.fetchone())
cur.execute(
    "SELECT relname, relrowsecurity, relforcerowsecurity FROM pg_class WHERE relname IN ('patients', 'visits', 'appointments') AND relkind = 'r'"
)
for row in cur.fetchall():
    print(row)
cur.close()
conn.close()
