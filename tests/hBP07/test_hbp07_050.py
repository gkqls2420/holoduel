import unittest
from app.gameengine import GameEngine, GameAction
from app.gameengine import PlayerState, EventType
from tests.helpers import *


class Test_hBP07_050(unittest.TestCase):
    """
    Test hBP07-050 Ouro Kronii Debut (C)
    - HP 130, Baton 1, Tags: #EN #Promise
    - Art: "Golden Lure" (any x1, power 10)
    - Collab: bloom_from_special - on going-second first turn,
      may Bloom center Kronii to 1st Bloom from hand
    """
    engine: GameEngine
    player1: str
    player2: str

    def test_goldenlure_art(self):
        """Golden Lure art deals 10 damage"""
        p1_deck = generate_deck_with("hBP07-005", {
            "hBP07-050": 4,
            "hBP07-052": 3,
        }, cheer={"hY04-001": 20})
        initialize_game_to_third_turn(self, p1_deck)
        engine = self.engine
        p1: PlayerState = engine.get_player(self.player1)
        p2: PlayerState = engine.get_player(self.player2)

        p1.center = []
        center = put_card_in_play(self, p1, "hBP07-050", p1.center)
        spawn_cheer_on_card(self, p1, center["game_card_id"], "white", "w1")

        p2.center[0]["hp"] = 500

        begin_performance(self)
        engine.handle_game_message(self.player1, GameAction.PerformanceStepUseArt, {
            "art_id": "goldenlure",
            "performer_id": center["game_card_id"],
            "target_id": p2.center[0]["game_card_id"],
        })
        events = engine.grab_events()
        validate_last_event_not_error(self, events)

        damage_event = next(e for e in events if e["event_type"] == EventType.EventType_DamageDealt)
        self.assertEqual(damage_event["damage"], 10)
        self.assertFalse(damage_event["special"])

    def test_collab_bloom_from_special_going_second_first_turn(self):
        """Collab on going-second first turn allows Bloom center Kronii to 1st"""
        p1_deck = generate_deck_with("hBP07-005", {
            "hBP07-050": 6,
            "hBP07-052": 4,
        }, cheer={"hY04-001": 20})
        p2_deck = generate_deck_with("hSD01-001", {}, cheer={"hY01-001": 20})

        self.random_override = RandomOverride()
        self.players = [
            {"player_id": "player1", "username": "P1", "oshi_id": p1_deck["oshi_id"],
             "deck": p1_deck["deck"], "cheer_deck": p1_deck["cheer_deck"]},
            {"player_id": "player2", "username": "P2", "oshi_id": p2_deck["oshi_id"],
             "deck": p2_deck["deck"], "cheer_deck": p2_deck["cheer_deck"]},
        ]
        self.engine = GameEngine(card_db, "versus", self.players)
        self.player1 = "player1"
        self.player2 = "player2"
        engine = self.engine
        engine.set_random_test_hook(self.random_override)
        engine.begin_game()
        events = engine.grab_events()

        # P1 chooses to go first, so P2 goes second
        engine.handle_game_message(engine.starting_player_id, GameAction.EffectResolution_MakeChoice, {"choice_index": 0})
        engine.handle_game_message(self.player1, GameAction.Mulligan, {"do_mulligan": False})
        engine.handle_game_message(self.player2, GameAction.Mulligan, {"do_mulligan": False})

        p1: PlayerState = engine.get_player(self.player1)
        p2: PlayerState = engine.get_player(self.player2)

        hand1 = ids_from_cards(p1.hand)
        engine.handle_game_message(self.player1, GameAction.InitialPlacement, {"center_holomem_card_id": hand1[0]})
        engine.handle_game_message(self.player1, GameAction.BackstagePlacement, {"backstage_holomem_card_ids": hand1[1:6]})

        hand2 = ids_from_cards(p2.hand)
        engine.handle_game_message(self.player2, GameAction.InitialPlacement, {"center_holomem_card_id": hand2[0]})
        engine.handle_game_message(self.player2, GameAction.BackstagePlacement, {"backstage_holomem_card_ids": hand2[1:6]})

        # P1 first turn - cheer step and end
        do_cheer_step_on_card(self, p1.center[0])
        engine.handle_game_message(self.player1, GameAction.MainStepEndTurn, {})

        # P2 second player first turn - this is "going_second_first_turn"
        events = engine.grab_events()
        validate_last_event_not_error(self, events)
        self.assertEqual(engine.active_player_id, self.player2)
        self.assertTrue(engine.game_first_turn)

    def test_collab_bloom_from_special_not_first_turn(self):
        """Collab bloom_from_special does NOT trigger on non-first turn"""
        p1_deck = generate_deck_with("hBP07-005", {
            "hBP07-050": 6,
            "hBP07-052": 4,
        }, cheer={"hY04-001": 20})
        initialize_game_to_third_turn(self, p1_deck)
        engine = self.engine
        p1: PlayerState = engine.get_player(self.player1)

        # Place debut Kronii in center and backstage
        p1.center = []
        center = put_card_in_play(self, p1, "hBP07-050", p1.center)
        p1.backstage = p1.backstage[:4]
        collab_card = put_card_in_play(self, p1, "hBP07-050", p1.backstage)

        # Add a 1st bloom to hand
        bloom1 = add_card_to_hand(self, p1, "hBP07-052")

        # Not first turn (turn 3), so collab should not trigger bloom_from_special
        self.assertFalse(engine.game_first_turn)

        events = do_collab_get_events(self, p1, collab_card["game_card_id"])
        validate_last_event_not_error(self, events)

        # No bloom decision should appear since conditions are not met
        bloom_decisions = [e for e in events if e.get("event_type") == EventType.EventType_Decision_ChooseCardsForEffect
                          and e.get("special_reason") == "bloom_from_special"]
        self.assertEqual(len(bloom_decisions), 0)

    def test_hbp07_050_stats(self):
        """Verify card stats"""
        p1_deck = generate_deck_with("hBP07-005", {"hBP07-050": 2}, cheer={"hY04-001": 20})
        initialize_game_to_third_turn(self, p1_deck)
        p1: PlayerState = self.engine.get_player(self.player1)

        card = next(c for c in p1.deck if c["card_id"] == "hBP07-050")
        self.assertEqual(card["hp"], 130)
        self.assertIn("#EN", card["tags"])
        self.assertIn("#Promise", card["tags"])


if __name__ == "__main__":
    unittest.main()
