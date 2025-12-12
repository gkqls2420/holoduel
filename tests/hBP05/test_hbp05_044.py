import unittest
from app.gameengine import GameEngine, GameAction
from app.gameengine import PlayerState
from app.gameengine import EventType
from tests.helpers import *


class Test_hBP05_044(unittest.TestCase):
    """
    Test hBP05-044 Nekomata Okayu (1st Bloom, Blue)
    - Bloom Effect: "Lunch Time...?" - Deal 10 special damage to opponent's center AND 10 special damage to opponent's backstage (pick one).
        - Once per turn limit (using effect_id "dosirakunetime")
    - Arts: "Don't Stop Gaming!" (cost: blue 1 + any 1, power: 40)
        - Deal 10 special damage to opponent's holomem (pick one)
    """
    engine: GameEngine
    player1: str
    player2: str

    def setUp(self):
        p1_deck = generate_deck_with("hSD03-001", {  # Okayu oshi
            "hBP05-044": 3,  # 1st bloom Okayu
            "hSD03-002": 3,  # debut Okayu
        })
        initialize_game_to_third_turn(self, p1_deck)


    def test_hbp05_044_bloom_effect(self):
        """Bloom effect deals 10 special damage to opponent's center and 10 to one backstage member"""
        engine = self.engine

        p1: PlayerState = engine.get_player(self.player1)
        p2: PlayerState = engine.get_player(self.player2)

        # Setup debut Okayu in center and 1st Okayu in hand
        p1.center = []
        _, center_card_id = unpack_game_id(put_card_in_play(self, p1, "hSD03-002", p1.center))
        _, bloom_card_id = unpack_game_id(add_card_to_hand(self, p1, "hBP05-044"))

        # Record initial damage on opponent's center and backstage
        p2_center_initial_damage = p2.center[0].get("damage", 0)
        p2_back_initial_damage = p2.backstage[0].get("damage", 0)

        # Get backstage card id for selection
        p2_back_card_id = p2.backstage[0]["game_card_id"]


        """Test"""
        self.assertEqual(engine.active_player_id, self.player1)

        # Bloom Okayu
        engine.handle_game_message(self.player1, GameAction.MainStepBloom, {
            "card_id": bloom_card_id,
            "target_id": center_card_id
        })

        events = engine.grab_events()
        validate_last_event_not_error(self, events)

        # Should have dealt damage to center
        center_damage_event = next((e for e in events if e["event_type"] == EventType.EventType_DamageDealt and e["target_id"] == p2.center[0]["game_card_id"]), None)
        self.assertIsNotNone(center_damage_event)
        self.assertEqual(center_damage_event["damage"], 10)
        self.assertTrue(center_damage_event["special"])

        # Now choose backstage target for the second effect
        engine.handle_game_message(self.player1, GameAction.EffectResolution_ChooseCardsForEffect, {
            "card_ids": [p2_back_card_id]
        })

        events = engine.grab_events()
        validate_last_event_not_error(self, events)

        # Verify backstage was damaged
        self.assertEqual(p2.backstage[0].get("damage", 0), p2_back_initial_damage + 10)


    def test_hbp05_044_bloom_effect_once_per_turn(self):
        """Bloom effect can only be used once per turn across all copies"""
        engine = self.engine

        p1: PlayerState = engine.get_player(self.player1)
        p2: PlayerState = engine.get_player(self.player2)

        # Setup debut Okayu in center and backstage, two 1st Okayu in hand
        p1.center = []
        _, center_card_id = unpack_game_id(put_card_in_play(self, p1, "hSD03-002", p1.center))
        p1.backstage = p1.backstage[:-1]
        _, back_card_id = unpack_game_id(put_card_in_play(self, p1, "hSD03-002", p1.backstage))

        _, bloom_card_1_id = unpack_game_id(add_card_to_hand(self, p1, "hBP05-044"))
        _, bloom_card_2_id = unpack_game_id(add_card_to_hand(self, p1, "hBP05-044"))

        # Get backstage card id for selection
        p2_back_card_id = p2.backstage[0]["game_card_id"]

        # Record initial damage
        p2_center_initial_damage = p2.center[0].get("damage", 0)


        """Test"""
        self.assertEqual(engine.active_player_id, self.player1)

        # First bloom - effect should trigger
        engine.handle_game_message(self.player1, GameAction.MainStepBloom, {
            "card_id": bloom_card_1_id,
            "target_id": center_card_id
        })

        events = engine.grab_events()
        validate_last_event_not_error(self, events)

        # Choose backstage target
        engine.handle_game_message(self.player1, GameAction.EffectResolution_ChooseCardsForEffect, {
            "card_ids": [p2_back_card_id]
        })

        events = engine.grab_events()
        validate_last_event_not_error(self, events)

        # Verify damage was dealt
        self.assertEqual(p2.center[0].get("damage", 0), p2_center_initial_damage + 10)

        # Second bloom - effect should NOT trigger (once per turn)
        p2_center_damage_after_first = p2.center[0].get("damage", 0)

        engine.handle_game_message(self.player1, GameAction.MainStepBloom, {
            "card_id": bloom_card_2_id,
            "target_id": back_card_id
        })

        events = engine.grab_events()
        validate_last_event_not_error(self, events)

        # Bloom event should be there but no damage dealt
        bloom_event = next((e for e in events if e["event_type"] == EventType.EventType_Bloom), None)
        self.assertIsNotNone(bloom_event)

        # Damage should not have increased
        self.assertEqual(p2.center[0].get("damage", 0), p2_center_damage_after_first)


    def test_hbp05_044_dontstopgaming_art(self):
        """Don't Stop Gaming art deals 40 damage + 10 special damage to any opponent holomem"""
        engine = self.engine

        p1: PlayerState = engine.get_player(self.player1)
        p2: PlayerState = engine.get_player(self.player2)

        # Setup 1st Okayu in center with cheer
        p1.center = []
        bloom_card = put_card_in_play(self, p1, "hBP05-044", p1.center)
        bloom_card_id = bloom_card["game_card_id"]

        spawn_cheer_on_card(self, p1, bloom_card_id, "blue", "b1")
        spawn_cheer_on_card(self, p1, bloom_card_id, "white", "w1")

        # Set opponent HP high so they don't die
        p2.center[0]["hp"] = 500
        p2_center_initial_damage = p2.center[0].get("damage", 0)

        # Get target - pick a backstage member for the special damage
        p2_back_card_id = p2.backstage[0]["game_card_id"]
        p2_back_initial_damage = p2.backstage[0].get("damage", 0)


        """Test"""
        self.assertEqual(engine.active_player_id, self.player1)

        begin_performance(self)
        engine.handle_game_message(self.player1, GameAction.PerformanceStepUseArt, {
            "art_id": "dontstopgaming",
            "performer_id": bloom_card_id,
            "target_id": p2.center[0]["game_card_id"]
        })

        events = engine.grab_events()
        validate_last_event_not_error(self, events)

        # Choose target for special damage (pick backstage)
        engine.handle_game_message(self.player1, GameAction.EffectResolution_ChooseCardsForEffect, {
            "card_ids": [p2_back_card_id]
        })

        events = engine.grab_events()
        validate_last_event_not_error(self, events)

        # Verify special damage dealt to backstage
        self.assertEqual(p2.backstage[0].get("damage", 0), p2_back_initial_damage + 10)

        # Verify main art damage dealt to center (40)
        damage_events = [e for e in events if e["event_type"] == EventType.EventType_DamageDealt]
        art_damage_event = next((e for e in damage_events if e["target_id"] == p2.center[0]["game_card_id"]), None)
        self.assertIsNotNone(art_damage_event)
        self.assertEqual(art_damage_event["damage"], 40)


    def test_hbp05_044_baton_pass(self):
        """Test baton pass cost of 1 any color"""
        engine = self.engine

        p1: PlayerState = engine.get_player(self.player1)

        # Setup
        p1.center = []
        center_card = put_card_in_play(self, p1, "hBP05-044", p1.center)
        center_card_id = center_card["game_card_id"]


        """Test"""
        self.assertEqual(engine.active_player_id, self.player1)

        # No cheers - baton pass should not be available
        self.assertEqual(len(center_card["attached_cheer"]), 0)

        actions = reset_mainstep(self)
        baton_action = next((action for action in actions if action["action_type"] == GameAction.MainStepBatonPass and action["center_id"] == center_card_id), None)
        self.assertIsNone(baton_action)

        # With 1 cheer - baton pass should be available
        spawn_cheer_on_card(self, p1, center_card_id, "white", "w1")
        actions = reset_mainstep(self)
        baton_action = next((action for action in actions if action["action_type"] == GameAction.MainStepBatonPass and action["center_id"] == center_card_id), None)
        self.assertIsNotNone(baton_action)


    def test_hbp05_044_overall_check(self):
        """Test HP and tags match the card definition"""
        p1: PlayerState = self.engine.get_player(self.player1)
        card = next((card for card in p1.deck if card["card_id"] == "hBP05-044"), None)
        self.assertIsNotNone(card)

        # Check hp and tags
        self.assertEqual(card["hp"], 130)
        self.assertCountEqual(card["tags"], ["#JP", "#Gamers", "#AnimalEars"])


if __name__ == "__main__":
    unittest.main()

