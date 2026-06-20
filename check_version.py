import sys
sys.stdout.reconfigure(encoding='utf-8')
from dotenv import load_dotenv
load_dotenv()
from app_factory import create_app
app = create_app()
with app.app_context():
    from sqlalchemy import text
    from app_factory import db
    try:
        result = db.session.execute(text("SELECT version_num FROM alembic_version")).fetchall()
        for r in result:
            print(f"Current alembic version: {r[0]}")
    except Exception as e:
        print(f"No alembic_version table or error: {e}")
        # Try to create it
        try:
            db.session.execute(text("CREATE TABLE alembic_version (version_num VARCHAR(32) NOT NULL)"))
            db.session.commit()
            print("Created alembic_version table")
        except:
            print("Could not create")
