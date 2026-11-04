from web_app.app import app, db
from web_app.models import ResearcherProfile

with app.app_context():
    db.create_all()
    if not ResearcherProfile.query.first():
        profile = ResearcherProfile()
        db.session.add(profile)
        db.session.commit()
        print("Created default ResearcherProfile.")
    else:
        print("ResearcherProfile already exists.")
