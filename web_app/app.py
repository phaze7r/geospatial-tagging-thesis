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
from models import db, AdminUser, ProjectConfig, Note, Report, ResearcherProfile, TeamMember
from datetime import datetime
from flask_dance.contrib.github import make_github_blueprint, github

app = Flask(__name__)
# Fix for Nginx SSL termination
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_prefix=1)

app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-secret-key-change-this')
# Use absolute path for DB to avoid confusion with CWD
basedir = os.path.dirname(os.path.abspath(__file__))
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(basedir, 'instance', 'site.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['UPLOAD_FOLDER'] = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'static', 'uploads')

# Security Config
app.config['SESSION_COOKIE_SECURE'] = False # Temporarily disabled for debugging
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
# Removed hardcoded credentials for security.
# Admin access is now strictly controlled via the database (AdminUser model).

# --- API Routes for Frontend ---

@app.route('/api/data')
def get_data():
    config = ProjectConfig.query.first()
    if not config:
        config = ProjectConfig(progress=80)
        db.session.add(config)
        db.session.commit()
    
    profile = ResearcherProfile.query.first()
    if not profile:
        profile = ResearcherProfile()
        db.session.add(profile)
        db.session.commit()

    notes = Note.query.order_by(Note.created_at.desc()).all()
    reports = Report.query.order_by(Report.id.desc()).all()
    team_members = TeamMember.query.all()
    
    data = {
        "progress": config.progress,
        "config": {
            "githubRepo": config.github_repo,
            "contactLink": config.contact_link,
            "dashboardTitle": config.dashboard_title,
            "sidebarTitle": config.sidebar_title,
            "reports": [r.to_dict() for r in reports]
        },
        "profile": profile.to_dict(),
        "team": [m.to_dict() for m in team_members],
        "notes": [note.to_dict() for note in notes]
    }
    return jsonify(data)

@app.route('/api/reports/accuracy')
def get_accuracy_metrics():
    metrics_path = os.path.join(app.static_folder, 'dashboard_metrics.json')
    if os.path.exists(metrics_path):
        try:
            import json
            with open(metrics_path, 'r') as f:
                return jsonify(json.load(f))
        except Exception as e:
            print(f"Error reading metrics: {e}")
            return jsonify({})
    return jsonify({})

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
                        user = AdminUser.query.filter_by(username='Faizan').first()
                        if user:
                            login_user(user)
                            flash(f'Verified GitHub Identity: {username}', 'success')
                            return redirect(url_for('admin'))
                    else:
                        flash(f'Access Denied. GitHub user "{username}" is not on the allowlist.', 'danger')
            except Exception as e:
                print(f"GitHub Auth Error: {e}")
                flash('GitHub Login Failed. Please check server logs.', 'danger')

        # Handle Standard Login POST
        if request.method == 'POST':
             username = request.form.get('username')
             password = request.form.get('password')
             
             if username: # Ensure it is a login attempt
                print(f"DEBUG: Login attempt for user: '{username}'")
                # Authenticate against Database ONLY (Case Insensitive)
                user = AdminUser.query.filter(AdminUser.username.collate('NOCASE') == username).first()
                # Fallback if NOCASE not supported (though it is in SQLite)
                if not user:
                     print(f"DEBUG: User not found via query.")
                     users = AdminUser.query.all()
                     for u in users:
                         if u.username.lower() == username.lower():
                             user = u
                             print(f"DEBUG: User found via fallback loop: '{u.username}'")
                             break
                
                if user:
                    check = check_password_hash(user.password_hash, password)
                    print(f"DEBUG: Password check for '{user.username}': {check}")
                    if check:
                        login_user(user)
                        return redirect(url_for('admin'))
                else:
                    print("DEBUG: User object is None after checks.")
                    
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

    profile = ResearcherProfile.query.first()
    if not profile:
        profile = ResearcherProfile()
        db.session.add(profile)
        db.session.commit()

    team_members = TeamMember.query.all()

    if request.method == 'POST':
        if 'update_config' in request.form:
            config.progress = int(request.form.get('progress'))
            config.contact_link = request.form.get('contact_link')
            config.dashboard_title = request.form.get('dashboard_title')
            config.sidebar_title = request.form.get('sidebar_title')
            db.session.commit()
            flash('Configuration updated!', 'success')
        
        elif 'update_profile' in request.form:
            profile.name = request.form.get('name')
            profile.title = request.form.get('title')
            profile.bio = request.form.get('bio')
            profile.email = request.form.get('email')
            profile.github = request.form.get('github')
            profile.linkedin = request.form.get('linkedin')
            profile.twitter = request.form.get('twitter')
            
            # Image Upload
            file = request.files.get('image_file')
            if file and file.filename != '' and allowed_file(file.filename):
                filename = secure_filename(file.filename)
                file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
                profile.image_path = f'/static/uploads/{filename}'
            
            db.session.commit()
            flash('Researcher Profile updated!', 'success')
        
        elif 'add_team_member' in request.form:
            name = request.form.get('name')
            role = request.form.get('role')
            title = request.form.get('title')
            bio = request.form.get('bio')
            
            new_member = TeamMember(name=name, role=role, title=title, bio=bio)
            new_member.email = request.form.get('email', '')
            new_member.github = request.form.get('github', '')
            new_member.linkedin = request.form.get('linkedin', '')
            new_member.twitter = request.form.get('twitter', '')

            file = request.files.get('image_file')
            if file and file.filename != '' and allowed_file(file.filename):
                filename = secure_filename(file.filename)
                file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
                new_member.image_path = f'/static/uploads/{filename}'

            db.session.add(new_member)
            db.session.commit()
            flash(f'Added {role}: {name}', 'success')
            return redirect(url_for('admin'))

        elif 'update_team_member' in request.form:
            member_id = request.form.get('member_id')
            member = TeamMember.query.get(member_id)
            if member:
                member.name = request.form.get('name')
                member.role = request.form.get('role')
                member.title = request.form.get('title')
                member.bio = request.form.get('bio')
                member.email = request.form.get('email')
                member.github = request.form.get('github')
                member.linkedin = request.form.get('linkedin')
                member.twitter = request.form.get('twitter')
                
                file = request.files.get('image_file')
                if file and file.filename != '' and allowed_file(file.filename):
                    filename = secure_filename(file.filename)
                    file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
                    member.image_path = f'/static/uploads/{filename}'
                
                db.session.commit()
                flash(f'Updated {member.role}: {member.name}', 'success')
            else:
                flash('Member not found.', 'danger')
            return redirect(url_for('admin'))
        
        elif 'delete_team_member' in request.form:
            member_id = request.form.get('member_id')
            member = TeamMember.query.get(member_id)
            if member:
                db.session.delete(member)
                db.session.commit()
                flash(f'Deleted {member.name}', 'success')
            return redirect(url_for('admin'))

        elif 'change_password' in request.form:
            new_password = request.form.get('new_password')
            if new_password:
                current_user.password_hash = generate_password_hash(new_password)
                db.session.commit()
                flash('Password changed successfully! Please login again.', 'success')
                logout_user()
                return redirect(url_for('admin'))
            else:
                flash('Password cannot be empty.', 'danger')

        elif 'add_note' in request.form:
            # ...

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
            
    # --- RENDER ADMIN TEMPLATE ---
    notes = Note.query.order_by(Note.created_at.desc()).all()
    reports = Report.query.order_by(Report.id.desc()).all()
    
    return render_template('admin.html', 
                         config=config, 
                         profile=profile, 
                         team_members=team_members,
                         notes=notes, 
                         reports=reports)

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
    session.clear()
    flash('You have been logged out.', 'info')
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