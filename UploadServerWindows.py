#!/usr/bin/env python3
import os
import sys
import time
import random
import subprocess
import importlib.util
from tkinter import font

# list rquired libraries
REQUIRED_LIBS = ["cgi", "qrcode"]

# function to install missing libraries
def install_missing_libs():
    print("checking for required libraries")
    missing = []
    for lib in REQUIRED_LIBS:
        if importlib.util.find_spec(lib) is None:
            missing.append(lib)
    if missing:
        print(f"missing libraries: {', '.join(missing)}")
        print("installing...")
        for lib in missing:
            try:
                subprocess.check_call([sys.executable, "-m", "pip", "install", lib])
                print(f"✅ installed sucesfully {lib}")
            except Exception as e:
                print(f"❌ cant install: {lib}: {e}")
                print("check https://github.com/charozi/file-drop/blob/main/QRCODEFAILED.md for more info.")
    else:
        print("all required libraries are already installed, proceeding.")
        time.sleep(1)

install_missing_libs()

import cgi
import qrcode
import socket
import getpass
import zipfile
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs

# setup and config

def clear_screen():
    os.system('cls' if os.name == 'nt' else 'clear')

def first_time_setup():
    config_path = os.path.join(os.path.expanduser("~"), ".filetransferconfig.txt")
    
    if not os.path.exists(config_path):
        clear_screen()
        print("welcome to file transfer setup")
        username = input("your windows username: ").strip() or "User"
        
        default_path = os.path.join(os.path.expanduser("~"), "Downloads", "filetransfer")
        print(f"\nyour downloads folder: {default_path}")
        custom_path = input("would you like to change the folder? (enter to skip): ").strip()
        if custom_path:
            upload_dir = os.path.expanduser(custom_path)
        else:
            upload_dir = default_path
        
        os.makedirs(upload_dir, exist_ok=True)
        
        with open(config_path, "w", encoding="utf-8") as f:
            f.write(f"username={username}\n")
            f.write(f"upload_dir={upload_dir}\n")
        
        print(f"config saved in {config_path}")
        time.sleep(1.5)
        return username, upload_dir
    else:
        with open(config_path, "r", encoding="utf-8") as f:
            data = dict(line.strip().split("=", 1) for line in f if "=" in line)
        username = data.get("username", "User")
        upload_dir = data.get("upload_dir", os.path.join(os.path.expanduser("~"), "Downloads", "filetransfer"))
        os.makedirs(upload_dir, exist_ok=True)
        return username, upload_dir

username, UPLOAD_DIR = first_time_setup()
BLOCKED_IPS_FILE = os.path.join(UPLOAD_DIR, "blocked_ips.txt")

# server stuff

SECRET_CODE = f"{random.randint(100000, 999999)}"
failed_attempts = {}
upload_times = {}
blocked_ips = set()
MAX_ATTEMPTS = 5
MAX_UPLOADS_PER_MINUTE = 3
TIME_WINDOW = 60

def get_local_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "192.168.1.100"

def generate_qr_code(url):
    try:
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_L,
            box_size=3,
            border=4,
        )
        qr.add_data(url)
        qr.make(fit=True)
        qr.print_ascii(invert=True)
        return True
    except Exception as e:
        print(f"[qr] error: {e}")
        return False

def format_file_size(size_bytes):
    if size_bytes == 0:
        return "0B"
    size_names = ["B", "KB", "MB", "GB"]
    i = 0
    while size_bytes >= 1024 and i < len(size_names) - 1:
        size_bytes /= 1024.0
        i += 1
    return f"{size_bytes:.1f}{size_names[i]}"

# html handler

class UploadHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        pass

    def send_html_response(self, body, status=200):
        """Send an HTML response ensuring bytes are written and headers are set."""
        if isinstance(body, str):
            body_bytes = body.encode("utf-8")
        else:
            body_bytes = body
        self.send_response(status)
        self.send_header('Content-Type', 'text/html; charset=utf-8')
        self.send_header('Content-Length', str(len(body_bytes)))
        self.end_headers()
        self.wfile.write(body_bytes)

    def do_GET(self):
        if self.path == '/':
            self.send_response(200)
            self.send_header('Content-type', 'text/html; charset=utf-8')
            self.end_headers()
            html = """
                <!DOCTYPE html>
<html>
<head>
    <title>{username} file transfer</title>
    <!-- 312faaw -->
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <style>
        /* (desktop first) */
        body {
            font-family: sans-serif;
            text-align: center;
            background: #eef;
            margin: 0;
            padding: 20px;
        }

        h1 {
            font-size: 2em; /* Default for desktop */
        }

        form {
            max-width: 500px;
            margin: 0 auto;
            padding: 20px;
            background: #fff;
            border-radius: 8px;
            box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
        }

        input[type="text"],
        input[type="file"],
        button {
            width: 100%;
            box-sizing: border-box; /* padding */
            padding: 10px;
            margin-bottom: 15px;
            border: 1px solid #ccc;
            border-radius: 4px;
        }

        button {
            background-color: #007bff;
            color: white;
            border: none;
            cursor: pointer;
            font-size: 1.2em;
            padding: 15px;
        }

        button:hover {
            background-color: #0056b3;
        }

        /* beter font */
        @media (max-width: 600px) {
            /* font */
            body {
                padding: 10px;
            }
            
            h1 {
                font-size: 2.5em;
            }

            p {
                font-size: 1.2em;
            }

            /* bigger */
            input[type="text"],
            input[type="file"],
            button {
                font-size: 1.1em;
                padding: 15px;
            }

            button {
                padding: 20px;
            }
            
            /* bigger thingy alt
            body {
                transform: scale(1.5);
                transform-origin: 0 0;
            }
            */
        }
    </style>
</head>
<body>
    <h1>📱 {username} file transfer</h1>
    <form method="POST" enctype="multipart/form-data">
        <p>🔑 Code: <b>######</b></p>
        <p><input type="text" name="secret_code" placeholder="Code..."></p>
        <p><input type="file" name="file" multiple></p>
        <p><button type="submit">Upload Files</button></p>
    </form>
</body>
</html>
            """
            # replace placeholters to ccs not bug
            html = html.replace("{username}", username).replace("{secret_code}", SECRET_CODE)
            self.wfile.write(html.encode('utf-8'))
        else:
            self.send_error(404)

    def do_POST(self):
        form = cgi.FieldStorage(
            fp=self.rfile,
            headers=self.headers,
            environ={'REQUEST_METHOD': 'POST'}
        )
        code = form.getvalue("secret_code", "")
        if code != SECRET_CODE:
            self.send_html_response("<h1>wrong code</h1>", status=200)
            return
        if "file" not in form:
            self.send_html_response("<h1>no file</h1>", status=400)
            return
        files = form["file"]
        if not isinstance(files, list):
            files = [files]
        os.makedirs(UPLOAD_DIR, exist_ok=True)
        for f in files:
            filename = f.filename
            if filename:
                data = f.file.read()
                path = os.path.join(UPLOAD_DIR, filename)
                with open(path, "wb") as out:
                    out.write(data)
                print(f"got {filename} ({format_file_size(len(data))}) from {self.client_address[0]}")
        self.send_html_response("<h1>files uploaded! check console for details</h1>", status=200)

# server launching

if __name__ == '__main__':
    try:
        port = random.randint(8000, 9999)
        local_ip = get_local_ip()
        url = f"http://{local_ip}:{port}"
        clear_screen()
        print("file transfer server - started")
        print("=" * 50)
        print(f"user: {username}")
        print(f"connect to: {url}")
        print(f"code: {SECRET_CODE}")
        print(f"upload dir: {UPLOAD_DIR}")
        print("=" * 50)
        print("phone qr code:")
        generate_qr_code(url)
        print("===Console===============================================")
        server = HTTPServer(('0.0.0.0', port), UploadHandler)
        print("http server has stared successfully")
        server.serve_forever()
    except KeyboardInterrupt:
        clear_screen()
        print("bye")
    except Exception as e:
        print(f"server error: {e}")
        input("hit enter to force stop")
