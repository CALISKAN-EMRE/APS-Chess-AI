import math
import os
import random
import shutil
import sys
import tempfile
import time

# Ensure proper utf-8 encoding on Windows console
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

import chess
import numpy as np
import tensorflow as tf


# ------------------------------------------------------------
# 1) MODEL LOADING
# ------------------------------------------------------------
# Put the shared Keras model file next to this script.
# If WhatsApp/Drive downloaded it as *.keras.zip, this loader handles it too.
MODEL_PATH = "chess_value_model.keras.zip"


def load_chess_model(path: str):
    if not os.path.exists(path):
        raise FileNotFoundError(
            f"Model bulunamadı: {path}\n"
            "MODEL_PATH değişkenini paylaşılan model dosyasının adına göre düzeltin."
        )

    # Keras v3 files are ZIP archives internally, but load_model normally expects
    # the .keras extension. If the file arrived as .zip, make a temporary .keras copy.
    if path.lower().endswith(".zip"):
        temp_dir = tempfile.mkdtemp(prefix="chess_model_")
        temp_path = os.path.join(temp_dir, "chess_value_model.keras")
        shutil.copyfile(path, temp_path)
        try:
            return tf.keras.models.load_model(temp_path, compile=False)
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    return tf.keras.models.load_model(path, compile=False)


model = load_chess_model(MODEL_PATH)
print("Model yüklendi.")
print("Girdi şekli:", model.input_shape)
print("Çıktı şekli:", model.output_shape)


# ------------------------------------------------------------
# 2) BOARD -> 8x8x12 TENSOR
# ------------------------------------------------------------
def board_to_tensor(board: chess.Board) -> np.ndarray:
    """
    Mavi ekibin veri encoding'i ile aynı mantık:
      channel 0..5  : white pawn, knight, bishop, rook, queen, king
      channel 6..11 : black pawn, knight, bishop, rook, queen, king

    Dataset diskte int8 olabilir; model girdisinin float32 olması normaldir.
    Değerler yine 0/1'dir.
    """
    tensor = np.zeros((8, 8, 12), dtype=np.float32)

    for square in chess.SQUARES:
        piece = board.piece_at(square)
        if piece is None:
            continue

        piece_type = piece.piece_type - 1
        color_offset = 0 if piece.color == chess.WHITE else 6
        channel = piece_type + color_offset

        # Dataset orientation: black back rank at row 0, white back rank at row 7.
        row = 7 - chess.square_rank(square)
        col = chess.square_file(square)
        tensor[row, col, channel] = 1.0

    return tensor


# ------------------------------------------------------------
# 3) POSITION EVALUATION & BOUNDED NN EVALUATION CACHE
# ------------------------------------------------------------
MATE_SCORE = 10.0
MAX_EVAL_CACHE_SIZE = 200_000
EVAL_CACHE_ENABLED = True

# Bounded evaluation cache for non-terminal positions:
# Key: board.board_fen() (piece placement only) -> Value: float (raw model output)
eval_cache = {}
eval_cache_stats = {
    "hits": 0,
    "misses": 0,
}

# Transposition Table (TT)
TT_ENABLED = True
tt_table = {}


def clear_tt():
    global tt_table
    tt_table.clear()


def set_tt_enabled(enabled: bool):
    global TT_ENABLED
    TT_ENABLED = enabled


def is_repetition_sensitive(board: chess.Board) -> bool:
    """
    Returns True if position depends on repetition history or 50-move clock.
    Bypasses TT lookup/store to guarantee 100% safe claim_draw=True semantics.
    """
    return (
        board.is_repetition(2)
        or board.can_claim_threefold_repetition()
        or board.can_claim_fifty_moves()
        or board.halfmove_clock >= 80
    )


def make_tt_key(board: chess.Board):
    """
    Constructs a complete hashable transposition key distinguishing:
    - piece placement (bitboards for pawns, knights, bishops, rooks, queens, kings)
    - occupied squares per color
    - side to move (turn)
    - clean castling rights
    - en-passant square (only if legal en-passant capture is available)
    """
    return board._transposition_key()


# Principal Variation Search (PVS) settings
PVS_ENABLED = False
PVS_EPSILON = 1e-7


def set_pvs_enabled(enabled: bool):
    global PVS_ENABLED
    PVS_ENABLED = enabled


# Search instrumentation stats
search_stats = {
    "nodes_visited": 0,
    "neural_evaluations": 0,
    "alpha_beta_cutoffs": 0,
    "tt_probes": 0,
    "tt_hits": 0,
    "usable_tt_hits": 0,
    "tt_cutoffs": 0,
    "tt_move_ordering_hits": 0,
    "tt_stores": 0,
    "pvs_narrow_searches": 0,
    "pvs_researches": 0,
}

tt_stats_by_depth = {
    d: {"probes": 0, "hits": 0, "usable_hits": 0, "cutoffs": 0, "ordering_hits": 0, "stores": 0}
    for d in range(1, 10)
}


def clear_eval_cache():
    global eval_cache
    eval_cache.clear()
    eval_cache_stats["hits"] = 0
    eval_cache_stats["misses"] = 0


def set_eval_cache_enabled(enabled: bool):
    global EVAL_CACHE_ENABLED
    EVAL_CACHE_ENABLED = enabled


def reset_search_stats():
    search_stats["nodes_visited"] = 0
    search_stats["neural_evaluations"] = 0
    search_stats["alpha_beta_cutoffs"] = 0
    search_stats["tt_probes"] = 0
    search_stats["tt_hits"] = 0
    search_stats["usable_tt_hits"] = 0
    search_stats["tt_cutoffs"] = 0
    search_stats["tt_move_ordering_hits"] = 0
    search_stats["tt_stores"] = 0
    search_stats["pvs_narrow_searches"] = 0
    search_stats["pvs_researches"] = 0
    global tt_stats_by_depth
    tt_stats_by_depth = {
        d: {"probes": 0, "hits": 0, "usable_hits": 0, "cutoffs": 0, "ordering_hits": 0, "stores": 0}
        for d in range(1, 10)
    }


def get_eval_cache_stats():
    hits = eval_cache_stats["hits"]
    misses = eval_cache_stats["misses"]
    total = hits + misses
    hit_rate = (hits / total) if total > 0 else 0.0
    return {
        "hits": hits,
        "misses": misses,
        "total_lookups": total,
        "hit_rate": hit_rate,
        "cache_size": len(eval_cache),
        "max_size": MAX_EVAL_CACHE_SIZE,
    }


def evaluate_position(board: chess.Board, model) -> float:
    """
    Positive -> white is better.
    Negative -> black is better.

    Important: terminal positions are handled explicitly. Otherwise a checkmate
    could be evaluated only by the neural network and the search might fail to
    strongly prefer a forced mate.
    """
    # 1. Terminal checks MUST remain before cache lookup
    if board.is_checkmate():
        # Side to move is checkmated.
        return -MATE_SCORE if board.turn == chess.WHITE else MATE_SCORE

    if (
        board.is_stalemate()
        or board.is_insufficient_material()
        or board.can_claim_threefold_repetition()
        or board.is_fivefold_repetition()
        or board.can_claim_fifty_moves()
        or board.is_seventyfive_moves()
    ):
        return 0.0

    # 2. Non-terminal NN evaluation cache lookup (keyed by piece placement)
    if EVAL_CACHE_ENABLED:
        key = board.board_fen()
        if key in eval_cache:
            eval_cache_stats["hits"] += 1
            return eval_cache[key]
        eval_cache_stats["misses"] += 1

    search_stats["neural_evaluations"] += 1
    tensor = board_to_tensor(board)
    tensor_batch = np.expand_dims(tensor, axis=0)
    prediction = model(tensor_batch, training=False)
    val = float(prediction[0][0])

    if EVAL_CACHE_ENABLED:
        if len(eval_cache) >= MAX_EVAL_CACHE_SIZE:
            eval_cache.pop(next(iter(eval_cache)))
        eval_cache[key] = val

    return val


# ------------------------------------------------------------
# 4) MOVE ORDERING (helps alpha-beta prune earlier)
# ------------------------------------------------------------
def ordered_legal_moves(board: chess.Board):
    moves = list(board.legal_moves)

    def score(move):
        s = 0
        if board.is_capture(move):
            s += 100
        if move.promotion:
            s += 80

        board.push(move)
        if board.is_check():
            s += 50
        board.pop()
        return s

    moves.sort(key=score, reverse=True)
    return moves


# ------------------------------------------------------------
# 5) ALPHA-BETA BOUND TYPES & MINIMAX
# ------------------------------------------------------------
EXACT = "EXACT"
LOWER_BOUND = "LOWER_BOUND"  # Fail-high: true_val >= value
UPPER_BOUND = "UPPER_BOUND"  # Fail-low: true_val <= value


def minimax(
    board: chess.Board,
    depth: int,
    alpha: float,
    beta: float,
    model,
    use_tt: bool = True,
    use_pvs: bool = False,
) -> tuple[float, str]:
    search_stats["nodes_visited"] += 1

    if depth == 0 or board.is_game_over(claim_draw=True):
        return evaluate_position(board, model), EXACT

    tt_key = None
    tt_move = None
    tt_bound = None
    tt_val = None

    if use_tt and TT_ENABLED and not is_repetition_sensitive(board):
        tt_key = make_tt_key(board)
        search_stats["tt_probes"] += 1
        if depth in tt_stats_by_depth:
            tt_stats_by_depth[depth]["probes"] += 1

        entry = tt_table.get(tt_key)
        if entry is not None:
            search_stats["tt_hits"] += 1
            if depth in tt_stats_by_depth:
                tt_stats_by_depth[depth]["hits"] += 1
            stored_depth, stored_val, stored_bound, stored_best_move = entry
            tt_move = stored_best_move
            tt_bound = stored_bound
            tt_val = stored_val

            # TT lookup rules:
            # 1. Only reuse entry if stored search depth is at least requested depth
            if stored_depth >= depth:
                search_stats["usable_tt_hits"] += 1
                if depth in tt_stats_by_depth:
                    tt_stats_by_depth[depth]["usable_hits"] += 1
                # 2. EXACT may return immediately
                if stored_bound == EXACT:
                    search_stats["tt_cutoffs"] += 1
                    search_stats["alpha_beta_cutoffs"] += 1
                    if depth in tt_stats_by_depth:
                        tt_stats_by_depth[depth]["cutoffs"] += 1
                    return stored_val, EXACT
                # 3. LOWER_BOUND may raise alpha
                elif stored_bound == LOWER_BOUND:
                    alpha = max(alpha, stored_val)
                # 4. UPPER_BOUND may lower beta
                elif stored_bound == UPPER_BOUND:
                    beta = min(beta, stored_val)

                # 5. If resulting window closes, allow normal alpha-beta cutoff
                if alpha >= beta:
                    search_stats["tt_cutoffs"] += 1
                    search_stats["alpha_beta_cutoffs"] += 1
                    if depth in tt_stats_by_depth:
                        tt_stats_by_depth[depth]["cutoffs"] += 1
                    return stored_val, stored_bound

    moves = ordered_legal_moves(board)
    if not moves:
        return evaluate_position(board, model), EXACT

    # 6. Use TT best_move as first move in move ordering when legal
    if tt_move is not None and tt_move in moves:
        search_stats["tt_move_ordering_hits"] += 1
        if depth in tt_stats_by_depth:
            tt_stats_by_depth[depth]["ordering_hits"] += 1
        moves.remove(tt_move)
        moves.insert(0, tt_move)

    best_move_found = moves[0]

    # White maximizes the value-network score; black minimizes it.
    if board.turn == chess.WHITE:
        best = -math.inf
        original_alpha = alpha
        cutoff = False
        for i, move in enumerate(moves):
            board.push(move)
            if not use_pvs or i == 0 or alpha <= original_alpha or alpha >= beta:
                value, bound = minimax(board, depth - 1, alpha, beta, model, use_tt=use_tt, use_pvs=use_pvs)
            else:
                # PVS: scout search with null/narrow window
                search_stats["pvs_narrow_searches"] += 1
                narrow_beta = min(beta, alpha + PVS_EPSILON)
                value, bound = minimax(board, depth - 1, alpha, narrow_beta, model, use_tt=use_tt, use_pvs=use_pvs)
                if value > alpha and narrow_beta < beta:
                    # Move improved over alpha: re-search with full alpha-beta window
                    search_stats["pvs_researches"] += 1
                    if use_tt and not is_repetition_sensitive(board):
                        tt_table.pop(make_tt_key(board), None)
                    value, bound = minimax(board, depth - 1, alpha, beta, model, use_tt=use_tt, use_pvs=use_pvs)
            board.pop()

            if value > best:
                best = value
                best_move_found = move
            if best > alpha:
                alpha = best
            if alpha >= beta:
                search_stats["alpha_beta_cutoffs"] += 1
                cutoff = True
                break

        if cutoff:
            bound_type = LOWER_BOUND
        elif best <= original_alpha:
            bound_type = UPPER_BOUND
        else:
            bound_type = EXACT

    else:
        best = math.inf
        original_beta = beta
        cutoff = False
        for i, move in enumerate(moves):
            board.push(move)
            if not use_pvs or i == 0 or beta >= original_beta or alpha >= beta:
                value, bound = minimax(board, depth - 1, alpha, beta, model, use_tt=use_tt, use_pvs=use_pvs)
            else:
                # PVS: scout search with null/narrow window
                search_stats["pvs_narrow_searches"] += 1
                narrow_alpha = max(alpha, beta - PVS_EPSILON)
                value, bound = minimax(board, depth - 1, narrow_alpha, beta, model, use_tt=use_tt, use_pvs=use_pvs)
                if value < beta and narrow_alpha > alpha:
                    # Move improved over beta: re-search with full alpha-beta window
                    search_stats["pvs_researches"] += 1
                    if use_tt and not is_repetition_sensitive(board):
                        tt_table.pop(make_tt_key(board), None)
                    value, bound = minimax(board, depth - 1, alpha, beta, model, use_tt=use_tt, use_pvs=use_pvs)
            board.pop()

            if value < best:
                best = value
                best_move_found = move
            if best < beta:
                beta = best
            if alpha >= beta:
                search_stats["alpha_beta_cutoffs"] += 1
                cutoff = True
                break

        if cutoff:
            bound_type = UPPER_BOUND
        elif best >= original_beta:
            bound_type = LOWER_BOUND
        else:
            bound_type = EXACT

    # Store search result in Transposition Table
    if use_tt and TT_ENABLED and tt_key is not None:
        tt_table[tt_key] = (depth, best, bound_type, best_move_found)
        search_stats["tt_stores"] += 1
        if depth in tt_stats_by_depth:
            tt_stats_by_depth[depth]["stores"] += 1

    return best, bound_type


