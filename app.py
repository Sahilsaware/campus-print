import os
import json
import uuid
import time
import base64
from flask import Flask, request, jsonify, render_template, session, redirect, url_for
from flask_cors import CORS
from pypdf import PdfReader
from flask_sock import Sock

# Gunicorn expects this exact variable 'app' at the top level
app = Flask(__name__)
CORS(app)
sock = Sock(app)
app.secret_key = 'campus_print_secure_admin_key_2026'

HISTORY_FILE = 'print_history.json'
ADMINS_FILE = 'admins.json'

SUPER_ADMIN_USER = "campus_admin"
SUPER_ADMIN_PASS = "CampusPrint@2026#Secure"

PRINT_JOBS = []
connected_printers = set()
last_heartbeat_time = 0

def load_history():
    if os.path.exists(HISTORY_FILE):
        try:
            with open(HISTORY_FILE, 'r') as f:
                return json.load(f)
        except Exception:
            return []
    return []

def save_history(history):
    with open(HISTORY_FILE, 'w') as f:
        json.dump(history, f, indent=4)

def load_admins():
    if os.path.exists(ADMINS_FILE):
        try:
            with open(ADMINS_FILE, 'r') as f:
                return json.load(f)
        except Exception:
            return {}
    return {}

def save_admins(admins):
    with open(ADMINS_FILE, 'w') as f:
        json.dump(admins, f, indent=4)

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/admin/login', methods=['GET', 'POST'])
def admin_login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        if username == SUPER_ADMIN_USER and password == SUPER_ADMIN_PASS:
            session['admin_logged_in'] = True
            session['username'] = username
            session['role'] = 'Super Admin'
            return redirect(url_for('admin_panel'))
        admins = load_admins()
        if username in admins and admins[username]['password'] == password:
            session['admin_logged_in'] = True
            session['username'] = username
            session['role'] = admins[username].get('role', 'Sub-Admin')
            return redirect(url_for('admin_panel'))
        return render_template('admin_login.html', error='Invalid username or password')
    return render_template('admin_login.html')

@app.route('/admin/logout')
def admin_logout():
    session.clear()
    return redirect(url_for('admin_login'))

@app.route('/admin')
def admin_panel():
    if not session.get('admin_logged_in'):
        return redirect(url_for('admin_login'))
    history = load_history()
    return render_template('admin.html', pending_jobs=PRINT_JOBS, history=history, username=session.get('username'))

@app.route('/count-multiple-pages', methods=['POST'])
def count_multiple_pages():
    if 'files' not in request.files:
        return jsonify({'error': 'No files uploaded'}), 400
    
    total_pages = 0
    files = request.files.getlist('files')
    for file in files:
        if file.filename != '':
            ext = os.path.splitext(file.filename)[1].lower()
            if ext == '.pdf':
                try:
                    from io import BytesIO
                    file_bytes = file.read()
                    reader = PdfReader(BytesIO(file_bytes))
                    total_pages += len(reader.pages)
                except Exception:
                    total_pages += 1
            else:
                total_pages += 1
                
    return jsonify({'success': True, 'total_pages': total_pages})

@app.route('/print-multiple', methods=['POST'])
def print_multiple():
    if 'files' not in request.files:
        return jsonify({'error': 'No files uploaded'}), 400

    copies = int(request.form.get('copies', 1))
    orientation = request.form.get('orientation', 'portrait')
    color_mode = request.form.get('color_mode', 'bw')
    paper_size = request.form.get('paper_size', 'A4')
    duplex = request.form.get('duplex', 'false').lower() == 'true'
    page_range = request.form.get('page_range', '')
    pages_per_sheet = int(request.form.get('pages_per_sheet', 1))
    
    price_per_page = 5 if color_mode == 'color' else 2
    files = request.files.getlist('files')

    for file in files:
        if file.filename != '':
            ext = os.path.splitext(file.filename)[1].lower()
            if ext in ['.pdf', '.png', '.jpg', '.jpeg', '.docx', '.pptx', '.doc']:
                job_id = str(uuid.uuid4())
                file_bytes = file.read()
                file_base64 = base64.b64encode(file_bytes).decode('utf-8')

                pages = 1
                if ext == '.pdf':
                    try:
                        from io import BytesIO
                        reader = PdfReader(BytesIO(file_bytes))
                        pages = len(reader.pages)
                    except Exception:
                        pass
                
                total_price = pages * copies * price_per_page

                job_data = {
                    'id': job_id,
                    'filename': file.filename,
                    'copies': copies,
                    'orientation': orientation,
                    'color_mode': color_mode,
                    'paper_size': paper_size,
                    'duplex': duplex,
                    'page_range': page_range,
                    'pages_per_sheet': pages_per_sheet,
                    'total_price': total_price,
                    'file_data': file_base64,
                    'timestamp': time.strftime('%Y-%m-%d %H:%M:%S')
                }

                PRINT_JOBS.append(job_data)

    return jsonify({'success': True, 'message': 'Print job queued successfully!'})

@app.route('/get-pending-jobs', methods=['GET'])
def get_pending_jobs():
    global last_heartbeat_time
    last_heartbeat_time = time.time()
    return jsonify({'jobs': PRINT_JOBS})

@app.route('/printer-status', methods=['GET'])
def printer_status():
    global last_heartbeat_time
    current_time = time.time()
    is_online = len(connected_printers) > 0 or ((current_time - last_heartbeat_time) < 15 if last_heartbeat_time > 0 else False)
    return jsonify({'online': is_online})

# Fixed route decorators with proper  parameter
@app.route('/complete-job/', methods=['POST'])
@app.route('/complete-job//', methods=['POST'])
def complete_job(job_id):
    global PRINT_JOBS
    job = next((j for j in PRINT_JOBS if j['id'] == job_id), None)
    if job:
        PRINT_JOBS = [j for j in PRINT_JOBS if j['id'] != job_id]
        history = load_history()
        history.insert(0, job)
        save_history(history)
        return jsonify({'success': True})
    return jsonify({'error': 'Job not found'}), 404

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
