import sys
import os
import time
import chess
import numpy as np

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

os.chdir(PROJECT_ROOT)
import green_team_stage4_fixed as stage4

def main():
    print(f"Python interpreter : {sys.executable}")
    print(f"Python version     : {sys.version.split()[0]}")
    print(f"Process PID        : {os.getpid()}")
    print(f"TensorFlow version : {stage4.tf.__version__}")
    print(f"Physical devices   : {[d.name for d in stage4.tf.config.list_physical_devices()]}")

    board = chess.Board()
    tensor = stage4.board_to_tensor(board)
    batch = np.expand_dims(tensor, axis=0)

    # 1. Measure raw first inference
    t0 = time.perf_counter()
    _ = stage4.model(batch, training=False)
    t_first_ms = (time.perf_counter() - t0) * 1000.0
    print(f"First NN inference (cold trace) : {t_first_ms:.2f} ms")

    # 2. Measure subsequent 100 inferences
    t0 = time.perf_counter()
    for _ in range(100):
        _ = stage4.model(batch, training=False)
    t_100_ms = (time.perf_counter() - t0) * 1000.0
    avg_nn_ms = t_100_ms / 100.0
    print(f"100 subsequent NN inferences    : {t_100_ms:.2f} ms total, {avg_nn_ms:.2f} ms/call")

    # 3. Depth-2 search 1 (cold TT)
    stage4.clear_tt()
    stage4.set_eval_cache_enabled(False)
    stage4.reset_search_stats()
    t0 = time.perf_counter()
    res1 = stage4.iterative_deepening_search(
        board=board,
        max_depth=2,
        model=stage4.model,
        propagate_root_bounds=True,
        randomize_equal_moves=False,
        use_tt=True,
        use_pvs=True,
    )
    t_search1 = time.perf_counter() - t0
    nodes1 = res1.get("cumulative_nodes", 0)
    nn_evals1 = res1.get("cumulative_nn_evals", 0)
    print(f"Depth-2 Search 1 (cold TT)      : {t_search1:.2f} s ({nodes1} nodes, {nn_evals1} NN evals)")

    # 4. Depth-2 search 2 (different position, e.g. after 1. e4)
    board.push_san("e4")
    stage4.clear_tt()
    stage4.set_eval_cache_enabled(False)
    stage4.reset_search_stats()
    t0 = time.perf_counter()
    res2 = stage4.iterative_deepening_search(
        board=board,
        max_depth=2,
        model=stage4.model,
        propagate_root_bounds=True,
        randomize_equal_moves=False,
        use_tt=True,
        use_pvs=True,
    )
    t_search2 = time.perf_counter() - t0
    nodes2 = res2.get("cumulative_nodes", 0)
    nn_evals2 = res2.get("cumulative_nn_evals", 0)
    print(f"Depth-2 Search 2 (after 1. e4)  : {t_search2:.2f} s ({nodes2} nodes, {nn_evals2} NN evals)")

if __name__ == "__main__":
    main()
