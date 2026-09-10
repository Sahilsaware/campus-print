import os
import json
import uuid
import time
from flask import Flask, request, jsonify, render_template, send_from_directory, session, redirect, url_for
from flask_cors import CORS
from pypdf import PdfReader

app = Flask(__name__)
CORS(app)
app.secret_key = 'campus_print_secure_admin_key_2026'

UPLOAD_FOLDER = 'uploads'
HISTORY_FILE = 'print_history.json'
ADMINS_FILE = 'admins.json'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# Main Super Admin Credentials (Aapka account)
SUPER_ADMIN_USER = "campus_admin"
SUPER_ADMIN_PASS = "CampusPrint@2026#Secure"

# In-memory active queue
PRINT_JOBS = []
last_heartbeat_time = 0

def load_history():
    if os.path.exists(HISTORY_FILE):
        try:
            with open(HISTORY_FILE, 'r') as f:
                return json.load(f)
        except:
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
        except:
            return {}
    return {}

def save_admins(admins):
    with open(ADMINS_FILE, 'w') as f:
        json.dump(admins, f, indent=4)

@app.route('/')
def home():
    return render_template('index.html')

# Admin Login Route
@app.route('/admin/login', methods=['GET', 'POST'])
def admin_login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        # Check Super Admin
        if username == SUPER_ADMIN_USER and password == SUPER_ADMIN_PASS:
            session['admin_logged_in'] = True
            session['username'] = username
            session['role'] = 'Super Admin'
            return redirect(url_for('admin_panel'))
        
        # Check Sub-Admins
        admins = load_admins()
        if username in admins and admins[username]['password'] == password:
            session['admin_logged_in'] = True
            session['username'] = username
            session['role'] = admins[username].get('role', 'Sub-Admin')
            return redirect(url_for('admin_panel'))
        
        return render_template('admin_login.html', error='Invalid username or password')
    return render_template('admin_login.html')

# Admin Logout Route
@app.route('/admin/logout')
def admin_logout():
    session.clear()
    return redirect(url_for('admin_login'))

# Admin Dashboard Route
@app.route('/admin')
def admin_panel():
    if not session.get('admin_logged_in'):
        return redirect(url_for('admin_login'))
    
    history = load_history()
    total_prints = len(history)
    total_copies = sum(job.get('copies', 1) for job in history)
    total_earnings = sum(job.get('total_price', 0) for job in history)
    
    is_super = (session.get('username') == SUPER_ADMIN_USER)
    sub_admins = load_admins() if is_super else {}
    
    return render_template('admin.html', 
                           pending_jobs=PRINT_JOBS, 
                           history=history,
                           total_prints=total_prints,
                           total_copies=total_copies,
                           total_earnings=total_earnings,
                           username=session.get('username'),
                           role=session.get('role'),
                           is_super_admin=is_super,
                           sub_admins=sub_admins)

# Super Admin: Add Sub-Admin
@app.route('/admin/add-admin', methods=['POST'])
def add_admin():
    if not session.get('admin_logged_in') or session.get('username') != SUPER_ADMIN_USER:
        return redirect(url_for('admin_login'))
    
    new_user = request.form.get('new_username')
    new_pass = request.form.get('new_password')
    if new_user and new_pass and new_user != SUPER_ADMIN_USER:
        admins = load_admins()
        admins[new_user] = {'password': new_pass, 'role': 'Sub-Admin'}
        save_admins(admins)
    return redirect(url_for('admin_panel'))

# Super Admin: Delete Sub-Admin
@app.route('/admin/delete-admin/<username>', methods=['POST'])
def delete_admin(username):
    if not session.get('admin_logged_in') or session.get('username') != SUPER_ADMIN_USER:
        return redirect(url_for('admin_login'))
    
    admins = load_admins()
    if username in admins:
        del admins[username]
        save_admins(admins)
    return redirect(url_for('admin_panel'))

