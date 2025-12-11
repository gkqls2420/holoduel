import unittest
from app.gameengine import GameEngine, GameAction
from app.gameengine import PlayerState
from app.gameengine import EventType
from tests.helpers import *


class Test_hBP05_037(unittest.TestCase):
    """
    Test hBP05-037 Hoshimachi Suisei (2nd Bloom, Red)
    - Arts 1: Non-Limit Boost (cost: 4 any, power: 50 + 50 boost)
        - If red AND blue cheer attached -> send 0~2 cheer from archive to this holomem
        - If only red OR only blue cheer attached -> send 0~1 cheer from archive to this holomem
    - Arts 2: Shout in Crisis (cost: 4 any, power: 220 + 50 boost)
        - Archive all cheer from this holomem
    """
    engine: GameEngine
    player1: str
    player2: str

    def setUp(self):
        # Create deck with hBP05-037 (2nd bloom) and hBP05-036 (debut)
        p1_deck = generate_deck_with("hSD01-001", {  # Sora oshi (white)
            "hBP05-036": 2,  # Suisei debut (red)
            "hBP05-037": 2,  # Suisei 2nd bloom (red)
        }, cheer={
            "hY03-001": 5,  # 5 red cheer
            "hY04-001": 5,  # 5 blue cheer
            "hY01-001": 10,  # 10 white cheer
        })
        initialize_game_to_third_turn(self, p1_deck)

    def test_hbp05_037_nonlimitboost_red_and_blue_cheer(self):
        """Non-Limit Boost with both red and blue cheer attached -> can send 0~2 from archive"""
        engine = self.engine
        p1: PlayerState = engine.get_player(self.player1)
        p2: PlayerState = engine.get_player(self.player2)

        # Setup: Put Suisei 2nd bloom in center
        p1.center = []
        suisei_bloom = put_card_in_play(self, p1, "hBP05-037", p1.center)
        suisei_id = suisei_bloom["game_card_id"]

        # Attach 4 any cheer (cost requirement) + red and blue cheer
        spawn_cheer_on_card(self, p1, suisei_id, "red", "r1")
        spawn_cheer_on_card(self, p1, suisei_id, "red", "r2")
        spawn_cheer_on_card(self, p1, suisei_id, "blue", "b1")
        spawn_cheer_on_card(self, p1, suisei_id, "white", "w1")

        # Put some cheer in archive to send
        cheer1 = spawn_cheer_on_card(self, p1, "archive", "red", "ar1")
        cheer2 = spawn_cheer_on_card(self, p1, "archive", "blue", "ab1")

        # Set opponent HP high so they don't die
        p2.center[0]["hp"] = 500

        # Verify setup
        self.assertEqual(len(suisei_bloom["attached_cheer"]), 4)
        self.assertEqual(len(p1.archive), 2)

        """Test"""
        self.assertEqual(engine.active_player_id, self.player1)

        begin_performance(self)
        engine.handle_game_message(self.player1, GameAction.PerformanceStepUseArt, {
            "art_id": "nonlimitboost",
            "performer_id": suisei_id,
            "target_id": p2.center[0]["game_card_id"]
        })

        events = engine.grab_events()
        # Should have power boost (+50) and perform art with base 50 = 100 total
        validate_last_event_not_error(self, events)

        # Now we should have a choice to send cheer or pass (red+blue condition met)
        # Choice 0: send 0~2 cheer, Choice 1: pass
        engine.handle_game_message(self.player1, GameAction.EffectResolution_MakeChoice, {"choice_index": 0})

        events = engine.grab_events()
        validate_last_event_not_error(self, events)

        # Choose to send 2 cheer from archive - use placements dict
        placements = {
            cheer1["game_card_id"]: suisei_id,
            cheer2["game_card_id"]: suisei_id,
        }
        engine.handle_game_message(self.player1, GameAction.EffectResolution_MoveCheerBetweenHolomems, {
            "placements": placements
        })

        events = engine.grab_events()
        validate_last_event_not_error(self, events)

        # Verify cheer moved from archive to holomem
        self.assertEqual(len(p1.archive), 0)
        self.assertEqual(len(suisei_bloom["attached_cheer"]), 6)  # 4 + 2

    def test_hbp05_037_nonlimitboost_only_red_cheer(self):
        """Non-Limit Boost with only red cheer attached -> can send 0~1 from archive"""
        engine = self.engine
        p1: PlayerState = engine.get_player(self.player1)
        p2: PlayerState = engine.get_player(self.player2)

        # Setup: Put Suisei 2nd bloom in center
        p1.center = []
        suisei_bloom = put_card_in_play(self, p1, "hBP05-037", p1.center)
        suisei_id = suisei_bloom["game_card_id"]

        # Attach 4 red cheer only (no blue)
        spawn_cheer_on_card(self, p1, suisei_id, "red", "r1")
        spawn_cheer_on_card(self, p1, suisei_id, "red", "r2")
        spawn_cheer_on_card(self, p1, suisei_id, "red", "r3")
        spawn_cheer_on_card(self, p1, suisei_id, "red", "r4")

        # Put cheer in archive
        cheer1 = spawn_cheer_on_card(self, p1, "archive", "red", "ar1")
        cheer2 = spawn_cheer_on_card(self, p1, "archive", "blue", "ab1")

        # Set opponent HP high so they don't die
        p2.center[0]["hp"] = 500

        """Test"""
        self.assertEqual(engine.active_player_id, self.player1)

        begin_performance(self)
        engine.handle_game_message(self.player1, GameAction.PerformanceStepUseArt, {
            "art_id": "nonlimitboost",
            "performer_id": suisei_id,
            "target_id": p2.center[0]["game_card_id"]
        })

        events = engine.grab_events()
        validate_last_event_not_error(self, events)

        # First choice (red+blue) should NOT be available, so second choice (red OR blue) should trigger
        # Choice 0: send 0~1 cheer, Choice 1: pass
        engine.handle_game_message(self.player1, GameAction.EffectResolution_MakeChoice, {"choice_index": 0})

        events = engine.grab_events()
        validate_last_event_not_error(self, events)

        # Can only choose up to 1 cheer - use placements dict
        placements = {
            cheer1["game_card_id"]: suisei_id,
        }
        engine.handle_game_message(self.player1, GameAction.EffectResolution_MoveCheerBetweenHolomems, {
            "placements": placements
        })

        events = engine.grab_events()
        validate_last_event_not_error(self, events)

        # Verify only 1 cheer moved
        self.assertEqual(len(p1.archive), 1)
        self.assertEqual(len(suisei_bloom["attached_cheer"]), 5)  # 4 + 1

    def test_hbp05_037_nonlimitboost_only_blue_cheer(self):
        """Non-Limit Boost with only blue cheer attached -> can send 0~1 from archive"""
        engine = self.engine
        p1: PlayerState = engine.get_player(self.player1)
        p2: PlayerState = engine.get_player(self.player2)

        # Setup: Put Suisei 2nd bloom in center
        p1.center = []
        suisei_bloom = put_card_in_play(self, p1, "hBP05-037", p1.center)
        suisei_id = suisei_bloom["game_card_id"]

        # Attach 4 blue cheer only (no red)
        spawn_cheer_on_card(self, p1, suisei_id, "blue", "b1")
        spawn_cheer_on_card(self, p1, suisei_id, "blue", "b2")
        spawn_cheer_on_card(self, p1, suisei_id, "blue", "b3")
        spawn_cheer_on_card(self, p1, suisei_id, "blue", "b4")

        # Put cheer in archive
        cheer1 = spawn_cheer_on_card(self, p1, "archive", "red", "ar1")

        # Set opponent HP high so they don't die
        p2.center[0]["hp"] = 500

        """Test"""
        self.assertEqual(engine.active_player_id, self.player1)

        begin_performance(self)
        engine.handle_game_message(self.player1, GameAction.PerformanceStepUseArt, {
            "art_id": "nonlimitboost",
            "performer_id": suisei_id,
            "target_id": p2.center[0]["game_card_id"]
        })

        events = engine.grab_events()
        validate_last_event_not_error(self, events)

        # Only blue cheer, so second choice (1 cheer max) should trigger
        engine.handle_game_message(self.player1, GameAction.EffectResolution_MakeChoice, {"choice_index": 0})

        events = engine.grab_events()
        validate_last_event_not_error(self, events)

        # Use placements dict
        placements = {
            cheer1["game_card_id"]: suisei_id,
        }
        engine.handle_game_message(self.player1, GameAction.EffectResolution_MoveCheerBetweenHolomems, {
            "placements": placements
        })

        events = engine.grab_events()
        validate_last_event_not_error(self, events)

        self.assertEqual(len(p1.archive), 0)
        self.assertEqual(len(suisei_bloom["attached_cheer"]), 5)  # 4 + 1

    def test_hbp05_037_nonlimitboost_no_matching_cheer(self):
        """Non-Limit Boost with no red or blue cheer -> no send cheer effect"""
        engine = self.engine
        p1: PlayerState = engine.get_player(self.player1)
        p2: PlayerState = engine.get_player(self.player2)

        # Setup: Put Suisei 2nd bloom in center
        p1.center = []
        suisei_bloom = put_card_in_play(self, p1, "hBP05-037", p1.center)
        suisei_id = suisei_bloom["game_card_id"]

        # Attach only white cheer (no red, no blue)
        spawn_cheer_on_card(self, p1, suisei_id, "white", "w1")
        spawn_cheer_on_card(self, p1, suisei_id, "white", "w2")
        spawn_cheer_on_card(self, p1, suisei_id, "white", "w3")
        spawn_cheer_on_card(self, p1, suisei_id, "white", "w4")

        # Put cheer in archive
        spawn_cheer_on_card(self, p1, "archive", "red", "ar1")

        initial_archive_count = len(p1.archive)
        initial_cheer_count = len(suisei_bloom["attached_cheer"])

        """Test"""
        self.assertEqual(engine.active_player_id, self.player1)

        begin_performance(self)
        engine.handle_game_message(self.player1, GameAction.PerformanceStepUseArt, {
            "art_id": "nonlimitboost",
            "performer_id": suisei_id,
            "target_id": p2.center[0]["game_card_id"]
        })

        events = engine.grab_events()
        validate_last_event_not_error(self, events)

        # No red or blue cheer, so no choice should be presented for sending cheer
        # The art should complete without the send_cheer effect triggering
        # Verify no change in archive or attached cheer
        self.assertEqual(len(p1.archive), initial_archive_count)
        self.assertEqual(len(suisei_bloom["attached_cheer"]), initial_cheer_count)

    def test_hbp05_037_shoutincrisis_archive_all_cheer(self):
        """Shout in Crisis archives all cheer from this holomem"""
        engine = self.engine
        p1: PlayerState = engine.get_player(self.player1)
        p2: PlayerState = engine.get_player(self.player2)

        # Setup: Put Suisei 2nd bloom in center
        p1.center = []
        suisei_bloom = put_card_in_play(self, p1, "hBP05-037", p1.center)
        suisei_id = suisei_bloom["game_card_id"]

        # Attach 5 cheer of various colors
        spawn_cheer_on_card(self, p1, suisei_id, "red", "r1")
        spawn_cheer_on_card(self, p1, suisei_id, "red", "r2")
        spawn_cheer_on_card(self, p1, suisei_id, "blue", "b1")
        spawn_cheer_on_card(self, p1, suisei_id, "white", "w1")
        spawn_cheer_on_card(self, p1, suisei_id, "white", "w2")

        initial_cheer_count = len(suisei_bloom["attached_cheer"])
        self.assertEqual(initial_cheer_count, 5)

        initial_archive_count = len(p1.archive)

        # Set opponent HP high so they don't die
        p2.center[0]["hp"] = 500

        """Test"""
        self.assertEqual(engine.active_player_id, self.player1)

        begin_performance(self)
        engine.handle_game_message(self.player1, GameAction.PerformanceStepUseArt, {
            "art_id": "shoutincrisis",
            "performer_id": suisei_id,
            "target_id": p2.center[0]["game_card_id"]
        })

        events = engine.grab_events()
        validate_last_event_not_error(self, events)

        # Verify all cheer archived
        self.assertEqual(len(suisei_bloom["attached_cheer"]), 0)
        self.assertEqual(len(p1.archive), initial_archive_count + initial_cheer_count)

    def test_hbp05_037_shoutincrisis_power(self):
        """Shout in Crisis deals 220 + 50 = 270 damage"""
        engine = self.engine
        p1: PlayerState = engine.get_player(self.player1)
        p2: PlayerState = engine.get_player(self.player2)

        # Setup: Put Suisei 2nd bloom in center
        p1.center = []
        suisei_bloom = put_card_in_play(self, p1, "hBP05-037", p1.center)
        suisei_id = suisei_bloom["game_card_id"]

        # Attach enough cheer for cost
        spawn_cheer_on_card(self, p1, suisei_id, "white", "w1")
        spawn_cheer_on_card(self, p1, suisei_id, "white", "w2")
        spawn_cheer_on_card(self, p1, suisei_id, "white", "w3")
        spawn_cheer_on_card(self, p1, suisei_id, "white", "w4")

        # Set opponent center HP high to survive
        p2.center[0]["hp"] = 300

        initial_damage = p2.center[0].get("damage", 0)

        """Test"""
        begin_performance(self)
        engine.handle_game_message(self.player1, GameAction.PerformanceStepUseArt, {
            "art_id": "shoutincrisis",
            "performer_id": suisei_id,
            "target_id": p2.center[0]["game_card_id"]
        })

        events = engine.grab_events()
        validate_last_event_not_error(self, events)

        # Verify damage dealt is 220 + 50 = 270
        damage_event = next((e for e in events if e["event_type"] == EventType.EventType_DamageDealt), None)
        self.assertIsNotNone(damage_event)
        self.assertEqual(damage_event["damage"], 270)  # 220 base + 50 boost

    def test_hbp05_037_nonlimitboost_power(self):
        """Non-Limit Boost deals 50 + 50 = 100 damage"""
        engine = self.engine
        p1: PlayerState = engine.get_player(self.player1)
        p2: PlayerState = engine.get_player(self.player2)

        # Setup: Put Suisei 2nd bloom in center
        p1.center = []
        suisei_bloom = put_card_in_play(self, p1, "hBP05-037", p1.center)
        suisei_id = suisei_bloom["game_card_id"]

        # Attach enough cheer for cost (white only to avoid choice)
        spawn_cheer_on_card(self, p1, suisei_id, "white", "w1")
        spawn_cheer_on_card(self, p1, suisei_id, "white", "w2")
        spawn_cheer_on_card(self, p1, suisei_id, "white", "w3")
        spawn_cheer_on_card(self, p1, suisei_id, "white", "w4")

        # Set opponent center HP high to survive
        p2.center[0]["hp"] = 300

        """Test"""
        begin_performance(self)
        engine.handle_game_message(self.player1, GameAction.PerformanceStepUseArt, {
            "art_id": "nonlimitboost",
            "performer_id": suisei_id,
            "target_id": p2.center[0]["game_card_id"]
        })

        events = engine.grab_events()
        validate_last_event_not_error(self, events)

        # Verify damage dealt is 50 + 50 = 100
        damage_event = next((e for e in events if e["event_type"] == EventType.EventType_DamageDealt), None)
        self.assertIsNotNone(damage_event)
        self.assertEqual(damage_event["damage"], 100)  # 50 base + 50 boost

    def test_hbp05_037_nonlimitboost_pass_option(self):
        """Non-Limit Boost - player can choose to pass instead of sending cheer"""
        engine = self.engine
        p1: PlayerState = engine.get_player(self.player1)
        p2: PlayerState = engine.get_player(self.player2)

        # Setup: Put Suisei 2nd bloom in center
        p1.center = []
        suisei_bloom = put_card_in_play(self, p1, "hBP05-037", p1.center)
        suisei_id = suisei_bloom["game_card_id"]

        # Attach red and blue cheer
        spawn_cheer_on_card(self, p1, suisei_id, "red", "r1")
        spawn_cheer_on_card(self, p1, suisei_id, "blue", "b1")
        spawn_cheer_on_card(self, p1, suisei_id, "white", "w1")
        spawn_cheer_on_card(self, p1, suisei_id, "white", "w2")

        # Put cheer in archive
        spawn_cheer_on_card(self, p1, "archive", "red", "ar1")
        spawn_cheer_on_card(self, p1, "archive", "blue", "ab1")

        initial_archive_count = len(p1.archive)
        initial_cheer_count = len(suisei_bloom["attached_cheer"])

        # Set opponent HP high so they don't die
        p2.center[0]["hp"] = 500

        """Test"""
        begin_performance(self)
        engine.handle_game_message(self.player1, GameAction.PerformanceStepUseArt, {
            "art_id": "nonlimitboost",
            "performer_id": suisei_id,
            "target_id": p2.center[0]["game_card_id"]
        })

        events = engine.grab_events()
        validate_last_event_not_error(self, events)

        # Choose pass (index 1)
        engine.handle_game_message(self.player1, GameAction.EffectResolution_MakeChoice, {"choice_index": 1})

        events = engine.grab_events()
        validate_last_event_not_error(self, events)

        # Verify no cheer was moved
        self.assertEqual(len(p1.archive), initial_archive_count)
        self.assertEqual(len(suisei_bloom["attached_cheer"]), initial_cheer_count)


if __name__ == "__main__":
    unittest.main()
