import os
import json
import uuid
import time
import base64
import subprocess
from flask import Flask, request, jsonify, render_template, session, redirect, url_for
from flask_cors import CORS
from pypdf import PdfReader
from flask_sock import Sock

app = Flask(__name__)
CORS(app)
sock = Sock(app)
app.secret_key = 'campus_print_secure_admin_key_2026'

HISTORY_FILE = 'print_history.json'
PENDING_JOBS_FILE = 'pending_jobs.json'
ADMINS_FILE = 'admins.json'
UPLOAD_FOLDER = 'uploads'

os.makedirs(UPLOAD_FOLDER, exist_ok=True)

SUPER_ADMIN_USER = "campus_admin"
SUPER_ADMIN_PASS = "CampusPrint@2026#Secure"

last_heartbeat_time = 0
PI_PRINTER_ONLINE = False

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

def load_pending_jobs():
    if os.path.exists(PENDING_JOBS_FILE):
        try:
            with open(PENDING_JOBS_FILE, 'r') as f:
                return json.load(f)
        except Exception:
            return []
    return []

def save_pending_jobs(jobs):
    with open(PENDING_JOBS_FILE, 'w') as f:
        json.dump(jobs, f, indent=4)

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
    pending_jobs = load_pending_jobs()
    return render_template('admin.html', pending_jobs=pending_jobs, history=history, username=session.get('username'))

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

    pending_jobs = load_pending_jobs()

    for file in files:
        if file.filename != '':
            ext = os.path.splitext(file.filename)[1].lower()
            if ext in ['.pdf', '.png', '.jpg', '.jpeg', '.docx', '.pptx', '.doc']:
                job_id = str(uuid.uuid4())
                file_bytes = file.read()
                
                local_filename = f"{job_id}{ext}"
                local_path = os.path.join(UPLOAD_FOLDER, local_filename)
                with open(local_path, 'wb') as f:
                    f.write(file_bytes)

                print_path = local_path
                if ext in ['.docx', '.doc', '.pptx']:
                    try:
                        subprocess.run(['libreoffice', '--headless', '--convert-to', 'pdf', local_path, '--outdir', UPLOAD_FOLDER], check=True)
                        pdf_filename = f"{job_id}.pdf"
                        converted_pdf_path = os.path.join(UPLOAD_FOLDER, pdf_filename)
                        if os.path.exists(converted_pdf_path):
                            print_path = converted_pdf_path
                    except Exception:
                        pass

                pages = 1
                if print_path.endswith('.pdf'):
                    try:
                        reader = PdfReader(print_path)
                        pages = len(reader.pages)
                    except Exception:
                        pass
                
                total_price = pages * copies * price_per_page

                file_b64 = ""
                if os.path.exists(print_path):
                    with open(print_path, "rb") as pf:
                        file_b64 = base64.b64encode(pf.read()).decode('utf-8')

                job_data = {
                    'id': job_id,
                    'filename': file.filename,
                    'file_data': file_b64,
                    'copies': copies,
                    'orientation': orientation,
                    'color_mode': color_mode,
                    'paper_size': paper_size,
                    'duplex': duplex,
                    'page_range': page_range,
                    'pages_per_sheet': pages_per_sheet,
                    'total_price': total_price,
                    'timestamp': time.strftime('%Y-%m-%d %H:%M:%S'),
                    'status': 'pending'
                }

                pending_jobs.append(job_data)

    save_pending_jobs(pending_jobs)
    return jsonify({'success': True, 'message': 'Print job queued successfully!'})

@app.route('/get-pending-jobs', methods=['GET', 'POST'])
def get_pending_jobs():
    global last_heartbeat_time, PI_PRINTER_ONLINE
    last_heartbeat_time = time.time()
    
    if request.method == 'POST':
        data = request.get_json(silent=True) or {}
        if 'printer_online' in data:
            PI_PRINTER_ONLINE = bool(data['printer_online'])
    
    pending_jobs = load_pending_jobs()
    unlocked_jobs = [j for j in pending_jobs if j.get('status', 'pending') == 'pending']
    
    for j in unlocked_jobs:
        j['status'] = 'processing'
    save_pending_jobs(pending_jobs)
    
    return jsonify({'jobs': unlocked_jobs})

@app.route('/update-status', methods=['POST'])
def update_status():
    global PI_PRINTER_ONLINE, last_heartbeat_time
    last_heartbeat_time = time.time()
    data = request.get_json(silent=True) or {}
    PI_PRINTER_ONLINE = bool(data.get('printer_online', False))
    return jsonify({'success': True})

@app.route('/printer-status', methods=['GET'])
def printer_status():
    global last_heartbeat_time, PI_PRINTER_ONLINE
    
    if time.time() - last_heartbeat_time > 15:
        PI_PRINTER_ONLINE = False
        
    return jsonify({'online': PI_PRINTER_ONLINE})

@app.route('/complete-job/<job_id>', methods=['POST'])
def complete_job(job_id):
    pending_jobs = load_pending_jobs()
    job = next((j for j in pending_jobs if j['id'] == job_id), None)
    if job:
        pending_jobs = [j for j in pending_jobs if j['id'] != job_id]
        save_pending_jobs(pending_jobs)
        history = load_history()
        history.insert(0, job)
        save_history(history)
        return jsonify({'success': True})
    return jsonify({'error': 'Job not found'}), 404

@app.route('/fail-job/<job_id>', methods=['POST'])
def fail_job(job_id):
    pending_jobs = load_pending_jobs()
    for j in pending_jobs:
        if j['id'] == job_id:
            j['status'] = 'failed'
    save_pending_jobs(pending_jobs)
    return jsonify({'success': True})

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
