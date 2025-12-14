from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
from flask_login import UserMixin

db = SQLAlchemy()

class AdminUser(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(120), nullable=False)

class ProjectConfig(db.Model):
    # Singleton store for "Progress" and other config
    id = db.Column(db.Integer, primary_key=True)
    progress = db.Column(db.Integer, default=0)
    github_repo = db.Column(db.String(120), default="phaze7r/geospatial-tagging-thesis")
    contact_link = db.Column(db.String(200), default="")

class Note(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    content = db.Column(db.Text, nullable=False)
    date_str = db.Column(db.String(20), nullable=False) # e.g. "2025-12-10"
    author = db.Column(db.String(50), default="admin")
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            "id": self.id,
            "content": self.content,
            "date": self.date_str,
            "author": self.author,
            "createdAt": self.created_at.isoformat()
        }

class Report(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(120), nullable=False)
    path = db.Column(db.String(200), nullable=False) # e.g. "reports/foo.md" or "https://..."
    date_str = db.Column(db.String(20), nullable=False)
    
    def to_dict(self):
        return {
            "id": self.id,
            "title": self.title,
            "path": self.path,
            "date": self.date_str
        }
