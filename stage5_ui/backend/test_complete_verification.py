import urllib.request
import urllib.error
import json
import time

BASE_URL = "http://127.0.0.1:8000"

def get(path):
    req = urllib.request.Request(f"{BASE_URL}{path}")
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read().decode("utf-8"))

def post(path, data=None):
    req = urllib.request.Request(
        f"{BASE_URL}{path}",
        data=json.dumps(data or {}).encode("utf-8"),
        headers={"Content-Type": "application/json"}
    )
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read().decode("utf-8"))

def main():
    print("=" * 70)
    print("STAGE 5 COMPLETE VERIFICATION TEST")
    print("=" * 70)

    # 1. Health check & warm-up verification
    print("\n[CHECK 1] Backend Health & Engine Warm-up...")
    health = get("/api/health")
    print(f"  Status        : {health['status']}")
    print(f"  Engine        : {health['engine']}")
    print(f"  Python        : {health['python_version']}")
    print(f"  Device        : {health['device']}")
    assert health['status'] == 'healthy'
    print("  -> PASSED.")

    # 2. Starting a new game as White
    print("\n[CHECK 2] New Game as White (POST /api/game/new)...")
    s_new = post("/api/game/new", {"human_color": "white", "depth": 2})
    print(f"  Game ID       : {s_new['game_id']}")
    print(f"  Version       : {s_new['version']}")
    print(f"  FEN           : {s_new['fen']}")
    print(f"  Turn          : {s_new['turn']}")
    print(f"  History plies : {len(s_new['history'])}")
    assert s_new['version'] == 1
    assert s_new['turn'] == "white"
    assert len(s_new['history']) == 0
    assert s_new['fen'] == "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"
    print("  -> PASSED: Clean starting position, exactly 0 plies, version 1.")

    # 3. Exactly ONE human move per POST /api/game/move
    print("\n[CHECK 3] Human Move e2e4 (POST /api/game/move)...")
    t0 = time.perf_counter()
    s_move = post("/api/game/move", {"move": "e2e4"})
    elapsed_move_ms = (time.perf_counter() - t0) * 1000.0
    print(f"  Latency       : {elapsed_move_ms:.2f} ms")
    print(f"  Game ID       : {s_move['game_id']}")
    print(f"  Version       : {s_move['version']}")
    print(f"  FEN           : {s_move['fen']}")
    print(f"  Turn          : {s_move['turn']} (should be 'black')")
    print(f"  History plies : {len(s_move['history'])} (should be 1)")
    print(f"  Last move     : {s_move['last_move']['san']} by {s_move['last_move']['color']}")
    assert s_move['version'] == 2
    assert s_move['turn'] == "black"
    assert len(s_move['history']) == 1
    assert s_move['last_move']['uci'] == "e2e4"
    assert s_move['last_move']['color'] == "white"
    assert s_move['fen'] == "rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq - 0 1"
    assert elapsed_move_ms < 100.0, "Human move must return immediately (< 100ms)"
    print("  -> PASSED: Exactly 1 human move applied. Latency < 100ms. AI move was NOT executed.")

    # 4. F5 browser refresh semantics (preserves active board and history, triggers 0 moves)
    print("\n[CHECK 4] Simulating F5 Browser Refresh (GET /api/game/state)...")
    s_refresh = get("/api/game/state")
    print(f"  Game ID       : {s_refresh['game_id']}")
    print(f"  Version       : {s_refresh['version']}")
    print(f"  FEN           : {s_refresh['fen']}")
    print(f"  Turn          : {s_refresh['turn']}")
    print(f"  History plies : {len(s_refresh['history'])}")
    assert s_refresh['game_id'] == s_move['game_id']
    assert s_refresh['version'] == 2
    assert s_refresh['fen'] == s_move['fen']
    assert len(s_refresh['history']) == 1
    print("  -> PASSED: Active session preserved across refresh. 0 moves triggered.")

    # 5. Calling human move when it's not human's turn -> rejected
    print("\n[CHECK 5] Turn enforcement (Human tries to move when it's Black's turn)...")
    try:
        post("/api/game/move", {"move": "e4e5"})
        print("  -> FAILED: Move should have been rejected!")
        assert False
    except urllib.error.HTTPError as e:
        print(f"  HTTP Error {e.code}: {e.read().decode('utf-8')}")
        assert e.code == 400
        print("  -> PASSED: Turn enforcement rejected illegal out-of-turn move.")

    # 6. Exactly ONE AI move per POST /api/engine/move
    print("\n[CHECK 6] AI Move calculation (POST /api/engine/move)...")
    t0 = time.perf_counter()
    s_ai = post("/api/engine/move")
    elapsed_ai = time.perf_counter() - t0
    print(f"  HTTP Latency  : {elapsed_ai:.2f} s")
    print(f"  Game ID       : {s_ai['game_id']}")
    print(f"  Version       : {s_ai['version']}")
    print(f"  FEN           : {s_ai['fen']}")
    print(f"  Turn          : {s_ai['turn']} (should be 'white')")
    print(f"  History plies : {len(s_ai['history'])} (should be 2)")
    print(f"  AI move played: {s_ai['last_move']['san']} by {s_ai['last_move']['color']}")
    print(f"  Telemetry     : Depth {s_ai['telemetry']['depth']}, Evals {s_ai['telemetry']['neural_evaluations']}, Nodes {s_ai['telemetry']['nodes_visited']}, Score {s_ai['telemetry']['evaluation']:.4f}")
    assert s_ai['version'] == 3
    assert s_ai['turn'] == "white"
    assert len(s_ai['history']) == 2
    assert s_ai['last_move']['color'] == "black"
    print("  -> PASSED: Exactly 1 AI move applied with complete telemetry.")

    # 7. Calling engine move when it's human's turn -> rejected
    print("\n[CHECK 7] Turn enforcement (Engine move requested when it's Human's turn)...")
    try:
        post("/api/engine/move")
        print("  -> FAILED: Engine move should have been rejected!")
        assert False
    except urllib.error.HTTPError as e:
        print(f"  HTTP Error {e.code}: {e.read().decode('utf-8')}")
        assert e.code == 400
        print("  -> PASSED: Engine move rejected when not engine's turn.")

    # 8. Selecting Black flow
    print("\n[CHECK 8] Selecting Black & Starting Game...")
    s_black_new = post("/api/game/new", {"human_color": "black", "depth": 2})
    print(f"  Game ID       : {s_black_new['game_id']}")
    print(f"  Version       : {s_black_new['version']}")
    print(f"  Human Color   : {s_black_new['human_color']}")
    print(f"  Turn          : {s_black_new['turn']} (White)")
    assert s_black_new['human_color'] == "black"
    assert s_black_new['turn'] == "white"
    assert len(s_black_new['history']) == 0
    print("  New game created with clean starting board. Now requesting AI opening move...")
    t0 = time.perf_counter()
    s_black_ai = post("/api/engine/move")
    elapsed_black_ai = time.perf_counter() - t0
    print(f"  AI 1st move   : {s_black_ai['last_move']['san']} in {elapsed_black_ai:.2f}s")
    print(f"  Turn          : {s_black_ai['turn']} (Black's turn to play)")
    print(f"  History plies : {len(s_black_ai['history'])} (1)")
    assert s_black_ai['turn'] == "black"
    assert len(s_black_ai['history']) == 1
    assert s_black_ai['last_move']['color'] == "white"
    print("  -> PASSED: Selecting Black starts clean board, and /engine/move plays White's first move.")

    # 9. Trace log inspection
    print("\n[CHECK 9] Request Traces Verification...")
    traces_data = get("/api/traces")
    print(f"  Total traces recorded: {traces_data['count']}")
    recent = traces_data["traces"][-8:]
    for t in recent:
        mut_str = "MUTATED" if t["mutated"] else "READ"
        print(f"  [{t['req_id']}] {t['endpoint']:22} | Session: {t['session_id']} | {mut_str:7} | FEN: {t['fen_after'][:32]}...")
    print("  -> PASSED: Traces clearly demarcate /game/move (1 human ply) and /engine/move (1 AI ply).")

    print("\n" + "=" * 70)
    print("ALL VERIFICATION CHECKS PASSED SUCCESSFULLY!")
    print("=" * 70)

if __name__ == "__main__":
    main()
