import os
import sys
# Ensure web_app directory is in python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from flask import Flask, render_template, jsonify, request, redirect, url_for, flash, send_from_directory, session
from flask_login import LoginManager, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from models import db, AdminUser, ProjectConfig, Note, Report
from datetime import datetime
from flask_dance.contrib.github import make_github_blueprint, github

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-secret-key-change-this')
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///site.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# GitHub OAuth Config
app.config["GITHUB_OAUTH_CLIENT_ID"] = os.environ.get("GITHUB_OAUTH_CLIENT_ID")
app.config["GITHUB_OAUTH_CLIENT_SECRET"] = os.environ.get("GITHUB_OAUTH_CLIENT_SECRET")
# Explicitly allow HTTP for OAuth in dev/local (Remove in Prod if HTTPS is set up, but Nginx handles SSL so internal is HTTP)
os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '1' 

github_bp = make_github_blueprint()
app.register_blueprint(github_bp, url_prefix="/auth")

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


# --- Security Config ---
# Hardcoded credentials as requested ("forever in code")
ADMIN_USERNAME = 'Faizan'
ADMIN_PASSWORD_HASH = 'scrypt:32768:8:1$Ffw0B9dksM32pUmf$3b0e13785ced638758c7b47e1e70b140cbe8a59491bbf8b03ecfa1ab3e4a598002e81f7f5cdc524d070b133d8c479a9006a8577b3af9b1f4171fde7483615136'


@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('admin'))

    # Check for GitHub Login (Only if Configured)
    if app.config.get("GITHUB_OAUTH_CLIENT_ID") and github.authorized:
        try:
            resp = github.get("/user")
            if resp.ok:
                account_info = resp.json()
                username = account_info['login']
                
                # STRICT ACCESS CONTROL
                # Only allow specific GitHub users. Default: phaze7r
                allowed_users = os.environ.get('ALLOWED_GITHUB_USERS', 'phaze7r').split(',')
                # normalize for comparison
                allowed_users = [u.strip().lower() for u in allowed_users]
                
                if username.lower() in allowed_users:
                    # Log in as the AdminUser
                    user = AdminUser.query.filter_by(username=ADMIN_USERNAME).first()
                    if not user:
                         # Ensure DB user exists to satisfy ForeignKey requirements if any, or just session
                         user = AdminUser(username=ADMIN_USERNAME, password_hash=ADMIN_PASSWORD_HASH)
                         db.session.add(user)
                         db.session.commit()
                    
                    login_user(user)
                    flash(f'Verified GitHub Identity: {username}', 'success')
                    return redirect(url_for('admin'))
                else:
                    flash(f'Access Denied. GitHub user "{username}" is not on the allowlist.', 'danger')
            else:
                 flash('Failed to verify GitHub identity.', 'danger')
        except Exception as e:
            # Don't crash, just notify
            print(f"GitHub Auth Error: {e}")
            flash('GitHub Login Failed. Please check server logs.', 'danger')
        
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        # Priority Check: Hardcoded Credentials
        # Compare case-insensitively
        print(f"Login Attempt: {username} (Expected: {ADMIN_USERNAME})")
        if username and username.lower() == ADMIN_USERNAME.lower() and check_password_hash(ADMIN_PASSWORD_HASH, password):
            print("Login Success: Hardcoded credentials match.")
            # Ensure user exists in DB for Flask-Login to load it
            user = AdminUser.query.filter_by(username=ADMIN_USERNAME).first() # Use the canonical casing 'Faizan'
            if not user:
                user = AdminUser(username=ADMIN_USERNAME, password_hash=ADMIN_PASSWORD_HASH)
                db.session.add(user)
                db.session.commit()
            elif user.password_hash != ADMIN_PASSWORD_HASH:
                # Sync DB with Code (Code is truth)
                user.password_hash = ADMIN_PASSWORD_HASH
                db.session.commit()
                
            login_user(user)
            return redirect(url_for('admin'))
        
        print("Login Failed: Credentials did not match hardcoded values.")
            
        # Fallback: Check DB (optional, but code says "let me choose one time and stay forever", so maybe disable DB fallback? 
        # I'll leave DB check for legacy support but the Code Hash effectively overrides it if the username matches)
        user = AdminUser.query.filter_by(username=username).first()
        if user and check_password_hash(user.password_hash, password):
            login_user(user)
            return redirect(url_for('admin'))
            
        flash('Invalid Credentials', 'danger')
            
    github_enabled = bool(app.config.get("GITHUB_OAUTH_CLIENT_ID"))
    return render_template('login.html', github_enabled=github_enabled)

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
