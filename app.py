import os
import win32api
import win32print
import tkinter as tk
from tkinter import messagebox
from flask import Flask, request, jsonify
from flask_cors import CORS
from pypdf import PdfReader

app = Flask(__name__)
CORS(app)

UPLOAD_FOLDER = 'uploads'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

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
                # Non-PDF files default to 1 page
                total_pages += 1

    return jsonify({'total_pages': total_pages})

# 2. PC Screen Permission Pop-Up Box
def ask_print_confirmation(filename, copies):
    root = tk.Tk()
    root.withdraw()
    root.attributes("-topmost", True)

    response = messagebox.askyesno(
        "🖨️ Campus Print - Permission Needed",
        f"New Print Job Received!\n\n📄 File: {filename}\n📑 Copies: {copies}\n\nDo you want to print this document now?"
    )
    root.destroy()
    return response

# 3. Windows Default Printer Execution
def print_to_windows_printer(filepath, copies):
    try:
        default_printer = win32print.GetDefaultPrinter()
        print(f"Target Printer: {default_printer}")
        
        for _ in range(int(copies)):
            win32api.ShellExecute(
                0,
                "print",
                filepath,
                f'/d:"{default_printer}"',
                ".",
                0
            )
        return True
    except Exception as e:
        print("Print Error:", str(e))
        return False

# 4. Print Route Triggered from Website/Phone
@app.route('/print-multiple', methods=['POST'])
def print_multiple():
    if 'files' not in request.files:
        return jsonify({'error': 'No files uploaded'}), 400
        
    files = request.files.getlist('files')
    copies = request.form.get('copies', 1)

    printed_files = []
    cancelled_files = []

    for file in files:
        if file.filename != '':
            filepath = os.path.join(UPLOAD_FOLDER, file.filename)
            file.save(filepath)
            abs_path = os.path.abspath(filepath)
            
            user_allowed = ask_print_confirmation(file.filename, copies)
            
            if user_allowed:
                if print_to_windows_printer(abs_path, copies):
                    printed_files.append(file.filename)
            else:
                cancelled_files.append(file.filename)

    if printed_files:
        return jsonify({'message': f'Printed successfully: {", ".join(printed_files)}'})
    else:
        return jsonify({'error': 'Print job cancelled by PC operator.'}), 400

if __name__ == '__main__':
    print("🚀 Campus Print Server Active!")
    app.run(host='0.0.0.0', port=5000, debug=True)
