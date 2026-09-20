import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

import unittest
import time
from unittest.mock import patch
import chess

from stage5_ui.backend.game_manager import GameManager


class TestGameStartClockSemantics(unittest.TestCase):
    def setUp(self):
        self.gm = GameManager()

    def test_new_game_as_white_clocks_paused_until_first_move(self):
        # 1. New Game as White (3 min)
        res = self.gm.new_game(human_color_str="white", depth=1, time_control=180)
        self.assertFalse(res.clock.game_started)
        self.assertIsNone(res.clock.active_clock)
        self.assertEqual(res.clock.white_time, 180.0)
        self.assertEqual(res.clock.black_time, 180.0)

        # 2. Wait 0.4s: both clocks must remain strictly frozen at 180.0
        time.sleep(0.4)
        res_check = self.gm.get_state_response(log=False)
        self.assertFalse(res_check.clock.game_started)
        self.assertIsNone(res_check.clock.active_clock)
        self.assertEqual(res_check.clock.white_time, 180.0)
        self.assertEqual(res_check.clock.black_time, 180.0)

        # 3. Human plays 1. e4: first move consumes zero time!
        res_after_move1 = self.gm.apply_move("e2e4")
        self.assertTrue(res_after_move1.clock.game_started)
        self.assertEqual(res_after_move1.clock.active_clock, "black")
        self.assertEqual(res_after_move1.clock.white_time, 180.0)
        self.assertEqual(res_after_move1.clock.black_time, 180.0)

        # 4. Wait 0.3s: Black clock now counts down, White clock stays at 180.0
        time.sleep(0.3)
        res_after_wait = self.gm.get_state_response(log=False)
        self.assertTrue(res_after_wait.clock.game_started)
        self.assertEqual(res_after_wait.clock.active_clock, "black")
        self.assertEqual(res_after_wait.clock.white_time, 180.0)
        self.assertLess(res_after_wait.clock.black_time, 180.0)

    def test_new_game_as_black_ai_opening_move_consumes_no_time(self):
        # 1. New Game as Black (3 min)
        res = self.gm.new_game(human_color_str="black", depth=1, time_control=180)
        self.assertFalse(res.clock.game_started)
        self.assertIsNone(res.clock.active_clock)
        self.assertEqual(res.clock.white_time, 180.0)
        self.assertEqual(res.clock.black_time, 180.0)

        # Mock a 1.0s search duration for AI opening move
        def mock_compute_ai_move(board, depth):
            time.sleep(1.0)
            return chess.Move.from_uci("e2e4"), {
                "depth": depth,
                "evaluation": 0.1,
                "search_time": 1.0,
                "nodes_visited": 100,
                "neural_evaluations": 90,
                "cutoffs": 5,
            }

        # 2. Engine makes opening move 1 as White
        with patch("stage5_ui.backend.game_manager.engine_adapter.compute_ai_move", side_effect=mock_compute_ai_move):
            res_engine = self.gm.apply_engine_move()

        # Opening AI move must NOT consume clock time!
        self.assertTrue(res_engine.clock.game_started)
        self.assertEqual(res_engine.clock.active_clock, "black")
        self.assertEqual(res_engine.clock.white_time, 180.0, "AI opening move should consume 0s!")
        self.assertEqual(res_engine.clock.black_time, 180.0, "Black clock should start from full 180.0s!")

        # 3. Wait 0.3s: Black clock counts down while human thinks for move 1
        time.sleep(0.3)
        res_after_wait = self.gm.get_state_response(log=False)
        self.assertEqual(res_after_wait.clock.white_time, 180.0)
        self.assertLess(res_after_wait.clock.black_time, 180.0)

    def test_from_ply_2_onward_normal_timing_applies(self):
        # White human move 1 (0s)
        self.gm.new_game(human_color_str="white", depth=1, time_control=180)
        self.gm.apply_move("e2e4")

        # Mock 1.0s search for Black AI move 1
        def mock_compute_ai_move(board, depth):
            time.sleep(1.0)
            return chess.Move.from_uci("e7e5"), {
                "depth": depth,
                "evaluation": 0.0,
                "search_time": 1.0,
                "nodes_visited": 100,
                "neural_evaluations": 90,
                "cutoffs": 5,
            }

        with patch("stage5_ui.backend.game_manager.engine_adapter.compute_ai_move", side_effect=mock_compute_ai_move):
            res_black = self.gm.apply_engine_move()

        # Black is ply 2: normal timing applies! Black clock lost ~1.0s
        self.assertAlmostEqual(res_black.clock.black_time, 179.0, delta=0.25)
        self.assertEqual(res_black.clock.active_clock, "white")

        # Human White thinks for move 2
        time.sleep(0.4)
        res_white_thinking = self.gm.get_state_response(log=False)
        self.assertLess(res_white_thinking.clock.white_time, 180.0)

    def test_restart_resets_game_started_and_exact_clocks(self):
        self.gm.new_game(human_color_str="white", depth=1, time_control=180)
        self.gm.apply_move("e2e4")
        self.assertTrue(self.gm.game_started)

        # Restart with 5 min
        res_restart = self.gm.new_game(human_color_str="white", depth=1, time_control=300)
        self.assertFalse(res_restart.clock.game_started)
        self.assertIsNone(res_restart.clock.active_clock)
        self.assertEqual(res_restart.clock.white_time, 300.0)
        self.assertEqual(res_restart.clock.black_time, 300.0)

    def test_refresh_preserves_game_started_state(self):
        # Before move 1: game_started is False
        self.gm.new_game(human_color_str="white", depth=1, time_control=180)
        res1 = self.gm.get_state_response(log=False)
        self.assertFalse(res1.clock.game_started)

        # After move 1: game_started is True
        self.gm.apply_move("e2e4")
        res2 = self.gm.get_state_response(log=False)
        self.assertTrue(res2.clock.game_started)
        self.assertEqual(res2.clock.active_clock, "black")


if __name__ == "__main__":
    unittest.main()
