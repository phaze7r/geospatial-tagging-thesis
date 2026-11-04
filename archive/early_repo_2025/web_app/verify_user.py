import os
import sys
# Add current dir to path so we can import app and models
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app import app, db
from models import AdminUser

with app.app_context():
    users = AdminUser.query.all()
    if users:
        for user in users:
            print(f"Found user: '{user.username}'")
        print("\nPassword hashes are stored securely and are not displayed.")
    else:
        print("No admin users found in the database.")

