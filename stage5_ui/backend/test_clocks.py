import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

import unittest
import time
import chess
from stage5_ui.backend.game_manager import GameManager
from stage5_ui.backend.schemas import ClockState


class TestBulletChessClocks(unittest.TestCase):
    def setUp(self):
        self.gm = GameManager()

    def test_clock_initialization_3min(self):
        res = self.gm.new_game(human_color_str="white", depth=1, time_control=180)
        self.assertEqual(res.clock.time_control, 180)
        self.assertEqual(res.clock.white_time, 180.0)
        self.assertEqual(res.clock.black_time, 180.0)
        self.assertIsNone(res.clock.active_clock)
        self.assertFalse(res.clock.game_started)
        self.assertFalse(res.game_status.is_over)

    def test_clock_initialization_5min(self):
        res = self.gm.new_game(human_color_str="white", depth=1, time_control=300)
        self.assertEqual(res.clock.time_control, 300)
        self.assertEqual(res.clock.white_time, 300.0)
        self.assertEqual(res.clock.black_time, 300.0)
        self.assertIsNone(res.clock.active_clock)
        self.assertFalse(res.clock.game_started)

    def test_white_clock_decreases_on_white_turn_after_start(self):
        self.gm.new_game(human_color_str="white", depth=1, time_control=180)
        # Before first move, clocks remain paused
        time.sleep(0.2)
        res_paused = self.gm.get_state_response(log=False)
        self.assertEqual(res_paused.clock.white_time, 180.0)
        self.assertEqual(res_paused.clock.black_time, 180.0)

        # White plays 1. e4 (takes 0s)
        res1 = self.gm.apply_move("e2e4")
        self.assertEqual(res1.clock.white_time, 180.0)
        self.assertEqual(res1.clock.active_clock, "black")

    def test_active_clock_switches_after_legal_move(self):
        self.gm.new_game(human_color_str="white", depth=1, time_control=180)
        res1 = self.gm.apply_move("e2e4")
        self.assertEqual(res1.clock.active_clock, "black")
        white_time_after_move = res1.clock.white_time

        time.sleep(0.3)
        res2 = self.gm.get_state_response(log=False)
        # Black clock should decrease
        self.assertLess(res2.clock.black_time, 180.0)
        # White clock should NOT decrease while Black's clock is active
        self.assertAlmostEqual(res2.clock.white_time, white_time_after_move, delta=0.01)

    def test_engine_search_time_counts_against_ai_clock(self):
        # Human is White, AI is Black
        self.gm.new_game(human_color_str="white", depth=1, time_control=180)
        self.gm.apply_move("e2e4")
        res_engine = self.gm.apply_engine_move()
        # Engine was Black, so black_time must have decreased
        self.assertLess(res_engine.clock.black_time, 180.0)
        # After engine move, active clock should switch back to White
        self.assertEqual(res_engine.clock.active_clock, "white")

    def test_timeout_terminates_game(self):
        self.gm.new_game(human_color_str="white", depth=1, time_control=180)
        # Game must be started for clocks to run
        with self.gm.state_lock:
            self.gm.game_started = True
            self.gm.active_clock = "white"
            self.gm.white_time = 0.05
            self.gm.last_clock_update = time.monotonic()

        time.sleep(0.1)
        res = self.gm.get_state_response(log=False)
        self.assertTrue(res.game_status.is_over)
        self.assertEqual(res.game_status.winner, "black")
        self.assertEqual(res.game_status.result, "0-1")
        self.assertIn("time", res.game_status.reason.lower())
        self.assertEqual(res.legal_moves, [])
        self.assertIsNone(res.clock.active_clock)

        # Further moves should be rejected
        with self.assertRaises(ValueError):
            self.gm.apply_move("e2e4")

    def test_restart_resets_clocks(self):
        self.gm.new_game(human_color_str="white", depth=1, time_control=180)
        time.sleep(0.2)
        self.gm.apply_move("e2e4")
        # Now restart with 5min
        res = self.gm.new_game(human_color_str="white", depth=1, time_control=300)
        self.assertEqual(res.clock.time_control, 300)
        self.assertEqual(res.clock.white_time, 300.0)
        self.assertEqual(res.clock.black_time, 300.0)
        self.assertIsNone(res.clock.active_clock)
        self.assertFalse(res.clock.game_started)
        self.assertFalse(res.game_status.is_over)

    def test_obsolete_search_discard_does_not_modify_new_game_clock(self):
        # Start game 1
        self.gm.new_game(human_color_str="white", depth=1, time_control=180)
        self.gm.apply_move("e2e4")
        old_game_id = self.gm.game_id
        old_version = self.gm.version

        # Reset game to a brand new 5-minute game
        new_res = self.gm.new_game(human_color_str="white", depth=1, time_control=300)
        new_game_id = new_res.game_id

        # Simulating an obsolete engine move returning for old_game_id
        with self.gm.state_lock:
            # Check clock state before
            white_before = self.gm.white_time
            black_before = self.gm.black_time

        # Attempt engine move with old session
        with self.assertRaises(ValueError):
            self.gm.apply_engine_move(game_id=old_game_id, expected_version=old_version)

        # Active game clocks must remain intact
        state = self.gm.get_state_response(log=False)
        self.assertEqual(state.game_id, new_game_id)
        self.assertEqual(state.clock.time_control, 300)


if __name__ == "__main__":
    unittest.main()
