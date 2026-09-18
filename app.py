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
ADMINS_FILE = 'admins.json'
UPLOAD_FOLDER = 'uploads'

os.makedirs(UPLOAD_FOLDER, exist_ok=True)

SUPER_ADMIN_USER = "campus_admin"
SUPER_ADMIN_PASS = "CampusPrint@2026#Secure"

PRINT_JOBS = []
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

def get_default_printer():
    """CUPS se automatically active ya default printer ka naam nikalta hai (Dynamic support)"""
    try:
        result = subprocess.run(['lpstat', '-d'], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        if result.returncode == 0:
            # Output format: "system default destination: Printer_Name"
            parts = result.stdout.strip().split(':')
            if len(parts) > 1:
                return parts[1].strip()
        
        # Agar default set nahi hai, toh pehla available printer utha lo
        result2 = subprocess.run(['lpstat', '-p'], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        if result2.returncode == 0:
            for line in result2.stdout.splitlines():
                if line.startswith('printer'):
                    return line.split()[1]
    except Exception:
        pass
    return None

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
                
                # Save file locally for processing/printing
                local_filename = f"{job_id}{ext}"
                local_path = os.path.join(UPLOAD_FOLDER, local_filename)
                with open(local_path, 'wb') as f:
                    f.write(file_bytes)

                # Convert Word/PPT to PDF automatically using libreoffice if needed
                print_path = local_path
                if ext in ['.docx', '.doc', '.pptx']:
                    try:
                        subprocess.run(['libreoffice', '--headless', '--convert-to', 'pdf', local_path, '--outdir', UPLOAD_FOLDER], check=True)
                        pdf_filename = f"{job_id}.pdf"
                        converted_pdf_path = os.path.join(UPLOAD_FOLDER, pdf_filename)
                        if os.path.exists(converted_pdf_path):
                            print_path = converted_pdf_path
                    except Exception:
                        pass # Fallback to original if conversion tool missing

                pages = 1
                if print_path.endswith('.pdf'):
                    try:
                        reader = PdfReader(print_path)
                        pages = len(reader.pages)
                    except Exception:
                        pass
                
                total_price = pages * copies * price_per_page

                job_data = {
                    'id': job_id,
                    'filename': file.filename,
                    'file_path': print_path,
                    'copies': copies,
                    'orientation': orientation,
                    'color_mode': color_mode,
                    'paper_size': paper_size,
                    'duplex': duplex,
                    'page_range': page_range,
                    'pages_per_sheet': pages_per_sheet,
                    'total_price': total_price,
                    'timestamp': time.strftime('%Y-%m-%d %H:%M:%S')
                }

                # Automatically trigger local print execution if running on the print server/Pi
                execute_local_print(job_data)

                PRINT_JOBS.append(job_data)

    return jsonify({'success': True, 'message': 'Print job processed and sent successfully!'})

def execute_local_print(job):
    """Dynamically finds any available printer and applies exact layout settings (Duplex, Landscape, Copies)"""
    printer_name = get_default_printer()
    if not printer_name:
        return # No printer available to dispatch

    options = []
    
    # 1. Orientation Handling
    if job.get('orientation') == 'landscape':
        options.extend(['-o', 'landscape'])
    else:
        options.extend(['-o', 'portrait'])
        
    # 2. Duplex / Sides Handling
    if job.get('duplex'):
        options.extend(['-o', 'sides=two-sided-long-edge'])
    else:
        options.extend(['-o', 'sides=one-sided'])
        
    # 3. Copies Handling
    copies = job.get('copies', 1)
    options.extend(['-n', str(copies)])

    # 4. Page Range Handling (if specified)
    page_range = job.get('page_range', '').strip()
    if page_range and page_range.lower() != 'all pages':
        options.extend(['-o', f'page-ranges={page_range}'])

    # Execute lp command dynamically
    file_path = job.get('file_path')
    if file_path and os.path.exists(file_path):
        cmd = ['lp', '-d', printer_name] + options + [file_path]
        try:
            subprocess.run(cmd, check=True)
        except Exception:
            pass

@app.route('/get-pending-jobs', methods=['GET', 'POST'])
def get_pending_jobs():
    global last_heartbeat_time, PI_PRINTER_ONLINE
    last_heartbeat_time = time.time()
    
    if request.method == 'POST':
        data = request.get_json(silent=True) or {}
        if 'printer_online' in data:
            PI_PRINTER_ONLINE = bool(data['printer_online'])
    
    return jsonify({'jobs': PRINT_JOBS})

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