# ------------------------------------------------------------
# 6) BEST MOVE & ITERATIVE DEEPENING
# ------------------------------------------------------------
def get_best_move(
    board: chess.Board,
    depth: int,
    model,
    propagate_root_bounds: bool = True,
    previous_best_move: chess.Move = None,
    randomize_equal_moves: bool = False,
    use_tt: bool = True,
    use_pvs: bool = False,
):
    search_stats["nodes_visited"] += 1
    moves = ordered_legal_moves(board)
    if not moves:
        return None, None

    tt_key = None
    tt_move = None

    if use_tt and TT_ENABLED and not is_repetition_sensitive(board):
        tt_key = make_tt_key(board)
        search_stats["tt_probes"] += 1
        if depth in tt_stats_by_depth:
            tt_stats_by_depth[depth]["probes"] += 1
        entry = tt_table.get(tt_key)
        if entry is not None:
            search_stats["tt_hits"] += 1
            if depth in tt_stats_by_depth:
                tt_stats_by_depth[depth]["hits"] += 1
            stored_depth, stored_val, stored_bound, stored_best_move = entry
            tt_move = stored_best_move
            if stored_depth >= depth and stored_bound == EXACT and stored_best_move in moves:
                search_stats["usable_tt_hits"] += 1
                search_stats["tt_cutoffs"] += 1
                if depth in tt_stats_by_depth:
                    tt_stats_by_depth[depth]["usable_hits"] += 1
                    tt_stats_by_depth[depth]["cutoffs"] += 1
                return stored_best_move, float(stored_val)

    # Use TT move or previous_best_move as first move in root move ordering
    preferred_move = tt_move if (tt_move is not None and tt_move in moves) else previous_best_move
    if preferred_move is not None and preferred_move in moves:
        if preferred_move == tt_move:
            search_stats["tt_move_ordering_hits"] += 1
            if depth in tt_stats_by_depth:
                tt_stats_by_depth[depth]["ordering_hits"] += 1
        moves.remove(preferred_move)
        moves.insert(0, preferred_move)

    white_to_move = board.turn == chess.WHITE
    best_value = -math.inf if white_to_move else math.inf
    best_moves = []

    # Initialize root alpha/beta window
    alpha = -math.inf
    beta = math.inf

    for i, move in enumerate(moves):
        board.push(move)
        if not use_pvs or i == 0 or (white_to_move and alpha == -math.inf) or (not white_to_move and beta == math.inf):
            if propagate_root_bounds:
                value, bound_type = minimax(board, depth - 1, alpha, beta, model, use_tt=use_tt, use_pvs=use_pvs)
            else:
                value, bound_type = minimax(board, depth - 1, -math.inf, math.inf, model, use_tt=use_tt, use_pvs=use_pvs)
        else:
            # PVS root narrow-window scout search
            search_stats["pvs_narrow_searches"] += 1
            if white_to_move:
                narrow_beta = min(beta, alpha + PVS_EPSILON)
                value, bound_type = minimax(board, depth - 1, alpha, narrow_beta, model, use_tt=use_tt, use_pvs=use_pvs)
                if value > alpha and narrow_beta < beta:
                    search_stats["pvs_researches"] += 1
                    if use_tt and not is_repetition_sensitive(board):
                        tt_table.pop(make_tt_key(board), None)
                    value, bound_type = minimax(board, depth - 1, alpha, beta, model, use_tt=use_tt, use_pvs=use_pvs)
            else:
                narrow_alpha = max(alpha, beta - PVS_EPSILON)
                value, bound_type = minimax(board, depth - 1, narrow_alpha, beta, model, use_tt=use_tt, use_pvs=use_pvs)
                if value < beta and narrow_alpha > alpha:
                    search_stats["pvs_researches"] += 1
                    if use_tt and not is_repetition_sensitive(board):
                        tt_table.pop(make_tt_key(board), None)
                    value, bound_type = minimax(board, depth - 1, alpha, beta, model, use_tt=use_tt, use_pvs=use_pvs)
        board.pop()

        if white_to_move:
            # White maximizes root:
            # Only exact values can be used for tie comparison.
            # A cutoff (UPPER_BOUND) proves this move cannot beat best_value (true score <= value <= best_value).
            # It must not enter best_moves.
            if bound_type == EXACT:
                if np.isclose(value, best_value, rtol=0.0, atol=1e-7):
                    best_moves.append(move)
                elif value > best_value:
                    best_value = value
                    best_moves = [move]
            elif bound_type == LOWER_BOUND:
                if value > best_value and not np.isclose(value, best_value, rtol=0.0, atol=1e-7):
                    best_value = value
                    best_moves = [move]
        else:
            # Black minimizes root:
            # Only exact values can be used for tie comparison.
            # A cutoff (LOWER_BOUND) proves this move cannot beat best_value (true score >= value >= best_value).
            # It must not enter best_moves.
            if bound_type == EXACT:
                if np.isclose(value, best_value, rtol=0.0, atol=1e-7):
                    best_moves.append(move)
                elif value < best_value:
                    best_value = value
                    best_moves = [move]
            elif bound_type == UPPER_BOUND:
                if value < best_value and not np.isclose(value, best_value, rtol=0.0, atol=1e-7):
                    best_value = value
                    best_moves = [move]

        # Update root bounds after evaluating each root move
        if propagate_root_bounds:
            if white_to_move:
                alpha = max(alpha, best_value)
            else:
                beta = min(beta, best_value)

    if randomize_equal_moves:
        chosen_move = random.choice(best_moves)
    else:
        # Deterministic tie-breaking: first move according to existing root move ordering
        chosen_move = best_moves[0]

    # Store root evaluation in TT
    if use_tt and TT_ENABLED and tt_key is not None:
        tt_table[tt_key] = (depth, best_value, EXACT, chosen_move)
        search_stats["tt_stores"] += 1
        if depth in tt_stats_by_depth:
            tt_stats_by_depth[depth]["stores"] += 1

    return chosen_move, float(best_value)


def iterative_deepening_search(
    board: chess.Board,
    max_depth: int,
    model,
    propagate_root_bounds: bool = True,
    randomize_equal_moves: bool = False,
    use_tt: bool = True,
    use_pvs: bool = False,
):
    """
    Iterative deepening search wrapper:
    Searches depth 1, depth 2, ..., up to max_depth.
    Uses the best move from the previous completed depth (or TT move) as the first root move at the next depth.
    Instruments each depth separately and tracks cumulative stats.
    """
    depth_records = []
    previous_best_move = None
    cumulative_time = 0.0
    cumulative_nodes = 0
    cumulative_nn_evals = 0
    cumulative_cutoffs = 0

    best_move = None
    best_value = 0.0

    for d in range(1, max_depth + 1):
        nodes_before = search_stats["nodes_visited"]
        nn_before = search_stats["neural_evaluations"]
        cutoffs_before = search_stats["alpha_beta_cutoffs"]
        pvs_narrow_before = search_stats["pvs_narrow_searches"]
        pvs_re_before = search_stats["pvs_researches"]

        t0 = time.perf_counter()
        best_move, best_value = get_best_move(
            board,
            depth=d,
            model=model,
            propagate_root_bounds=propagate_root_bounds,
            previous_best_move=previous_best_move,
            randomize_equal_moves=randomize_equal_moves,
            use_tt=use_tt,
            use_pvs=use_pvs,
        )
        t1 = time.perf_counter()

        elapsed = t1 - t0
        d_nodes = search_stats["nodes_visited"] - nodes_before
        d_nn_evals = search_stats["neural_evaluations"] - nn_before
        d_cutoffs = search_stats["alpha_beta_cutoffs"] - cutoffs_before
        d_pvs_narrow = search_stats["pvs_narrow_searches"] - pvs_narrow_before
        d_pvs_re = search_stats["pvs_researches"] - pvs_re_before

        cumulative_time += elapsed
        cumulative_nodes += d_nodes
        cumulative_nn_evals += d_nn_evals
        cumulative_cutoffs += d_cutoffs

        record = {
            "depth": d,
            "best_move": best_move,
            "best_value": best_value,
            "elapsed_time": elapsed,
            "nodes_visited": d_nodes,
            "neural_evaluations": d_nn_evals,
            "alpha_beta_cutoffs": d_cutoffs,
            "pvs_narrow_searches": d_pvs_narrow,
            "pvs_researches": d_pvs_re,
            "cumulative_time": cumulative_time,
            "cumulative_nodes": cumulative_nodes,
            "cumulative_nn_evals": cumulative_nn_evals,
            "cumulative_cutoffs": cumulative_cutoffs,
            "cumulative_pvs_narrow": search_stats["pvs_narrow_searches"],
            "cumulative_pvs_researches": search_stats["pvs_researches"],
        }
        depth_records.append(record)
        previous_best_move = best_move

    return {
        "best_move": best_move,
        "best_value": best_value,
        "depth_records": depth_records,
        "final_depth_record": depth_records[-1] if depth_records else None,
        "cumulative_time": cumulative_time,
        "cumulative_nodes": cumulative_nodes,
        "cumulative_nn_evals": cumulative_nn_evals,
        "cumulative_cutoffs": cumulative_cutoffs,
        "pvs_narrow_searches": search_stats["pvs_narrow_searches"],
        "pvs_researches": search_stats["pvs_researches"],
    }


