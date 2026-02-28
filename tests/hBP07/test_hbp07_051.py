import unittest
from app.gameengine import GameEngine, GameAction
from app.gameengine import PlayerState, EventType
from tests.helpers import *


class Test_hBP07_051(unittest.TestCase):
    """
    Test hBP07-051 Ouro Kronii Debut (U)
    - HP 130, Baton 1, Tags: #EN #Promise
    - Art: "Check This Out Yo" (any x1, power 30)
    - Collab: Choice - move 1 cheer between holomems to #Promise (exclude source), or pass
    """
    engine: GameEngine
    player1: str
    player2: str

    def setUp(self):
        p1_deck = generate_deck_with("hBP07-005", {
            "hBP07-050": 3,
            "hBP07-051": 3,
        }, cheer={"hY04-001": 20})
        initialize_game_to_third_turn(self, p1_deck)

    def test_checkthisoutyo_art(self):
        """Check This Out Yo art deals 30 damage"""
        engine = self.engine
        p1: PlayerState = engine.get_player(self.player1)
        p2: PlayerState = engine.get_player(self.player2)

        p1.center = []
        center = put_card_in_play(self, p1, "hBP07-051", p1.center)
        spawn_cheer_on_card(self, p1, center["game_card_id"], "white", "w1")

        p2.center[0]["hp"] = 500

        begin_performance(self)
        engine.handle_game_message(self.player1, GameAction.PerformanceStepUseArt, {
            "art_id": "checkthisoutyo",
            "performer_id": center["game_card_id"],
            "target_id": p2.center[0]["game_card_id"],
        })
        events = engine.grab_events()
        validate_last_event_not_error(self, events)

        damage_event = next(e for e in events if e["event_type"] == EventType.EventType_DamageDealt)
        self.assertEqual(damage_event["damage"], 30)

    def test_collab_move_cheer_pass(self):
        """Collab: choose to pass (no cheer movement)"""
        engine = self.engine
        p1: PlayerState = engine.get_player(self.player1)

        # Need #Promise center to receive cheer
        p1.center = []
        center = put_card_in_play(self, p1, "hBP07-050", p1.center)
        spawn_cheer_on_card(self, p1, center["game_card_id"], "blue", "b1")

        p1.backstage = p1.backstage[:3]
        collab_card = put_card_in_play(self, p1, "hBP07-051", p1.backstage)

        cheer_count_before = len(center["attached_cheer"])

        events = do_collab_get_events(self, p1, collab_card["game_card_id"])
        validate_last_event_not_error(self, events)

        # Choice: 1 = pass
        events = pick_choice(self, self.player1, 1)
        validate_last_event_not_error(self, events)

        self.assertEqual(len(center["attached_cheer"]), cheer_count_before)

    def test_hbp07_051_stats(self):
        """Verify card stats"""
        p1: PlayerState = self.engine.get_player(self.player1)
        card = next(c for c in p1.deck if c["card_id"] == "hBP07-051")
        self.assertEqual(card["hp"], 130)
        self.assertIn("#EN", card["tags"])
        self.assertIn("#Promise", card["tags"])


if __name__ == "__main__":
    unittest.main()
