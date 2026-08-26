import os
import tempfile
import urllib.parse
from flask import Flask, render_template_string, request, jsonify
from PyPDF2 import PdfReader

try:
    import win32api
    import win32print
except ImportError:
    win32api = None
    win32print = None

app = Flask(__name__)

YOUR_UPI_ID = "9324557708@ptyes"
YOUR_NAME = "CampusPrint Kiosk"
TARGET_PRINTER = None  

KIOSK_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>CampusPrint Kiosk Machine</title>
    <style>
        :root { --primary: #2563eb; --success: #16a34a; --bg: #0f172a; --card-bg: #1e293b; --text: #f8fafc; }
        body { font-family: 'Segoe UI', Arial, sans-serif; background: var(--bg); color: var(--text); margin: 0; display: flex; justify-content: center; align-items: center; min-height: 100vh; }
        .kiosk-box { background: var(--card-bg); width: 90%; max-width: 500px; padding: 25px; border-radius: 24px; box-shadow: 0 20px 50px rgba(0,0,0,0.5); border: 1px solid #334155; text-align: center; position: relative; }
        .logo { font-size: 28px; font-weight: 800; color: #38bdf8; margin: 0 0 5px 0; }
        .sub { color: #94a3b8; font-size: 14px; margin-bottom: 20px; }
        .step-container { display: none; }
        .step-container.active { display: block; }
        
        .nav-header { display: flex; align-items: center; justify-content: space-between; margin-bottom: 15px; }
        .back-btn { background: #334155; color: white; border: none; padding: 8px 16px; border-radius: 8px; cursor: pointer; font-weight: bold; }
        
        .big-btn { background: var(--primary); color: white; border: none; padding: 16px; font-size: 18px; font-weight: 700; border-radius: 14px; width: 100%; cursor: pointer; margin-top: 15px; }
        .option-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; margin: 15px 0; }
        .option-card { background: #334155; padding: 15px; border-radius: 14px; cursor: pointer; border: 2px solid transparent; text-align: center; }
        .option-card.selected { border-color: #38bdf8; background: #0f172a; }

        .setting-group { text-align: left; margin: 12px 0; }
        .setting-group label { display: block; font-size: 13px; color: #94a3b8; margin-bottom: 5px; }
        .setting-group select, .setting-group input { width: 100%; padding: 10px; border-radius: 8px; background: #0f172a; border: 1px solid #334155; color: white; box-sizing: border-box; }

        .upload-area { border: 2px dashed #475569; padding: 25px; border-radius: 16px; margin: 15px 0; cursor: pointer; background: #0f172a; display: block; }
        .price-summary { background: #0f172a; padding: 15px; border-radius: 12px; text-align: left; margin: 15px 0; }
        .qr-img { background: white; padding: 10px; border-radius: 12px; width: 200px; height: 200px; margin: 10px auto; }
        .file-item { background: #334155; padding: 8px 12px; border-radius: 6px; font-size: 12px; margin-bottom: 5px; text-align: left; }
    </style>
</head>
<body>

    <div class="kiosk-box">
        <!-- STEP 1: WELCOME SCREEN -->
        <div class="step-container active" id="step1">
            <h1 class="logo">CampusPrint 🖨️</h1>
            <p class="sub">Self-Service Instant Printing Kiosk</p>
            <div style="font-size: 60px; margin: 25px 0;">📄</div>
            <button class="big-btn" onclick="goToStep(2)">+ START PRINTING</button>
        </div>

        <!-- STEP 2: PRINT OPTIONS -->
        <div class="step-container" id="step2">
            <div class="nav-header">
                <button class="back-btn" onclick="goToStep(1)">← Back</button>
                <h3 style="margin:0;">Print Settings</h3>
                <div></div>
            </div>

            <div class="option-grid">
                <div class="option-card selected" id="optBW" onclick="selectColorMode('BW', 2)">
                    <h4 style="margin:0;">Black & White</h4>
                    <span style="color:#38bdf8;">₹2 / page</span>
                </div>
                <div class="option-card" id="optColor" onclick="selectColorMode('Color', 10)">
                    <h4 style="margin:0;">Color</h4>
                    <span style="color:#38bdf8;">₹10 / page</span>
                </div>
            </div>

            <div class="setting-group">
                <label>Print Sides:</label>
                <select id="printSides" onchange="calculateTotal()">
                    <option value="single">Single-Sided (One Side)</option>
                    <option value="double">Double-Sided (Both Sides - 20% Off)</option>
                </select>
            </div>

            <div class="setting-group">
                <label>Copies (Quantity):</label>
                <input type="number" id="copyCount" value="1" min="1" onchange="calculateTotal()">
            </div>

            <button class="big-btn" onclick="goToStep(3)">Next: Select Files ➔</button>
        </div>

        <!-- STEP 3: UPLOAD & PAGE SELECTION -->
        <div class="step-container" id="step3">
            <div class="nav-header">
                <button class="back-btn" onclick="goToStep(2)">⬅ Back</button>
                <h3 style="margin:0;">Upload & Range</h3>
                <div></div>
            </div>

            <label class="upload-area" for="fileInput">
                <div style="font-size: 35px;">📁</div>
                <p style="margin: 5px 0 0 0; font-size: 13px; color: #94a3b8;">Tap to Select Multiple PDFs / Photos</p>
            </label>
            <input type="file" id="fileInput" accept="application/pdf,image/*" multiple style="display:none;" onchange="handleMultipleFiles()">
            
            <div id="fileListContainer"></div>

            <div class="setting-group" id="pageRangeBox" style="display:none;">
                <label>Page Range (e.g. 1-5, 2, 4 or Leave blank for All):</label>
                <input type="text" id="pageRange" placeholder="All pages" oninput="calculateTotal()">
            </div>

            <div class="price-summary" id="priceSummaryBox" style="display:none;">
                <p style="margin:4px 0;">Total Document Pages: <strong id="docPagesText">0</strong></p>
                <p style="margin:4px 0;">Selected Pages to Print: <strong id="totalPagesText">0</strong></p>
                <p style="margin:4px 0;">Copies: <strong id="copiesSummaryText">1</strong></p>
                <hr style="border-color:#334155;">
                <p style="margin:4px 0; font-size: 18px; color:#22c55e;">Total Amount: <strong>₹<span id="finalAmountText">0</span></strong></p>
            </div>

            <button class="big-btn" id="proceedToPayBtn" style="display:none;" onclick="generatePayment()">Scan & Pay ➔</button>
        </div>

        <!-- STEP 4: SCANNER SCREEN -->
        <div class="step-container" id="step4">
            <div class="nav-header">
                <button class="back-btn" onclick="goToStep(3)">⬅ Back</button>
                <h3 style="margin:0;">Scan UPI QR Code</h3>
                <div></div>
            </div>
            
            <p style="font-size: 14px; color: #94a3b8; margin: 5px 0;">Scan using GPay, PhonePe, Paytm or any UPI App</p>
            
            <img id="upiQrCode" class="qr-img" src="" alt="UPI QR Code">
            
            <h2 style="color: #38bdf8; margin: 10px 0;">Amount: ₹<span id="payAmountText">0</span></h2>
            
            <button class="big-btn" style="background: var(--success);" onclick="confirmPaymentAndPrint()">I Have Paid - Start Printing 🖨️</button>
        </div>

        <!-- STEP 5: SUCCESS -->
        <div class="step-container" id="step5">
            <div style="font-size: 50px; color: #22c55e;">✅</div>
            <h2 style="color: #22c55e; margin: 10px 0;">Printing In Progress!</h2>
            <p style="font-size: 15px; color: #94a3b8; line-height: 1.4;">Please collect your printed documents from the output tray below. 📥</p>
            <button class="big-btn" onclick="resetKiosk()">Done / Next Student</button>
        </div>
    </div>

    <script>
        let selectedColorMode = 'BW';
        let baseRate = 2;
        let selectedFilesArr = [];
        let totalDocPages = 0;
        let finalCost = 0;

        function goToStep(stepNum) {
            document.querySelectorAll('.step-container').forEach(el => el.classList.remove('active'));
            document.getElementById('step' + stepNum).classList.add('active');
        }

        function selectColorMode(mode, rate) {
            selectedColorMode = mode;
            baseRate = rate;
            document.getElementById('optBW').classList.toggle('selected', mode === 'BW');
            document.getElementById('optColor').classList.toggle('selected', mode === 'Color');
            calculateTotal();
        }

        async function handleMultipleFiles() {
            const input = document.getElementById('fileInput');
            if(!input.files.length) return;

            selectedFilesArr = Array.from(input.files);
            const fileListContainer = document.getElementById('fileListContainer');
            fileListContainer.innerHTML = "";

            const formData = new FormData();
            selectedFilesArr.forEach(file => {
                formData.append('files', file);
                fileListContainer.innerHTML += `<div class="file-item">📄 ${file.name}</div>`;
            });

            const res = await fetch('/count-multiple-pages', { method: 'POST', body: formData });
            const data = await res.json();
            
            totalDocPages = data.total_pages || selectedFilesArr.length;

            document.getElementById('pageRangeBox').style.display = 'block';
            document.getElementById('priceSummaryBox').style.display = 'block';
            document.getElementById('proceedToPayBtn').style.display = 'block';

            calculateTotal();
        }

        function parsePageRange(rangeStr, maxPages) {
            if (!rangeStr || rangeStr.trim() === "" || rangeStr.toLowerCase() === "all") {
                return maxPages;
            }
            let pages = new Set();
            let parts = rangeStr.split(',');
            parts.forEach(part => {
                part = part.trim();
                if (part.includes('-')) {
                    let [start, end] = part.split('-').map(num => parseInt(num.trim()));
                    if (start && end) {
                        for (let i = start; i <= end; i++) {
                            if (i >= 1 && i <= maxPages) pages.add(i);
                        }
                    }
                } else {
                    let p = parseInt(part);
                    if (p && p >= 1 && p <= maxPages) pages.add(p);
                }
            });
            return pages.size > 0 ? pages.size : maxPages;
        }

        function calculateTotal() {
            if(!selectedFilesArr.length) return;

            let copies = parseInt(document.getElementById('copyCount').value) || 1;
            let sides = document.getElementById('printSides').value;
            let rangeInput = document.getElementById('pageRange').value;

            let pagesToPrint = parsePageRange(rangeInput, totalDocPages);

            let ratePerPage = baseRate;
            if(sides === 'double') ratePerPage = baseRate * 0.8;

            finalCost = Math.ceil(pagesToPrint * ratePerPage * copies);

            document.getElementById('docPagesText').innerText = totalDocPages;
            document.getElementById('totalPagesText').innerText = pagesToPrint;
            document.getElementById('copiesSummaryText').innerText = copies;
            document.getElementById('finalAmountText').innerText = finalCost;
        }

        async function generatePayment() {
            if (finalCost <= 0) finalCost = 2;
            document.getElementById('payAmountText').innerText = finalCost;
            
            const res = await fetch(`/get-upi-qr?amount=${finalCost}`);
            const data = await res.json();
            document.getElementById('upiQrCode').src = data.qr;
            goToStep(4);
        }

        async function confirmPaymentAndPrint() {
            const formData = new FormData();
            selectedFilesArr.forEach(file => formData.append('files', file));
            formData.append('copies', document.getElementById('copyCount').value);
            formData.append('range', document.getElementById('pageRange').value);

            const res = await fetch('/print-multiple', { method: 'POST', body: formData });
            const data = await res.json();

            if(data.success) {
                goToStep(5);
            } else {
                alert("Print Alert: " + data.error);
                goToStep(5);
            }
        }

        function resetKiosk() {
            selectedFilesArr = [];
            totalDocPages = 0;
            document.getElementById('fileInput').value = "";
            document.getElementById('pageRange').value = "";
            document.getElementById('fileListContainer').innerHTML = "";
            document.getElementById('pageRangeBox').style.display = 'none';
            document.getElementById('priceSummaryBox').style.display = 'none';
            document.getElementById('proceedToPayBtn').style.display = 'none';
            goToStep(1);
        }
    </script>
</body>
</html>
"""

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
            except:
                total_pages += 1
        else:
            total_pages += 1
    return jsonify({'total_pages': total_pages})

@app.route('/get-upi-qr', methods=['GET'])
def get_upi_qr():
    amount = request.args.get('amount', '2')
    upi_url = f"upi://pay?pa={YOUR_UPI_ID}&pn={urllib.parse.quote(YOUR_NAME)}&am={amount}&cu=INR"
    qr_api_url = f"https://api.qrserver.com/v1/create-qr-code/?size=250x250&data={urllib.parse.quote(upi_url)}"
    return jsonify({'qr': qr_api_url})

@app.route('/print-multiple', methods=['POST'])
def print_multiple():
    try:
        files = request.files.getlist('files')
        copies = int(request.form.get('copies', 1))

        if win32print and win32api:
            printer = TARGET_PRINTER if TARGET_PRINTER else win32print.GetDefaultPrinter()
            for file in files:
                temp_path = os.path.join(tempfile.gettempdir(), f"job_{file.filename}")
                file.save(temp_path)
                for _ in range(copies):
                    win32api.ShellExecute(0, "print", temp_path, f'/d:"{printer}"', ".", 0)
            return jsonify({'success': True})
        else:
            return jsonify({'success': True, 'error': 'Server mode: Printing bypassed successfully!'})
            
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
