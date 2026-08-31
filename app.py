import os
import win32api
import win32print
import tkinter as tk
from tkinter import messagebox
from flask import Flask, request, jsonify

app = Flask(__name__)
UPLOAD_FOLDER = 'uploads'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# 1. PC Screen par Permission Pop-Up Box
def ask_print_confirmation(filename, copies):
    root = tk.Tk()
    root.withdraw()  # Main blank window ko chhupane ke liye
    root.attributes("-topmost", True)  # Pop-up sabse upar dikhega

    response = messagebox.askyesno(
        "🖨️ Campus Print - Permission Needed",
        f"New Print Job Received!\n\n📄 File: {filename}\n📑 Copies: {copies}\n\nDo you want to print this document now?"
    )
    root.destroy()
    return response

# 2. Windows Default Printer par Print bhejne ka Logic
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

# 3. Print Route (Website Trigger)
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
            
            # Pop-up se YES / NO confirmation pucho
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
