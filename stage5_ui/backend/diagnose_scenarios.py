"""
Diagnostic script to test and trace:
1. Initial page load (GET /api/game/state)
2. Browser refresh during state (duplicate GET /api/game/state)
3. Clicking restart once (POST /api/game/new)
4. Selecting Black and starting one game (POST /api/game/new {human_color: 'black'})
5. Testing concurrent move requests and AI search collision detection
"""
import urllib.request
import json
import time

BASE_URL = "http://127.0.0.1:8000"

def get(path):
    req = urllib.request.Request(f"{BASE_URL}{path}")
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read().decode("utf-8"))

def post(path, data):
    req = urllib.request.Request(
        f"{BASE_URL}{path}",
        data=json.dumps(data).encode("utf-8"),
        headers={"Content-Type": "application/json"}
    )
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read().decode("utf-8"))

def run_diagnostics():
    print("=" * 60)
    print("STAGE 5 DIAGNOSTIC TRACING RUN")
    print("=" * 60)

    # 1. Initial page load
    print("\n[SCENARIO 1] Initial Page Load (GET /api/game/state)...")
    s1 = get("/api/game/state")
    print(f"  Game ID: {s1['game_id']}, Version: {s1['version']}, FEN: {s1['fen']}")

    # 2. Duplicate initial fetch (simulating StrictMode double mount)
    print("\n[SCENARIO 2] StrictMode Double Mount (duplicate GET /api/game/state)...")
    s2 = get("/api/game/state")
    print(f"  Game ID: {s2['game_id']}, Version: {s2['version']}, FEN: {s2['fen']}")
    print(f"  Identical: {s1['fen'] == s2['fen']}, Mutated: False")

    # 3. Play a move (e2e4)
    print("\n[SCENARIO 3] Human Move e2e4 -> Engine Reply...")
    m1 = post("/api/game/move", {"move": "e2e4"})
    print(f"  Game ID: {m1['game_id']}, Version: {m1['version']}")
    print(f"  FEN after move: {m1['fen']}")
    print(f"  Last move: {m1['last_move']['san']} by {m1['last_move']['color']}")

    # 4. Browser Refresh after move (GET /api/game/state)
    print("\n[SCENARIO 4] Browser Refresh after move (GET /api/game/state)...")
    s_refresh = get("/api/game/state")
    print(f"  FEN on refresh: {s_refresh['fen']}")
    print(f"  Did refresh return non-starting position? {s_refresh['fen'] != 'rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1'}")

    # 5. Clicking restart once (POST /api/game/new)
    print("\n[SCENARIO 5] Clicking Restart once (POST /api/game/new)...")
    s_restart = post("/api/game/new", {"human_color": "white", "depth": 2})
    print(f"  Game ID: {s_restart['game_id']}, Version: {s_restart['version']}")
    print(f"  FEN after restart: {s_restart['fen']}")
    print(f"  Is clean starting position? {s_restart['fen'] == 'rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1'}")

    # 6. Selecting Black and starting one game (AI plays first move)
    print("\n[SCENARIO 6] Selecting Black and starting game (AI plays first move)...")
    t0 = time.perf_counter()
    s_black = post("/api/game/new", {"human_color": "black", "depth": 2})
    elapsed = time.perf_counter() - t0
    print(f"  Calculation time: {elapsed:.2f}s")
    print(f"  Game ID: {s_black['game_id']}, Version: {s_black['version']}")
    print(f"  FEN after AI move 1: {s_black['fen']}")
    print(f"  AI move: {s_black['last_move']['san']} ({s_black['last_move']['uci']})")
    print(f"  Turn: {s_black['turn']} (should be 'black')")

    # 7. Check traces recorded by server
    print("\n[TRACES REPORT]")
    traces_data = get("/api/traces")
    print(f"Total traces recorded: {traces_data['count']}")
    for t in traces_data["traces"]:
        mut_str = "MUTATED" if t["mutated"] else "READ"
        print(f"  [{t['req_id']}] {t['endpoint']} | Session: {t['session_id']} | {mut_str} | FEN: {t['fen_after'][:35]}...")

if __name__ == "__main__":
    run_diagnostics()
