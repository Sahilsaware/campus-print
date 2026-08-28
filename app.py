import os
import sys
import tempfile
import threading
from flask import Flask, render_template, request, jsonify
from pypdf import PdfReader

win32api = None
win32print = None
if sys.platform == "win32":
    try:
        import win32api
        import win32print
    except ImportError:
        pass

app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 50 * 1024 * 1024

# Printer Concurrency Lock (Queue System to prevent mixing documents)
printer_lock = threading.Lock()

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/count-multiple-pages', methods=['POST'])
def count_multiple_pages():
    if 'files' not in request.files:
        return jsonify({'error': 'No files uploaded'}), 400

    files = request.files.getlist('files')
    total_pages = 0

    for file in files:
        filename = file.filename.lower()
        if filename.endswith('.pdf'):
            try:
                reader = PdfReader(file)
                total_pages += len(reader.pages)
            except Exception as e:
                return jsonify({'error': f'Failed to process PDF {file.filename}: {str(e)}'}), 400
        elif filename.endswith(('.png', '.jpg', '.jpeg', '.doc', '.docx', '.ppt', '.pptx')):
            total_pages += 1
        else:
            return jsonify({'error': f'Unsupported file type: {file.filename}'}), 400

    return jsonify({'total_pages': total_pages})

@app.route('/print-multiple', methods=['POST'])
def print_multiple():
    if 'files' not in request.files:
        return jsonify({'error': 'No files provided'}), 400

    files = request.files.getlist('files')
    copies = int(request.form.get('copies', 1))

    # Acquire lock so print jobs are processed sequentially (FIFO Queue)
    with printer_lock:
        if sys.platform != "win32" or not win32print:
            return jsonify({'success': True, 'message': 'Simulated print success (Cloud/Non-Windows platform)'})

        try:
            printer_name = win32print.GetDefaultPrinter()
            temp_dir = tempfile.gettempdir()

            for file in files:
                temp_path = os.path.join(temp_dir, file.filename)
                file.save(temp_path)

                for _ in range(copies):
                    win32api.ShellExecute(
                        0,
                        "print",
                        temp_path,
                        f'/d:"{printer_name}"',
                        ".",
                        0
                    )

            return jsonify({'success': True, 'message': 'Print job sent successfully!'})
        except Exception as e:
            return jsonify({'error': f'Printing failed: {str(e)}'}), 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 10000))
    app.run(host='0.0.0.0', port=port)
