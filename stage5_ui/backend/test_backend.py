"""
Backend smoke test for Stage 5 API and Engine Adapter.
Validates:
1. Health endpoint logic
2. New game creation (White & Black)
3. Move application (Player e2e4 -> Engine reply)
4. Telemetry structure
5. Exhibition data response
"""
import os
import sys

# Ensure backend and root paths are available
backend_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(backend_dir, "..", ".."))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from stage5_ui.backend.game_manager import game_manager
from stage5_ui.backend.engine_adapter import engine_adapter
from stage5_ui.backend.main import app, health, get_exhibition_data


def test_backend_direct():
    print("[1/5] Testing health...")
    h = health()
    print(f"  Health: {h.status}, Python: {h.python_version}, Model loaded: {h.model_loaded}")
    assert h.model_loaded, "Model should be loaded"
    print("  -> Health PASS.")

    print("\n[2/5] Testing new game (Human as White, Depth 1 for speed)...")
    state = game_manager.new_game(human_color_str="white", depth=1)
    print(f"  FEN: {state.fen}")
    print(f"  Turn: {state.turn}, Legal moves count: {len(state.legal_moves)}")
    assert state.turn == "white"
    assert len(state.legal_moves) == 20
    print("  -> New game (White) PASS.")

    print("\n[3/5] Testing move application (e2e4) and AI reply...")
    state_after_move = game_manager.apply_move("e2e4")
    print(f"  Last move: {state_after_move.last_move.uci} ({state_after_move.last_move.san}) by {state_after_move.last_move.color}")
    print(f"  Telemetry: Depth={state_after_move.telemetry.depth}, Eval={state_after_move.telemetry.evaluation:+.4f}, Nodes={state_after_move.telemetry.nodes_visited}, Time={state_after_move.telemetry.search_time:.2f}s")
    print(f"  Board FEN: {state_after_move.fen}")
    assert len(state_after_move.history) == 2, f"Expected 2 plies in history, got {len(state_after_move.history)}"
    assert state_after_move.turn == "white", "Turn should be back to White after AI response"
    print("  -> Move execution PASS.")

    print("\n[4/5] Testing new game (Human as Black, AI should play first move)...")
    state_black = game_manager.new_game(human_color_str="black", depth=1)
    print(f"  AI 1st move: {state_black.last_move.uci} ({state_black.last_move.san})")
    print(f"  Turn: {state_black.turn}")
    assert state_black.turn == "black", "Turn should be Black (human's turn) after AI 1st move"
    assert len(state_black.history) == 1
    print("  -> AI 1st move (Human Black) PASS.")

    print("\n[5/5] Testing exhibition data...")
    exhib = get_exhibition_data()
    assert len(exhib.architecture["stages"]) == 6
    assert exhib.benchmarks["summary"]["depth2_median_cpl"] == 69.5
    print("  -> Exhibition data PASS.")

    print("\n" + "=" * 50)
    print("ALL BACKEND INTEGRATION TESTS PASSED SUCCESSFULLY!")
    print("=" * 50)


if __name__ == "__main__":
    test_backend_direct()
