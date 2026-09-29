import os
import fitz  # PyMuPDF
from flask import Flask, render_template, request, jsonify
from flask_cors import CORS
from werkzeug.utils import secure_filename

app = Flask(__name__)
CORS(app)

UPLOAD_FOLDER = 'uploads'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

ALLOWED_EXTENSIONS = {'pdf', 'png', 'jpg', 'jpeg', 'doc', 'docx', 'ppt', 'pptx'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def convert_to_pdf(input_path, file_extension):
    if file_extension in ['doc', 'docx', 'ppt', 'pptx']:
        output_dir = app.config['UPLOAD_FOLDER']
        # LibreOffice headless command to convert docs to PDF
        os.system(f'libreoffice --headless --convert-to pdf "{input_path}" --outdir "{output_dir}"')
        base_name = os.path.splitext(os.path.basename(input_path))[0]
        return os.path.join(output_dir, f"{base_name}.pdf")
    return input_path

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/upload', methods=['POST'])
def upload_file():
    if 'file' not in request.files:
        return jsonify({'error': 'No file part'}), 400
    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'No selected file'}), 400
    
    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(file_path)
        
        ext = filename.rsplit('.', 1)[1].lower()
        pdf_path = convert_to_pdf(file_path, ext)
        
        # Count pages using PyMuPDF (fitz)
        doc = fitz.open(pdf_path)
        total_pages = len(doc)
        doc.close()
        
        return jsonify({
            'success': True,
            'filename': filename,
            'total_pages': total_pages,
            'pdf_path': pdf_path
        })
    
    return jsonify({'error': 'Invalid file format'}), 400

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
