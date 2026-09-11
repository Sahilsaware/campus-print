import os
import time
import base64
import tempfile
import subprocess
import requests

SERVER_URL = "https://campus-print-ppbq.onrender.com"

def process_print_jobs():
    print("Starting local print worker on kiosk-print-01...")
    while True:
        try:
            response = requests.get(f"{SERVER_URL}/get-pending-jobs", timeout=10)
            if response.status_code == 200:
                data = response.json()
                jobs = data.get('jobs', [])
                
                for job in jobs:
                    job_id = job['id']
                    filename = job['filename']
                    file_base64 = job['file_data']
                    copies = job.get('copies', 1)
                    color_mode = job.get('color_mode', 'bw')
                    orientation = job.get('orientation', 'portrait')
                    
                    print(f"Received print task ({job_id}). Decoding file...")
                    
                    file_bytes = base64.b64decode(file_base64)
                    
                    with tempfile.NamedTemporaryFile(delete=False, suffix=os.path.splitext(filename)[1]) as tmp:
                        tmp.write(file_bytes)
                        tmp_path = tmp.name
                        
                    try:
                        lp_args = ['lp', '-n', str(copies)]
                        if color_mode == 'color':
                            lp_args.extend(['-o', 'ColorModel=Color'])
                        else:
                            lp_args.extend(['-o', 'ColorModel=Monochrome'])
                            
                        if orientation == 'landscape':
                            lp_args.extend(['-o', 'landscape'])
                        else:
                            lp_args.extend(['-o', 'portrait'])
                            
                        lp_args.append(tmp_path)
                        
                        subprocess.run(lp_args, check=True)
                        print("Print job sent to CUPS successfully!")
                        
                        complete_res = requests.post(f"{SERVER_URL}/complete-job/{job_id}/", timeout=10)
                        if complete_res.status_code == 200:
                            print(f"Job {job_id} marked as completed on server.")
                        else:
                            print(f"Failed to clear job on server: {complete_res.status_code}")
                            
                    except Exception as e:
                        print(f"Error printing file: {e}")
                    finally:
                        if os.path.exists(tmp_path):
                            os.remove(tmp_path)
                            
        except Exception as e:
            print(f"Connection error with server: {e}")
            
        time.sleep(5)

if __name__ == '__main__':
    process_print_jobs()
