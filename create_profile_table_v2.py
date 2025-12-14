import sys
import os
sys.path.append(os.getcwd())
from web_app.app import app, db
from web_app.models import ResearcherProfile

with app.app_context():
    db.create_all()
    try:
        if not ResearcherProfile.query.first():
            p = ResearcherProfile()
            db.session.add(p)
            db.session.commit()
            print("Created ResearcherProfile.")
        else:
            print("ResearcherProfile exists.")
    except Exception as e:
        print(f"Error: {e}")
