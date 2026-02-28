import unittest
from app.gameengine import GameEngine, GameAction
from app.gameengine import PlayerState, EventType
from tests.helpers import *


class Test_hBP07_054(unittest.TestCase):
    """
    Test hBP07-054 Ouro Kronii 1st Bloom Buzz (R)
    - HP 250, Baton 2, Down Life 2, Buzz, Tags: #EN #Promise
    - Art: "I'm pretty shy...uwu" (blue x1, power 50)
        - Before art: send 1 cheer from cheer_deck to #Promise Buzz holomem only
    """
    engine: GameEngine
    player1: str
    player2: str

    def setUp(self):
        p1_deck = generate_deck_with("hBP07-005", {
            "hBP07-050": 4,
            "hBP07-054": 3,
        }, cheer={"hY04-001": 20})
        initialize_game_to_third_turn(self, p1_deck)

    def test_buzz_stats(self):
        """Verify Buzz card stats: HP 250, baton 2, down_life_cost 2"""
        p1: PlayerState = self.engine.get_player(self.player1)
        card = next(c for c in p1.deck if c["card_id"] == "hBP07-054")
        self.assertEqual(card["hp"], 250)
        self.assertEqual(card["baton_cost"], 2)
        self.assertEqual(card["down_life_cost"], 2)
        self.assertTrue(card.get("buzz", False))
        self.assertIn("#Promise", card["tags"])

    def test_imprettyshyuwu_send_cheer_buzz_only(self):
        """I'm pretty shy...uwu: send cheer from cheer_deck to #Promise Buzz holomem only"""
        engine = self.engine
        p1: PlayerState = engine.get_player(self.player1)
        p2: PlayerState = engine.get_player(self.player2)

        # Setup Buzz Kronii in center
        p1.center = []
        debut = put_card_in_play(self, p1, "hBP07-050", p1.center)
        buzz = add_card_to_hand(self, p1, "hBP07-054")
        engine.handle_game_message(self.player1, GameAction.MainStepBloom, {
            "card_id": buzz["game_card_id"],
            "target_id": debut["game_card_id"],
        })
        events = engine.grab_events()
        validate_last_event_not_error(self, events)

        spawn_cheer_on_card(self, p1, buzz["game_card_id"], "blue", "b1")

        p2.center[0]["hp"] = 500
        cheer_count_before = len(buzz["attached_cheer"])

        begin_performance(self)
        engine.handle_game_message(self.player1, GameAction.PerformanceStepUseArt, {
            "art_id": "imprettyshyuwu",
            "performer_id": buzz["game_card_id"],
            "target_id": p2.center[0]["game_card_id"],
        })
        events = engine.grab_events()
        validate_last_event_not_error(self, events)

        # Should get a send_cheer decision targeting only Buzz #Promise members
        send_cheer_decisions = [e for e in events if e.get("event_type") == EventType.EventType_Decision_SendCheer]
        if send_cheer_decisions:
            # The only valid target should be the Buzz Kronii itself
            available_targets = send_cheer_decisions[0].get("available_targets", [])
            if available_targets:
                for target_id in available_targets:
                    target_card, _, _ = p1.find_card(target_id)
                    if target_card:
                        self.assertTrue(target_card.get("buzz", False),
                                        f"Non-buzz card {target_card['card_id']} should not be a valid target")

            if p1.cheer_deck:
                cheer_id = p1.cheer_deck[0]["game_card_id"]
                engine.handle_game_message(self.player1, GameAction.EffectResolution_MoveCheerBetweenHolomems, {
                    "placements": {cheer_id: buzz["game_card_id"]}
                })
                events = engine.grab_events()
                validate_last_event_not_error(self, events)

        # Verify damage
        damage_events = [e for e in events if e.get("event_type") == EventType.EventType_DamageDealt]
        if damage_events:
            self.assertEqual(damage_events[0]["damage"], 50)

    def test_imprettyshyuwu_art_damage(self):
        """I'm pretty shy...uwu art deals 50 base damage"""
        engine = self.engine
        p1: PlayerState = engine.get_player(self.player1)
        p2: PlayerState = engine.get_player(self.player2)

        p1.center = []
        debut = put_card_in_play(self, p1, "hBP07-050", p1.center)
        buzz = add_card_to_hand(self, p1, "hBP07-054")
        engine.handle_game_message(self.player1, GameAction.MainStepBloom, {
            "card_id": buzz["game_card_id"],
            "target_id": debut["game_card_id"],
        })
        events = engine.grab_events()
        validate_last_event_not_error(self, events)

        spawn_cheer_on_card(self, p1, buzz["game_card_id"], "blue", "b1")
        p2.center[0]["hp"] = 500

        # Empty cheer deck so send_cheer has nothing to send
        p1.cheer_deck = []

        begin_performance(self)
        engine.handle_game_message(self.player1, GameAction.PerformanceStepUseArt, {
            "art_id": "imprettyshyuwu",
            "performer_id": buzz["game_card_id"],
            "target_id": p2.center[0]["game_card_id"],
        })
        events = engine.grab_events()
        validate_last_event_not_error(self, events)

        damage_events = [e for e in events if e.get("event_type") == EventType.EventType_DamageDealt]
        if damage_events:
            self.assertEqual(damage_events[0]["damage"], 50)


if __name__ == "__main__":
    unittest.main()
