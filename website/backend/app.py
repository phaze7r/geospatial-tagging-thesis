from flask import Flask, jsonify, request, render_template, redirect, url_for, session
from flask_cors import CORS
import json
import os
from datetime import datetime

app = Flask(__name__)
app.secret_key = 'your-secret-key-change-this'  # Change this in production
CORS(app)

# File paths
PROGRESS_FILE = 'data/progress.json'
MESSAGES_FILE = 'data/messages.json'

# Admin credentials
ADMIN_CREDENTIALS = {
    'username': 'phazer7r',
    'password': 'goodluckthesisbrother2025'
}

# Notes admin password (change this!)
NOTES_ADMIN_PASSWORD = 'CHANGE_THIS_PASSWORD_FOR_NOTES_ADMIN'

def ensure_data_files():
    os.makedirs('data', exist_ok=True)
    if not os.path.exists(PROGRESS_FILE):
        with open(PROGRESS_FILE, 'w') as f:
            json.dump({'progress': 25, 'last_updated': datetime.now().isoformat()}, f)
    if not os.path.exists(MESSAGES_FILE):
        with open(MESSAGES_FILE, 'w') as f:
            json.dump({
                'messages': [
                    {
                        'id': 1,
                        'text': 'Started working on data collection and preprocessing',
                        'timestamp': datetime.now().isoformat(),
                        'author': 'Faizan'
                    }
                ]
            }, f)

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/api/progress')
def get_progress():
    try:
        with open(PROGRESS_FILE, 'r') as f:
            data = json.load(f)
        return jsonify(data)
    except:
        return jsonify({'progress': 0, 'last_updated': datetime.now().isoformat()})

@app.route('/api/messages')
def get_messages():
    try:
        with open(MESSAGES_FILE, 'r') as f:
            data = json.load(f)
        return jsonify(data)
    except:
        return jsonify({'messages': []})

@app.route('/admin', methods=['GET', 'POST'])
def admin():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        if username == ADMIN_CREDENTIALS['username'] and password == ADMIN_CREDENTIALS['password']:
            session['admin_logged_in'] = True
            return redirect(url_for('admin_dashboard'))
        else:
            return render_template('admin_login.html', error='Invalid credentials')
    if session.get('admin_logged_in'):
        return redirect(url_for('admin_dashboard'))
    return render_template('admin_login.html')

@app.route('/admin/dashboard')
def admin_dashboard():
    if not session.get('admin_logged_in'):
        return redirect(url_for('admin'))
    try:
        with open(PROGRESS_FILE, 'r') as f:
            data = json.load(f)
        current_progress = data.get('progress', 0)
    except:
        current_progress = 0
    return render_template('admin_dashboard.html', current_progress=current_progress)

@app.route('/admin/update-progress', methods=['POST'])
def update_progress():
    if not session.get('admin_logged_in'):
        return redirect(url_for('admin'))
    try:
        progress = int(request.form.get('progress', 0))
        progress = max(0, min(100, progress))
        data = {
            'progress': progress,
            'last_updated': datetime.now().isoformat()
        }
        with open(PROGRESS_FILE, 'w') as f:
            json.dump(data, f)
        return redirect(url_for('admin_dashboard'))
    except:
        return redirect(url_for('admin_dashboard'))

@app.route('/notes-admin', methods=['GET', 'POST'])
def notes_admin():
    if request.method == 'POST':
        action = request.form.get('action')
        if action == 'login':
            password = request.form.get('password')
            if password == NOTES_ADMIN_PASSWORD:
                session['notes_admin_logged_in'] = True
                return redirect(url_for('notes_dashboard'))
            else:
                return render_template('notes_admin_login.html', error='Invalid password')
        elif action == 'add_message' and session.get('notes_admin_logged_in'):
            message_text = request.form.get('message')
            author = request.form.get('author', 'Anonymous')
            if message_text:
                try:
                    with open(MESSAGES_FILE, 'r') as f:
                        data = json.load(f)
                    new_message = {
                        'id': max([m['id'] for m in data['messages']], default=0) + 1,
                        'text': message_text,
                        'timestamp': datetime.now().isoformat(),
                        'author': author
                    }
                    data['messages'].insert(0, new_message)
                    with open(MESSAGES_FILE, 'w') as f:
                        json.dump(data, f)
                except:
                    pass
            return redirect(url_for('notes_dashboard'))
    if session.get('notes_admin_logged_in'):
        return redirect(url_for('notes_dashboard'))
    return render_template('notes_admin_login.html')

@app.route('/notes-admin/dashboard')
def notes_dashboard():
    if not session.get('notes_admin_logged_in'):
        return redirect(url_for('notes_admin'))
    try:
        with open(MESSAGES_FILE, 'r') as f:
            data = json.load(f)
        messages = data.get('messages', [])
    except:
        messages = []
    return render_template('notes_dashboard.html', messages=messages)

@app.route('/notes-admin/delete/<int:message_id>')
def delete_message(message_id):
    if not session.get('notes_admin_logged_in'):
        return redirect(url_for('notes_admin'))
    try:
        with open(MESSAGES_FILE, 'r') as f:
            data = json.load(f)
        data['messages'] = [m for m in data['messages'] if m['id'] != message_id]
        with open(MESSAGES_FILE, 'w') as f:
            json.dump(data, f)
    except:
        pass
    return redirect(url_for('notes_dashboard'))

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('home'))

if __name__ == '__main__':
    ensure_data_files()
    app.run(debug=True)