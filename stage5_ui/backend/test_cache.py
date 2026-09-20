import os
import sys
import time
import chess

sys.path.insert(0, "c:/Users/3mrec/Desktop/chess_bot")
os.chdir("c:/Users/3mrec/Desktop/chess_bot")
import green_team_stage4_fixed as stage4

board = chess.Board()

# Test 1: No eval cache
stage4.clear_tt()
stage4.set_eval_cache_enabled(False)
stage4.reset_search_stats()
t0 = time.perf_counter()
res_no_cache = stage4.iterative_deepening_search(
    board, 2, stage4.model, True, False, True, True
)
t_no_cache = time.perf_counter() - t0

# Test 2: With eval cache
stage4.clear_tt()
stage4.clear_eval_cache()
stage4.set_eval_cache_enabled(True)
stage4.reset_search_stats()
t0 = time.perf_counter()
res_cache = stage4.iterative_deepening_search(
    board, 2, stage4.model, True, False, True, True
)
t_cache = time.perf_counter() - t0

print(f"No eval cache   : {t_no_cache:.3f}s, nodes={res_no_cache['cumulative_nodes']}, evals={res_no_cache['cumulative_nn_evals']}")
print(f"With eval cache : {t_cache:.3f}s, nodes={res_cache['cumulative_nodes']}, evals={res_cache['cumulative_nn_evals']}")
print(f"Move identical  : {res_no_cache['best_move'] == res_cache['best_move']}")
print(f"Score identical : {res_no_cache['best_value'] == res_cache['best_value']}")
