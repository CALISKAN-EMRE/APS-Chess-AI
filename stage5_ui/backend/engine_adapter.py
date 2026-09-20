import os
import sys
import time
from typing import Dict, Any, Tuple, Optional
import chess

# Ensure project root is in sys.path so frozen Stage 4 engine can be imported cleanly
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

# Switch working directory temporarily if needed during module load to locate model zip
_orig_cwd = os.getcwd()
try:
    os.chdir(PROJECT_ROOT)
    import green_team_stage4_fixed as stage4
finally:
    os.chdir(_orig_cwd)


import tensorflow as tf


class CompiledInferenceWrapper:
    """
    Stage-5-only graph-compiled inference wrapper using @tf.function(reduce_retracing=True).
    Eliminates Python Keras layer-traversal overhead during minimax search.
    Numerically equivalent to eager execution (max abs diff < 2e-7).
    """

    def __init__(self, raw_model):
        self._raw_model = raw_model

        @tf.function(reduce_retracing=True)
        def _infer(tensor_batch):
            return self._raw_model(tensor_batch, training=False)

        self._infer = _infer

    def __call__(self, tensor_batch, training=False):
        return self._infer(tensor_batch)

    def __getattr__(self, name):
        return getattr(self._raw_model, name)


class EngineAdapter:
    """
    Thin, read-only adapter interfacing with the frozen Stage 4 engine.
    Does not modify any search internals, minimax routines, or neural weights.
    """

    def __init__(self):
        self.raw_model = stage4.model
        self.model = CompiledInferenceWrapper(self.raw_model)
        self.reset_for_new_game()

    def reset_for_new_game(self) -> None:
        """Resets the transposition table, cache, and search counters for a new game."""
        stage4.clear_tt()
        stage4.set_eval_cache_enabled(False)
        stage4.clear_eval_cache()
        stage4.reset_search_stats()

    def compute_ai_move(self, board: chess.Board, depth: int = 2) -> Tuple[Optional[chess.Move], Dict[str, Any]]:
        """
        Executes an iterative deepening PVS search on the frozen Stage 4 engine.
        Returns: (best_move, telemetry_dict)
        """
        stage4.reset_search_stats()
        t0 = time.perf_counter()

        id_res = stage4.iterative_deepening_search(
            board=board,
            max_depth=depth,
            model=self.model,
            propagate_root_bounds=True,
            randomize_equal_moves=False,
            use_tt=True,
            use_pvs=True,
        )

        elapsed = time.perf_counter() - t0
        best_move = id_res.get("best_move")
        best_val = float(id_res.get("best_value", 0.0))

        telemetry = {
            "depth": depth,
            "evaluation": best_val,
            "search_time": elapsed,
            "nodes_visited": int(id_res.get("cumulative_nodes", 0)),
            "neural_evaluations": int(id_res.get("cumulative_nn_evals", 0)),
            "cutoffs": int(id_res.get("cumulative_cutoffs", 0)),
            "best_move_uci": best_move.uci() if best_move else None,
            "best_move_san": board.san(best_move) if best_move and best_move in board.legal_moves else None,
            "pvs_narrow_searches": int(stage4.search_stats.get("pvs_narrow_searches", 0)),
            "pvs_researches": int(stage4.search_stats.get("pvs_researches", 0)),
        }

        return best_move, telemetry

    def check_termination(self, board: chess.Board) -> Tuple[bool, Optional[str], str]:
        """
        Delegates game termination detection to Stage 4 check_game_termination:
        Returns: (is_over, reason, result_str)
        """
        return stage4.check_game_termination(board)

    def warm_up(self) -> float:
        """
        Executes a safe single inference using the validated direct-inference path
        to warm up TensorFlow graph compilation and oneDNN threads at server startup.
        """
        dummy_board = chess.Board()
        tensor = stage4.board_to_tensor(dummy_board)
        import numpy as np
        batch = np.expand_dims(tensor, axis=0)
        t0 = time.perf_counter()
        _ = self.model(batch, training=False)
        warmup_ms = (time.perf_counter() - t0) * 1000.0
        print(f"[ENGINE WARMUP] Direct-inference warm-up completed in {warmup_ms:.2f} ms")
        return warmup_ms

    def get_system_info(self) -> Dict[str, Any]:
        """Returns model metadata and environment information."""
        return {
            "model_input_shape": list(self.model.input_shape) if hasattr(self.model, "input_shape") else None,
            "model_output_shape": list(self.model.output_shape) if hasattr(self.model, "output_shape") else None,
            "tf_version": stage4.tf.__version__,
            "devices": [d.name for d in stage4.tf.config.list_physical_devices()],
        }


# Singleton engine adapter instance
engine_adapter = EngineAdapter()