# API for Live Stats & Polling
@app.route('/admin/stats', methods=['GET'])
def admin_stats():
    if not session.get('admin_logged_in'):
        return jsonify({'error': 'Unauthorized'}), 401
        
    history = load_history()
    total_prints = len(history)
    total_copies = sum(job.get('copies', 1) for job in history)
    total_earnings = sum(job.get('total_price', 0) for job in history)
    
    return jsonify({
        'pending_count': len(PRINT_JOBS),
        'total_prints': total_prints,
        'total_copies': total_copies,
        'total_earnings': total_earnings
    })

# API for Earnings Breakdown with Monthly Filter
@app.route('/admin/earnings-breakdown', methods=['GET'])
def earnings_breakdown():
    if not session.get('admin_logged_in'):
        return jsonify({'error': 'Unauthorized'}), 401
        
    selected_month = request.args.get('month', '') # Format YYYY-MM
    history = load_history()
    
    filtered_history = []
    for job in history:
        timestamp = job.get('timestamp', '')
        if selected_month:
            if timestamp.startswith(selected_month):
                filtered_history.append(job)
        else:
            filtered_history.append(job)
            
    total_earnings = sum(job.get('total_price', 0) for job in filtered_history)
    total_copies = sum(job.get('copies', 1) for job in filtered_history)
    
    return jsonify({
        'history': filtered_history,
        'total_earnings': total_earnings,
        'total_copies': total_copies,
        'count': len(filtered_history)
    })

# Page Count & Print Queue Endpoints
@app.route('/count-multiple-pages', methods=['POST'])
def count_multiple_pages():
    if 'files' not in request.files:
        return jsonify({'error': 'No files uploaded'}), 400
    files = request.files.getlist('files')
    total_pages = 0
    for file in files:
        if file.filename != '':
            ext = os.path.splitext(file.filename)[1].lower()
            if ext == '.pdf':
                try:
                    reader = PdfReader(file)
                    total_pages += len(reader.pages)
                except:
                    total_pages += 1
            else:
                total_pages += 1
    return jsonify({'total_pages': total_pages})

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
                filename = f"{job_id}_{file.filename}"
                filepath = os.path.join(UPLOAD_FOLDER, filename)
                file.save(filepath)

                pages = 1
                if ext == '.pdf':
                    try:
                        reader = PdfReader(filepath)
                        pages = len(reader.pages)
                    except:
                        pass
                
                total_price = pages * copies * price_per_page

                PRINT_JOBS.append({
                    'id': job_id,
                    'filename': filename,
                    'original_name': file.filename,
                    'copies': copies,
                    'orientation': orientation,
                    'color_mode': color_mode,
                    'paper_size': paper_size,
                    'duplex': duplex,
                    'page_range': page_range,
                    'pages_per_sheet': pages_per_sheet,
                    'total_price': total_price,
                    'timestamp': time.strftime('%Y-%m-%d %H:%M:%S')
                })
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
    is_online = (current_time - last_heartbeat_time) < 15 if last_heartbeat_time > 0 else False
    return jsonify({'online': is_online})

@app.route('/uploads/<filename>', methods=['GET'])
def download_file(filename):
    return send_from_directory(UPLOAD_FOLDER, filename)

@app.route('/complete-job/<job_id>', methods=['POST'])
def complete_job(job_id):
    global PRINT_JOBS
    job = next((j for j in PRINT_JOBS if j['id'] == job_id), None)
    if job:
        filepath = os.path.join(UPLOAD_FOLDER, job['filename'])
        if os.path.exists(filepath):
            os.remove(filepath)
        
        PRINT_JOBS = [j for j in PRINT_JOBS if j['id'] != job_id]
        
        # Save to persistent history file
        history = load_history()
        history.insert(0, job)
        save_history(history)
        
        return jsonify({'success': True})
    return jsonify({'error': 'Job not found'}), 404

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
        
