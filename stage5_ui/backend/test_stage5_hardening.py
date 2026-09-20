import time
import threading
import requests

BASE_URL = "http://127.0.0.1:8000/api"

def log_test(title):
    print(f"\n{'='*60}\n{title}\n{'='*60}")

def test_stage5_hardening():
    log_test("[TEST 1] Health Check & Startup Verification")
    r = requests.get(f"{BASE_URL}/health")
    assert r.status_code == 200, f"Health check failed: {r.text}"
    health_data = r.json()
    print("Health Status:", health_data)
    assert health_data["model_loaded"] is True

    # -------------------------------------------------------------
    # Scenario A: State Isolation during search (GET /api/game/state never mutates during search)
    # -------------------------------------------------------------
    log_test("[TEST 2] State Isolation: FEN Stability during AI Search")
    # Start new game as White, depth 2
    r = requests.post(f"{BASE_URL}/game/new", json={"human_color": "white", "depth": 2})
    assert r.status_code == 200
    init_state = r.json()
    game_id = init_state["game_id"]
    version = init_state["version"]
    print(f"Initialized Game: ID={game_id}, Version={version}")

    # Human plays e2e4
    r = requests.post(
        f"{BASE_URL}/game/move",
        json={"move": "e2e4", "game_id": game_id, "expected_version": version}
    )
    assert r.status_code == 200
    after_human = r.json()
    human_fen = after_human["fen"]
    expected_fen = "rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq - 0 1"
    assert human_fen == expected_fen, f"Expected FEN {expected_fen}, got {human_fen}"
    version = after_human["version"]
    print(f"Human Move e2e4 applied. FEN: {human_fen} (Version: {version})")

    # Launch AI move in background thread
    search_result = {}
    def run_ai_search():
        t0 = time.perf_counter()
        resp = requests.post(
            f"{BASE_URL}/engine/move",
            json={"game_id": game_id, "expected_version": version}
        )
        search_result["status_code"] = resp.status_code
        search_result["data"] = resp.json()
        search_result["time"] = time.perf_counter() - t0

    t_thread = threading.Thread(target=run_ai_search)
    t_thread.start()

    # Repeatedly poll /api/game/state while search is calculating
    poll_fens = []
    poll_count = 0
    while t_thread.is_alive():
        if "data" in search_result:
            break
        r_poll = requests.get(f"{BASE_URL}/game/state")
        assert r_poll.status_code == 200
        data_poll = r_poll.json()
        poll_fens.append(data_poll["fen"])
        poll_count += 1
        time.sleep(0.05)

    t_thread.join()
    assert search_result["status_code"] == 200, f"AI search failed: {search_result}"

    print(f"Polled /api/game/state {poll_count} times during active search.")
    # Verify that all polled FENs during the search were strictly equal to human_fen!
    # Minimax push/pop states must NEVER be observed!
    corrupted_fens = [f for f in poll_fens if f != human_fen]
    assert len(corrupted_fens) == 0, f"Observed {len(corrupted_fens)} unstable FEN states during search: {corrupted_fens[:3]}"
    print("-> PASSED: All intermediate GET /api/game/state calls saw strictly stable authoritative FEN!")

    ai_data = search_result["data"]
    print(f"AI Move Committed: {ai_data['last_move']['san']} ({ai_data['last_move']['uci']})")
    print(f"Search Time: {search_result['time']:.2f}s, Telemetry: {ai_data['telemetry']}")

    # -------------------------------------------------------------
    # Scenario B: Fast Restart During Active Search & Discard Obsolete AI Move
    # -------------------------------------------------------------
    log_test("[TEST 3] Immediate Restart During Active Search & Discard Obsolete Move")
    r = requests.post(f"{BASE_URL}/game/new", json={"human_color": "white", "depth": 2})
    g2_data = r.json()
    g2_id = g2_data["game_id"]
    g2_ver = g2_data["version"]

    # Human plays d2d4
    r = requests.post(f"{BASE_URL}/game/move", json={"move": "d2d4", "game_id": g2_id, "expected_version": g2_ver})
    assert r.status_code == 200
    g2_ver = r.json()["version"]

    # Start AI move in thread
    g2_ai_resp = {}
    def run_g2_search():
        t0 = time.perf_counter()
        resp = requests.post(f"{BASE_URL}/engine/move", json={"game_id": g2_id, "expected_version": g2_ver})
        g2_ai_resp["status_code"] = resp.status_code
        g2_ai_resp["data"] = resp.json()
        g2_ai_resp["time"] = time.perf_counter() - t0

    t_search2 = threading.Thread(target=run_g2_search)
    t_search2.start()

    # Sleep briefly to ensure search is running
    time.sleep(0.1)

    # User clicks New Game while search is active
    t_restart0 = time.perf_counter()
    r_restart = requests.post(f"{BASE_URL}/game/new", json={"human_color": "white", "depth": 2})
    restart_latency = time.perf_counter() - t_restart0

    assert r_restart.status_code == 200
    g3_data = r_restart.json()
    g3_id = g3_data["game_id"]
    print(f"Restart Response Latency: {restart_latency*1000:.2f} ms (Target < 50ms)")
    assert restart_latency < 0.1, f"Restart took too long: {restart_latency}s"
    assert g3_id != g2_id, "New game must have a distinct game_id"

    # Wait for the obsolete search to complete
    t_search2.join()

    # Verify that the active game remains g3_id and has NOT been corrupted by g2 AI move
    r_check = requests.get(f"{BASE_URL}/game/state")
    current_state = r_check.json()
    assert current_state["game_id"] == g3_id, "Active game_id was corrupted by obsolete search!"
    assert current_state["fen"] == "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1", "Active game FEN was corrupted!"
    assert len(current_state["history"]) == 0, "Active game history was corrupted!"
    print("-> PASSED: Restart returned immediately and obsolete AI move was safely discarded!")

    # -------------------------------------------------------------
    # Scenario C: Concurrent Search Rejection
    # -------------------------------------------------------------
    log_test("[TEST 4] Concurrent Search Rejection (409 Conflict)")
    # Human plays e2e4 on g3
    r = requests.post(f"{BASE_URL}/game/move", json={"move": "e2e4", "game_id": g3_id, "expected_version": g3_data["version"]})
    g3_ver = r.json()["version"]

    def run_g3_search():
        requests.post(f"{BASE_URL}/engine/move", json={"game_id": g3_id, "expected_version": g3_ver})

    t_search3 = threading.Thread(target=run_g3_search)
    t_search3.start()
    time.sleep(0.05)

    # Second concurrent search request must be rejected with 409
    r_conflict = requests.post(f"{BASE_URL}/engine/move", json={"game_id": g3_id, "expected_version": g3_ver})
    print(f"Concurrent Search Request Status: {r_conflict.status_code} ({r_conflict.json().get('detail')})")
    assert r_conflict.status_code == 409, f"Expected 409 Conflict, got {r_conflict.status_code}"
    t_search3.join()
    print("-> PASSED: Concurrent engine search strictly rejected with 409 Conflict!")

    # -------------------------------------------------------------
    # Scenario D: Request Versioning Stale Rejection
    # -------------------------------------------------------------
    log_test("[TEST 5] Request Versioning Stale Rejection")
    r_stale = requests.post(
        f"{BASE_URL}/game/move",
        json={"move": "e4e5", "game_id": "stale_game_xyz", "expected_version": 999}
    )
    print(f"Stale Move Request Status: {r_stale.status_code} ({r_stale.json().get('detail')})")
    assert r_stale.status_code == 409, f"Expected 409 Conflict, got {r_stale.status_code}"
    print("-> PASSED: Stale game_id/version rejected with 409 Conflict!")

    # -------------------------------------------------------------
    # Scenario E: Controlled D2 Move & Latency Benchmark
    # -------------------------------------------------------------
    log_test("[TEST 6] Performance & D2 Move Benchmark")
    r_new = requests.post(f"{BASE_URL}/game/new", json={"human_color": "white", "depth": 2})
    bench_id = r_new.json()["game_id"]
    bench_ver = r_new.json()["version"]

    # Play e2e4
    r_m = requests.post(f"{BASE_URL}/game/move", json={"move": "e2e4", "game_id": bench_id, "expected_version": bench_ver})
    bench_ver = r_m.json()["version"]

    # Calculate AI move
    t0 = time.perf_counter()
    r_ai = requests.post(f"{BASE_URL}/engine/move", json={"game_id": bench_id, "expected_version": bench_ver})
    t_total = time.perf_counter() - t0
    assert r_ai.status_code == 200
    ai_state = r_ai.json()
    tel = ai_state["telemetry"]

    ms_per_eval = (tel["search_time"] / tel["neural_evaluations"]) * 1000.0 if tel["neural_evaluations"] > 0 else 0

    print(f"D2 Search Results after 1. e4:")
    print(f"  Chosen AI Move:       {ai_state['last_move']['san']} ({ai_state['last_move']['uci']})")
    print(f"  Evaluation Score:     {tel['evaluation']:.4f}")
    print(f"  Total Search Time:    {tel['search_time']:.2f} s  (HTTP total {t_total:.2f} s)")
    print(f"  Total NN Evaluations: {tel['neural_evaluations']}")
    print(f"  Nodes Visited:        {tel['nodes_visited']}")
    print(f"  Cutoffs:              {tel['cutoffs']}")
    print(f"  Speed (ms / eval):    {ms_per_eval:.2f} ms / NN evaluation")
    print(f"  Speedup vs old 66ms:  {66.12 / ms_per_eval:.2f}x faster!")

    print("\n" + "="*60 + "\nALL STAGE 5 HARDENING VERIFICATIONS PASSED!\n" + "="*60)

if __name__ == "__main__":
    test_stage5_hardening()
