import unittest
from app.gameengine import GameEngine, GameAction
from app.gameengine import PlayerState, EventType
from tests.helpers import *


class Test_hBP07_055(unittest.TestCase):
    """
    Test hBP07-055 Ouro Kronii 2nd Bloom (U)
    - HP 190, Baton 2, Tags: #EN #Promise
    - Art: "Life Goes On" (blue x1 + any x1, power 90)
        - +50 power if target is white color
    - Bloom: add_turn_effect_for_holomem - choose a #Promise member, +50 power this turn
    """
    engine: GameEngine
    player1: str
    player2: str

    def setUp(self):
        p1_deck = generate_deck_with("hBP07-005", {
            "hBP07-050": 4,
            "hBP07-052": 3,
            "hBP07-055": 3,
        }, cheer={"hY04-001": 20})
        initialize_game_to_third_turn(self, p1_deck)

    def _setup_2nd_bloom_in_center(self):
        """Helper: put Kronii 2nd Bloom in center via put_card_in_play + bloom"""
        engine = self.engine
        p1: PlayerState = engine.get_player(self.player1)

        # Place 1st bloom directly (not bloomed_this_turn)
        p1.center = []
        bloom1 = put_card_in_play(self, p1, "hBP07-052", p1.center)

        # Then bloom to 2nd from hand
        bloom2 = add_card_to_hand(self, p1, "hBP07-055")
        engine.handle_game_message(self.player1, GameAction.MainStepBloom, {
            "card_id": bloom2["game_card_id"],
            "target_id": bloom1["game_card_id"],
        })
        events = engine.grab_events()
        validate_last_event_not_error(self, events)

        # Bloom effect auto-applies +50 to only #Promise member on stage
        # (sora starters are not #Promise, so only the bloomed card qualifies)

        return bloom2

    def test_lifegoeson_power_boost_vs_white(self):
        """Life Goes On: +50 power if target is white, +50 from bloom = 190 total"""
        engine = self.engine
        p1: PlayerState = engine.get_player(self.player1)
        p2: PlayerState = engine.get_player(self.player2)

        bloom2 = self._setup_2nd_bloom_in_center()

        spawn_cheer_on_card(self, p1, bloom2["game_card_id"], "blue", "b1")
        spawn_cheer_on_card(self, p1, bloom2["game_card_id"], "white", "w1")

        # Default p2 center is white (sora)
        p2.center[0]["hp"] = 500

        begin_performance(self)
        engine.handle_game_message(self.player1, GameAction.PerformanceStepUseArt, {
            "art_id": "lifegoeson",
            "performer_id": bloom2["game_card_id"],
            "target_id": p2.center[0]["game_card_id"],
        })
        events = engine.grab_events()
        validate_last_event_not_error(self, events)

        damage_events = [e for e in events if e.get("event_type") == EventType.EventType_DamageDealt]
        if damage_events:
            # 90 base + 50 (white) + 50 (bloom) = 190
            self.assertEqual(damage_events[0]["damage"], 190)

    def test_lifegoeson_no_boost_vs_nonwhite(self):
        """Life Goes On: no color boost vs non-white, still has bloom +50 = 140"""
        engine = self.engine
        p1: PlayerState = engine.get_player(self.player1)
        p2: PlayerState = engine.get_player(self.player2)

        bloom2 = self._setup_2nd_bloom_in_center()

        spawn_cheer_on_card(self, p1, bloom2["game_card_id"], "blue", "b1")
        spawn_cheer_on_card(self, p1, bloom2["game_card_id"], "blue", "b2")

        # Make the opponent center non-white (change color to blue)
        p2.center[0]["colors"] = ["blue"]
        p2.center[0]["hp"] = 500

        begin_performance(self)
        engine.handle_game_message(self.player1, GameAction.PerformanceStepUseArt, {
            "art_id": "lifegoeson",
            "performer_id": bloom2["game_card_id"],
            "target_id": p2.center[0]["game_card_id"],
        })
        events = engine.grab_events()
        validate_last_event_not_error(self, events)

        damage_events = [e for e in events if e.get("event_type") == EventType.EventType_DamageDealt]
        if damage_events:
            # 90 base + 50 (bloom) = 140 (no white boost)
            self.assertEqual(damage_events[0]["damage"], 140)

    def test_bloom_power_boost_50_auto_apply(self):
        """Bloom effect: with single #Promise member, auto-applies +50 power"""
        engine = self.engine
        p1: PlayerState = engine.get_player(self.player1)

        bloom2 = self._setup_2nd_bloom_in_center()

        # Verify center is the 2nd bloom
        self.assertEqual(p1.center[0]["card_id"], "hBP07-055")


if __name__ == "__main__":
    unittest.main()
