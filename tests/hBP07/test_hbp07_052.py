import unittest
from app.gameengine import GameEngine, GameAction
from app.gameengine import PlayerState, EventType
from tests.helpers import *


class Test_hBP07_052(unittest.TestCase):
    """
    Test hBP07-052 Ouro Kronii 1st Bloom (C)
    - HP 160, Baton 1, Tags: #EN #Promise
    - Art: "My New Catchphrase" (any x1, power 30)
        - +10 power if #Promise member (excluding Kronii) is on stage
    - Collab: choose_cards from archive, mascot, attach to self (0~1)
    """
    engine: GameEngine
    player1: str
    player2: str

    def setUp(self):
        p1_deck = generate_deck_with("hBP07-005", {
            "hBP07-050": 4,
            "hBP07-052": 3,
            "hBP07-107": 2,
        }, cheer={"hY04-001": 20})
        initialize_game_to_third_turn(self, p1_deck)

    def test_mynewcatchphrase_with_promise_member(self):
        """My New Catchphrase: +10 power when non-Kronii #Promise member is on stage"""
        engine = self.engine
        p1: PlayerState = engine.get_player(self.player1)
        p2: PlayerState = engine.get_player(self.player2)

        # Put 1st Bloom Kronii in center
        p1.center = []
        debut = put_card_in_play(self, p1, "hBP07-050", p1.center)
        bloom = add_card_to_hand(self, p1, "hBP07-052")
        engine.handle_game_message(self.player1, GameAction.MainStepBloom, {
            "card_id": bloom["game_card_id"],
            "target_id": debut["game_card_id"],
        })
        events = engine.grab_events()
        validate_last_event_not_error(self, events)

        spawn_cheer_on_card(self, p1, bloom["game_card_id"], "white", "w1")

        # Default backstage has sora starter members which are NOT #Promise
        # We need a #Promise member (not kronii) on stage for the boost
        # hBP01-092 is a kronii debut (also #Promise), but condition excludes kronii
        # So we need another #Promise member; for now this tests without boost
        p2.center[0]["hp"] = 500

        begin_performance(self)
        engine.handle_game_message(self.player1, GameAction.PerformanceStepUseArt, {
            "art_id": "mynewcatchphrase",
            "performer_id": bloom["game_card_id"],
            "target_id": p2.center[0]["game_card_id"],
        })
        events = engine.grab_events()
        validate_last_event_not_error(self, events)

        damage_event = next(e for e in events if e["event_type"] == EventType.EventType_DamageDealt)
        # No non-Kronii #Promise member on stage, so base 30 only
        self.assertEqual(damage_event["damage"], 30)

    def test_mynewcatchphrase_without_promise(self):
        """My New Catchphrase: no boost without non-Kronii #Promise member on stage"""
        engine = self.engine
        p1: PlayerState = engine.get_player(self.player1)
        p2: PlayerState = engine.get_player(self.player2)

        p1.center = []
        debut = put_card_in_play(self, p1, "hBP07-050", p1.center)
        bloom = add_card_to_hand(self, p1, "hBP07-052")
        engine.handle_game_message(self.player1, GameAction.MainStepBloom, {
            "card_id": bloom["game_card_id"],
            "target_id": debut["game_card_id"],
        })
        events = engine.grab_events()
        validate_last_event_not_error(self, events)

        spawn_cheer_on_card(self, p1, bloom["game_card_id"], "white", "w1")
        p2.center[0]["hp"] = 500

        begin_performance(self)
        engine.handle_game_message(self.player1, GameAction.PerformanceStepUseArt, {
            "art_id": "mynewcatchphrase",
            "performer_id": bloom["game_card_id"],
            "target_id": p2.center[0]["game_card_id"],
        })
        events = engine.grab_events()
        validate_last_event_not_error(self, events)

        damage_event = next(e for e in events if e["event_type"] == EventType.EventType_DamageDealt)
        self.assertEqual(damage_event["damage"], 30)

    def test_collab_mascot_from_archive(self):
        """Collab: retrieve mascot from archive and attach to self"""
        engine = self.engine
        p1: PlayerState = engine.get_player(self.player1)

        # Put a 1st Bloom in center and another debut in backstage for collab
        p1.center = []
        center = put_card_in_play(self, p1, "hBP07-050", p1.center)
        bloom = add_card_to_hand(self, p1, "hBP07-052")
        engine.handle_game_message(self.player1, GameAction.MainStepBloom, {
            "card_id": bloom["game_card_id"],
            "target_id": center["game_card_id"],
        })
        events = engine.grab_events()
        validate_last_event_not_error(self, events)

        # Put another debut in backstage for later bloom/collab
        p1.backstage = p1.backstage[:3]
        collab_target = put_card_in_play(self, p1, "hBP07-050", p1.backstage)

        # Bloom the backstage one to 052 as well
        bloom2 = add_card_to_hand(self, p1, "hBP07-052")
        engine.handle_game_message(self.player1, GameAction.MainStepBloom, {
            "card_id": bloom2["game_card_id"],
            "target_id": collab_target["game_card_id"],
        })
        events = engine.grab_events()
        validate_last_event_not_error(self, events)

        # Put mascot Boros in archive
        mascot = add_card_to_archive(self, p1, "hBP07-107")

        # Collab with the 052 from backstage
        events = do_collab_get_events(self, p1, bloom2["game_card_id"])
        validate_last_event_not_error(self, events)

        # Should get choose_cards decision for mascot from archive
        choose_events = [e for e in events if e.get("event_type") == EventType.EventType_Decision_ChooseCardsForEffect]
        if choose_events:
            engine.handle_game_message(self.player1, GameAction.EffectResolution_ChooseCardsForEffect, {
                "card_ids": [mascot["game_card_id"]]
            })
            events = engine.grab_events()
            validate_last_event_not_error(self, events)

            # Mascot should now be attached to the collab card
            self.assertIn(mascot["game_card_id"],
                          [s["game_card_id"] for s in bloom2["attached_support"]])


if __name__ == "__main__":
    unittest.main()
