import os
import uuid
from flask import Flask, request, jsonify, render_template, send_from_directory, session, redirect, url_for
from flask_cors import CORS
from pypdf import PdfReader

app = Flask(__name__)
CORS(app)
app.secret_key = 'campus_print_secure_admin_key_2026'

UPLOAD_FOLDER = 'uploads'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# In-memory print queue
PRINT_JOBS = []

# Admin Credentials
ADMIN_USERNAME = "campus_admin"
ADMIN_PASSWORD = "CampusPrint@2026#Secure"

@app.route('/')
def home():
    return render_template('index.html')

# Admin Login Route
@app.route('/admin/login', methods=['GET', 'POST'])
def admin_login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        if username == ADMIN_USERNAME and password == ADMIN_PASSWORD:
            session['admin_logged_in'] = True
            return redirect(url_for('admin_panel'))
        else:
            return render_template('admin_login.html', error='Invalid username or password')
    return render_template('admin_login.html')

# Admin Logout Route
@app.route('/admin/logout')
def admin_logout():
    session.pop('admin_logged_in', None)
    return redirect(url_for('admin_login'))

# Admin Dashboard Route (Protected)
@app.route('/admin')
def admin_panel():
    if not session.get('admin_logged_in'):
        return redirect(url_for('admin_login'))
    return render_template('admin.html')

# 1. Page Count Endpoint
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
                except Exception as e:
                    return jsonify({'error': f'Error reading PDF {file.filename}: {str(e)}'}), 400
            elif ext in ['.png', '.jpg', '.jpeg', '.docx', '.pptx', '.doc']:
                total_pages += 1
            else:
                return jsonify({'error': f'Unsupported file format: {file.filename}'}), 400

    return jsonify({'total_pages': total_pages})

# 2. Direct Print Endpoint
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

    files = request.files.getlist('files')

    for file in files:
        if file.filename != '':
            ext = os.path.splitext(file.filename)[1].lower()
            if ext in ['.pdf', '.png', '.jpg', '.jpeg', '.docx', '.pptx', '.doc']:
                job_id = str(uuid.uuid4())
                filename = f"{job_id}_{file.filename}"
                filepath = os.path.join(UPLOAD_FOLDER, filename)
                file.save(filepath)

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
                    'pages_per_sheet': pages_per_sheet
                })
            else:
                return jsonify({'error': f'Unsupported file format: {file.filename}'}), 400

    return jsonify({'success': True, 'message': 'Print job queued successfully!'})
    
# 3. Local Script Polling Endpoint
@app.route('/get-pending-jobs', methods=['GET'])
def get_pending_jobs():
    return jsonify({'jobs': PRINT_JOBS})

# 4. Download File Endpoint
@app.route('/uploads/<filename>', methods=['GET'])
def download_file(filename):
    return send_from_directory(UPLOAD_FOLDER, filename)

# 5. Job Complete / Delete Endpoint
@app.route('/complete-job/<job_id>', methods=['POST'])
def complete_job(job_id):
    if not session.get('admin_logged_in'):
        return jsonify({'error': 'Unauthorized'}), 401
        
    global PRINT_JOBS
    job = next((j for j in PRINT_JOBS if j['id'] == job_id), None)
    if job:
        filepath = os.path.join(UPLOAD_FOLDER, job['filename'])
        if os.path.exists(filepath):
            os.remove(filepath)
        PRINT_JOBS = [j for j in PRINT_JOBS if j['id'] != job_id]
        return jsonify({'success': True})
    return jsonify({'error': 'Job not found'}), 404

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
