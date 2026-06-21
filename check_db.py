from sqlalchemy import create_engine, text
e = create_engine('postgresql://postgres:123@localhost:5432/medical_system')
with e.connect() as c:
    print(f"Medications: {c.execute(text('SELECT COUNT(*) FROM medications')).scalar()}")
    print(f"PharmacySales: {c.execute(text('SELECT COUNT(*) FROM pharmacy_sales')).scalar()}")
    r = c.execute(text("SELECT column_name FROM information_schema.columns WHERE table_name='pharmacy_sales' AND column_name='customer_name'"))
    print(f"Customer col exists: {r.fetchone() is not None}")
