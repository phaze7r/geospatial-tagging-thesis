import os
import sys
# Add current dir to path so we can import app and models
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app import app, db
from models import ResearcherProfile

with app.app_context():
    db.create_all()
    if not ResearcherProfile.query.first():
        db.session.add(ResearcherProfile())
        db.session.commit()
        print("Created Profile.")
    else:
        print("Profile Exists.")
