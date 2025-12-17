import os
import sys
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app import app, db
from sqlalchemy import text

with app.app_context():
    print(f"Fixing DB: {app.config['SQLALCHEMY_DATABASE_URI']}")
    try:
        with db.engine.connect() as conn:
            conn.execute(text("ALTER TABLE project_config ADD COLUMN sidebar_title VARCHAR(50)"))
            conn.commit()
            print("Added 'sidebar_title' column.")
    except Exception as e:
        print(f"Skipping 'sidebar_title' (already exists or error): {e}")
