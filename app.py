import os
import time
import queue
import threading
import tempfile
import uuid
from flask import Flask, render_template, request, jsonify
from PyPDF2 import PdfReader, PdfWriter

app = Flask(__name__)
print_queue = queue.Queue()

def parse_range_string(range_str, total_pages):
    """Parses range strings like '1-3, 5' into zero-based indices"""
    if not range_str or range_str.strip().lower() in ["", "all"]:
        return list(range(total_pages))
    
    pages = set()
    parts = range_str.split(',')
    for part in parts:
        part = part.strip()
        if '-' in part:
            try:
                start, end = map(int, part.split('-'))
                for p in range(start, end + 1):
                    if 1 <= p <= total_pages:
                        pages.add(p - 1)
            except ValueError:
                continue
        else:
            try:
                p = int(part)
                if 1 <= p <= total_pages:
                    pages.add(p - 1)
            except ValueError:
                continue
    return sorted(list(pages)) if pages else list(range(total_pages))

def slice_pdf(input_path, output_path, page_range_str):
    """Slices PDF safely"""
    reader = PdfReader(input_path)
    total_pages = len(reader.pages)
    selected_indices = parse_range_string(page_range_str, total_pages)
    
    writer = PdfWriter()
    for idx in selected_indices:
        writer.add_page(reader.pages[idx])
        
    with open(output_path, "wb") as f_out:
        writer.write(f_out)

def print_worker():
    while True:
        job = print_queue.get()
        if job is None:
            break
        file_path, copies = job
        print(f"[Render Processing Job] File: {file_path} | Copies: {copies}")
        
        # Temp File Cleanup
        if os.path.exists(file_path):
            time.sleep(2)
            try:
                os.remove(file_path)
            except Exception as e:
                print(f"Cleanup error: {e}")
        print_queue.task_done()

threading.Thread(target=print_worker, daemon=True).start()

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/count-multiple-pages', methods=['POST'])
def count_multiple_pages():
    files = request.files.getlist('files')
    total_pages = 0
    for file in files:
        if file.filename.lower().endswith('.pdf'):
            try:
                reader = PdfReader(file)
                total_pages += len(reader.pages)
            except Exception:
                total_pages += 1
        else:
            total_pages += 1
    return jsonify({'total_pages': total_pages})

@app.route('/print-multiple', methods=['POST'])
def print_multiple():
    try:
        files = request.files.getlist('files')
        copies = int(request.form.get('copies', 1))
        page_range = request.form.get('range', '')

        for file in files:
            file_id = str(uuid.uuid4())
            raw_path = os.path.join(tempfile.gettempdir(), f"raw_{file_id}_{file.filename}")
            file.save(raw_path)

            if file.filename.lower().endswith('.pdf') and page_range.strip():
                sliced_path = os.path.join(tempfile.gettempdir(), f"job_{file_id}_{file.filename}")
                slice_pdf(raw_path, sliced_path, page_range)
                os.remove(raw_path)
                final_print_path = sliced_path
            else:
                final_print_path = raw_path

            print_queue.put((final_print_path, copies))

        return jsonify({'success': True})
            
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port, debug=True)