# ------------------------------------------------------------
# 7) QUICK TEST: AI vs RANDOM
# ------------------------------------------------------------
def ai_vs_random(model, depth=1, ai_color=chess.WHITE, max_plies=600):
    board = chess.Board()
    ply = 0

    while not board.is_game_over(claim_draw=True) and ply < max_plies:
        ply += 1
        print("\n" + "=" * 50)
        print(f"Ply {ply} | {'White' if board.turn else 'Black'} to move")

        if board.turn == ai_color:
            start = time.time()
            move, value = get_best_move(board, depth, model)
            elapsed = time.time() - start
            print(f"AI move: {move} | eval: {value:+.4f} | time: {elapsed:.2f}s")
        else:
            move = random.choice(list(board.legal_moves))
            print(f"Random move: {move}")

        if move is None:
            break

        board.push(move)
        print(board)

    print("\nGame over")
    print("Result:", board.result(claim_draw=True))
    print("Final FEN:", board.fen())
    print("\n--- DRAW / GAME END DEBUG ---")
    print("Checkmate:", board.is_checkmate())
    print("Stalemate:", board.is_stalemate())
    print("Insufficient material:", board.is_insufficient_material())

    print("Can claim 3-fold repetition:", board.can_claim_threefold_repetition())
    print("Fivefold repetition:", board.is_fivefold_repetition())

    print("Can claim 50 moves:", board.can_claim_fifty_moves())
    print("75-move rule:", board.is_seventyfive_moves())

    print("Game over (strict):", board.is_game_over())
    print("Game over (claim_draw=True):", board.is_game_over(claim_draw=True))

    print("Result (strict):", board.result())
    print("Result (claim_draw=True):", board.result(claim_draw=True))

    print("Outcome (strict):", board.outcome())
    print("Outcome (claim_draw=True):", board.outcome(claim_draw=True))
    return board


# ------------------------------------------------------------
# 8) BENCHMARK: MULTI-GAME AI vs RANDOM
# ------------------------------------------------------------
def run_benchmark(
    model,
    num_games: int = 20,
    depth: int = 1,
    alternate_colors: bool = True,
    ai_color: chess.Color = chess.WHITE,
    max_plies: int = 600,
    use_cache: bool = False,
    random_seed: int = None,
    propagate_root_bounds: bool = True,
):
    """
    Runs a benchmark of multiple games between the AI and a Random bot.
    If alternate_colors=True (default):
      - Odd-numbered games (1, 3, 5...): AI plays White, Random plays Black.
      - Even-numbered games (2, 4, 6...): AI plays Black, Random plays White.
    Tracks wins, specific draw reasons, average game length, AI calculation time,
    and search instrumentation.
    """
    if random_seed is not None:
        random.seed(random_seed)
        np.random.seed(random_seed)

    set_eval_cache_enabled(use_cache)
    clear_eval_cache()
    reset_search_stats()

    stats = {
        "games_played": 0,
        "ai_wins": 0,
        "ai_wins_white": 0,
        "ai_wins_black": 0,
        "random_wins": 0,
        "random_wins_white": 0,
        "random_wins_black": 0,
        "draws": 0,
        "timeouts": 0,
        # Termination reasons (each game maps to exactly one of these):
        "checkmate": 0,
        "stalemate": 0,
        "insufficient_material": 0,
        "threefold_repetition": 0,
        "fivefold_repetition": 0,
        "fifty_move_claim": 0,
        "seventy_five_move_rule": 0,
        "max_ply_timeout": 0,
        "total_plies": 0,
        "total_ai_moves": 0,
        "total_ai_time": 0.0,
        "game_records": [],
    }

    mode_str = "Alternating (Odd: White, Even: Black)" if alternate_colors else f"Fixed AI Color ({'White' if ai_color == chess.WHITE else 'Black'})"
    cache_status_str = "ENABLED" if use_cache else "DISABLED"
    root_bounds_str = "PROPAGATED" if propagate_root_bounds else "RESET (-inf, +inf)"

    print(f"\n{'=' * 65}")
    print(f" STARTING BENCHMARK: {num_games} Games")
    print(f" Color Mode: {mode_str}")
    print(f" Search Depth: {depth} | Max Plies per game: {max_plies}")
    print(f" Root Bounds: {root_bounds_str} | Eval Cache: {cache_status_str} | Seed: {random_seed}")
    print(f"{'=' * 65}\n")

    for game_idx in range(1, num_games + 1):
        if alternate_colors:
            current_ai_color = chess.WHITE if (game_idx % 2 == 1) else chess.BLACK
        else:
            current_ai_color = ai_color

        current_opp_color = chess.BLACK if current_ai_color == chess.WHITE else chess.WHITE
        ai_col_str = "White" if current_ai_color == chess.WHITE else "Black"

        board = chess.Board()
        ply = 0
        game_ai_time = 0.0
        game_ai_moves = 0

        while not board.is_game_over(claim_draw=True) and ply < max_plies:
            ply += 1
            if board.turn == current_ai_color:
                t0 = time.perf_counter()
                move, value = get_best_move(
                    board, depth, model, propagate_root_bounds=propagate_root_bounds
                )
                t1 = time.perf_counter()
                elapsed = t1 - t0
                game_ai_time += elapsed
                game_ai_moves += 1
            else:
                move = random.choice(list(board.legal_moves))

            if move is None:
                break

            board.push(move)

        # Classify game outcome and termination reason into exactly one category.
        # Order matters to prevent double counting:
        # 1. Checkmate takes absolute precedence.
        # 2. Fivefold repetition takes precedence over threefold repetition.
        # 3. 75-move rule takes precedence over 50-move claim.
        # 4. Max-ply timeout is tracked as a timeout, NOT as a draw.
        is_checkmate = board.is_checkmate()
        is_stalemate = board.is_stalemate()
        is_insufficient = board.is_insufficient_material()
        is_fivefold = board.is_fivefold_repetition()
        can_threefold = board.can_claim_threefold_repetition()
        is_seventyfive = board.is_seventyfive_moves()
        can_fifty = board.can_claim_fifty_moves()

        if is_checkmate:
            stats["checkmate"] += 1
            reason_str = "Checkmate"
            winner = chess.BLACK if board.turn == chess.WHITE else chess.WHITE
            if winner == current_ai_color:
                outcome_str = "AI Win"
                stats["ai_wins"] += 1
                if current_ai_color == chess.WHITE:
                    stats["ai_wins_white"] += 1
                else:
                    stats["ai_wins_black"] += 1
            else:
                outcome_str = "Random Win"
                stats["random_wins"] += 1
                if current_opp_color == chess.WHITE:
                    stats["random_wins_white"] += 1
                else:
                    stats["random_wins_black"] += 1
        elif is_stalemate:
            stats["draws"] += 1
            stats["stalemate"] += 1
            outcome_str = "Draw"
            reason_str = "Stalemate"
        elif is_insufficient:
            stats["draws"] += 1
            stats["insufficient_material"] += 1
            outcome_str = "Draw"
            reason_str = "Insufficient material"
        elif is_fivefold:
            stats["draws"] += 1
            stats["fivefold_repetition"] += 1
            outcome_str = "Draw"
            reason_str = "Fivefold repetition"
        elif can_threefold:
            stats["draws"] += 1
            stats["threefold_repetition"] += 1
            outcome_str = "Draw"
            reason_str = "Threefold repetition"
        elif is_seventyfive:
            stats["draws"] += 1
            stats["seventy_five_move_rule"] += 1
            outcome_str = "Draw"
            reason_str = "75-move rule"
        elif can_fifty:
            stats["draws"] += 1
            stats["fifty_move_claim"] += 1
            outcome_str = "Draw"
            reason_str = "Fifty-move claim"
        elif ply >= max_plies:
            stats["timeouts"] += 1
            stats["max_ply_timeout"] += 1
            outcome_str = "Timeout"
            reason_str = "Max-ply timeout"
        else:
            stats["draws"] += 1
            outcome_str = "Draw"
            reason_str = "Draw (claim)"

        stats["games_played"] += 1
        stats["total_plies"] += ply
        stats["total_ai_moves"] += game_ai_moves
        stats["total_ai_time"] += game_ai_time

        avg_game_ai_move_time = (game_ai_time / game_ai_moves) if game_ai_moves > 0 else 0.0
        moves_count = board.fullmove_number
        moves_history = [m.uci() for m in board.move_stack]

        stats["game_records"].append({
            "game": game_idx,
            "ai_color": ai_col_str,
            "outcome": outcome_str,
            "reason": reason_str,
            "plies": ply,
            "moves": moves_count,
            "ai_time": game_ai_time,
            "avg_move_time": avg_game_ai_move_time,
            "moves_history": moves_history,
        })

        print(
            f"Game {game_idx:2d}/{num_games:2d} | "
            f"AI: {ai_col_str:<5} | "
            f"Result: {outcome_str:<10} | "
            f"Reason: {reason_str:<22} | "
            f"Plies: {ply:3d} (~{moves_count:2d} moves) | "
            f"AI Time: {game_ai_time:5.2f}s (avg {avg_game_ai_move_time:6.3f}s/move)"
        )

    # Aggregate calculations
    total_games = stats["games_played"]
    avg_plies = stats["total_plies"] / total_games if total_games > 0 else 0.0
    avg_moves = avg_plies / 2.0
    avg_move_time = (stats["total_ai_time"] / stats["total_ai_moves"]) if stats["total_ai_moves"] > 0 else 0.0
    avg_game_time = (stats["total_ai_time"] / total_games) if total_games > 0 else 0.0

    pct_ai_win = (stats["ai_wins"] / total_games) * 100 if total_games > 0 else 0.0
    pct_random_win = (stats["random_wins"] / total_games) * 100 if total_games > 0 else 0.0
    pct_draw = (stats["draws"] / total_games) * 100 if total_games > 0 else 0.0
    pct_timeout = (stats["timeouts"] / total_games) * 100 if total_games > 0 else 0.0

    # Cache & Search metrics
    cache_stats = get_eval_cache_stats()
    stats["use_cache"] = use_cache
    stats["cache_hits"] = cache_stats["hits"]
    stats["cache_misses"] = cache_stats["misses"]
    stats["cache_hit_rate"] = cache_stats["hit_rate"]
    stats["cache_size"] = cache_stats["cache_size"]
    stats["nodes_visited"] = search_stats["nodes_visited"]
    stats["neural_evaluations"] = search_stats["neural_evaluations"]
    stats["alpha_beta_cutoffs"] = search_stats["alpha_beta_cutoffs"]
    stats["avg_move_time"] = avg_move_time
    stats["avg_game_time"] = avg_game_time

    avg_nodes_per_move = (stats["nodes_visited"] / stats["total_ai_moves"]) if stats["total_ai_moves"] > 0 else 0.0
    avg_nn_per_move = (stats["neural_evaluations"] / stats["total_ai_moves"]) if stats["total_ai_moves"] > 0 else 0.0
    stats["avg_nodes_per_move"] = avg_nodes_per_move
    stats["avg_nn_per_move"] = avg_nn_per_move

    print(f"\n{'=' * 65}")
    print("                      BENCHMARK REPORT")
    print(f"{'=' * 65}")
    print(f"Total Games Played:          {total_games}")
    print(f"Color Mode:                  {mode_str}")
    print(f"Opponent:                    Random Bot")
    print(f"Search Depth:                {depth}")
    print(f"Max Plies per Game:          {max_plies}")
    print(f"Eval Cache Status:           {cache_status_str}")
    print(f"{'-' * 65}")
    print("MATCH OUTCOMES:")
    print(f"  AI Wins:                   {stats['ai_wins']:3d}  ({pct_ai_win:5.1f}%) [As White: {stats['ai_wins_white']}, As Black: {stats['ai_wins_black']}]")
    print(f"  Random Bot Wins:           {stats['random_wins']:3d}  ({pct_random_win:5.1f}%) [As White: {stats['random_wins_white']}, As Black: {stats['random_wins_black']}]")
    print(f"  Draws:                     {stats['draws']:3d}  ({pct_draw:5.1f}%)")
    print(f"  Timeouts (Max-ply):        {stats['timeouts']:3d}  ({pct_timeout:5.1f}%)")
    print(f"{'-' * 65}")
    print("DETAILED TERMINATION REASONS:")
    print(f"  Checkmate:                 {stats['checkmate']:3d}  (AI: {stats['ai_wins']}, Random: {stats['random_wins']})")
    print(f"  Stalemate:                 {stats['stalemate']:3d}")
    print(f"  Insufficient Material:     {stats['insufficient_material']:3d}")
    print(f"  Threefold Repetition:      {stats['threefold_repetition']:3d}")
    print(f"  Fivefold Repetition:       {stats['fivefold_repetition']:3d}")
    print(f"  Fifty-Move Claim:          {stats['fifty_move_claim']:3d}")
    print(f"  Seventy-Five Move Rule:    {stats['seventy_five_move_rule']:3d}")
    print(f"  Max-Ply Timeout:           {stats['max_ply_timeout']:3d}")
    print(f"{'-' * 65}")
    print("EVALUATION CACHE PERFORMANCE:")
    print(f"  Cache Entries / Limit:     {cache_stats['cache_size']} / {cache_stats['max_size']}")
    print(f"  Cache Hits:                {cache_stats['hits']}")
    print(f"  Cache Misses:              {cache_stats['misses']}")
    print(f"  Cache Hit Rate:            {cache_stats['hit_rate'] * 100:.1f}%")
    print(f"{'-' * 65}")
    print("SEARCH INSTRUMENTATION:")
    print(f"  Total Nodes Visited:       {stats['nodes_visited']}")
    print(f"  Neural Network Evals:      {stats['neural_evaluations']}")
    print(f"  Alpha-Beta Cutoffs:        {stats['alpha_beta_cutoffs']}")
    print(f"  Avg Nodes / AI Move:       {avg_nodes_per_move:.1f}")
    print(f"  Avg NN Evals / AI Move:    {avg_nn_per_move:.1f}")
    print(f"{'-' * 65}")
    print("PERFORMANCE & TIMING:")
    print(f"  Total Plies Played:        {stats['total_plies']}")
    print(f"  Average Game Length:       {avg_plies:.1f} plies (~{avg_moves:.1f} moves)")
    print(f"  Total AI Moves Made:       {stats['total_ai_moves']}")
    print(f"  Total AI Calculation Time: {stats['total_ai_time']:.2f} s")
    print(f"  Average AI Time / Move:    {avg_move_time:.4f} s")
    print(f"  Average AI Time / Game:    {avg_game_time:.2f} s")
    print(f"{'=' * 65}\n")

    return stats


