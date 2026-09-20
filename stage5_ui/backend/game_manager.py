import time
from typing import List, Dict, Optional, Tuple
import uuid
import threading
import chess

from .schemas import (
    GameStateResponse,
    GameStatus,
    CapturedPieces,
    MoveHistoryItem,
    MoveResult,
    EngineTelemetry,
    ClockState,
)
from .engine_adapter import engine_adapter
from .tracing import log_trace

# Piece values for material advantage calculation
PIECE_VALUES = {
    chess.PAWN: 1,
    chess.KNIGHT: 3,
    chess.BISHOP: 3,
    chess.ROOK: 5,
    chess.QUEEN: 9,
}

PIECE_NAMES = {
    chess.PAWN: "pawn",
    chess.KNIGHT: "knight",
    chess.BISHOP: "bishop",
    chess.ROOK: "rook",
    chess.QUEEN: "queen",
    chess.KING: "king",
}


class GameManager:
    """
    Authoritative backend chess session manager.
    Maintains official chess.Board(), enforces legality, updates move history,
    and coordinates AI responses via the EngineAdapter.

    Concurrency Architecture:
    - state_lock: Short, microsecond-level lock protecting authoritative session
      mutations and state reads. Minimax search NEVER runs under state_lock.
    - search_lock: Serializes Stage 4 search execution and global Transposition
      Table access so only one search executes at a time.
    """

    def __init__(self):
        self.state_lock = threading.Lock()
        self.search_lock = threading.Lock()
        self.is_searching = False
        self.pending_tt_reset = False

        self.game_id: str = f"game_{uuid.uuid4().hex[:8]}"
        self.version: int = 0
        self.board: chess.Board = chess.Board()
        self.human_color: chess.Color = chess.WHITE
        self.depth: int = 2
        self.history: List[MoveHistoryItem] = []
        self.last_move: Optional[MoveResult] = None
        self.last_telemetry: Optional[EngineTelemetry] = None

        # Bullet Chess Clock System
        self.game_started: bool = False
        self.time_control: int = 180
        self.white_time: float = 180.0
        self.black_time: float = 180.0
        self.last_clock_update: Optional[float] = None
        self.active_clock: Optional[str] = None
        self.is_timeout: bool = False
        self.timeout_winner: Optional[str] = None

    def new_game(
        self,
        human_color_str: str = "white",
        depth: int = 2,
        time_control: int = 180,
    ) -> GameStateResponse:
        """
        Starts a brand new game session.
        Resets authoritative state immediately without waiting for any active search.
        If an old search is still in progress, TT reset is deferred until the search releases search_lock.
        """
        with self.state_lock:
            fen_before = self.board.fen()
            old_game_id = self.game_id

            # Create new game session
            self.game_id = f"game_{uuid.uuid4().hex[:8]}"
            self.version = 1
            self.board = chess.Board()
            self.human_color = chess.WHITE if human_color_str.lower() == "white" else chess.BLACK
            self.depth = max(1, min(4, depth))
            self.history = []
            self.last_move = None
            self.last_telemetry = None

            # Reset clocks in paused GAME READY state
            self.game_started = False
            tc = 300 if time_control == 300 else 180
            self.time_control = tc
            self.white_time = float(tc)
            self.black_time = float(tc)
            self.is_timeout = False
            self.timeout_winner = None
            self.active_clock = None
            self.last_clock_update = None

            # If search is active, defer TT clearing until engine search finishes
            if self.search_lock.locked():
                self.pending_tt_reset = True
                print(f"[GAME MANAGER] Active search in progress; deferring Stage 4 TT reset until search lock release.")
            else:
                engine_adapter.reset_for_new_game()
                self.pending_tt_reset = False

            fen_after = self.board.fen()
            log_trace(
                endpoint="/api/game/new",
                method="POST",
                fen_before=fen_before,
                fen_after=fen_after,
                session_id=self.game_id,
                details={
                    "old_session_id": old_game_id,
                    "human_color": human_color_str,
                    "depth": depth,
                    "version": self.version,
                    "time_control": self.time_control,
                },
            )

            return self._build_state_response(log=False)

    def _update_clock_under_lock(self, now: Optional[float] = None) -> None:
        """
        Deducts elapsed time from the active clock using monotonic timestamps.
        Must be called with state_lock held.
        Clocks remain strictly paused if game_started is False.
        """
        if not self.game_started or self.is_timeout or self.active_clock is None:
            return

        if now is None:
            now = time.monotonic()

        if self.last_clock_update is not None:
            elapsed = max(0.0, now - self.last_clock_update)
            if self.active_clock == "white":
                self.white_time = max(0.0, self.white_time - elapsed)
                if self.white_time <= 0.0:
                    self.white_time = 0.0
                    self._trigger_timeout("white")
            elif self.active_clock == "black":
                self.black_time = max(0.0, self.black_time - elapsed)
                if self.black_time <= 0.0:
                    self.black_time = 0.0
                    self._trigger_timeout("black")

        self.last_clock_update = now

    def _trigger_timeout(self, timed_out_side: str) -> None:
        """Flags game as terminated by time forfeit."""
        self.is_timeout = True
        self.timeout_winner = "black" if timed_out_side == "white" else "white"
        self.active_clock = None

    def apply_move(
        self,
        move_str: str,
        game_id: Optional[str] = None,
        expected_version: Optional[int] = None,
    ) -> GameStateResponse:
        """
        Applies exactly one human move (UCI or SAN) and immediately returns authoritative state.
        Validates game_id and expected_version to reject stale requests.
        """
        with self.state_lock:
            if self.is_searching:
                raise ValueError("Engine is currently calculating a move. Concurrent moves rejected.")

            # Validate request session versioning
            if game_id is not None and self.game_id != game_id:
                raise ValueError(f"Stale game ID: active game is '{self.game_id}', request received '{game_id}'.")
            if expected_version is not None and self.version != expected_version:
                raise ValueError(
                    f"Stale game version: active version is {self.version}, request expected {expected_version}."
                )

            # Update clock for human thinking time only if game has started
            if self.game_started:
                self._update_clock_under_lock()
                if self.is_timeout:
                    raise ValueError("Game is already over: time forfeit.")

            fen_before = self.board.fen()

            # Check if human turn
            if self.board.turn != self.human_color:
                raise ValueError("Not player's turn.")

            # Check if game is already over
            is_over, _, _ = engine_adapter.check_termination(self.board)
            if is_over:
                self.active_clock = None
                raise ValueError("Game is already over.")

            # Parse move
            move = self._parse_move(move_str)
            if move is None or move not in self.board.legal_moves:
                raise ValueError(f"Illegal or unrecognized move: '{move_str}'")

            # Record and apply human move
            san = self.board.san(move)
            color_str = "white" if self.board.turn == chess.WHITE else "black"
            self.board.push(move)
            self.version += 1

            # Check termination after move
            is_over_now, _, _ = engine_adapter.check_termination(self.board)
            if is_over_now:
                self.active_clock = None
            else:
                self.game_started = True
                self.active_clock = "black" if self.board.turn == chess.BLACK else "white"
                self.last_clock_update = time.monotonic()

            ply = len(self.board.move_stack)
            move_num = (ply + 1) // 2
            hist_item = MoveHistoryItem(
                ply=ply,
                move_number=move_num,
                color=color_str,
                uci=move.uci(),
                san=san,
            )
            self.history.append(hist_item)

            self.last_move = MoveResult(
                uci=move.uci(),
                san=san,
                color=color_str,
                telemetry=None,
            )

            fen_after = self.board.fen()
            log_trace(
                endpoint="/api/game/move",
                method="POST",
                fen_before=fen_before,
                fen_after=fen_after,
                session_id=self.game_id,
                details={"human_move": move_str, "version": self.version},
            )

            return self._build_state_response(log=False)

    def apply_engine_move(
        self,
        game_id: Optional[str] = None,
        expected_version: Optional[int] = None,
    ) -> GameStateResponse:
        """
        Calculates and applies exactly one AI move on an isolated board snapshot.
        Authoritative GameManager.board is NEVER mutated by minimax push/pop.
        Revalidates game_id and version after search completes before committing.
        """
        # Ensure only one search executes globally
        search_acquired = self.search_lock.acquire(blocking=False)
        if not search_acquired:
            raise ValueError("Engine is currently calculating a move. Concurrent searches rejected.")

        try:
            # Handle any deferred TT reset
            with self.state_lock:
                if self.pending_tt_reset:
                    engine_adapter.reset_for_new_game()
                    self.pending_tt_reset = False

            # 1. Snapshot search state under short state_lock
            with self.state_lock:
                # Update clock up to search start only if game has started
                if self.game_started:
                    self._update_clock_under_lock()
                    if self.is_timeout:
                        raise ValueError("Cannot calculate move: game is already over (time forfeit).")

                # Validate session versioning
                if game_id is not None and self.game_id != game_id:
                    raise ValueError(f"Stale game ID: active game is '{self.game_id}', request received '{game_id}'.")
                if expected_version is not None and self.version != expected_version:
                    raise ValueError(
                        f"Stale game version: active version is {self.version}, request expected {expected_version}."
                    )

                # Verify it is engine's turn
                if self.board.turn == self.human_color:
                    raise ValueError("It is currently the human player's turn, not the engine's.")

                # Verify game is not over
                is_over, _, _ = engine_adapter.check_termination(self.board)
                if is_over:
                    self.active_clock = None
                    raise ValueError("Cannot calculate move: game is already over.")

                # Create isolated snapshot for minimax search
                snap_game_id = self.game_id
                snap_version = self.version
                snap_depth = self.depth
                search_board = self.board.copy(stack=True)
                ai_color_str = "white" if search_board.turn == chess.WHITE else "black"
                fen_before = self.board.fen()

                self.is_searching = True

            # 2. Execute search on isolated copy OUTSIDE state_lock
            ai_move, telemetry_dict = engine_adapter.compute_ai_move(search_board, depth=snap_depth)
            search_end_time = time.monotonic()

            # 3. Commit or discard under state_lock
            with self.state_lock:
                self.is_searching = False

                # Verify game session and version are still identical
                if self.game_id != snap_game_id or self.version != snap_version:
                    print(
                        f"[ENGINE MOVE DISCARDED] Search finished for game {snap_game_id} (v{snap_version}), "
                        f"but active session is now {self.game_id} (v{self.version}). Discarding obsolete AI move."
                    )
                    log_trace(
                        endpoint="/api/engine/move",
                        method="POST",
                        fen_before=fen_before,
                        fen_after=self.board.fen(),
                        session_id=self.game_id,
                        details={
                            "status": "DISCARDED_OBSOLETE",
                            "searched_game_id": snap_game_id,
                            "searched_version": snap_version,
                            "current_game_id": self.game_id,
                            "current_version": self.version,
                        },
                    )
                    return self._build_state_response(log=False)

                if not self.game_started:
                    # AI opening move (when Human plays Black): does not consume clock time!
                    if ai_move is None or ai_move not in self.board.legal_moves:
                        return self._build_state_response(log=False)

                    san = self.board.san(ai_move)
                    self.board.push(ai_move)
                    self.version += 1

                    is_over_now, _, _ = engine_adapter.check_termination(self.board)
                    if is_over_now:
                        self.active_clock = None
                    else:
                        self.game_started = True
                        self.active_clock = "black"
                        self.last_clock_update = time.monotonic()
                else:
                    # Normal bullet timing: charge elapsed search time to AI clock
                    self._update_clock_under_lock(now=search_end_time)

                    # Check if AI timed out during search
                    if self.is_timeout:
                        print("[ENGINE TIMEOUT] AI ran out of time during calculation.")
                        return self._build_state_response(log=False)

                    if ai_move is None or ai_move not in self.board.legal_moves:
                        return self._build_state_response(log=False)

                    # Apply verified move to authoritative board
                    san = self.board.san(ai_move)
                    self.board.push(ai_move)
                    self.version += 1

                    # Check termination after AI move
                    is_over_now, _, _ = engine_adapter.check_termination(self.board)
                    if is_over_now:
                        self.active_clock = None
                    else:
                        self.active_clock = "black" if self.board.turn == chess.BLACK else "white"
                        self.last_clock_update = time.monotonic()

                ply = len(self.board.move_stack)
                move_num = (ply + 1) // 2

                self.history.append(
                    MoveHistoryItem(
                        ply=ply,
                        move_number=move_num,
                        color=ai_color_str,
                        uci=ai_move.uci(),
                        san=san,
                    )
                )

                telemetry = EngineTelemetry(**telemetry_dict)
                self.last_telemetry = telemetry
                self.last_move = MoveResult(
                    uci=ai_move.uci(),
                    san=san,
                    color=ai_color_str,
                    telemetry=telemetry,
                )

                fen_after = self.board.fen()
                log_trace(
                    endpoint="/api/engine/move",
                    method="POST",
                    fen_before=fen_before,
                    fen_after=fen_after,
                    session_id=self.game_id,
                    details={
                        "ai_move": self.last_move.uci if self.last_move else None,
                        "version": self.version,
                        "depth": self.depth,
                    },
                )

                return self._build_state_response(log=False)

        finally:
            self.search_lock.release()

            # If a TT reset was deferred during our search, execute it now safely under search_lock
            if self.pending_tt_reset:
                if self.search_lock.acquire(blocking=False):
                    try:
                        with self.state_lock:
                            if self.pending_tt_reset:
                                engine_adapter.reset_for_new_game()
                                self.pending_tt_reset = False
                    finally:
                        self.search_lock.release()

    def _parse_move(self, move_str: str) -> Optional[chess.Move]:
        """Tries to parse move from UCI first, then SAN."""
        clean_str = move_str.strip()
        try:
            m = chess.Move.from_uci(clean_str.lower())
            if m in self.board.legal_moves:
                return m
        except ValueError:
            pass

        try:
            m = self.board.parse_san(clean_str)
            if m in self.board.legal_moves:
                return m
        except ValueError:
            pass

        return None

    def get_captured_pieces(self) -> CapturedPieces:
        """
        Calculates captured pieces by comparing starting piece counts with the current board.
        Returns White captured by Black, Black captured by White, and material advantage.
        Must be called with state_lock held.
        """
        starting_counts = {
            chess.PAWN: 8,
            chess.KNIGHT: 2,
            chess.BISHOP: 2,
            chess.ROOK: 2,
            chess.QUEEN: 1,
        }

        white_on_board = {pt: 0 for pt in starting_counts}
        black_on_board = {pt: 0 for pt in starting_counts}

        for square in chess.SQUARES:
            piece = self.board.piece_at(square)
            if piece and piece.piece_type in starting_counts:
                if piece.color == chess.WHITE:
                    white_on_board[piece.piece_type] += 1
                else:
                    black_on_board[piece.piece_type] += 1

        white_captured: List[str] = []
        black_captured: List[str] = []

        white_material = 0
        black_material = 0

        for pt, start_qty in starting_counts.items():
            w_missing = max(0, start_qty - white_on_board[pt])
            b_missing = max(0, start_qty - black_on_board[pt])
            name = PIECE_NAMES[pt]

            white_captured.extend([name] * w_missing)
            black_captured.extend([name] * b_missing)

            white_material += white_on_board[pt] * PIECE_VALUES[pt]
            black_material += black_on_board[pt] * PIECE_VALUES[pt]

        return CapturedPieces(
            white=white_captured,
            black=black_captured,
            material_advantage=white_material - black_material,
        )

    def get_game_status(self) -> GameStatus:
        """Returns game termination status. Must be called with state_lock held."""
        if self.is_timeout:
            winner = self.timeout_winner
            result = "1-0" if winner == "white" else "0-1"
            timed_out_side = "White" if winner == "black" else "Black"
            return GameStatus(
                is_over=True,
                winner=winner,
                reason=f"Time forfeit: {timed_out_side} ran out of time.",
                result=result,
                is_check=self.board.is_check(),
            )

        is_over, reason, result = engine_adapter.check_termination(self.board)
        if is_over:
            self.active_clock = None

        winner = None
        if is_over:
            if result == "1-0":
                winner = "white"
            elif result == "0-1":
                winner = "black"

        return GameStatus(
            is_over=is_over,
            winner=winner,
            reason=reason if is_over else None,
            result=result if is_over else "*",
            is_check=self.board.is_check(),
        )

    def get_state_response(self, log: bool = True) -> GameStateResponse:
        """Returns authoritative game state under state_lock."""
        with self.state_lock:
            self._update_clock_under_lock()
            return self._build_state_response(log=log)

    def _build_state_response(self, log: bool = True) -> GameStateResponse:
        """Builds GameStateResponse from current authoritative board. Must be called with state_lock held."""
        turn_str = "white" if self.board.turn == chess.WHITE else "black"
        human_str = "white" if self.human_color == chess.WHITE else "black"
        legal_uci = [] if (self.is_timeout or self.board.is_game_over()) else [m.uci() for m in self.board.legal_moves]
        fen_current = self.board.fen()

        if log:
            log_trace(
                endpoint="/api/game/state",
                method="GET",
                fen_before=fen_current,
                fen_after=fen_current,
                session_id=self.game_id,
                details={"version": self.version},
            )

        return GameStateResponse(
            game_id=self.game_id,
            version=self.version,
            fen=fen_current,
            turn=turn_str,
            human_color=human_str,
            depth=self.depth,
            legal_moves=legal_uci,
            last_move=self.last_move,
            game_status=self.get_game_status(),
            captured=self.get_captured_pieces(),
            history=self.history,
            telemetry=self.last_telemetry,
            clock=ClockState(
                white_time=round(max(0.0, self.white_time), 2),
                black_time=round(max(0.0, self.black_time), 2),
                active_clock=self.active_clock,
                time_control=self.time_control,
                game_started=self.game_started,
            ),
        )


game_manager = GameManager()
