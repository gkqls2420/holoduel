import unittest
from app.gameengine import GameEngine, GameAction
from app.gameengine import PlayerState, EventType
from tests.helpers import *


class Test_hBP07_005(unittest.TestCase):
    """
    Test hBP07-005 Ouro Kronii Oshi
    - Skill 1: "On the Ring of Oblivion" (cost 2, once per turn)
        - Draw 2 from bottom of deck, then archive 1 from hand
    - Skill 2: "Prison of Time" (cost 4, once per game)
        - Requires Kronii 2nd Bloom in center
        - Take an extra turn
    """
    engine: GameEngine
    player1: str
    player2: str

    def setUp(self):
        p1_deck = generate_deck_with("hBP07-005", {
            "hBP07-050": 4,
            "hBP07-052": 3,
            "hBP07-055": 3,
        }, cheer={
            "hY04-001": 20,
        })
        initialize_game_to_third_turn(self, p1_deck)

    def test_ontheringofoblivion_draw_from_bottom(self):
        """On the Ring of Oblivion: spend 2 holopower, draw 2 from bottom, archive 1 from hand"""
        engine = self.engine
        p1: PlayerState = engine.get_player(self.player1)

        p1.generate_holopower(3)
        actions = reset_mainstep(self)

        oshi_actions = [a for a in actions if a["action_type"] == GameAction.MainStepOshiSkill]
        skill_ids = [a["skill_id"] for a in oshi_actions]
        self.assertIn("ontheringofoblivion", skill_ids)

        hand_count_before = len(p1.hand)
        bottom_cards = [p1.deck[-1]["game_card_id"], p1.deck[-2]["game_card_id"]]

        engine.handle_game_message(self.player1, GameAction.MainStepOshiSkill, {
            "skill_id": "ontheringofoblivion",
        })
        events = engine.grab_events()
        validate_last_event_not_error(self, events)

        # Should have drawn 2 from bottom, so those cards are now in hand
        hand_ids = [c["game_card_id"] for c in p1.hand]
        for card_id in bottom_cards:
            self.assertIn(card_id, hand_ids)

        # Now need to archive 1 from hand
        archive_card = p1.hand[0]
        engine.handle_game_message(self.player1, GameAction.EffectResolution_ChooseCardsForEffect, {
            "card_ids": [archive_card["game_card_id"]]
        })
        events = engine.grab_events()
        validate_last_event_not_error(self, events)

        self.assertIn(archive_card["game_card_id"], [c["game_card_id"] for c in p1.archive])
        # Net gain: +2 draw -1 archive = +1 hand
        self.assertEqual(len(p1.hand), hand_count_before + 1)

    def test_ontheringofoblivion_once_per_turn(self):
        """On the Ring of Oblivion can only be used once per turn"""
        engine = self.engine
        p1: PlayerState = engine.get_player(self.player1)

        p1.generate_holopower(6)

        use_oshi_action(self, "ontheringofoblivion")

        # Archive 1 from hand
        engine.handle_game_message(self.player1, GameAction.EffectResolution_ChooseCardsForEffect, {
            "card_ids": [p1.hand[0]["game_card_id"]]
        })
        events = engine.grab_events()
        validate_last_event_not_error(self, events)

        actions = reset_mainstep(self)
        oshi_actions = [a for a in actions if a["action_type"] == GameAction.MainStepOshiSkill]
        skill_ids = [a["skill_id"] for a in oshi_actions]
        self.assertNotIn("ontheringofoblivion", skill_ids)

    def test_prisonoftime_extra_turn(self):
        """Prison of Time: with Kronii 2nd Bloom in center, take extra turn"""
        engine = self.engine
        p1: PlayerState = engine.get_player(self.player1)
        p2: PlayerState = engine.get_player(self.player2)

        # Put debut in center then bloom to 1st then 2nd
        p1.center = []
        debut = put_card_in_play(self, p1, "hBP07-050", p1.center)
        bloom1_card = add_card_to_hand(self, p1, "hBP07-052")
        engine.handle_game_message(self.player1, GameAction.MainStepBloom, {
            "card_id": bloom1_card["game_card_id"],
            "target_id": debut["game_card_id"],
        })
        events = engine.grab_events()
        validate_last_event_not_error(self, events)

        # Now bloom to 2nd
        bloom2_card = add_card_to_hand(self, p1, "hBP07-055")
        engine.handle_game_message(self.player1, GameAction.MainStepBloom, {
            "card_id": bloom2_card["game_card_id"],
            "target_id": bloom1_card["game_card_id"],
        })
        events = engine.grab_events()
        validate_last_event_not_error(self, events)

        # Now center has Kronii 2nd Bloom
        self.assertEqual(p1.center[0]["card_id"], "hBP07-055")

        p1.generate_holopower(5)
        actions = reset_mainstep(self)
        oshi_actions = [a for a in actions if a["action_type"] == GameAction.MainStepOshiSkill]
        skill_ids = [a["skill_id"] for a in oshi_actions]
        self.assertIn("prisonoftime", skill_ids)

        use_oshi_action(self, "prisonoftime")

        # End turn - should get an extra turn (same player active)
        self.assertEqual(engine.active_player_id, self.player1)
        engine.handle_game_message(self.player1, GameAction.MainStepEndTurn, {})
        events = engine.grab_events()
        validate_last_event_not_error(self, events)

        # After extra turn, active player should still be p1
        self.assertEqual(engine.active_player_id, self.player1)

    def test_prisonoftime_condition_fail_no_kronii_center(self):
        """Prison of Time not available without Kronii in center"""
        engine = self.engine
        p1: PlayerState = engine.get_player(self.player1)

        # Center is default sora starter card (not kronii)
        p1.generate_holopower(5)
        actions = reset_mainstep(self)
        oshi_actions = [a for a in actions if a["action_type"] == GameAction.MainStepOshiSkill]
        skill_ids = [a["skill_id"] for a in oshi_actions]
        self.assertNotIn("prisonoftime", skill_ids)

    def test_prisonoftime_condition_fail_not_2nd_bloom(self):
        """Prison of Time not available if Kronii is only 1st Bloom (not 2nd)"""
        engine = self.engine
        p1: PlayerState = engine.get_player(self.player1)

        # Put debut in center and bloom to 1st only
        p1.center = []
        debut = put_card_in_play(self, p1, "hBP07-050", p1.center)
        bloom1_card = add_card_to_hand(self, p1, "hBP07-052")
        engine.handle_game_message(self.player1, GameAction.MainStepBloom, {
            "card_id": bloom1_card["game_card_id"],
            "target_id": debut["game_card_id"],
        })
        events = engine.grab_events()
        validate_last_event_not_error(self, events)

        p1.generate_holopower(5)
        actions = reset_mainstep(self)
        oshi_actions = [a for a in actions if a["action_type"] == GameAction.MainStepOshiSkill]
        skill_ids = [a["skill_id"] for a in oshi_actions]
        self.assertNotIn("prisonoftime", skill_ids)

    def test_prisonoftime_once_per_game(self):
        """Prison of Time can only be used once per game"""
        engine = self.engine
        p1: PlayerState = engine.get_player(self.player1)

        p1.effects_used_this_game.append("prisonoftime")
        p1.generate_holopower(5)

        # Even with Kronii 2nd Bloom in center, skill should not be available
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

        actions = reset_mainstep(self)
        oshi_actions = [a for a in actions if a["action_type"] == GameAction.MainStepOshiSkill]
        skill_ids = [a["skill_id"] for a in oshi_actions]
        self.assertNotIn("prisonoftime", skill_ids)


if __name__ == "__main__":
    unittest.main()