# ------------------------------------------------------------
# 9) CONTROLLED A/B BENCHMARK HARNESS
# ------------------------------------------------------------
def run_ab_benchmark(model, depth: int = 2, max_plies: int = 600, random_seed: int = 42):
    """
    Runs a controlled A/B benchmark:
      Run A: Root bounds NOT propagated (every root move restarts with -inf, +inf)
      Run B: Root bounds PROPAGATED (alpha/beta window preserved across root moves)
    Both runs have evaluation cache DISABLED and use the identical random_seed.
    """
    print(f"\n{'=' * 75}")
    print(" CONTROLLED A/B BENCHMARK: ROOT ALPHA-BETA PROPAGATION")
    print(f" Depth: {depth} | Max Plies: {max_plies} | Seed: {random_seed} | Cache: DISABLED")
    print(f"{'=' * 75}\n")

    # Run A: Root Bounds Reset (-inf, +inf)
    print(">>> [RUN A / 2] Starting benchmark with ROOT BOUNDS RESET (-inf, +inf)...")
    stats_a = run_benchmark(
        model,
        num_games=2,
        depth=depth,
        alternate_colors=True,
        max_plies=max_plies,
        use_cache=False,
        random_seed=random_seed,
        propagate_root_bounds=False,
    )

    # Run B: Root Bounds Propagated
    print(">>> [RUN B / 2] Starting benchmark with ROOT BOUNDS PROPAGATED...")
    stats_b = run_benchmark(
        model,
        num_games=2,
        depth=depth,
        alternate_colors=True,
        max_plies=max_plies,
        use_cache=False,
        random_seed=random_seed,
        propagate_root_bounds=True,
    )

    # Verify identical move sequences and outcomes
    moves_match = True
    outcome_match = True
    mismatches = []
    for g_idx in range(len(stats_a["game_records"])):
        rec_a = stats_a["game_records"][g_idx]
        rec_b = stats_b["game_records"][g_idx]
        if rec_a["moves_history"] != rec_b["moves_history"]:
            moves_match = False
            mismatches.append(f"Game {g_idx+1}: move sequence mismatch")
        if rec_a["outcome"] != rec_b["outcome"] or rec_a["reason"] != rec_b["reason"]:
            outcome_match = False
            mismatches.append(f"Game {g_idx+1}: outcome mismatch ({rec_a['outcome']}/{rec_a['reason']} vs {rec_b['outcome']}/{rec_b['reason']})")

    node_reduction = (1.0 - (stats_b["nodes_visited"] / stats_a["nodes_visited"])) * 100.0 if stats_a["nodes_visited"] > 0 else 0.0
    nn_reduction = (1.0 - (stats_b["neural_evaluations"] / stats_a["neural_evaluations"])) * 100.0 if stats_a["neural_evaluations"] > 0 else 0.0
    speedup_move = stats_a["avg_move_time"] / stats_b["avg_move_time"] if stats_b["avg_move_time"] > 0 else 0.0
    speedup_game = stats_a["avg_game_time"] / stats_b["avg_game_time"] if stats_b["avg_game_time"] > 0 else 0.0

    print("\n" + "=" * 78)
    print("      CONTROLLED A/B BENCHMARK: ROOT ALPHA-BETA BOUNDS PROPAGATION")
    print("=" * 78)
    print(f"{'Metric':<36} | {'Run A (Reset)':<18} | {'Run B (Propagated)':<18}")
    print("-" * 78)
    print(f"{'Move Sequences Identical':<36} | {'N/A':<18} | {str(moves_match):<18}")
    print(f"{'Game Outcomes Identical':<36} | {'N/A':<18} | {str(outcome_match):<18}")
    print(f"{'Total Games Played':<36} | {stats_a['games_played']:<18} | {stats_b['games_played']:<18}")
    print(f"{'Total Plies Played':<36} | {stats_a['total_plies']:<18} | {stats_b['total_plies']:<18}")
    print(f"{'Total AI Moves Made':<36} | {stats_a['total_ai_moves']:<18} | {stats_b['total_ai_moves']:<18}")
    print("-" * 78)
    print(f"{'Total Nodes Visited':<36} | {stats_a['nodes_visited']:<18} | {stats_b['nodes_visited']:<18}")
    print(f"{'Neural-Network Evaluations':<36} | {stats_a['neural_evaluations']:<18} | {stats_b['neural_evaluations']:<18}")
    print(f"{'Alpha-Beta Cutoffs':<36} | {stats_a['alpha_beta_cutoffs']:<18} | {stats_b['alpha_beta_cutoffs']:<18}")
    print("-" * 78)
    print(f"{'Avg Nodes / AI Move':<36} | {stats_a['avg_nodes_per_move']:<18.1f} | {stats_b['avg_nodes_per_move']:<18.1f}")
    print(f"{'Avg NN Evals / AI Move':<36} | {stats_a['avg_nn_per_move']:<18.1f} | {stats_b['avg_nn_per_move']:<18.1f}")
    print(f"{'Average AI Time / Move':<36} | {stats_a['avg_move_time']:<15.4f} s | {stats_b['avg_move_time']:<15.4f} s")
    print(f"{'Average AI Time / Game':<36} | {stats_a['avg_game_time']:<15.2f} s | {stats_b['avg_game_time']:<15.2f} s")
    print(f"{'Total AI Calculation Time':<36} | {stats_a['total_ai_time']:<15.2f} s | {stats_b['total_ai_time']:<15.2f} s")
    print("-" * 78)
    print(f"NODE REDUCTION:                      {node_reduction:.1f}% fewer nodes")
    print(f"NEURAL EVALUATION REDUCTION:         {nn_reduction:.1f}% fewer NN calls")
    print(f"SEARCH-LEVEL SPEEDUP (Move Time):    {speedup_move:.2f}x FASTER")
    print(f"SEARCH-LEVEL SPEEDUP (Game Time):    {speedup_game:.2f}x FASTER")
    print("=" * 78 + "\n")

    if not moves_match or not outcome_match:
        print("EXPLANATION FOR MISMATCH:")
        for m in mismatches:
            print(f"  * {m}")

    return {
        "stats_a": stats_a,
        "stats_b": stats_b,
        "moves_match": moves_match,
        "outcome_match": outcome_match,
        "node_reduction": node_reduction,
        "nn_reduction": nn_reduction,
        "speedup_move": speedup_move,
        "speedup_game": speedup_game,
    }


# ------------------------------------------------------------
# 10) REPRESENTATIVE FEN BENCHMARK FOR ITERATIVE DEEPENING
# ------------------------------------------------------------
REPRESENTATIVE_FENS = [
    ("Start Position", "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"),
    ("Italian Middlegame", "r1bqk2r/pppp1ppp/2n2n2/2b1p3/2B1P3/3P1N2/PPP2PPP/RNBQK2R w KQkq - 1 5"),
    ("Sicilian Najdorf", "r1bqkb1r/1p2pppp/p1np1n2/8/3NP3/2N1B3/PPP2PPP/R2QKB1R b KQkq - 1 7"),
    ("QGD Tension", "r2q1rk1/pp1nbppp/2p1pn2/3p4/2PP4/2N1PN2/PP2BPPP/R1BQ1RK1 w - - 4 9"),
    ("Tactical Middlegame", "r1b2rk1/2q1bppp/p2p1n2/1p2p3/2n1P3/1BN1BN2/PPP1QPPP/R4RK1 w - - 0 14"),
    ("King's Indian Setup", "rnbq1rk1/ppp1ppbp/3p1np1/8/2PPP3/2N2N2/PP2BPPP/R1BQK2R b KQ - 2 6"),
    ("Rook Endgame", "8/5pk1/4p1p1/7p/r6P/4PKP1/5P2/2R5 w - - 2 37"),
    ("Minor Piece Endgame", "8/2p2pk1/1p1p2p1/p2P3p/P1P2P2/1P4P1/4K2P/8 b - - 0 32"),
]

# 4 representative fixed FEN positions for Depth-3 Transposition Table Benchmark
DEPTH3_BENCHMARK_FENS = [
    ("Start Position", "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"),
    ("Tactical Middlegame", "r1b2rk1/2q1bppp/p2p1n2/1p2p3/2n1P3/1BN1BN2/PPP1QPPP/R4RK1 w - - 0 14"),
    ("Rook Endgame", "8/5pk1/4p1p1/7p/r6P/4PKP1/5P2/2R5 w - - 2 37"),
    ("Sicilian Najdorf", "r1bqkb1r/1p2pppp/p1np1n2/8/3NP3/2N1B3/PPP2PPP/R2QKB1R b KQkq - 1 7"),
]


