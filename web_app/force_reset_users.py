import os
import sys
# Add current dir to path so we can import app and models
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app import app, db
from models import AdminUser
from werkzeug.security import generate_password_hash

with app.app_context():
    # Delete existing 'admin' user if exists to start fresh
    old_admin = AdminUser.query.filter_by(username='admin').first()
    if old_admin:
        db.session.delete(old_admin)
        db.session.commit()
    
    # Create new 'admin' user
    hashed_pw = generate_password_hash('admin')
    new_user = AdminUser(username='admin', password_hash=hashed_pw)
    db.session.add(new_user)
    db.session.commit()
    print("Created user 'admin' with password 'admin'.")
    
    # Also verify 'Faizan'
    faizan = AdminUser.query.filter_by(username='Faizan').first()
    if faizan:
        faizan.password_hash = generate_password_hash('admin')
        db.session.commit()
        print("Reset user 'Faizan' password to 'admin'.")
