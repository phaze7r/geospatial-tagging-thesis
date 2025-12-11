import os
import sys
# Ensure web_app directory is in python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from flask import Flask, render_template, jsonify, request, redirect, url_for, flash, send_from_directory
from flask_login import LoginManager, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from models import db, AdminUser, ProjectConfig, Note, Report
from datetime import datetime

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-secret-key-change-this')
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///site.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db.init_app(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'

@login_manager.user_loader
def load_user(user_id):
    return AdminUser.query.get(int(user_id))

# --- API Routes for Frontend ---

@app.route('/api/data')
def get_data():
    config = ProjectConfig.query.first()
    if not config:
        config = ProjectConfig(progress=80)
        db.session.add(config)
        db.session.commit()
    
    notes = Note.query.order_by(Note.created_at.desc()).all()
    reports = Report.query.order_by(Report.id.desc()).all()
    
    data = {
        "progress": config.progress,
        "config": {
            "githubRepo": config.github_repo,
            "reports": [r.to_dict() for r in reports]
        },
        "notes": [note.to_dict() for note in notes]
    }
    return jsonify(data)

@app.route('/api/reports/accuracy')
def get_accuracy():
    try:
        # Path to benchmark_results.json
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        json_path = os.path.join(base_dir, 'datareported', 'classification', 'benchmark_results.json')
        
        if os.path.exists(json_path):
            import json
            with open(json_path, 'r') as f:
                data = json.load(f)
            return jsonify(data)
        else:
            return jsonify({"error": "Accuracy data not found"}), 404
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/files/<path:filename>')
def serve_datareported(filename):
    # Securely serve files from 'datareported' directory
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    datareported_dir = os.path.join(base_dir, 'datareported')
    return send_from_directory(datareported_dir, filename)

# --- Admin Routes ---

@app.route('/admin', methods=['GET', 'POST'])
@login_required
def admin():
    config = ProjectConfig.query.first()
    if not config:
        # Initialize default config if missing
        config = ProjectConfig(progress=80)
        db.session.add(config)
        db.session.commit()

    if request.method == 'POST':
        if 'update_progress' in request.form:
            config.progress = int(request.form.get('progress'))
            db.session.commit()
            flash('Progress updated!', 'success')
        
        elif 'add_note' in request.form:
            content = request.form.get('content')
            date_val = request.form.get('date')
            if date_val:
                date_str = date_val # form sends yyyy-mm-dd
            else:
                date_str = datetime.now().strftime("%Y-%m-%d")
            
            new_note = Note(content=content, date_str=date_str, author=current_user.username)
            db.session.add(new_note)
            db.session.commit()
            flash('Note added!', 'success')
            
        elif 'add_report' in request.form:
            title = request.form.get('title')
            path = request.form.get('path')
            date_str = datetime.now().strftime("%Y-%m-%d")
            new_report = Report(title=title, path=path, date_str=date_str)
            db.session.add(new_report)
            db.session.commit()
            flash('Report added!', 'success')
            
    notes = Note.query.order_by(Note.created_at.desc()).all()
    reports = Report.query.all()
    return render_template('admin.html', config=config, notes=notes, reports=reports)

@app.route('/admin/delete_note/<int:id>', methods=['POST'])
@login_required
def delete_note(id):
    note = Note.query.get_or_404(id)
    db.session.delete(note)
    db.session.commit()
    flash('Note deleted.', 'info')
    return redirect(url_for('admin'))

@app.route('/admin/delete_report/<int:id>', methods=['POST'])
@login_required
def delete_report(id):
    report = Report.query.get_or_404(id)
    db.session.delete(report)
    db.session.commit()
    flash('Report deleted.', 'info')
    return redirect(url_for('admin'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('admin'))
        
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        user = AdminUser.query.filter_by(username=username).first()
        
        if user and check_password_hash(user.password_hash, password):
            login_user(user)
            return redirect(url_for('admin'))
        else:
            flash('Login Unsuccessful. Please check username and password', 'danger')
            
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('index'))

# --- Main App Serving ---

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/<path:path>')
def static_proxy(path):
    # serve static files if needed, though Nginx should handle this in prod
    return app.send_static_file(path)

# --- CLI for Initial Setup ---
@app.cli.command("create-admin")
def create_admin():
    db.create_all()
    if not AdminUser.query.filter_by(username='Faizan').first():
        hashed_pw = generate_password_hash('admin') # Default checks for this
        user = AdminUser(username='Faizan', password_hash=hashed_pw)
        db.session.add(user)
        
        # Also init config
        if not ProjectConfig.query.first():
             db.session.add(ProjectConfig(progress=80))
             
        db.session.commit()
        print("Admin user created (user: Faizan, pass: admin)")
    else:
        print("Admin already exists")

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True, port=5000)
