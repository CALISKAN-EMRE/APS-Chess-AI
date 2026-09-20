import socket
import sys
import urllib.request

if len(sys.argv) < 4:
    print("Usage: check_port.py <port> <url> <expected_text>")
    sys.exit(3)

port = int(sys.argv[1])
url = sys.argv[2]
expected_text = sys.argv[3]

# 1. Test if port is currently open
try:
    sock = socket.create_connection(("127.0.0.1", port), timeout=0.5)
    sock.close()
except OSError:
    # Port is not open -> FREE
    sys.exit(0)

# 2. Port is open. Query the verification URL
try:
    req = urllib.request.Request(url, headers={"User-Agent": "APS-Launcher-Check"})
    with urllib.request.urlopen(req, timeout=2.0) as resp:
        content = resp.read().decode("utf-8", errors="ignore")
        if expected_text in content:
            # Service is already running and healthy
            sys.exit(1)
except Exception:
    pass

# Port is occupied by an unresponsive or unrelated application -> CONFLICT
sys.exit(2)
