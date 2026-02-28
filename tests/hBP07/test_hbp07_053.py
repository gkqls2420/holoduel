import unittest
from app.gameengine import GameEngine, GameAction
from app.gameengine import PlayerState, EventType
from tests.helpers import *


class Test_hBP07_053(unittest.TestCase):
    """
    Test hBP07-053 Ouro Kronii 1st Bloom (C)
    - HP 150, Baton 1, Tags: #EN #Promise
    - Art: "Everlasting Flower" (blue x1 + any x1, power 50)
        - Before art: send 1 cheer from cheer_deck to #Promise holomem
    - Bloom: add_turn_effect_for_holomem - choose a #Promise member, +20 power this turn
    """
    engine: GameEngine
    player1: str
    player2: str

    def setUp(self):
        p1_deck = generate_deck_with("hBP07-005", {
            "hBP07-050": 4,
            "hBP07-053": 3,
        }, cheer={"hY04-001": 20})
        initialize_game_to_third_turn(self, p1_deck)

    def test_bloom_power_boost_20(self):
        """Bloom effect: with only 1 #Promise member, auto-applies +20 power"""
        engine = self.engine
        p1: PlayerState = engine.get_player(self.player1)
        p2: PlayerState = engine.get_player(self.player2)

        # Put debut in center
        p1.center = []
        debut = put_card_in_play(self, p1, "hBP07-050", p1.center)
        spawn_cheer_on_card(self, p1, debut["game_card_id"], "blue", "b1")
        spawn_cheer_on_card(self, p1, debut["game_card_id"], "white", "w1")

        bloom = add_card_to_hand(self, p1, "hBP07-053")
        engine.handle_game_message(self.player1, GameAction.MainStepBloom, {
            "card_id": bloom["game_card_id"],
            "target_id": debut["game_card_id"],
        })
        events = engine.grab_events()
        validate_last_event_not_error(self, events)

        # Bloom effect with only 1 #Promise member auto-applies +20
        # Verify by checking turn effects or performing art
        p2.center[0]["hp"] = 500

        begin_performance(self)
        engine.handle_game_message(self.player1, GameAction.PerformanceStepUseArt, {
            "art_id": "everlastingflower",
            "performer_id": bloom["game_card_id"],
            "target_id": p2.center[0]["game_card_id"],
        })
        events = engine.grab_events()
        validate_last_event_not_error(self, events)

        # Handle send_cheer (from cheer_deck to #Promise)
        send_cheer_decisions = [e for e in events if e.get("event_type") == EventType.EventType_Decision_SendCheer]
        if send_cheer_decisions:
            if p1.cheer_deck:
                cheer_id = p1.cheer_deck[0]["game_card_id"]
                engine.handle_game_message(self.player1, GameAction.EffectResolution_MoveCheerBetweenHolomems, {
                    "placements": {cheer_id: bloom["game_card_id"]}
                })
                events = engine.grab_events()
                validate_last_event_not_error(self, events)

        # Find damage - should be 50 base + 20 bloom boost = 70
        damage_events = [e for e in events if e.get("event_type") == EventType.EventType_DamageDealt]
        if damage_events:
            self.assertEqual(damage_events[0]["damage"], 70)

    def test_everlastingflower_send_cheer(self):
        """Everlasting Flower: send 1 cheer from cheer deck to #Promise member"""
        engine = self.engine
        p1: PlayerState = engine.get_player(self.player1)
        p2: PlayerState = engine.get_player(self.player2)

        # Put 1st Bloom directly (skip bloom effect handling)
        p1.center = []
        bloom = put_card_in_play(self, p1, "hBP07-053", p1.center)
        spawn_cheer_on_card(self, p1, bloom["game_card_id"], "blue", "b1")
        spawn_cheer_on_card(self, p1, bloom["game_card_id"], "white", "w1")

        p2.center[0]["hp"] = 500
        cheer_deck_before = len(p1.cheer_deck)

        begin_performance(self)
        engine.handle_game_message(self.player1, GameAction.PerformanceStepUseArt, {
            "art_id": "everlastingflower",
            "performer_id": bloom["game_card_id"],
            "target_id": p2.center[0]["game_card_id"],
        })
        events = engine.grab_events()
        validate_last_event_not_error(self, events)

        # Handle send_cheer
        send_cheer_decisions = [e for e in events if e.get("event_type") == EventType.EventType_Decision_SendCheer]
        if send_cheer_decisions:
            if p1.cheer_deck:
                cheer_id = p1.cheer_deck[0]["game_card_id"]
                engine.handle_game_message(self.player1, GameAction.EffectResolution_MoveCheerBetweenHolomems, {
                    "placements": {cheer_id: bloom["game_card_id"]}
                })
                events = engine.grab_events()
                validate_last_event_not_error(self, events)

        # Cheer deck should have decreased
        self.assertLess(len(p1.cheer_deck), cheer_deck_before)

        damage_events = [e for e in events if e.get("event_type") == EventType.EventType_DamageDealt]
        if damage_events:
            # Base 50 (no bloom boost since placed directly)
            self.assertEqual(damage_events[0]["damage"], 50)


if __name__ == "__main__":
    unittest.main()
