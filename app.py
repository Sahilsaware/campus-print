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

# Background Print Queue Setup
print_queue = queue.Queue()

def print_worker():
    """Background thread jo multi-user queue ko step-by-step execute aur clean karta hai."""
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
                    time.sleep(1) # Spooler stability buffer
            else:
                print(f"[MOCK PRINT] File: {file_path} | Copies: {copies}")
        except Exception as e:
            print(f"Print job error: {e}")
        finally:
            # Auto-Delete after printing
            if os.path.exists(file_path):
                try:
                    os.remove(file_path)
                except Exception:
                    pass
            print_queue.task_done()

# Worker thread launch
threading.Thread(target=print_worker, daemon=True).start()

KIOSK_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>CampusPrint Kiosk</title>
    <style>
        body { font-family: Arial, sans-serif; margin: 40px; background-color: #f4f4f9; }
        .container { max-width: 600px; background: #fff; padding: 25px; border-radius: 8px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); margin: 0 auto; }
        h2 { text-align: center; color: #333; }
        .form-group { margin-bottom: 15px; }
        label { display: block; margin-bottom: 5px; font-weight: bold; }
        input[type="file"], input[type="number"], input[type="text"] { width: 100%; padding: 8px; box-sizing: border-box; }
        button { width: 100%; padding: 12px; background: #28a745; color: white; border: none; font-size: 16px; border-radius: 5px; cursor: pointer; margin-top: 10px; }
        button:hover { background: #218838; }
        .price-box { margin-top: 15px; padding: 10px; background: #e9ecef; border-radius: 5px; text-align: center; font-size: 18px; font-weight: bold; }
    </style>
</head>
<body>

<div class="container">
    <h2>CampusPrint Kiosk</h2>
    <form id="printForm">
        <div class="form-group">
            <label>Select Document(s):</label>
            <input type="file" id="fileInput" name="files" multiple required>
        </div>
        
        <div class="form-group">
            <label>Copies:</label>
            <input type="number" id="copies" name="copies" value="1" min="1" required>
        </div>

        <div class="form-group">
            <label>Page Range (e.g., "1-3, 5" or leave blank for All):</label>
            <input type="text" id="pageRange" name="range" placeholder="e.g. 1-5">
        </div>

        <div class="price-box">
            Total Pages: <span id="totalPages">0</span> | Price: ₹<span id="totalCost">0</span>
        </div>

        <button type="submit" id="payBtn">Print Document</button>
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
                
                # Raw file clear karo after slicing
                if os.path.exists(temp_input):
                    os.remove(temp_input)
            else:
                final_print_path = temp_input

            # Queue me add karo background thread handling ke liye
            print_queue.put((final_print_path, copies))

        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
