import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

import unittest
import time
from unittest.mock import patch
import chess

from stage5_ui.backend.game_manager import GameManager
from stage5_ui.backend.schemas import ClockState


class TestClockAccountingAudit(unittest.TestCase):
    def setUp(self):
        self.gm = GameManager()

    def test_ai_search_deducted_exactly_once_not_twice(self):
        """
        Verify that AI thinking time is deducted exactly once (via active monotonic clock)
        and NOT twice (not double-subtracted using telemetry['search_time']).
        Mock a 2.0s search duration:
        - black_before - black_after should be ~2.0s, NOT ~4.0s.
        - white clock should not decrease during Black AI search.
        """
        # 1. Initialize 3-minute game where Human is White, AI is Black
        init_state = self.gm.new_game(human_color_str="white", depth=2, time_control=180)
        self.assertEqual(init_state.clock.time_control, 180)

        # 2. Human plays e2e4 (commits move, switches active clock to Black)
        state_after_human = self.gm.apply_move("e2e4")
        self.assertEqual(state_after_human.clock.active_clock, "black")
        
        black_before = state_after_human.clock.black_time
        white_before = state_after_human.clock.white_time

        # 3. Mock AI search with exact 2.0s duration and telemetry
        def mock_compute_ai_move(board, depth):
            time.sleep(2.0)
            return chess.Move.from_uci("e7e5"), {
                "depth": depth,
                "evaluation": 0.15,
                "search_time": 2.0,
                "nodes_visited": 500,
                "neural_evaluations": 450,
                "cutoffs": 20,
                "best_move_uci": "e7e5",
                "best_move_san": "e5",
            }

        with patch("stage5_ui.backend.game_manager.engine_adapter.compute_ai_move", side_effect=mock_compute_ai_move):
            state_after_ai = self.gm.apply_engine_move()

        black_after = state_after_ai.clock.black_time
        white_after = state_after_ai.clock.white_time

        elapsed_black = black_before - black_after
        elapsed_white = white_before - white_after

        print(f"\n[AUDIT CHECK 1] AI Thinking Time Deduction:")
        print(f"  Black clock before search : {black_before:.3f}s")
        print(f"  Black clock after commit  : {black_after:.3f}s")
        print(f"  Black elapsed decrease    : {elapsed_black:.3f}s (Target: ~2.0s, FAIL if ~4.0s)")
        print(f"  White clock before search : {white_before:.3f}s")
        print(f"  White clock after search  : {white_after:.3f}s")
        print(f"  White elapsed decrease    : {elapsed_white:.3f}s (Target: 0.0s)")

        # Verify elapsed_black is approximately 2.0s, NOT ~4.0s
        self.assertAlmostEqual(elapsed_black, 2.0, delta=0.25,
                               msg=f"Expected ~2.0s deduction, got {elapsed_black:.3f}s (potential double subtraction!)")
        self.assertLess(elapsed_black, 3.0,
                        msg=f"Elapsed black deduction ({elapsed_black:.3f}s) indicates double deduction!")

        # Verify White clock did NOT decrease during Black AI search
        self.assertAlmostEqual(elapsed_white, 0.0, delta=0.02,
                               msg="White clock decreased during Black AI search!")

        # Verify active clock switched back to White after AI move commit
        self.assertEqual(state_after_ai.clock.active_clock, "white")
        self.assertEqual(state_after_ai.last_move.uci, "e7e5")

    def test_timeout_occurs_before_move_commit_if_ai_runs_out_of_time(self):
        """
        Verify that if AI has less remaining time than search duration,
        timeout occurs before its move is committed to the authoritative board.
        """
        # 1. Human is White, AI is Black
        self.gm.new_game(human_color_str="white", depth=2, time_control=180)
        self.gm.apply_move("e2e4")

        # Artificially set Black clock to 0.8s
        with self.gm.state_lock:
            self.gm.black_time = 0.8
            self.gm.last_clock_update = time.monotonic()

        fen_before_ai = self.gm.board.fen()

        # Mock a 1.5s search (exceeds remaining 0.8s)
        def mock_compute_ai_move(board, depth):
            time.sleep(1.5)
            return chess.Move.from_uci("e7e5"), {
                "depth": depth,
                "evaluation": 0.0,
                "search_time": 1.5,
                "nodes_visited": 100,
                "neural_evaluations": 100,
                "cutoffs": 5,
            }

        with patch("stage5_ui.backend.game_manager.engine_adapter.compute_ai_move", side_effect=mock_compute_ai_move):
            res = self.gm.apply_engine_move()

        print(f"\n[AUDIT CHECK 2] Timeout During AI Search:")
        print(f"  Game is over: {res.game_status.is_over}")
        print(f"  Winner: {res.game_status.winner}")
        print(f"  Reason: {res.game_status.reason}")
        print(f"  Black time: {res.clock.black_time}s")
        print(f"  FEN unchanged: {res.fen == fen_before_ai}")

        # Assertions
        self.assertTrue(res.game_status.is_over, "Game should be terminated due to AI timeout")
        self.assertEqual(res.game_status.winner, "white", "White should win on Black timeout")
        self.assertEqual(res.game_status.result, "1-0")
        self.assertEqual(res.clock.black_time, 0.0)
        self.assertIsNone(res.clock.active_clock)
        # Move must NOT be committed
        self.assertEqual(res.fen, fen_before_ai, "AI move should NOT be committed after timeout!")
        self.assertEqual(len(res.history), 1, "Move history should only contain 1 move (e2e4)")

    def test_discarded_obsolete_search_deducts_zero_time_from_replacement_game(self):
        """
        Verify that when an obsolete search finishes after a game restart,
        it deducts zero time from the replacement game's clocks.
        """
        # Game 1: Human plays e4
        res1 = self.gm.new_game(human_color_str="white", depth=2, time_control=180)
        self.gm.apply_move("e2e4")
        old_game_id = self.gm.game_id
        old_version = self.gm.version

        # Now restart to Game 2 (5-minute game)
        res2 = self.gm.new_game(human_color_str="white", depth=2, time_control=300)
        new_game_id = self.gm.game_id

        g2_white_before = res2.clock.white_time
        g2_black_before = res2.clock.black_time

        # Attempt to commit obsolete search from Game 1
        with self.assertRaises(ValueError):
            self.gm.apply_engine_move(game_id=old_game_id, expected_version=old_version)

        # Check current state of Game 2
        state = self.gm.get_state_response(log=False)
        print(f"\n[AUDIT CHECK 3] Obsolete Search Discard Clock Isolation:")
        print(f"  Game 2 ID: {state.game_id}")
        print(f"  Game 2 White time: {state.clock.white_time}s (Initial: {g2_white_before}s)")
        print(f"  Game 2 Black time: {state.clock.black_time}s (Initial: {g2_black_before}s)")

        self.assertEqual(state.game_id, new_game_id)
        self.assertEqual(state.clock.time_control, 300)
        self.assertEqual(state.clock.black_time, 300.0, "Game 2 Black clock must be untouched!")
        self.assertAlmostEqual(state.clock.white_time, 300.0, delta=0.5,
                               msg="Game 2 White clock must remain intact!")


if __name__ == "__main__":
    unittest.main()
