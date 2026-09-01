import os
from flask import Flask, request, jsonify, render_template
from flask_cors import CORS
from pypdf import PdfReader

app = Flask(__name__)
CORS(app)

UPLOAD_FOLDER = 'uploads'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

@app.route('/')
def home():
    return render_template('index.html')

# 1. Page Counter Endpoint for Frontend
@app.route('/count-multiple-pages', methods=['POST'])
def count_multiple_pages():
    if 'files' not in request.files:
        return jsonify({'error': 'No files uploaded'}), 400

    files = request.files.getlist('files')
    total_pages = 0

    for file in files:
        if file.filename != '':
            filepath = os.path.join(UPLOAD_FOLDER, file.filename)
            file.save(filepath)
            
            try:
                reader = PdfReader(filepath)
                total_pages += len(reader.pages)
            except Exception:
                total_pages += 1

    return jsonify({'total_pages': total_pages})

# 2. Print Endpoint for Frontend
@app.route('/print-multiple', methods=['POST'])
def print_multiple():
    if 'files' not in request.files:
        return jsonify({'error': 'No files uploaded'}), 400

    files = request.files.getlist('files')
    copies = int(request.form.get('copies', 1))

    try:
        for file in files:
            if file.filename != '':
                filepath = os.path.join(UPLOAD_FOLDER, file.filename)
                file.save(filepath)

                for _ in range(copies):
                    os.startfile(filepath, "print")

        return jsonify({'success': True, 'message': 'Print jobs sent successfully'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