def run_iterative_deepening_benchmark(model, fens=None):
    """
    Controlled deterministic benchmark comparing:
      A) Direct depth-2 alpha-beta search
      B) Iterative deepening up to depth 2 (root move ordering from depth 1)
    Both runs have evaluation cache disabled and use deterministic tie-breaking.
    """
    if fens is None:
        fens = REPRESENTATIVE_FENS

    set_eval_cache_enabled(False)
    clear_eval_cache()

    print(f"\n{'=' * 78}")
    print("      BENCHMARK: DIRECT DEPTH-2 vs ITERATIVE DEEPENING (DEPTH 2)")
    print(f" Test Positions: {len(fens)} | Tie-Breaking: DETERMINISTIC | Cache: DISABLED")
    print(f"{'=' * 78}\n")

    # Aggregates for Direct D2 (Run A)
    tot_nodes_a = 0
    tot_nn_a = 0
    tot_cutoffs_a = 0
    tot_time_a = 0.0

    # Aggregates for Iterative Deepening (Run B)
    tot_nodes_b_cum = 0
    tot_nn_b_cum = 0
    tot_cutoffs_b_cum = 0
    tot_time_b_cum = 0.0

    tot_nodes_b_final = 0
    tot_nn_b_final = 0
    tot_cutoffs_b_final = 0
    tot_time_b_final = 0.0

    all_match = True
    mismatches = []
    position_results = []

    for idx, (name, fen) in enumerate(fens, 1):
        board = chess.Board(fen)
        turn_str = "White" if board.turn == chess.WHITE else "Black"

        # --- A) Direct depth-2 search ---
        reset_search_stats()
        t0 = time.perf_counter()
        move_a, val_a = get_best_move(
            board, depth=2, model=model, propagate_root_bounds=True,
            previous_best_move=None, randomize_equal_moves=False
        )
        t1 = time.perf_counter()
        time_a = t1 - t0
        nodes_a = search_stats["nodes_visited"]
        nn_a = search_stats["neural_evaluations"]
        cutoffs_a = search_stats["alpha_beta_cutoffs"]

        # --- B) Iterative deepening search up to depth 2 ---
        reset_search_stats()
        id_res = iterative_deepening_search(
            board, max_depth=2, model=model, propagate_root_bounds=True,
            randomize_equal_moves=False
        )
        move_b = id_res["best_move"]
        val_b = id_res["best_value"]
        cum_time_b = id_res["cumulative_time"]
        cum_nodes_b = id_res["cumulative_nodes"]
        cum_nn_b = id_res["cumulative_nn_evals"]
        cum_cutoffs_b = id_res["cumulative_cutoffs"]

        final_rec = id_res["final_depth_record"]
        final_time_b = final_rec["elapsed_time"]
        final_nodes_b = final_rec["nodes_visited"]
        final_nn_b = final_rec["neural_evaluations"]
        final_cutoffs_b = final_rec["alpha_beta_cutoffs"]

        # Verify equivalence
        moves_match = (move_a == move_b)
        scores_match = np.isclose(val_a, val_b, rtol=0.0, atol=1e-7)

        if not (moves_match and scores_match):
            all_match = False
            mismatches.append(
                f"Position {idx} ('{name}'): Direct({move_a}, {val_a:.6f}) vs ID({move_b}, {val_b:.6f})"
            )

        # Accumulate
        tot_nodes_a += nodes_a
        tot_nn_a += nn_a
        tot_cutoffs_a += cutoffs_a
        tot_time_a += time_a

        tot_nodes_b_cum += cum_nodes_b
        tot_nn_b_cum += cum_nn_b
        tot_cutoffs_b_cum += cum_cutoffs_b
        tot_time_b_cum += cum_time_b

        tot_nodes_b_final += final_nodes_b
        tot_nn_b_final += final_nn_b
        tot_cutoffs_b_final += final_cutoffs_b
        tot_time_b_final += final_time_b

        d1_rec = id_res["depth_records"][0]
        pos_info = {
            "name": name,
            "fen": fen,
            "turn": turn_str,
            "move_a": move_a.uci() if move_a else None,
            "val_a": val_a,
            "time_a": time_a,
            "nodes_a": nodes_a,
            "nn_a": nn_a,
            "cutoffs_a": cutoffs_a,
            "d1_move": d1_rec["best_move"].uci() if d1_rec["best_move"] else None,
            "d1_val": d1_rec["best_value"],
            "d1_time": d1_rec["elapsed_time"],
            "d1_nodes": d1_rec["nodes_visited"],
            "move_b": move_b.uci() if move_b else None,
            "val_b": val_b,
            "cum_time_b": cum_time_b,
            "cum_nodes_b": cum_nodes_b,
            "cum_nn_b": cum_nn_b,
            "final_time_b": final_time_b,
            "final_nodes_b": final_nodes_b,
            "final_nn_b": final_nn_b,
            "final_cutoffs_b": final_cutoffs_b,
            "match": moves_match and scores_match,
        }
        position_results.append(pos_info)

        status_str = "MATCH" if (moves_match and scores_match) else "MISMATCH"
        print(f"[{idx:2d}/{len(fens)}] {name:<22} ({turn_str:<5}) -> {status_str}")
        print(f"       Direct D2:  move={pos_info['move_a']:<5} | eval={val_a:+.4f} | time={time_a:6.3f}s | nodes={nodes_a:4d} | NN={nn_a:4d} | cutoffs={cutoffs_a:2d}")
        print(f"       ID D1:      move={pos_info['d1_move']:<5} | eval={d1_rec['best_value']:+.4f} | time={d1_rec['elapsed_time']:6.3f}s | nodes={d1_rec['nodes_visited']:4d}")
        print(f"       ID D2 only: move={pos_info['move_b']:<5} | eval={val_b:+.4f} | time={final_time_b:6.3f}s | nodes={final_nodes_b:4d} | NN={final_nn_b:4d} | cutoffs={final_cutoffs_b:2d}")
        print(f"       ID Cumul:   time={cum_time_b:6.3f}s | nodes={cum_nodes_b:4d} | NN={cum_nn_b:4d}\n")

    # Final-depth reductions
    final_node_red = (1.0 - (tot_nodes_b_final / tot_nodes_a)) * 100.0 if tot_nodes_a > 0 else 0.0
    final_nn_red = (1.0 - (tot_nn_b_final / tot_nn_a)) * 100.0 if tot_nn_a > 0 else 0.0
    final_speedup = (tot_time_a / tot_time_b_final) if tot_time_b_final > 0 else 0.0

    # Cumulative comparisons
    cum_node_diff = ((tot_nodes_b_cum - tot_nodes_a) / tot_nodes_a) * 100.0 if tot_nodes_a > 0 else 0.0
    cum_speedup = (tot_time_a / tot_time_b_cum) if tot_time_b_cum > 0 else 0.0

    print("=" * 82)
    print("                    AGGREGATE BENCHMARK REPORT")
    print("=" * 82)
    print(f"{'Metric':<38} | {'Direct Depth-2':<18} | {'Iterative Deepening':<18}")
    print("-" * 82)
    print(f"{'All Selected Moves Identical':<38} | {'N/A':<18} | {str(all_match):<18}")
    print(f"{'All Best Scores Identical':<38} | {'N/A':<18} | {str(all_match):<18}")
    print(f"{'Positions Evaluated':<38} | {len(fens):<18} | {len(fens):<18}")
    print("-" * 82)
    print("FINAL-DEPTH ONLY METRICS (Depth 2 effect of move ordering):")
    print(f"  {'Final-Depth Nodes Visited':<36} | {tot_nodes_a:<18} | {tot_nodes_b_final:<18}")
    print(f"  {'Final-Depth NN Evaluations':<36} | {tot_nn_a:<18} | {tot_nn_b_final:<18}")
    print(f"  {'Final-Depth Cutoffs':<36} | {tot_cutoffs_a:<18} | {tot_cutoffs_b_final:<18}")
    print(f"  {'Final-Depth Elapsed Time':<36} | {tot_time_a:15.3f} s | {tot_time_b_final:15.3f} s")
    print(f"  {'Final-Depth Node Reduction':<36} | {'baseline':<18} | {final_node_red:14.1f} %")
    print(f"  {'Final-Depth NN Eval Reduction':<36} | {'baseline':<18} | {final_nn_red:14.1f} %")
    print(f"  {'Final-Depth Search Speedup':<36} | {'1.00x':<18} | {final_speedup:14.2f} x")
    print("-" * 82)
    print("CUMULATIVE METRICS (Including Depth 1 overhead):")
    print(f"  {'Total Nodes Visited (All Depths)':<36} | {tot_nodes_a:<18} | {tot_nodes_b_cum:<18}")
    print(f"  {'Total NN Evaluations':<36} | {tot_nn_a:<18} | {tot_nn_b_cum:<18}")
    print(f"  {'Total Cutoffs':<36} | {tot_cutoffs_a:<18} | {tot_cutoffs_b_cum:<18}")
    print(f"  {'Cumulative Elapsed Time':<36} | {tot_time_a:15.3f} s | {tot_time_b_cum:15.3f} s")
    print(f"  {'Cumulative Node Overhead':<36} | {'baseline':<18} | {cum_node_diff:+14.1f} %")
    print(f"  {'Net Overall Speedup':<36} | {'1.00x':<18} | {cum_speedup:14.2f} x")
    print("=" * 82 + "\n")

    if not all_match:
        print("MISMATCH DETAILS:")
        for m in mismatches:
            print(f"  * {m}")

    return {
        "all_match": all_match,
        "mismatches": mismatches,
        "position_results": position_results,
        "tot_nodes_a": tot_nodes_a,
        "tot_nn_a": tot_nn_a,
        "tot_cutoffs_a": tot_cutoffs_a,
        "tot_time_a": tot_time_a,
        "tot_nodes_b_cum": tot_nodes_b_cum,
        "tot_nn_b_cum": tot_nn_b_cum,
        "tot_cutoffs_b_cum": tot_cutoffs_b_cum,
        "tot_time_b_cum": tot_time_b_cum,
        "tot_nodes_b_final": tot_nodes_b_final,
        "tot_nn_b_final": tot_nn_b_final,
        "tot_cutoffs_b_final": tot_cutoffs_b_final,
        "tot_time_b_final": tot_time_b_final,
        "final_node_red": final_node_red,
        "final_nn_red": final_nn_red,
        "final_speedup": final_speedup,
        "cum_speedup": cum_speedup,
    }


