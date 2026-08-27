import os
import time
import queue
import threading
import tempfile
from flask import Flask, render_template_string, request, jsonify
from PyPDF2 import PdfReader, PdfWriter

try:
    import win32api
    import win32print
    HAS_WIN32 = True
except ImportError:
    HAS_WIN32 = False

app = Flask(__name__)
TARGET_PRINTER = None

# Background Print Queue
print_queue = queue.Queue()

def print_worker():
    while True:
        job = print_queue.get()
        if job is None:
            break
        
        file_path, copies = job
        try:
            if HAS_WIN32:
                printer = TARGET_PRINTER if TARGET_PRINTER else win32print.GetDefaultPrinter()
                for _ in range(copies):
                    win32api.ShellExecute(0, "print", file_path, f'/d:"{printer}"', ".", 0)
                    time.sleep(1)
            else:
                print(f"[MOCK PRINT] File: {file_path} | Copies: {copies}")
        except Exception as e:
            print(f"Print job error: {e}")
        finally:
            if os.path.exists(file_path):
                try:
                    os.remove(file_path)
                except Exception:
                    pass
            print_queue.task_done()

threading.Thread(target=print_worker, daemon=True).start()

KIOSK_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>CampusPrint Kiosk</title>
    <link href="https://fonts.googleapis.com/css2?family=Poppins:wght@400;500;600;700&display=swap" rel="stylesheet">
    <script src="https://checkout.razorpay.com/v1/checkout.js"></script>
    <style>
        * { box-sizing: border-box; margin: 0; padding: 0; font-family: 'Poppins', sans-serif; }
        body { background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); min-height: 100vh; display: flex; align-items: center; justify-content: center; padding: 20px; }
        .card { background: #ffffff; width: 100%; max-width: 500px; padding: 35px 30px; border-radius: 16px; box-shadow: 0 15px 35px rgba(0,0,0,0.2); }
        .header { text-align: center; margin-bottom: 25px; }
        .header h2 { font-size: 26px; color: #2d3748; font-weight: 700; }
        .header p { color: #718096; font-size: 14px; margin-top: 4px; }
        .form-group { margin-bottom: 18px; }
        .form-group label { display: block; font-size: 14px; font-weight: 600; color: #4a5568; margin-bottom: 8px; }
        .input-control { width: 100%; padding: 12px 14px; font-size: 14px; border: 2px solid #e2e8f0; border-radius: 10px; outline: none; transition: 0.3s; }
        .input-control:focus { border-color: #667eea; box-shadow: 0 0 0 3px rgba(102,126,234,0.15); }
        input[type="file"] { background: #f7fafc; cursor: pointer; }
        .price-summary { background: #f7fafc; border: 1px dashed #cbd5e0; border-radius: 12px; padding: 15px; text-align: center; margin: 20px 0; }
        .price-summary span { font-size: 18px; font-weight: 700; color: #2d3748; }
        .btn-pay { width: 100%; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; border: none; padding: 14px; font-size: 16px; font-weight: 600; border-radius: 10px; cursor: pointer; transition: 0.3s; box-shadow: 0 4px 12px rgba(118,75,162,0.3); }
        .btn-pay:hover { opacity: 0.95; transform: translateY(-1px); }
    </style>
</head>
<body>

<div class="card">
    <div class="header">
        <h2>CampusPrint Kiosk</h2>
        <p>Instant Smart Document Printing</p>
    </div>
    
    <form id="printForm">
        <div class="form-group">
            <label>Select Document(s)</label>
            <input type="file" id="fileInput" class="input-control" name="files" multiple required>
        </div>
        
        <div class="form-group">
            <label>Number of Copies</label>
            <input type="number" id="copies" class="input-control" name="copies" value="1" min="1" required>
        </div>

        <div class="form-group">
            <label>Page Range</label>
            <input type="text" id="pageRange" class="input-control" name="range" placeholder="e.g. 1-3, 5 (Leave blank for All)">
        </div>

        <div class="price-summary">
            Pages: <span id="totalPages">0</span> | Total: <span style="color:#667eea;">₹<span id="totalCost">0</span></span>
        </div>

        <button type="submit" id="payBtn" class="btn-pay">Pay & Print</button>
    </form>
</div>

<script>
    const fileInput = document.getElementById('fileInput');
    const copiesInput = document.getElementById('copies');
    const totalPagesSpan = document.getElementById('totalPages');
    const totalCostSpan = document.getElementById('totalCost');
    const PRICE_PER_PAGE = 2;

    async function updatePrice() {
        const files = fileInput.files;
        if (files.length === 0) {
            totalPagesSpan.innerText = "0";
            totalCostSpan.innerText = "0";
            return;
        }

        const formData = new FormData();
        for (let file of files) {
            formData.append('files', file);
        }

        try {
            const response = await fetch('/count-multiple-pages', { method: 'POST', body: formData });
            const data = await response.json();
            const totalPages = data.total_pages * parseInt(copiesInput.value || 1);
            totalPagesSpan.innerText = totalPages;
            totalCostSpan.innerText = totalPages * PRICE_PER_PAGE;
        } catch (err) {
            console.error(err);
        }
    }

    fileInput.addEventListener('change', updatePrice);
    copiesInput.addEventListener('input', updatePrice);

    document.getElementById('printForm').addEventListener('submit', async function(e) {
        e.preventDefault();
        
        const files = fileInput.files;
        if (files.length === 0) return alert("Please select files!");

        const formData = new FormData();
        for (let file of files) {
            formData.append('files', file);
        }
        formData.append('copies', copiesInput.value);
        formData.append('range', document.getElementById('pageRange').value);

        const res = await fetch('/print-multiple', { method: 'POST', body: formData });
        const result = await res.json();
        
        if (result.success) {
            alert("Print job queued successfully!");
        } else {
            alert("Print failed: " + result.error);
        }
    });
</script>

</body>
</html>
"""

def parse_range_string(range_str, total_pages):
    if not range_str or range_str.strip() == "" or range_str.lower() == "all":
        return set(range(total_pages))
    
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
    return pages if pages else set(range(total_pages))

@app.route('/')
def index():
    return render_template_string(KIOSK_HTML)

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
        page_range_str = request.form.get('range', '')

        for file in files:
            filename = file.filename.lower()
            temp_dir = tempfile.gettempdir()
            temp_input = os.path.join(temp_dir, f"raw_{file.filename}")
            file.save(temp_input)

            if filename.endswith('.pdf') and page_range_str:
                reader = PdfReader(temp_input)
                total_p = len(reader.pages)
                target_indices = parse_range_string(page_range_str, total_p)
                
                writer = PdfWriter()
                for idx in sorted(target_indices):
                    writer.add_page(reader.pages[idx])
                
                final_print_path = os.path.join(temp_dir, f"queue_{file.filename}")
                with open(final_print_path, "wb") as f_out:
                    writer.write(f_out)
                
                if os.path.exists(temp_input):
                    os.remove(temp_input)
            else:
                final_print_path = temp_input

            print_queue.put((final_print_path, copies))

        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
