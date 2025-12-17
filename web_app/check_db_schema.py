import os
import sys
# Add current dir to path so we can import app and models
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app import app, db
from models import ProjectConfig
from sqlalchemy import inspect

with app.app_context():
    print(f"DB URI: {app.config['SQLALCHEMY_DATABASE_URI']}")
    inspector = inspect(db.engine)
    columns = [c['name'] for c in inspector.get_columns('project_config')]
    print(f"ProjectConfig Columns: {columns}")