def run_tt_ab_benchmark(model, fens=None, depth: int = 3):
    """
    Controlled deterministic A/B benchmark comparing:
      A) Iterative deepening up to depth D, TT DISABLED
      B) Iterative deepening up to depth D, TT ENABLED
    Both runs have neural-network evaluation cache disabled and use deterministic tie-breaking.
    """
    if fens is None:
        fens = DEPTH3_BENCHMARK_FENS

    set_eval_cache_enabled(False)
    clear_eval_cache()

    print(f"\n{'=' * 88}")
    print(f"      A/B BENCHMARK: ITERATIVE DEEPENING (D={depth}) - TT DISABLED vs TT ENABLED")
    print(f" Test Positions: {len(fens)} | Tie-Breaking: DETERMINISTIC | Cache: DISABLED")
    print(f"{'=' * 88}\n")

    # Aggregates for Run A (TT Disabled)
    tot_nodes_a_cum = 0
    tot_nn_a_cum = 0
    tot_cutoffs_a_cum = 0
    tot_time_a_cum = 0.0

    tot_nodes_a_final = 0
    tot_nn_a_final = 0
    tot_cutoffs_a_final = 0
    tot_time_a_final = 0.0

    # Aggregates for Run B (TT Enabled)
    tot_nodes_b_cum = 0
    tot_nn_b_cum = 0
    tot_cutoffs_b_cum = 0
    tot_time_b_cum = 0.0

    tot_nodes_b_final = 0
    tot_nn_b_final = 0
    tot_cutoffs_b_final = 0
    tot_time_b_final = 0.0

    # TT-specific metrics (Run B)
    tot_tt_probes = 0
    tot_tt_hits = 0
    tot_tt_usable = 0
    tot_tt_cutoffs = 0
    tot_tt_ordering_hits = 0
    tot_tt_stores = 0

    # TT metrics aggregated by depth (Run B)
    agg_tt_by_depth = {
        d: {"probes": 0, "hits": 0, "usable_hits": 0, "cutoffs": 0, "ordering_hits": 0, "stores": 0}
        for d in range(1, depth + 1)
    }

    all_scores_match = True
    all_moves_match = True
    mismatches = []
    position_results = []

    for idx, (name, fen) in enumerate(fens, 1):
        board = chess.Board(fen)
        turn_str = "White" if board.turn == chess.WHITE else "Black"

        # --- A) Iterative Deepening: TT DISABLED ---
        reset_search_stats()
        clear_tt()
        res_a = iterative_deepening_search(
            board, max_depth=depth, model=model, propagate_root_bounds=True,
            randomize_equal_moves=False, use_tt=False
        )
        rec_a_final = res_a["final_depth_record"]

        # --- B) Iterative Deepening: TT ENABLED ---
        reset_search_stats()
        clear_tt()
        res_b = iterative_deepening_search(
            board, max_depth=depth, model=model, propagate_root_bounds=True,
            randomize_equal_moves=False, use_tt=True
        )
        rec_b_final = res_b["final_depth_record"]

        # TT stats for position
        pos_tt_probes = search_stats["tt_probes"]
        pos_tt_hits = search_stats["tt_hits"]
        pos_tt_usable = search_stats["usable_tt_hits"]
        pos_tt_cutoffs = search_stats["tt_cutoffs"]
        pos_tt_ordering_hits = search_stats["tt_move_ordering_hits"]
        pos_tt_stores = search_stats["tt_stores"]

        tot_tt_probes += pos_tt_probes
        tot_tt_hits += pos_tt_hits
        tot_tt_usable += pos_tt_usable
        tot_tt_cutoffs += pos_tt_cutoffs
        tot_tt_ordering_hits += pos_tt_ordering_hits
        tot_tt_stores += pos_tt_stores

        # Accumulate depth breakdown
        pos_depth_stats = {}
        for d in range(1, depth + 1):
            pos_depth_stats[d] = dict(tt_stats_by_depth[d])
            for k in agg_tt_by_depth[d]:
                agg_tt_by_depth[d][k] += tt_stats_by_depth[d][k]

        # Verification
        scores_match = np.isclose(res_a["best_value"], res_b["best_value"], rtol=0.0, atol=1e-7)
        moves_match = (res_a["best_move"] == res_b["best_move"])

        if not scores_match:
            all_scores_match = False
            mismatches.append(
                f"Position {idx} ('{name}'): Score mismatch A={res_a['best_value']:.6f} vs B={res_b['best_value']:.6f}"
            )
        if not moves_match:
            all_moves_match = False
            # Check whether it's an equal-optimal-move issue:
            if scores_match:
                mismatches.append(
                    f"Position {idx} ('{name}'): Different equal-optimal moves selected: A={res_a['best_move']} vs B={res_b['best_move']} (both score {res_a['best_value']:.6f})"
                )
            else:
                mismatches.append(
                    f"Position {idx} ('{name}'): Move mismatch A={res_a['best_move']} vs B={res_b['best_move']} (scores: A={res_a['best_value']:.6f}, B={res_b['best_value']:.6f})"
                )

        # Accumulate Run A
        tot_nodes_a_cum += res_a["cumulative_nodes"]
        tot_nn_a_cum += res_a["cumulative_nn_evals"]
        tot_cutoffs_a_cum += res_a["cumulative_cutoffs"]
        tot_time_a_cum += res_a["cumulative_time"]

        tot_nodes_a_final += rec_a_final["nodes_visited"]
        tot_nn_a_final += rec_a_final["neural_evaluations"]
        tot_cutoffs_a_final += rec_a_final["alpha_beta_cutoffs"]
        tot_time_a_final += rec_a_final["elapsed_time"]

        # Accumulate Run B
        tot_nodes_b_cum += res_b["cumulative_nodes"]
        tot_nn_b_cum += res_b["cumulative_nn_evals"]
        tot_cutoffs_b_cum += res_b["cumulative_cutoffs"]
        tot_time_b_cum += res_b["cumulative_time"]

        tot_nodes_b_final += rec_b_final["nodes_visited"]
        tot_nn_b_final += rec_b_final["neural_evaluations"]
        tot_cutoffs_b_final += rec_b_final["alpha_beta_cutoffs"]
        tot_time_b_final += rec_b_final["elapsed_time"]

        status_str = "MATCH" if (scores_match and moves_match) else "MISMATCH"
        pos_speedup_final = (rec_a_final["elapsed_time"] / rec_b_final["elapsed_time"]) if rec_b_final["elapsed_time"] > 0 else 0.0
        pos_speedup_cum = (res_a["cumulative_time"] / res_b["cumulative_time"]) if res_b["cumulative_time"] > 0 else 0.0

        pos_info = {
            "name": name,
            "fen": fen,
            "turn": turn_str,
            "res_a": res_a,
            "res_b": res_b,
            "pos_tt_probes": pos_tt_probes,
            "pos_tt_hits": pos_tt_hits,
            "pos_tt_usable": pos_tt_usable,
            "pos_tt_cutoffs": pos_tt_cutoffs,
            "pos_tt_ordering_hits": pos_tt_ordering_hits,
            "pos_tt_stores": pos_tt_stores,
            "pos_depth_stats": pos_depth_stats,
            "scores_match": scores_match,
            "moves_match": moves_match,
            "pos_speedup_final": pos_speedup_final,
            "pos_speedup_cum": pos_speedup_cum,
        }
        position_results.append(pos_info)

        print(f"[{idx:2d}/{len(fens)}] {name:<22} ({turn_str:<5}) -> {status_str}")
        print(f"       TT Off: move={res_a['best_move'].uci():<5} | eval={res_a['best_value']:+.4f} | final_time={rec_a_final['elapsed_time']:6.2f}s | cum_time={res_a['cumulative_time']:6.2f}s | nodes_final={rec_a_final['nodes_visited']:4d} | nodes_cum={res_a['cumulative_nodes']:4d} | NN_final={rec_a_final['neural_evaluations']:4d} | NN_cum={res_a['cumulative_nn_evals']:4d} | cutoffs_final={rec_a_final['alpha_beta_cutoffs']:3d} | cutoffs_cum={res_a['cumulative_cutoffs']:3d}")
        print(f"       TT On:  move={res_b['best_move'].uci():<5} | eval={res_b['best_value']:+.4f} | final_time={rec_b_final['elapsed_time']:6.2f}s | cum_time={res_b['cumulative_time']:6.2f}s | nodes_final={rec_b_final['nodes_visited']:4d} | nodes_cum={res_b['cumulative_nodes']:4d} | NN_final={rec_b_final['neural_evaluations']:4d} | NN_cum={res_b['cumulative_nn_evals']:4d} | cutoffs_final={rec_b_final['alpha_beta_cutoffs']:3d} | cutoffs_cum={res_b['cumulative_cutoffs']:3d}")
        print(f"       TT Ops: probes={pos_tt_probes:3d} | hits={pos_tt_hits:3d} | usable={pos_tt_usable:3d} | cutoffs={pos_tt_cutoffs:3d} | ordering_hits={pos_tt_ordering_hits:3d} | stores={pos_tt_stores:3d}")
        print(f"       Speedup: final-depth={pos_speedup_final:5.2f}x | cumulative={pos_speedup_cum:5.2f}x\n")

    # Aggregate calculations
    final_node_red = (1.0 - (tot_nodes_b_final / tot_nodes_a_final)) * 100.0 if tot_nodes_a_final > 0 else 0.0
    final_nn_red = (1.0 - (tot_nn_b_final / tot_nn_a_final)) * 100.0 if tot_nn_a_final > 0 else 0.0
    final_speedup = (tot_time_a_final / tot_time_b_final) if tot_time_b_final > 0 else 0.0

    cum_node_red = (1.0 - (tot_nodes_b_cum / tot_nodes_a_cum)) * 100.0 if tot_nodes_a_cum > 0 else 0.0
    cum_nn_red = (1.0 - (tot_nn_b_cum / tot_nn_a_cum)) * 100.0 if tot_nn_a_cum > 0 else 0.0
    cum_speedup = (tot_time_a_cum / tot_time_b_cum) if tot_time_b_cum > 0 else 0.0

    tt_hit_rate = (tot_tt_hits / tot_tt_probes) * 100.0 if tot_tt_probes > 0 else 0.0
    tt_usable_hit_rate = (tot_tt_usable / tot_tt_probes) * 100.0 if tot_tt_probes > 0 else 0.0

    print("=" * 88)
    print(f"          TRANSPOSITION TABLE A/B BENCHMARK REPORT (DEPTH {depth})")
    print("=" * 88)
    print(f"{'Metric':<42} | {'Run A (TT Disabled)':<20} | {'Run B (TT Enabled)':<20}")
    print("-" * 88)
    print(f"{'All Best Scores Identical':<42} | {'N/A':<20} | {str(all_scores_match):<20}")
    print(f"{'All Selected Moves Identical':<42} | {'N/A':<20} | {str(all_moves_match):<20}")
    print(f"{'Positions Evaluated':<42} | {len(fens):<20} | {len(fens):<20}")
    print("-" * 88)
    print("FINAL-DEPTH METRICS:")
    print(f"  {'Final-Depth Nodes Visited':<40} | {tot_nodes_a_final:<20} | {tot_nodes_b_final:<20}")
    print(f"  {'Final-Depth Node Reduction':<40} | {'baseline':<20} | {final_node_red:16.1f} %")
    print(f"  {'Final-Depth NN Evaluations':<40} | {tot_nn_a_final:<20} | {tot_nn_b_final:<20}")
    print(f"  {'Final-Depth NN Reduction':<40} | {'baseline':<20} | {final_nn_red:16.1f} %")
    print(f"  {'Final-Depth Alpha-Beta Cutoffs':<40} | {tot_cutoffs_a_final:<20} | {tot_cutoffs_b_final:<20}")
    print(f"  {'Final-Depth Elapsed Time':<40} | {tot_time_a_final:16.2f} s | {tot_time_b_final:16.2f} s")
    print(f"  {'Final-Depth Speedup':<40} | {'1.00x':<20} | {final_speedup:16.2f} x")
    print("-" * 88)
    print("CUMULATIVE SEARCH METRICS (Depths 1 to {depth}):".format(depth=depth))
    print(f"  {'Cumulative Nodes Visited':<40} | {tot_nodes_a_cum:<20} | {tot_nodes_b_cum:<20}")
    print(f"  {'Cumulative Node Reduction':<40} | {'baseline':<20} | {cum_node_red:16.1f} %")
    print(f"  {'Cumulative NN Evaluations':<40} | {tot_nn_a_cum:<20} | {tot_nn_b_cum:<20}")
    print(f"  {'Cumulative NN Reduction':<40} | {'baseline':<20} | {cum_nn_red:16.1f} %")
    print(f"  {'Cumulative Alpha-Beta Cutoffs':<40} | {tot_cutoffs_a_cum:<20} | {tot_cutoffs_b_cum:<20}")
    print(f"  {'Cumulative Elapsed Time':<40} | {tot_time_a_cum:16.2f} s | {tot_time_b_cum:16.2f} s")
    print(f"  {'Cumulative Search Speedup':<40} | {'1.00x':<20} | {cum_speedup:16.2f} x")
    print("-" * 88)
    print("TRANSPOSITION TABLE INSTRUMENTATION (Run B Totals):")
    print(f"  {'Total TT Probes':<40} | {'N/A':<20} | {tot_tt_probes:<20}")
    print(f"  {'Total TT Hits':<40} | {'N/A':<20} | {tot_tt_hits:<20}")
    print(f"  {'Overall TT Hit Rate':<40} | {'N/A':<20} | {tt_hit_rate:16.1f} %")
    print(f"  {'Usable TT Hits (depth >= target)':<40} | {'N/A':<20} | {tot_tt_usable:<20}")
    print(f"  {'Usable TT Hit Rate':<40} | {'N/A':<20} | {tt_usable_hit_rate:16.1f} %")
    print(f"  {'TT-Induced Cutoffs':<40} | {'N/A':<20} | {tot_tt_cutoffs:<20}")
    print(f"  {'TT Best-Move Ordering Hits':<40} | {'N/A':<20} | {tot_tt_ordering_hits:<20}")
    print(f"  {'Total TT Stores':<40} | {'N/A':<20} | {tot_tt_stores:<20}")
    print("-" * 88)
    print("TRANSPOSITION TABLE BREAKDOWN BY REQUESTED DEPTH (Run B):")
    print(f"  {'Depth':<6} | {'Probes':<8} | {'Hits':<8} | {'Hit Rate':<10} | {'Usable':<8} | {'Cutoffs':<8} | {'Order Hits':<10} | {'Stores':<8}")
    print(f"  {'-'*6}-+-{'-'*8}-+-{'-'*8}-+-{'-'*10}-+-{'-'*8}-+-{'-'*8}-+-{'-'*10}-+-{'-'*8}")
    for d in range(1, depth + 1):
        d_p = agg_tt_by_depth[d]["probes"]
        d_h = agg_tt_by_depth[d]["hits"]
        d_rate = (d_h / d_p * 100.0) if d_p > 0 else 0.0
        d_u = agg_tt_by_depth[d]["usable_hits"]
        d_c = agg_tt_by_depth[d]["cutoffs"]
        d_o = agg_tt_by_depth[d]["ordering_hits"]
        d_s = agg_tt_by_depth[d]["stores"]
        print(f"  d={d:<4} | {d_p:<8} | {d_h:<8} | {d_rate:8.1f} % | {d_u:<8} | {d_c:<8} | {d_o:<10} | {d_s:<8}")
    print("=" * 88 + "\n")

    if mismatches:
        print("INVESTIGATION OF MISMATCHES:")
        for m in mismatches:
            print(f"  * {m}")

    return {
        "all_scores_match": all_scores_match,
        "all_moves_match": all_moves_match,
        "mismatches": mismatches,
        "position_results": position_results,
        "tot_tt_probes": tot_tt_probes,
        "tot_tt_hits": tot_tt_hits,
        "tot_tt_usable": tot_tt_usable,
        "tot_tt_cutoffs": tot_tt_cutoffs,
        "tot_tt_ordering_hits": tot_tt_ordering_hits,
        "tot_tt_stores": tot_tt_stores,
        "agg_tt_by_depth": agg_tt_by_depth,
        "tot_nodes_a_final": tot_nodes_a_final,
        "tot_nodes_b_final": tot_nodes_b_final,
        "tot_nn_a_final": tot_nn_a_final,
        "tot_nn_b_final": tot_nn_b_final,
        "tot_cutoffs_a_final": tot_cutoffs_a_final,
        "tot_cutoffs_b_final": tot_cutoffs_b_final,
        "tot_time_a_final": tot_time_a_final,
        "tot_time_b_final": tot_time_b_final,
        "tot_nodes_a_cum": tot_nodes_a_cum,
        "tot_nodes_b_cum": tot_nodes_b_cum,
        "tot_nn_a_cum": tot_nn_a_cum,
        "tot_nn_b_cum": tot_nn_b_cum,
        "tot_cutoffs_a_cum": tot_cutoffs_a_cum,
        "tot_cutoffs_b_cum": tot_cutoffs_b_cum,
        "tot_time_a_cum": tot_time_a_cum,
        "tot_time_b_cum": tot_time_b_cum,
        "final_node_red": final_node_red,
        "final_nn_red": final_nn_red,
        "final_speedup": final_speedup,
        "cum_node_red": cum_node_red,
        "cum_nn_red": cum_nn_red,
        "cum_speedup": cum_speedup,
    }


