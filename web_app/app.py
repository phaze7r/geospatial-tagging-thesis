import os
import sys
# Ensure web_app directory is in python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from flask import Flask, render_template, jsonify, request, redirect, url_for, flash, send_from_directory, session
from flask_login import LoginManager, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from werkzeug.middleware.proxy_fix import ProxyFix
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from models import db, AdminUser, ProjectConfig, Note, Report
from datetime import datetime
from flask_dance.contrib.github import make_github_blueprint, github

app = Flask(__name__)
# Fix for Nginx SSL termination
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_prefix=1)

app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-secret-key-change-this')
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///site.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['UPLOAD_FOLDER'] = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'static', 'uploads')

# Security Config
app.config['SESSION_COOKIE_SECURE'] = True # Requires HTTPS
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'

# Setup Limiter
limiter = Limiter(
    get_remote_address,
    app=app,
    default_limits=["200 per day", "50 per hour"],
    storage_uri="memory://"
)

# Ensure upload directory exists
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

ALLOWED_EXTENSIONS = {'txt', 'pdf', 'png', 'jpg', 'jpeg', 'gif', 'md', 'json', 'csv'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# GitHub OAuth Config
app.config["GITHUB_OAUTH_CLIENT_ID"] = os.environ.get("GITHUB_OAUTH_CLIENT_ID")
app.config["GITHUB_OAUTH_CLIENT_SECRET"] = os.environ.get("GITHUB_OAUTH_CLIENT_SECRET")
# Removed OAUTHLIB_INSECURE_TRANSPORT as we are now behind Nginx ProxyFix with HTTPS

github_bp = make_github_blueprint()
app.register_blueprint(github_bp, url_prefix="/auth")

db.init_app(app)
login_manager = LoginManager(app)
# If a user hits a @login_required route, send them to admin (which will show login)
login_manager.login_view = 'admin' 

@login_manager.user_loader
def load_user(user_id):
    return AdminUser.query.get(int(user_id))

# --- Security Config ---
# Hardcoded credentials as requested ("forever in code")
ADMIN_USERNAME = 'Faizan'
ADMIN_PASSWORD_HASH = 'scrypt:32768:8:1$Ffw0B9dksM32pUmf$3b0e13785ced638758c7b47e1e70b140cbe8a59491bbf8b03ecfa1ab3e4a598002e81f7f5cdc524d070b133d8c479a9006a8577b3af9b1f4171fde7483615136'

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
            "contactLink": config.contact_link,
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
@limiter.limit("10 per minute") # Rate limit login attempts/admin access
def admin():
    # --- AUTHENTICATION LOGIC ---
    if not current_user.is_authenticated:
        # Check for GitHub Login (Only if Configured)
        if app.config.get("GITHUB_OAUTH_CLIENT_ID") and github.authorized:
            try:
                resp = github.get("/user")
                if resp.ok:
                    account_info = resp.json()
                    username = account_info['login']
                    
                    # STRICT ACCESS CONTROL
                    allowed_users = os.environ.get('ALLOWED_GITHUB_USERS', 'phaze7r').split(',')
                    allowed_users = [u.strip().lower() for u in allowed_users]
                    
                    if username.lower() in allowed_users:
                        # Log in as the AdminUser
                        user = AdminUser.query.filter_by(username=ADMIN_USERNAME).first()
                        if not user:
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
                print(f"GitHub Auth Error: {e}")
                flash('GitHub Login Failed. Please check server logs.', 'danger')

        # Handle Standard Login POST
        if request.method == 'POST':
             username = request.form.get('username')
             password = request.form.get('password')
             
             if username: # Ensure it is a login attempt
                print(f"Login Attempt: {username} (Expected: {ADMIN_USERNAME})")
                if username.lower() == ADMIN_USERNAME.lower() and check_password_hash(ADMIN_PASSWORD_HASH, password):
                    print("Login Success: Hardcoded credentials match.")
                    user = AdminUser.query.filter_by(username=ADMIN_USERNAME).first()
                    if not user:
                        user = AdminUser(username=ADMIN_USERNAME, password_hash=ADMIN_PASSWORD_HASH)
                        db.session.add(user)
                        db.session.commit()
                    elif user.password_hash != ADMIN_PASSWORD_HASH:
                        user.password_hash = ADMIN_PASSWORD_HASH
                        db.session.commit()
                        
                    login_user(user)
                    return redirect(url_for('admin'))
                
                # DB Fallback (Optional)
                user = AdminUser.query.filter_by(username=username).first()
                if user and check_password_hash(user.password_hash, password):
                    login_user(user)
                    return redirect(url_for('admin'))
                    
                flash('Invalid Credentials', 'danger')

        # Render Login Template if not authenticated
        github_enabled = bool(app.config.get("GITHUB_OAUTH_CLIENT_ID"))
        return render_template('login.html', github_enabled=github_enabled)


    # --- ADMIN DASHBOARD LOGIC (Authenticated) ---
    config = ProjectConfig.query.first()
    if not config:
        config = ProjectConfig(progress=80)
        db.session.add(config)
        db.session.commit()

    if request.method == 'POST':
        if 'update_config' in request.form:
            config.progress = int(request.form.get('progress'))
            config.contact_link = request.form.get('contact_link')
            db.session.commit()
            flash('Configuration updated!', 'success')
        
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
            
            # Handle File Upload
            file = request.files.get('file')
            if file and file.filename != '' and allowed_file(file.filename):
                filename = secure_filename(file.filename)
                # Save to web_app/static/uploads
                file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
                # Set path to be accessible via static route
                path = f'/static/uploads/{filename}'
            
            if not path:
                flash('Please provide a file or a path URL.', 'danger')
            else:
                date_str = datetime.now().strftime("%Y-%m-%d")
                new_report = Report(title=title, path=path, date_str=date_str)
                db.session.add(new_report)
                db.session.commit()
                flash('Report added successfully!', 'success')
            
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

# Redirect /login to /admin to consolidate
@app.route('/login')
def login_redirect():
    return redirect(url_for('admin'))

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