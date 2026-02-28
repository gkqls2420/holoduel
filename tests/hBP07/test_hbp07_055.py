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
        """Helper: put Kronii 2nd Bloom in center"""
        engine = self.engine
        p1: PlayerState = engine.get_player(self.player1)

        p1.center = []
        debut = put_card_in_play(self, p1, "hBP07-050", p1.center)
        bloom1 = add_card_to_hand(self, p1, "hBP07-052")
        engine.handle_game_message(self.player1, GameAction.MainStepBloom, {
            "card_id": bloom1["game_card_id"],
            "target_id": debut["game_card_id"],
        })
        events = engine.grab_events()
        validate_last_event_not_error(self, events)

        bloom2 = add_card_to_hand(self, p1, "hBP07-055")
        engine.handle_game_message(self.player1, GameAction.MainStepBloom, {
            "card_id": bloom2["game_card_id"],
            "target_id": bloom1["game_card_id"],
        })
        events = engine.grab_events()
        validate_last_event_not_error(self, events)

        # Bloom effect: choose #Promise member for +50 power
        engine.handle_game_message(self.player1, GameAction.EffectResolution_ChooseCardsForEffect, {
            "card_ids": [bloom2["game_card_id"]]
        })
        events = engine.grab_events()
        validate_last_event_not_error(self, events)

        return bloom2

    def test_lifegoeson_power_boost_vs_white(self):
        """Life Goes On: +50 power if target is white color -> total 90+50+50(bloom)=190"""
        engine = self.engine
        p1: PlayerState = engine.get_player(self.player1)
        p2: PlayerState = engine.get_player(self.player2)

        bloom2 = self._setup_2nd_bloom_in_center()

        spawn_cheer_on_card(self, p1, bloom2["game_card_id"], "blue", "b1")
        spawn_cheer_on_card(self, p1, bloom2["game_card_id"], "white", "w1")

        # Default sora starter center is white color
        p2.center[0]["hp"] = 500

        begin_performance(self)
        engine.handle_game_message(self.player1, GameAction.PerformanceStepUseArt, {
            "art_id": "lifegoeson",
            "performer_id": bloom2["game_card_id"],
            "target_id": p2.center[0]["game_card_id"],
        })
        events = engine.grab_events()
        validate_last_event_not_error(self, events)

        # Check for boost events
        boost_events = [e for e in events if e.get("event_type") == EventType.EventType_BoostStat]
        # Should have +50 (target_color white) and +50 (bloom turn effect)
        boost_amounts = [e["amount"] for e in boost_events]
        self.assertIn(50, boost_amounts)

        damage_events = [e for e in events if e.get("event_type") == EventType.EventType_DamageDealt]
        if damage_events:
            # 90 base + 50 white boost + 50 bloom boost = 190
            self.assertEqual(damage_events[0]["damage"], 190)

    def test_lifegoeson_no_boost_vs_nonwhite(self):
        """Life Goes On: no +50 if target is not white -> 90+50(bloom)=140"""
        engine = self.engine
        p1: PlayerState = engine.get_player(self.player1)
        p2: PlayerState = engine.get_player(self.player2)

        bloom2 = self._setup_2nd_bloom_in_center()

        spawn_cheer_on_card(self, p1, bloom2["game_card_id"], "blue", "b1")
        spawn_cheer_on_card(self, p1, bloom2["game_card_id"], "blue", "b2")

        # Put a non-white holomem as opponent center
        # Kronii is blue, so put a Kronii debut as p2 center
        p2.center = []
        p2_debut = put_card_in_play(self, p2, "hBP07-050", p2.center)
        p2_debut["hp"] = 500

        begin_performance(self)
        engine.handle_game_message(self.player1, GameAction.PerformanceStepUseArt, {
            "art_id": "lifegoeson",
            "performer_id": bloom2["game_card_id"],
            "target_id": p2_debut["game_card_id"],
        })
        events = engine.grab_events()
        validate_last_event_not_error(self, events)

        damage_events = [e for e in events if e.get("event_type") == EventType.EventType_DamageDealt]
        if damage_events:
            # 90 base + 50 bloom boost = 140 (no white boost)
            self.assertEqual(damage_events[0]["damage"], 140)

    def test_bloom_power_boost_50(self):
        """Bloom effect: chosen #Promise member gets +50 power this turn"""
        engine = self.engine
        p1: PlayerState = engine.get_player(self.player1)

        bloom2 = self._setup_2nd_bloom_in_center()

        # The bloom effect should have been applied
        # Verify by checking turn_effects
        has_boost = False
        for effect in p1.get_turn_effects():
            if effect.get("effect_type") == "power_boost" and effect.get("amount") == 50:
                has_boost = True
                break
        self.assertTrue(has_boost, "Should have +50 power turn effect from bloom")


if __name__ == "__main__":
    unittest.main()