def run_pvs_ab_benchmark(model, fens=None, depth: int = 3):
    """
    Controlled deterministic A/B benchmark comparing:
      A) Iterative deepening (Depth D) + TT + Alpha-Beta (PVS DISABLED)
      B) Iterative deepening (Depth D) + TT + PVS (PVS ENABLED)
    Both runs have neural-network evaluation cache disabled and use deterministic tie-breaking.
    """
    if fens is None:
        fens = DEPTH3_BENCHMARK_FENS

    set_eval_cache_enabled(False)
    clear_eval_cache()

    print(f"\n{'=' * 88}")
    print(f"      A/B BENCHMARK: DEPTH-{depth} TT + ALPHA-BETA vs TT + PVS")
    print(f" Test Positions: {len(fens)} | Tie-Breaking: DETERMINISTIC | Cache: DISABLED")
    print(f"{'=' * 88}\n")

    # Aggregates for Run A (PVS Disabled)
    tot_nodes_a_cum = 0
    tot_nn_a_cum = 0
    tot_cutoffs_a_cum = 0
    tot_time_a_cum = 0.0

    tot_nodes_a_final = 0
    tot_nn_a_final = 0
    tot_cutoffs_a_final = 0
    tot_time_a_final = 0.0

    # Aggregates for Run B (PVS Enabled)
    tot_nodes_b_cum = 0
    tot_nn_b_cum = 0
    tot_cutoffs_b_cum = 0
    tot_time_b_cum = 0.0

    tot_nodes_b_final = 0
    tot_nn_b_final = 0
    tot_cutoffs_b_final = 0
    tot_time_b_final = 0.0

    tot_pvs_narrow_cum = 0
    tot_pvs_re_cum = 0
    tot_pvs_narrow_final = 0
    tot_pvs_re_final = 0

    tot_tt_probes_b = 0
    tot_tt_hits_b = 0
    tot_tt_usable_b = 0
    tot_tt_cutoffs_b = 0
    tot_tt_ordering_hits_b = 0
    tot_tt_stores_b = 0

    all_scores_match = True
    all_moves_match = True
    mismatches = []
    position_results = []

    for idx, (name, fen) in enumerate(fens, 1):
        board = chess.Board(fen)
        turn_str = "White" if board.turn == chess.WHITE else "Black"

        # --- A) PVS DISABLED ---
        reset_search_stats()
        clear_tt()
        res_a = iterative_deepening_search(
            board, max_depth=depth, model=model, propagate_root_bounds=True,
            randomize_equal_moves=False, use_tt=True, use_pvs=False
        )
        rec_a_final = res_a["final_depth_record"]

        # --- B) PVS ENABLED ---
        reset_search_stats()
        clear_tt()
        res_b = iterative_deepening_search(
            board, max_depth=depth, model=model, propagate_root_bounds=True,
            randomize_equal_moves=False, use_tt=True, use_pvs=True
        )
        rec_b_final = res_b["final_depth_record"]

        pos_pvs_narrow = search_stats["pvs_narrow_searches"]
        pos_pvs_re = search_stats["pvs_researches"]
        pos_tt_probes = search_stats["tt_probes"]
        pos_tt_hits = search_stats["tt_hits"]
        pos_tt_usable = search_stats["usable_tt_hits"]
        pos_tt_cutoffs = search_stats["tt_cutoffs"]
        pos_tt_ordering_hits = search_stats["tt_move_ordering_hits"]
        pos_tt_stores = search_stats["tt_stores"]

        tot_pvs_narrow_cum += pos_pvs_narrow
        tot_pvs_re_cum += pos_pvs_re
        tot_pvs_narrow_final += rec_b_final["pvs_narrow_searches"]
        tot_pvs_re_final += rec_b_final["pvs_researches"]

        tot_tt_probes_b += pos_tt_probes
        tot_tt_hits_b += pos_tt_hits
        tot_tt_usable_b += pos_tt_usable
        tot_tt_cutoffs_b += pos_tt_cutoffs
        tot_tt_ordering_hits_b += pos_tt_ordering_hits
        tot_tt_stores_b += pos_tt_stores

        # Verification
        scores_match = np.isclose(res_a["best_value"], res_b["best_value"], rtol=0.0, atol=1e-7)
        moves_match = (res_a["best_move"] == res_b["best_move"])

        if not scores_match:
            all_scores_match = False
            mismatches.append(
                f"Position {idx} ('{name}'): Score mismatch A={res_a['best_value']:.6f} vs B={res_b['best_value']:.6f}"
            )
        if not moves_match:
            all_moves_match = False
            if scores_match:
                mismatches.append(
                    f"Position {idx} ('{name}'): Different equal-optimal moves selected: A={res_a['best_move']} vs B={res_b['best_move']} (both score {res_a['best_value']:.6f})"
                )
            else:
                mismatches.append(
                    f"Position {idx} ('{name}'): Move mismatch A={res_a['best_move']} vs B={res_b['best_move']} (scores: A={res_a['best_value']:.6f}, B={res_b['best_value']:.6f})"
                )

        # Accumulate Run A
        tot_nodes_a_cum += res_a["cumulative_nodes"]
        tot_nn_a_cum += res_a["cumulative_nn_evals"]
        tot_cutoffs_a_cum += res_a["cumulative_cutoffs"]
        tot_time_a_cum += res_a["cumulative_time"]

        tot_nodes_a_final += rec_a_final["nodes_visited"]
        tot_nn_a_final += rec_a_final["neural_evaluations"]
        tot_cutoffs_a_final += rec_a_final["alpha_beta_cutoffs"]
        tot_time_a_final += rec_a_final["elapsed_time"]

        # Accumulate Run B
        tot_nodes_b_cum += res_b["cumulative_nodes"]
        tot_nn_b_cum += res_b["cumulative_nn_evals"]
        tot_cutoffs_b_cum += res_b["cumulative_cutoffs"]
        tot_time_b_cum += res_b["cumulative_time"]

        tot_nodes_b_final += rec_b_final["nodes_visited"]
        tot_nn_b_final += rec_b_final["neural_evaluations"]
        tot_cutoffs_b_final += rec_b_final["alpha_beta_cutoffs"]
        tot_time_b_final += rec_b_final["elapsed_time"]

        status_str = "MATCH" if (scores_match and moves_match) else "MISMATCH"
        pos_speedup_final = (rec_a_final["elapsed_time"] / rec_b_final["elapsed_time"]) if rec_b_final["elapsed_time"] > 0 else 0.0
        pos_speedup_cum = (res_a["cumulative_time"] / res_b["cumulative_time"]) if res_b["cumulative_time"] > 0 else 0.0

        pos_info = {
            "name": name,
            "fen": fen,
            "turn": turn_str,
            "res_a": res_a,
            "res_b": res_b,
            "scores_match": scores_match,
            "moves_match": moves_match,
            "pos_pvs_narrow": pos_pvs_narrow,
            "pos_pvs_re": pos_pvs_re,
            "pos_speedup_final": pos_speedup_final,
            "pos_speedup_cum": pos_speedup_cum,
        }
        position_results.append(pos_info)

        print(f"[{idx:2d}/{len(fens)}] {name:<22} ({turn_str:<5}) -> {status_str}")
        print(f"       PVS Off: move={res_a['best_move'].uci():<5} | eval={res_a['best_value']:+.4f} | final_time={rec_a_final['elapsed_time']:6.2f}s | cum_time={res_a['cumulative_time']:6.2f}s | nodes_final={rec_a_final['nodes_visited']:4d} | nodes_cum={res_a['cumulative_nodes']:4d} | NN_final={rec_a_final['neural_evaluations']:4d} | NN_cum={res_a['cumulative_nn_evals']:4d} | cutoffs_final={rec_a_final['alpha_beta_cutoffs']:3d} | cutoffs_cum={res_a['cumulative_cutoffs']:3d}")
        print(f"       PVS On:  move={res_b['best_move'].uci():<5} | eval={res_b['best_value']:+.4f} | final_time={rec_b_final['elapsed_time']:6.2f}s | cum_time={res_b['cumulative_time']:6.2f}s | nodes_final={rec_b_final['nodes_visited']:4d} | nodes_cum={res_b['cumulative_nodes']:4d} | NN_final={rec_b_final['neural_evaluations']:4d} | NN_cum={res_b['cumulative_nn_evals']:4d} | cutoffs_final={rec_b_final['alpha_beta_cutoffs']:3d} | cutoffs_cum={res_b['cumulative_cutoffs']:3d}")
        print(f"       PVS Ops: narrow_searches={pos_pvs_narrow:3d} (final={rec_b_final['pvs_narrow_searches']:3d}) | researches={pos_pvs_re:3d} (final={rec_b_final['pvs_researches']:3d})")
        print(f"       Speedup: final-depth={pos_speedup_final:5.2f}x | cumulative={pos_speedup_cum:5.2f}x\n")

    # Aggregate calculations
    final_node_red = (1.0 - (tot_nodes_b_final / tot_nodes_a_final)) * 100.0 if tot_nodes_a_final > 0 else 0.0
    final_nn_red = (1.0 - (tot_nn_b_final / tot_nn_a_final)) * 100.0 if tot_nn_a_final > 0 else 0.0
    final_speedup = (tot_time_a_final / tot_time_b_final) if tot_time_b_final > 0 else 0.0

    cum_node_red = (1.0 - (tot_nodes_b_cum / tot_nodes_a_cum)) * 100.0 if tot_nodes_a_cum > 0 else 0.0
    cum_nn_red = (1.0 - (tot_nn_b_cum / tot_nn_a_cum)) * 100.0 if tot_nn_a_cum > 0 else 0.0
    cum_speedup = (tot_time_a_cum / tot_time_b_cum) if tot_time_b_cum > 0 else 0.0

    re_search_rate = (tot_pvs_re_cum / tot_pvs_narrow_cum * 100.0) if tot_pvs_narrow_cum > 0 else 0.0

    print("=" * 88)
    print(f"          PRINCIPAL VARIATION SEARCH (PVS) A/B BENCHMARK REPORT (DEPTH {depth})")
    print("=" * 88)
    print(f"{'Metric':<42} | {'Run A (PVS Disabled)':<20} | {'Run B (PVS Enabled)':<20}")
    print("-" * 88)
    print(f"{'All Best Scores Identical':<42} | {'N/A':<20} | {str(all_scores_match):<20}")
    print(f"{'All Selected Moves Identical':<42} | {'N/A':<20} | {str(all_moves_match):<20}")
    print(f"{'Positions Evaluated':<42} | {len(fens):<20} | {len(fens):<20}")
    print("-" * 88)
    print("FINAL-DEPTH METRICS (Depth {depth}):".format(depth=depth))
    print(f"  {'Final-Depth Nodes Visited':<40} | {tot_nodes_a_final:<20} | {tot_nodes_b_final:<20}")
    print(f"  {'Final-Depth Node Reduction':<40} | {'baseline':<20} | {final_node_red:16.1f} %")
    print(f"  {'Final-Depth NN Evaluations':<40} | {tot_nn_a_final:<20} | {tot_nn_b_final:<20}")
    print(f"  {'Final-Depth NN Reduction':<40} | {'baseline':<20} | {final_nn_red:16.1f} %")
    print(f"  {'Final-Depth Cutoffs':<40} | {tot_cutoffs_a_final:<20} | {tot_cutoffs_b_final:<20}")
    print(f"  {'Final-Depth Elapsed Time':<40} | {tot_time_a_final:16.2f} s | {tot_time_b_final:16.2f} s")
    print(f"  {'Final-Depth Speedup':<40} | {'1.00x':<20} | {final_speedup:16.2f} x")
    print("-" * 88)
    print("CUMULATIVE SEARCH METRICS (Depths 1 to {depth}):".format(depth=depth))
    print(f"  {'Cumulative Nodes Visited':<40} | {tot_nodes_a_cum:<20} | {tot_nodes_b_cum:<20}")
    print(f"  {'Cumulative Node Reduction':<40} | {'baseline':<20} | {cum_node_red:16.1f} %")
    print(f"  {'Cumulative NN Evaluations':<40} | {tot_nn_a_cum:<20} | {tot_nn_b_cum:<20}")
    print(f"  {'Cumulative NN Reduction':<40} | {'baseline':<20} | {cum_nn_red:16.1f} %")
    print(f"  {'Cumulative Cutoffs':<40} | {tot_cutoffs_a_cum:<20} | {tot_cutoffs_b_cum:<20}")
    print(f"  {'Cumulative Elapsed Time':<40} | {tot_time_a_cum:16.2f} s | {tot_time_b_cum:16.2f} s")
    print(f"  {'Cumulative Search Speedup':<40} | {'1.00x':<20} | {cum_speedup:16.2f} x")
    print("-" * 88)
    print("PVS INSTRUMENTATION (Run B):")
    print(f"  {'Total PVS Narrow-Window Searches':<40} | {'N/A':<20} | {tot_pvs_narrow_cum:<20}")
    print(f"  {'Total PVS Re-searches':<40} | {'N/A':<20} | {tot_pvs_re_cum:<20}")
    print(f"  {'PVS Re-search Rate':<40} | {'N/A':<20} | {re_search_rate:16.1f} %")
    print(f"  {'Final-Depth PVS Narrow Searches':<40} | {'N/A':<20} | {tot_pvs_narrow_final:<20}")
    print(f"  {'Final-Depth PVS Re-searches':<40} | {'N/A':<20} | {tot_pvs_re_final:<20}")
    print("-" * 88)
    print("TRANSPOSITION TABLE INSTRUMENTATION (Run B):")
    print(f"  {'Total TT Probes':<40} | {'N/A':<20} | {tot_tt_probes_b:<20}")
    print(f"  {'Total TT Hits':<40} | {'N/A':<20} | {tot_tt_hits_b:<20}")
    print(f"  {'TT Best-Move Ordering Hits':<40} | {'N/A':<20} | {tot_tt_ordering_hits_b:<20}")
    print(f"  {'TT-Induced Cutoffs':<40} | {'N/A':<20} | {tot_tt_cutoffs_b:<20}")
    print(f"  {'Total TT Stores':<40} | {'N/A':<20} | {tot_tt_stores_b:<20}")
    print("=" * 88 + "\n")

    if mismatches:
        print("INVESTIGATION OF MISMATCHES:")
        for m in mismatches:
            print(f"  * {m}")

    return {
        "all_scores_match": all_scores_match,
        "all_moves_match": all_moves_match,
        "mismatches": mismatches,
        "position_results": position_results,
        "tot_pvs_narrow_cum": tot_pvs_narrow_cum,
        "tot_pvs_re_cum": tot_pvs_re_cum,
        "tot_pvs_narrow_final": tot_pvs_narrow_final,
        "tot_pvs_re_final": tot_pvs_re_final,
        "tot_nodes_a_final": tot_nodes_a_final,
        "tot_nodes_b_final": tot_nodes_b_final,
        "tot_nn_a_final": tot_nn_a_final,
        "tot_nn_b_final": tot_nn_b_final,
        "tot_cutoffs_a_final": tot_cutoffs_a_final,
        "tot_cutoffs_b_final": tot_cutoffs_b_final,
        "tot_time_a_final": tot_time_a_final,
        "tot_time_b_final": tot_time_b_final,
        "tot_nodes_a_cum": tot_nodes_a_cum,
        "tot_nodes_b_cum": tot_nodes_b_cum,
        "tot_nn_a_cum": tot_nn_a_cum,
        "tot_nn_b_cum": tot_nn_b_cum,
        "tot_cutoffs_a_cum": tot_cutoffs_a_cum,
        "tot_cutoffs_b_cum": tot_cutoffs_b_cum,
        "tot_time_a_cum": tot_time_a_cum,
        "tot_time_b_cum": tot_time_b_cum,
        "final_node_red": final_node_red,
        "final_nn_red": final_nn_red,
        "final_speedup": final_speedup,
        "cum_node_red": cum_node_red,
        "cum_nn_red": cum_nn_red,
        "cum_speedup": cum_speedup,
    }


