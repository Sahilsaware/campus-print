import os
import tempfile
from flask import Flask, render_template_string, request, jsonify
from PyPDF2 import PdfReader

try:
    import win32api
    import win32print
except ImportError:
    win32api = None
    win32print = None

app = Flask(__name__)

TARGET_PRINTER = None  

KIOSK_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>CampusPrint - Smart Kiosk</title>
    <!-- Google Fonts -->
    <link href="https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&display=swap" rel="stylesheet">
    <!-- Razorpay Standard Checkout SDK -->
    <script src="https://checkout.razorpay.com/v1/checkout.js"></script>
    <style>
        :root {
            --primary: #3b82f6;
            --primary-glow: rgba(59, 130, 246, 0.35);
            --accent: #10b981;
            --bg-gradient: radial-gradient(circle at top left, #1e1b4b, #0f172a, #020617);
            --card-bg: rgba(30, 41, 59, 0.7);
            --card-border: rgba(255, 255, 255, 0.1);
            --text-main: #f8fafc;
            --text-muted: #94a3b8;
        }

        * {
            box-sizing: border-box;
            margin: 0;
            padding: 0;
            font-family: 'Plus Jakarta Sans', sans-serif;
            -webkit-tap-highlight-color: transparent;
        }

        body {
            background: var(--bg-gradient);
            color: var(--text-main);
            min-height: 100vh;
            display: flex;
            justify-content: center;
            align-items: center;
            padding: 20px;
            overflow-x: hidden;
        }

        /* Ambient Glow Background Effects */
        .glow-1 {
            position: fixed;
            top: 10%;
            left: 15%;
            width: 300px;
            height: 300px;
            background: #3b82f6;
            filter: blur(140px);
            opacity: 0.25;
            z-index: 0;
            pointer-events: none;
        }

        .glow-2 {
            position: fixed;
            bottom: 10%;
            right: 15%;
            width: 350px;
            height: 350px;
            background: #8b5cf6;
            filter: blur(150px);
            opacity: 0.2;
            z-index: 0;
            pointer-events: none;
        }

        .kiosk-card {
            position: relative;
            z-index: 1;
            background: var(--card-bg);
            backdrop-filter: blur(20px);
            -webkit-backdrop-filter: blur(20px);
            border: 1px solid var(--card-border);
            width: 100%;
            max-width: 520px;
            border-radius: 28px;
            padding: 32px 28px;
            box-shadow: 0 25px 60px -15px rgba(0, 0, 0, 0.6);
            animation: fadeIn 0.4s ease-out;
        }

        @keyframes fadeIn {
            from { opacity: 0; transform: translateY(15px); }
            to { opacity: 1; transform: translateY(0); }
        }

        .brand-header {
            text-align: center;
            margin-bottom: 24px;
        }

        .brand-logo {
            display: inline-flex;
            align-items: center;
            gap: 10px;
            font-size: 26px;
            font-weight: 800;
            background: linear-gradient(135deg, #60a5fa, #a78bfa);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
        }

        .brand-sub {
            color: var(--text-muted);
            font-size: 13px;
            margin-top: 4px;
            font-weight: 500;
        }

        /* Progress Steps */
        .step-indicator {
            display: flex;
            justify-content: space-between;
            margin-bottom: 28px;
            position: relative;
        }

        .step-indicator::before {
            content: '';
            position: absolute;
            top: 50%;
            left: 10%;
            right: 10%;
            height: 2px;
            background: rgba(255, 255, 255, 0.1);
            z-index: -1;
            transform: translateY(-50%);
        }

        .step-dot {
            width: 32px;
            height: 32px;
            border-radius: 50%;
            background: #0f172a;
            border: 2px solid #334155;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 13px;
            font-weight: 700;
            color: var(--text-muted);
            transition: all 0.3s;
        }

        .step-dot.active {
            border-color: var(--primary);
            background: var(--primary);
            color: white;
            box-shadow: 0 0 15px var(--primary-glow);
        }

        .step-dot.completed {
            background: var(--accent);
            border-color: var(--accent);
            color: white;
        }

        .step-content {
            display: none;
        }

        .step-content.active {
            display: block;
            animation: slideIn 0.3s ease-out;
        }

        @keyframes slideIn {
            from { opacity: 0; transform: translateX(10px); }
            to { opacity: 1; transform: translateX(0); }
        }

        .nav-bar {
            display: flex;
            align-items: center;
            justify-content: space-between;
            margin-bottom: 20px;
        }

        .btn-back {
            background: rgba(255, 255, 255, 0.05);
            border: 1px solid var(--card-border);
            color: var(--text-main);
            padding: 8px 16px;
            border-radius: 12px;
            cursor: pointer;
            font-size: 13px;
            font-weight: 600;
            display: flex;
            align-items: center;
            gap: 6px;
            transition: all 0.2s;
        }

        .btn-back:hover {
            background: rgba(255, 255, 255, 0.1);
        }

        /* Option Grid */
        .grid-options {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 14px;
            margin-bottom: 20px;
        }

        .option-card {
            background: rgba(15, 23, 42, 0.6);
            border: 2px solid var(--card-border);
            padding: 18px 14px;
            border-radius: 18px;
            cursor: pointer;
            text-align: center;
            transition: all 0.25s ease;
        }

        .option-card:hover {
            border-color: rgba(59, 130, 246, 0.5);
            transform: translateY(-2px);
        }

        .option-card.selected {
            border-color: var(--primary);
            background: rgba(59, 130, 246, 0.12);
            box-shadow: 0 8px 20px -6px var(--primary-glow);
        }

        .option-icon {
            font-size: 28px;
            margin-bottom: 8px;
        }

        .option-title {
            font-size: 14px;
            font-weight: 700;
            margin-bottom: 4px;
        }

        .option-badge {
            display: inline-block;
            font-size: 12px;
            font-weight: 700;
            color: #38bdf8;
            background: rgba(56, 189, 248, 0.1);
            padding: 4px 10px;
            border-radius: 20px;
        }

        /* Input Controls */
        .form-group {
            margin-bottom: 18px;
            text-align: left;
        }

        .form-group label {
            display: block;
            font-size: 13px;
            font-weight: 600;
            color: var(--text-muted);
            margin-bottom: 8px;
        }

        .form-control {
            width: 100%;
            padding: 12px 16px;
            border-radius: 14px;
            background: rgba(15, 23, 42, 0.8);
            border: 1px solid var(--card-border);
            color: white;
            font-size: 14px;
            outline: none;
            transition: all 0.2s;
        }

        .form-control:focus {
            border-color: var(--primary);
            box-shadow: 0 0 10px var(--primary-glow);
        }

        /* Upload Area */
        .upload-zone {
            border: 2px dashed rgba(59, 130, 246, 0.4);
            border-radius: 20px;
            padding: 30px 20px;
            text-align: center;
            cursor: pointer;
            background: rgba(15, 23, 42, 0.5);
            transition: all 0.3s;
            display: block;
            margin-bottom: 18px;
        }

        .upload-zone:hover {
            border-color: var(--primary);
            background: rgba(59, 130, 246, 0.08);
            transform: scale(1.01);
        }

        .upload-icon {
            width: 48px;
            height: 48px;
            margin-bottom: 10px;
            fill: var(--primary);
        }

        .file-list {
            max-height: 120px;
            overflow-y: auto;
            margin-bottom: 16px;
        }

        .file-chip {
            background: rgba(30, 41, 59, 0.9);
            border: 1px solid var(--card-border);
            padding: 10px 14px;
            border-radius: 12px;
            font-size: 13px;
            margin-bottom: 8px;
            display: flex;
            align-items: center;
            gap: 10px;
            text-align: left;
        }

        /* Price Breakdown Card */
        .summary-card {
            background: linear-gradient(135deg, rgba(15, 23, 42, 0.9), rgba(30, 41, 59, 0.6));
            border: 1px solid var(--card-border);
            border-radius: 18px;
            padding: 18px;
            margin-bottom: 20px;
        }

        .summary-row {
            display: flex;
            justify-content: space-between;
            font-size: 13px;
            color: var(--text-muted);
            margin-bottom: 8px;
        }

        .summary-row.total {
            font-size: 18px;
            font-weight: 800;
            color: var(--text-main);
            margin-top: 10px;
            padding-top: 10px;
            border-top: 1px dashed var(--card-border);
        }

        .total-price {
            color: var(--accent);
            font-weight: 800;
        }

        /* Main Buttons */
        .btn-action {
            width: 100%;
            background: linear-gradient(135deg, #2563eb, #1d4ed8);
            color: white;
            border: none;
            padding: 16px;
            border-radius: 16px;
            font-size: 16px;
            font-weight: 700;
            cursor: pointer;
            box-shadow: 0 10px 25px -5px var(--primary-glow);
            transition: all 0.25s ease;
            display: flex;
            align-items: center;
            justify-content: center;
            gap: 10px;
        }

        .btn-action:hover {
            transform: translateY(-2px);
            box-shadow: 0 14px 30px -5px var(--primary-glow);
        }

        .btn-action:active {
            transform: translateY(0);
        }

        .hero-banner {
            text-align: center;
            padding: 20px 0;
        }

        .hero-banner svg {
            width: 120px;
            height: 120px;
            margin-bottom: 15px;
            filter: drop-shadow(0 10px 20px var(--primary-glow));
        }

        /* Scrollbar */
        ::-webkit-scrollbar {
            width: 6px;
        }
        ::-webkit-scrollbar-thumb {
            background: rgba(255, 255, 255, 0.15);
            border-radius: 10px;
        }
    </style>
</head>
<body>

    <div class="glow-1"></div>
    <div class="glow-2"></div>

    <div class="kiosk-card">
        
        <!-- Header -->
        <div class="brand-header">
            <div class="brand-logo">
                <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5">
                    <polyline points="6 9 6 2 18 2 18 9"></polyline>
                    <path d="M6 18H4a2 2 0 0 1-2-2v-5a2 2 0 0 1 2-2h16a2 2 0 0 1 2 2v5a2 2 0 0 1-2 2h-2"></path>
                    <rect x="6" y="14" width="12" height="8"></rect>
                </svg>
                CampusPrint
            </div>
            <p class="brand-sub">Fast • Secure • Self-Service Kiosk</p>
        </div>

        <!-- Step Indicators -->
        <div class="step-indicator">
            <div class="step-dot active" id="dot1">1</div>
            <div class="step-dot" id="dot2">2</div>
            <div class="step-dot" id="dot3">3</div>
        </div>

        <!-- STEP 1: WELCOME SCREEN -->
        <div class="step-content active" id="step1">
            <div class="hero-banner">
                <svg viewBox="0 0 24 24" fill="none" stroke="url(#gradient)" stroke-width="1.5">
                    <defs>
                        <linearGradient id="gradient" x1="0%" y1="0%" x2="100%" y2="100%">
                            <stop offset="0%" stop-color="#60a5fa" />
                            <stop offset="100%" stop-color="#a78bfa" />
                        </linearGradient>
                    </defs>
                    <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path>
                    <polyline points="14 2 14 8 20 8"></polyline>
                    <line x1="16" y1="13" x2="8" y2="13"></line>
                    <line x1="16" y1="17" x2="8" y2="17"></line>
                    <polyline points="10 9 9 9 8 9"></polyline>
                </svg>
                <h2 style="font-size: 20px; font-weight: 700; margin-bottom: 6px;">Print Documents Instantly</h2>
                <p style="color: var(--text-muted); font-size: 13px; margin-bottom: 24px;">Upload PDFs or images, select options & pay via UPI/Cards.</p>
            </div>
            <button class="btn-action" onclick="goToStep(2)">
                <span>Start Printing</span>
                <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><path d="M5 12h14M12 5l7 7-7 7"/></svg>
            </button>
        </div>

        <!-- STEP 2: PRINT SETTINGS -->
        <div class="step-content" id="step2">
            <div class="nav-bar">
                <button class="btn-back" onclick="goToStep(1)">
                    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><path d="M19 12H5M12 19l-7-7 7-7"/></svg> Back
                </button>
                <h3 style="font-size: 16px; font-weight: 700;">Print Settings</h3>
                <div style="width: 60px;"></div>
            </div>

            <div class="grid-options">
                <div class="option-card selected" id="optBW" onclick="selectColorMode('BW', 2)">
                    <div class="option-icon">📄</div>
                    <div class="option-title">Black & White</div>
                    <span class="option-badge">₹2 / page</span>
                </div>
                <div class="option-card" id="optColor" onclick="selectColorMode('Color', 10)">
                    <div class="option-icon">🎨</div>
                    <div class="option-title">Color Print</div>
                    <span class="option-badge">₹10 / page</span>
                </div>
            </div>

            <div class="form-group">
                <label>Sides Option</label>
                <select class="form-control" id="printSides" onchange="calculateTotal()">
                    <option value="single">Single-Sided (One Side)</option>
                    <option value="double">Double-Sided (Both Sides - 20% Discount)</option>
                </select>
            </div>

            <div class="form-group">
                <label>Number of Copies</label>
                <input type="number" class="form-control" id="copyCount" value="1" min="1" onchange="calculateTotal()">
            </div>

            <button class="btn-action" onclick="goToStep(3)">
                <span>Next: Upload Documents</span>
                <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><path d="M5 12h14M12 5l7 7-7 7"/></svg>
            </button>
        </div>

        <!-- STEP 3: UPLOAD DOCUMENT & PAYMENT -->
        <div class="step-content" id="step3">
            <div class="nav-bar">
                <button class="btn-back" onclick="goToStep(2)">
                    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><path d="M19 12H5M12 19l-7-7 7-7"/></svg> Back
                </button>
                <h3 style="font-size: 16px; font-weight: 700;">Upload Document</h3>
                <div style="width: 60px;"></div>
            </div>

            <label class="upload-zone" for="fileInput">
                <svg class="upload-icon" viewBox="0 0 24 24">
                    <path d="M19.35 10.04C18.67 6.59 15.64 4 12 4 9.11 4 6.6 5.64 5.35 8.04 2.34 8.36 0 10.91 0 14c0 3.31 2.69 6 6 6h13c2.76 0 5-2.24 5-5 0-2.64-2.05-4.78-4.65-4.96zM14 13v4h-4v-4H7l5-5 5 5h-3z"/>
                </svg>
                <div style="font-size: 15px; font-weight: 700;">Tap to Choose Files</div>
                <div style="font-size: 12px; color: var(--text-muted); margin-top: 4px;">Supports PDFs or Images</div>
            </label>
            <input type="file" id="fileInput" accept="application/pdf,image/*" multiple style="display:none;" onchange="handleMultipleFiles()">
            
            <div class="file-list" id="fileListContainer"></div>

            <div class="form-group" id="pageRangeBox" style="display:none;">
                <label>Custom Page Range (Optional)</label>
                <input type="text" class="form-control" id="pageRange" placeholder="e.g. 1-5, 8 (Leave blank for all)" oninput="calculateTotal()">
            </div>

            <div class="summary-card" id="priceSummaryBox" style="display:none;">
                <div class="summary-row">
                    <span>Total Pages in Document:</span>
                    <strong id="docPagesText">0</strong>
                </div>
                <div class="summary-row">
                    <span>Selected Print Pages:</span>
                    <strong id="totalPagesText">0</strong>
                </div>
                <div class="summary-row">
                    <span>Copies:</span>
                    <strong id="copiesSummaryText">1</strong>
                </div>
                <div class="summary-row total">
                    <span>Total Bill:</span>
                    <span class="total-price">₹<span id="finalAmountText">0</span></span>
                </div>
            </div>

            <button class="btn-action" id="proceedToPayBtn" style="display:none;" onclick="payWithRazorpay()">
                <span>Proceed to Payment</span>
                <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><path d="M5 12h14M12 5l7 7-7 7"/></svg>
            </button>
        </div>

        <!-- STEP 4: SUCCESS / PRINTING -->
        <div class="step-content" id="step4">
            <div class="hero-banner">
                <div style="width: 80px; height: 80px; background: rgba(16, 185, 129, 0.15); border-radius: 50%; display: flex; align-items: center; justify-content: center; margin: 0 auto 16px;">
                    <svg width="45" height="45" viewBox="0 0 24 24" fill="none" stroke="#10b981" stroke-width="3"><polyline points="20 6 9 17 4 12"/></svg>
                </div>
                <h2 style="font-size: 22px; font-weight: 800; color: var(--accent); margin-bottom: 8px;">Printing Started!</h2>
                <p style="color: var(--text-muted); font-size: 14px; margin-bottom: 24px;">Please collect your printed pages from the output tray below. 📥</p>
            </div>
            <button class="btn-action" onclick="resetKiosk()">
                <span>Print Another Document</span>
            </button>
        </div>

    </div>

    <script>
        let selectedColorMode = 'BW';
        let baseRate = 2;
        let selectedFilesArr = [];
        let totalDocPages = 0;
        let finalCost = 0;

        function goToStep(stepNum) {
            document.querySelectorAll('.step-content').forEach(el => el.classList.remove('active'));
            document.getElementById('step' + stepNum).classList.add('active');

            // Update Progress Dots
            for (let i = 1; i <= 3; i++) {
                const dot = document.getElementById('dot' + i);
                dot.classList.remove('active', 'completed');
                if (i < stepNum) dot.classList.add('completed');
                else if (i === stepNum) dot.classList.add('active');
            }
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
                fileListContainer.innerHTML += `
                    <div class="file-chip">
                        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#60a5fa" stroke-width="2"><path d="M13 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V9z"/><polyline points="13 2 13 9 20 9"/></svg>
                        <span style="white-space:nowrap; overflow:hidden; text-overflow:ellipsis; flex:1;">${file.name}</span>
                    </div>
                `;
            });

            const res = await fetch('/count-multiple-pages', { method: 'POST', body: formData });
            const data = await res.json();
            
            totalDocPages = data.total_pages || selectedFilesArr.length;

            document.getElementById('pageRangeBox').style.display = 'block';
            document.getElementById('priceSummaryBox').style.display = 'block';
            document.getElementById('proceedToPayBtn').style.display = 'flex';

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

        function payWithRazorpay() {
            if (finalCost <= 0) finalCost = 2;

            const options = {
                "key": "rzp_test_TURAyEBXgKmNLg",
                "amount": finalCost * 100, // Amount in paise
                "currency": "INR",
                "name": "CampusPrint Kiosk",
                "description": "Document Printing Fee",
                "handler": function (response) {
                    confirmPaymentAndPrint();
                },
                "theme": {
                    "color": "#3b82f6"
                }
            };
            const rzp = new Razorpay(options);
            rzp.open();
        }

        async function confirmPaymentAndPrint() {
            const formData = new FormData();
            selectedFilesArr.forEach(file => formData.append('files', file));
            formData.append('copies', document.getElementById('copyCount').value);
            formData.append('range', document.getElementById('pageRange').value);

            const res = await fetch('/print-multiple', { method: 'POST', body: formData });
            const data = await res.json();

            if(data.success) {
                goToStep(4);
            } else {
                alert("Print Alert: " + data.error);
                goToStep(4);
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
