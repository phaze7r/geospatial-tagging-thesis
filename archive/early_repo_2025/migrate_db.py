from web_app.app import app, db
from sqlalchemy import text

with app.app_context():
    try:
        with db.engine.connect() as conn:
            conn.execute(text("ALTER TABLE project_config ADD COLUMN dashboard_title VARCHAR(120)"))
            conn.commit()
            print("Added dashboard_title column.")
    except Exception as e:
        print(f"Column likely exists or error: {e}")
