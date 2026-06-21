import socket
import threading
import json
import time
import os
import http.server
import socketserver
from urllib.parse import urlparse, parse_qs

# Configuration
EXPLORER_PORT = 8080
CLIENT_DATA_FILE = "xode_client_data.json"

class ExplorerData:
    def __init__(self):
        self.chain = []
        self.address = ""
        self.balance = 0
        self.block_height = 0
        self.total_issued = 0
        self.last_update = 0
        self.lock = threading.Lock()

    def load_from_file(self):
        """Load data from client data file"""
        # Try multiple possible paths
        paths = [
            CLIENT_DATA_FILE,
            os.path.join(os.path.expanduser("~"), CLIENT_DATA_FILE),
            os.path.join(os.path.dirname(os.path.abspath(__file__)), CLIENT_DATA_FILE)
        ]

        for path in paths:
            if not os.path.exists(path):
                continue
            try:
                with open(path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                with self.lock:
                    self.chain = data.get("chain", [])
                    self.address = data.get("address", "")
                    self.balance = data.get("balance", 0)
                    self.block_height = data.get("block_height", 0)
                    self.total_issued = data.get("total_issued", 0)
                    self.last_update = data.get("saved_at", time.time())
                print("[Explorer] Loaded data from: " + path)
                return True
            except Exception as e:
                print("[Explorer] Failed to load from " + path + ": " + str(e))
                continue

        print("[Explorer] No client data file found. Run client first.")
        return False

    def get_data(self):
        with self.lock:
            # Calculate total burned from chain data
            burned_total = 0
            for block in self.chain:
                reward = block.get("reward", {})
                if reward.get("burned", 0) > 0:
                    burned_total += reward["burned"]

            return {
                "chain": self.chain,
                "address": self.address,
                "balance": self.balance,
                "block_height": self.block_height,
                "total_issued": self.total_issued,
                "burned_total": burned_total,
                "last_update": self.last_update
            }

explorer_data = ExplorerData()

class ExplorerHandler(http.server.SimpleHTTPRequestHandler):
    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path

        if path == '/':
            self.serve_html()
        elif path == '/api/chain':
            self.serve_api()
        elif path == '/api/stats':
            self.serve_stats()
        else:
            self.send_error(404)

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()

    def serve_html(self):
        html_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'xode_explorer.html')
        if not os.path.exists(html_path):
            self.send_error(404, "Explorer HTML not found")
            return

        with open(html_path, 'r', encoding='utf-8') as f:
            content = f.read()

        self.send_response(200)
        self.send_header('Content-Type', 'text/html; charset=utf-8')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        self.wfile.write(content.encode('utf-8'))

    def serve_api(self):
        explorer_data.load_from_file()
        data = explorer_data.get_data()

        self.send_response(200)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        self.wfile.write(json.dumps(data, ensure_ascii=False).encode('utf-8'))

    def serve_stats(self):
        explorer_data.load_from_file()
        data = explorer_data.get_data()

        chain = data.get("chain", [])
        total_issued = data.get("total_issued", 0)
        burned_total = data.get("burned_total", 0)

        stats = {
            "block_height": len(chain) - 1 if chain else -1,
            "total_blocks": len(chain),
            "total_supply": 2100000000,
            "total_issued": total_issued,
            "remaining": 2100000000 - total_issued,
            "burned": burned_total,
            "my_address": data.get("address", ""),
            "my_balance": data.get("balance", 0),
            "last_update": data.get("last_update", 0)
        }

        self.send_response(200)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        self.wfile.write(json.dumps(stats, ensure_ascii=False).encode('utf-8'))

    def log_message(self, format, *args):
        print("[Explorer] " + format % args)


def data_watcher():
    """Background thread: periodically refresh data"""
    while True:
        explorer_data.load_from_file()
        time.sleep(5)


def start_explorer():
    print("=" * 60)
    print("XODE Blockchain Explorer (Client Mode)")
    print("=" * 60)
    print("Explorer URL: http://localhost:" + str(EXPLORER_PORT))
    print("API Endpoint: http://localhost:" + str(EXPLORER_PORT) + "/api/chain")
    print("Data Source: " + CLIENT_DATA_FILE + " (client data)")
    print("=" * 60)
    print("Make sure xode_client.py is running and saving data")
    print("Press Ctrl+C to stop")
    print("")

    # Start data watcher thread
    watcher = threading.Thread(target=data_watcher, daemon=True)
    watcher.start()

    # Start HTTP server
    with socketserver.TCPServer(("0.0.0.0", EXPLORER_PORT), ExplorerHandler) as httpd:
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("
[Explorer] Shutting down...")
            httpd.shutdown()


if __name__ == "__main__":
    start_explorer()
