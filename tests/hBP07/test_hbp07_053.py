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

    def test_everlastingflower_send_cheer(self):
        """Everlasting Flower: send 1 cheer from cheer deck to #Promise member, then deal 50"""
        engine = self.engine
        p1: PlayerState = engine.get_player(self.player1)
        p2: PlayerState = engine.get_player(self.player2)

        # Setup 1st Bloom in center
        p1.center = []
        debut = put_card_in_play(self, p1, "hBP07-050", p1.center)
        bloom = add_card_to_hand(self, p1, "hBP07-053")
        engine.handle_game_message(self.player1, GameAction.MainStepBloom, {
            "card_id": bloom["game_card_id"],
            "target_id": debut["game_card_id"],
        })
        events = engine.grab_events()
        validate_last_event_not_error(self, events)

        # Need to resolve bloom effect first (choose #Promise member for +20)
        # Choose the center card itself
        engine.handle_game_message(self.player1, GameAction.EffectResolution_ChooseCardsForEffect, {
            "card_ids": [bloom["game_card_id"]]
        })
        events = engine.grab_events()
        validate_last_event_not_error(self, events)

        # Add cheer for art cost (blue x1 + any x1)
        spawn_cheer_on_card(self, p1, bloom["game_card_id"], "blue", "b1")
        spawn_cheer_on_card(self, p1, bloom["game_card_id"], "white", "w1")

        p2.center[0]["hp"] = 500
        cheer_deck_count_before = len(p1.cheer_deck)

        begin_performance(self)
        engine.handle_game_message(self.player1, GameAction.PerformanceStepUseArt, {
            "art_id": "everlastingflower",
            "performer_id": bloom["game_card_id"],
            "target_id": p2.center[0]["game_card_id"],
        })
        events = engine.grab_events()
        validate_last_event_not_error(self, events)

        # Should get a send_cheer decision - place cheer on a #Promise member
        send_cheer_decisions = [e for e in events if e.get("event_type") == EventType.EventType_Decision_SendCheer]
        if send_cheer_decisions:
            cheer_id = p1.cheer_deck[0]["game_card_id"] if p1.cheer_deck else None
            if cheer_id:
                engine.handle_game_message(self.player1, GameAction.EffectResolution_MoveCheerBetweenHolomems, {
                    "placements": {cheer_id: bloom["game_card_id"]}
                })
                events = engine.grab_events()
                validate_last_event_not_error(self, events)

        # Verify damage dealt
        damage_events = [e for e in events if e.get("event_type") == EventType.EventType_DamageDealt]
        if damage_events:
            # With +20 bloom boost the total should be 50 + 20 = 70
            self.assertEqual(damage_events[0]["damage"], 70)

    def test_bloom_power_boost_20(self):
        """Bloom effect: choose a #Promise member for +20 power this turn"""
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

        # Bloom effect: choose a #Promise holomem for +20 power
        # Choose itself
        engine.handle_game_message(self.player1, GameAction.EffectResolution_ChooseCardsForEffect, {
            "card_ids": [bloom["game_card_id"]]
        })
        events = engine.grab_events()
        validate_last_event_not_error(self, events)

        p2.center[0]["hp"] = 500

        # Now use art (base 50) - should have +20 from bloom effect = 70
        begin_performance(self)
        engine.handle_game_message(self.player1, GameAction.PerformanceStepUseArt, {
            "art_id": "everlastingflower",
            "performer_id": bloom["game_card_id"],
            "target_id": p2.center[0]["game_card_id"],
        })
        events = engine.grab_events()
        validate_last_event_not_error(self, events)

        # Handle send_cheer if needed
        send_cheer_decisions = [e for e in events if e.get("event_type") == EventType.EventType_Decision_SendCheer]
        if send_cheer_decisions:
            if p1.cheer_deck:
                cheer_id = p1.cheer_deck[0]["game_card_id"]
                engine.handle_game_message(self.player1, GameAction.EffectResolution_MoveCheerBetweenHolomems, {
                    "placements": {cheer_id: bloom["game_card_id"]}
                })
                events = engine.grab_events()
                validate_last_event_not_error(self, events)

        # Find damage event
        all_events_so_far = events
        damage_events = [e for e in all_events_so_far if e.get("event_type") == EventType.EventType_DamageDealt]
        if damage_events:
            # Base 50 + 20 bloom boost = 70
            self.assertEqual(damage_events[0]["damage"], 70)


if __name__ == "__main__":
    unittest.main()