# ------------------------------------------------------------
# 12) HUMAN VS AI TERMINAL MODE
# ------------------------------------------------------------
def format_board(board: chess.Board, orientation: chess.Color = chess.WHITE) -> str:
    """
    Renders the chess board clearly with rank and file labels for terminal display.
    """
    lines = []
    files_str = "    a b c d e f g h" if orientation == chess.WHITE else "    h g f e d c b a"
    lines.append(files_str)
    lines.append("  +-----------------+")

    ranks = range(7, -1, -1) if orientation == chess.WHITE else range(8)
    files = range(8) if orientation == chess.WHITE else range(7, -1, -1)

    for rank in ranks:
        row_pieces = []
        for file in files:
            sq = chess.square(file, rank)
            piece = board.piece_at(sq)
            row_pieces.append(piece.symbol() if piece else ".")
        rank_num = rank + 1
        lines.append(f"{rank_num} | {' '.join(row_pieces)} | {rank_num}")

    lines.append("  +-----------------+")
    lines.append(files_str)
    return "\n".join(lines)


def check_game_termination(board: chess.Board) -> tuple[bool, str, str]:
    """
    Checks if the game has terminated under standard chess and draw claim rules.
    Returns: (is_terminated, reason_description, result_string)
    """
    if board.is_checkmate():
        winner = "Black" if board.turn == chess.WHITE else "White"
        result = "0-1" if winner == "Black" else "1-0"
        return True, f"Checkmate! {winner} wins.", result

    if board.is_stalemate():
        return True, "Draw by Stalemate.", "1/2-1/2"

    if board.is_insufficient_material():
        return True, "Draw by Insufficient Material.", "1/2-1/2"

    if board.is_fivefold_repetition() or board.can_claim_threefold_repetition():
        return True, "Draw by Threefold/Fivefold Repetition.", "1/2-1/2"

    if board.is_seventyfive_moves() or board.can_claim_fifty_moves():
        return True, "Draw by 50-Move / 75-Move Rule.", "1/2-1/2"

    if board.is_game_over(claim_draw=True):
        return True, "Game Over.", board.result(claim_draw=True)

    return False, "", ""


def play_human_vs_ai(
    model,
    default_depth: int = 2,
    human_color: chess.Color = None,
    depth: int = None,
    initial_board: chess.Board = None,
    input_fn=input,
    print_fn=print,
    max_plies: int = 600,
):
    """
    Interactive terminal mode for Human vs AI play using the validated
    Iterative Deepening + TT + PVS engine with deterministic tie-breaking.
    """
    print_fn("\n" + "=" * 60)
    print_fn("           CHESS AI: HUMAN vs ENGINE (PVS)")
    print_fn("=" * 60)

    # 1. Configurable search depth (default=2)
    if depth is None:
        while True:
            raw_d = input_fn(f"Enter search depth for AI (1-4, default={default_depth}): ").strip()
            if not raw_d:
                depth = default_depth
                break
            try:
                depth = int(raw_d)
                if depth >= 1:
                    break
                print_fn("Depth must be a positive integer (e.g. 2).")
            except ValueError:
                print_fn("Invalid input. Please enter an integer.")

    # 2. Side selection (White or Black)
    if human_color is None:
        while True:
            choice = input_fn("Choose your color ([W]hite / [B]lack, default=White): ").strip().lower()
            if choice in ("", "w", "white"):
                human_color = chess.WHITE
                break
            elif choice in ("b", "black"):
                human_color = chess.BLACK
                break
            else:
                print_fn("Please enter 'w' for White or 'b' for Black.")

    ai_color = chess.BLACK if human_color == chess.WHITE else chess.WHITE
    human_str = "White" if human_color == chess.WHITE else "Black"
    ai_str = "Black" if human_color == chess.WHITE else "White"

    print_fn(f"\nYou are playing as {human_str}.")
    print_fn(f"AI is playing as {ai_str} at Depth {depth} (PVS + TT enabled).")
    print_fn("Enter moves in standard UCI format (e.g. 'e2e4', 'g1f3', 'e7e8q').")
    print_fn("Commands: 'quit' to exit, 'moves' to list legal moves, 'fen' to show FEN.\n")

    board = initial_board.copy() if initial_board is not None else chess.Board()
    clear_tt()
    set_eval_cache_enabled(False)
    clear_eval_cache()

    ply = len(board.move_stack)
    while ply < max_plies:
        is_over, reason, res_str = check_game_termination(board)
        if is_over:
            print_fn("\n" + format_board(board, orientation=human_color))
            print_fn("\n" + "=" * 60)
            print_fn(f"GAME OVER: {reason}")
            print_fn(f"Final Result: {res_str}")
            print_fn("=" * 60 + "\n")
            return board

        print_fn("\n" + format_board(board, orientation=human_color))
        turn_str = "White" if board.turn == chess.WHITE else "Black"
        move_num = (ply // 2) + 1
        print_fn(f"\nMove {move_num} | {turn_str} to move.")

        if board.turn == human_color:
            # Human turn
            while True:
                user_cmd = input_fn(f"Your move ({human_str}) > ").strip()
                if not user_cmd:
                    continue
                if user_cmd.lower() in ("quit", "exit", "q"):
                    print_fn("Game aborted by user.")
                    return board
                if user_cmd.lower() == "fen":
                    print_fn(f"Current FEN: {board.fen()}")
                    continue
                if user_cmd.lower() in ("moves", "legal"):
                    legal_uci = [m.uci() for m in board.legal_moves]
                    print_fn(f"Legal moves ({len(legal_uci)}): {', '.join(legal_uci)}")
                    continue

                # Parse move: try UCI first, then SAN fallback
                parsed_move = None
                try:
                    m = chess.Move.from_uci(user_cmd.lower())
                    if m in board.legal_moves:
                        parsed_move = m
                except ValueError:
                    pass

                if parsed_move is None:
                    try:
                        m = board.parse_san(user_cmd)
                        if m in board.legal_moves:
                            parsed_move = m
                    except ValueError:
                        pass

                if parsed_move is not None:
                    board.push(parsed_move)
                    ply += 1
                    print_fn(f"You played: {parsed_move.uci()}")
                    break
                else:
                    print_fn(f"Illegal or unrecognized move '{user_cmd}'. Type 'moves' to see legal UCI moves.")
        else:
            # AI turn
            print_fn(f"AI ({ai_str}) is calculating (depth {depth})...")
            reset_search_stats()
            t0 = time.perf_counter()
            id_res = iterative_deepening_search(
                board,
                max_depth=depth,
                model=model,
                propagate_root_bounds=True,
                randomize_equal_moves=False,
                use_tt=True,
                use_pvs=True,
            )
            elapsed = time.perf_counter() - t0
            ai_move = id_res["best_move"]
            ai_val = id_res["best_value"]

            if ai_move is None or ai_move not in board.legal_moves:
                print_fn("AI could not find a legal move.")
                break

            board.push(ai_move)
            ply += 1
            print_fn(f"AI played: {ai_move.uci()} | Evaluation: {ai_val:+.4f} | Time: {elapsed:.2f}s | Nodes: {id_res['cumulative_nodes']}")

    is_over, reason, res_str = check_game_termination(board)
    if is_over:
        print_fn("\n" + format_board(board, orientation=human_color))
        print_fn(f"\nGAME OVER: {reason} (Result: {res_str})")

    return board


if __name__ == "__main__":
    # Clean Human vs AI terminal mode (default depth=2):
    play_human_vs_ai(model, default_depth=2)

    # Benchmark options available for on-demand execution:
    # run_ab_benchmark(model, depth=2, max_plies=600, random_seed=42)
    # run_iterative_deepening_benchmark(model)
    # run_tt_ab_benchmark(model, fens=DEPTH3_BENCHMARK_FENS, depth=3)
    # run_pvs_ab_benchmark(model, fens=DEPTH3_BENCHMARK_FENS, depth=3)





