import os
import subprocess
from flask import Flask, request, jsonify, render_template
from flask_cors import CORS
from pypdf import PdfReader
from io import BytesIO

app = Flask(__name__)
CORS(app)

UPLOAD_FOLDER = 'uploads'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

@app.route('/')
def home():
    return render_template('index.html')

# 1. Page Counter Endpoint
@app.route('/count-multiple-pages', methods=['POST'])
def count_multiple_pages():
    if 'files' not in request.files:
        return jsonify({'error': 'No files uploaded'}), 400

    files = request.files.getlist('files')
    total_pages = 0

    for file in files:
        if file.filename != '':
            file_ext = os.path.splitext(file.filename)[1].lower()
            
            try:
                if file_ext == '.pdf':
                    file_stream = BytesIO(file.read())
                    reader = PdfReader(file_stream)
                    total_pages += len(reader.pages)
                    file.stream.seek(0)
                else:
                    total_pages += 1
            except Exception:
                total_pages += 1

    return jsonify({'total_pages': total_pages})

# 2. Pre-Payment Printer Status Check Endpoint
@app.route('/check-printer', methods=['GET'])
def check_printer():
    try:
        status_check = subprocess.run(
            'powershell -Command "(Get-CimInstance Win32_Printer | Where-Object {$_.Default -eq $true}).WorkOffline"',
            capture_output=True, text=True, shell=True
        )
        if 'True' in status_check.stdout:
            return jsonify({'error': 'Printer is currently offline, disconnected, or out of paper.'}), 400
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# 3. Print Endpoint (Copy Limit + Windows Print + Auto Cleanup)
@app.route('/print-multiple', methods=['POST'])
def print_multiple():
    if 'files' not in request.files:
        return jsonify({'error': 'No files uploaded'}), 400

    # Validation: Copies limit (Max 100)
    try:
        copies = int(request.form.get('copies', 1))
        if copies < 1 or copies > 100:
            return jsonify({'error': 'Invalid copies! Max 100 copies allowed per print.'}), 400
    except ValueError:
        return jsonify({'error': 'Invalid copy count format'}), 400

    files = request.files.getlist('files')

    try:
        for file in files:
            if file.filename != '':
                filepath = os.path.join(UPLOAD_FOLDER, file.filename)
                file.save(filepath)

                file_ext = os.path.splitext(file.filename)[1].lower()
                abs_path = os.path.abspath(filepath).replace('\\', '/')
                
                if file_ext in ['.pdf', '.png', '.jpg', '.jpeg', '.docx', '.pptx', '.doc']:
                    for _ in range(copies):
                        subprocess.run(f'powershell -Command "Start-Process -FilePath \'{abs_path}\' -Verb Print"', shell=True)
                    
                    try:
                        os.remove(filepath)
                    except:
                        pass
                else:
                    return jsonify({'error': f'Unsupported file format: {file.filename}'}), 400

        return jsonify({'success': True, 'message': 'Print jobs sent successfully'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
