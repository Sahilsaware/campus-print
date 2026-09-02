import os
import uuid
import time
from flask import Flask, request, jsonify, render_template, send_from_directory
from flask_cors import CORS
from pypdf import PdfReader

app = Flask(__name__)
CORS(app)

UPLOAD_FOLDER = 'uploads'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# In-memory print queue and heartbeat tracker
PRINT_JOBS = []
LAST_PRINTER_HEARTBEAT = 0  # Timestamp in seconds

@app.route('/')
def home():
    return render_template('index.html')

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

# 2. Printer Status / Heartbeat Check Endpoint
@app.route('/printer-status', methods=['GET'])
def printer_status():
    global LAST_PRINTER_HEARTBEAT
    current_time = time.time()
    # If last poll was within 15 seconds, consider printer ONLINE
    is_online = (current_time - LAST_PRINTER_HEARTBEAT) <= 15
    return jsonify({'online': is_online, 'last_seen': int(current_time - LAST_PRINTER_HEARTBEAT)})

# 3. Direct Print Endpoint
@app.route('/print-multiple', methods=['POST'])
def print_multiple():
    if 'files' not in request.files:
        return jsonify({'error': 'No files uploaded'}), 400

    copies = int(request.form.get('copies', 1))
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
                    'copies': copies
                })
            else:
                return jsonify({'error': f'Unsupported file format: {file.filename}'}), 400

    return jsonify({'success': True, 'message': 'Print job queued successfully!'})

# 4. Local Script Polling Endpoint (Updates Heartbeat)
@app.route('/get-pending-jobs', methods=['GET'])
def get_pending_jobs():
    global LAST_PRINTER_HEARTBEAT
    LAST_PRINTER_HEARTBEAT = time.time()
    return jsonify({'jobs': PRINT_JOBS})

# 5. Download File Endpoint for Local PC
@app.route('/uploads/<filename>', methods=['GET'])
def download_file(filename):
    return send_from_directory(UPLOAD_FOLDER, filename)

# 6. Job Complete & Cleanup Endpoint
@app.route('/complete-job/<job_id>', methods=['POST'])
def complete_job(job_id):
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
