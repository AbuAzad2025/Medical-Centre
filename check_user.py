"""Clear ALL recent failed login attempts."""
from sqlalchemy import create_engine, text
import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

e = create_engine('postgresql://postgres:123@localhost:5432/medical_system')
with e.connect() as c:
    r = c.execute(text("DELETE FROM login_attempts WHERE success=False"))
    print(f"Deleted {r.rowcount} failed attempts")
    c.commit()
