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

    def test_mynewcatchphrase_without_promise(self):
        """My New Catchphrase: no boost without non-Kronii #Promise member -> base 30"""
        engine = self.engine
        p1: PlayerState = engine.get_player(self.player1)
        p2: PlayerState = engine.get_player(self.player2)

        # Put 1st Bloom directly in center
        p1.center = []
        bloom = put_card_in_play(self, p1, "hBP07-052", p1.center)
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
        # No non-Kronii #Promise on stage, base 30 only
        self.assertEqual(damage_event["damage"], 30)

    def test_collab_mascot_from_archive(self):
        """Collab: retrieve mascot from archive and attach to self"""
        engine = self.engine
        p1: PlayerState = engine.get_player(self.player1)

        # Put 052 in backstage for collab, another card in center
        p1.center = []
        put_card_in_play(self, p1, "hBP07-050", p1.center)

        p1.backstage = p1.backstage[:3]
        collab_card = put_card_in_play(self, p1, "hBP07-052", p1.backstage)

        # Put mascot Boros in archive
        mascot = add_card_to_archive(self, p1, "hBP07-107")
        self.assertIn(mascot["game_card_id"], [c["game_card_id"] for c in p1.archive])

        events = do_collab_get_events(self, p1, collab_card["game_card_id"])
        validate_last_event_not_error(self, events)

        # Step 1: choose mascot from archive
        engine.handle_game_message(self.player1, GameAction.EffectResolution_ChooseCardsForEffect, {
            "card_ids": [mascot["game_card_id"]]
        })
        events = engine.grab_events()
        validate_last_event_not_error(self, events)

        # Step 2: choose holomem to attach (should be source_card = collab card)
        engine.handle_game_message(self.player1, GameAction.EffectResolution_ChooseCardsForEffect, {
            "card_ids": [collab_card["game_card_id"]]
        })
        events = engine.grab_events()
        validate_last_event_not_error(self, events)

        # Mascot should be attached to the collab card
        attached_ids = [s["game_card_id"] for s in collab_card["attached_support"]]
        self.assertIn(mascot["game_card_id"], attached_ids)


if __name__ == "__main__":
    unittest.main()
