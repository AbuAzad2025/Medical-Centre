import psycopg2

conn = psycopg2.connect('postgresql://postgres:123@localhost:5432/medical_test')
cur = conn.cursor()

# Check alembic_version table
try:
    cur.execute("SELECT version_num FROM alembic_version")
    print('Alembic version:', cur.fetchone())
except Exception as e:
    print('alembic_version error:', e)

# Check RLS status on key tables
for table in ['patients', 'visits', 'appointments', 'phi_audit_logs']:
    cur.execute(f"""
        SELECT relrowsecurity, relforcerowsecurity 
        FROM pg_class 
        WHERE relname = '{table}' AND relkind = 'r'
    """)
    result = cur.fetchone()
    if result:
        print(f'{table}: row_security={result[0]}, force_row_security={result[1]}')
    else:
        print(f'{table}: NOT FOUND')

# Check if RLS policies exist
cur.execute("""
    SELECT schemaname, tablename, policyname, permissive, roles, cmd, qual, with_check
    FROM pg_policies 
    WHERE tablename IN ('patients', 'visits', 'appointments', 'phi_audit_logs')
    ORDER BY tablename, policyname
""")
for row in cur.fetchall():
    print(f'Policy: {row}')

cur.close()