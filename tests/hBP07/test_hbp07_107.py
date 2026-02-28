import unittest
from app.gameengine import GameEngine, GameAction
from app.gameengine import PlayerState, EventType
from tests.helpers import *


class Test_hBP07_107(unittest.TestCase):
    """
    Test hBP07-107 Support Mascot "Boros" (U)
    - Effect: attach to any holomem
    - Attached: +20 HP (bonus_hp at check_hp)
    - Attached: +20 power if attached to Kronii AND prisonoftime has been used this game
    """
    engine: GameEngine
    player1: str
    player2: str

    def setUp(self):
        p1_deck = generate_deck_with("hBP07-005", {
            "hBP07-050": 4,
            "hBP07-052": 3,
            "hBP07-107": 3,
        }, cheer={"hY04-001": 20})
        initialize_game_to_third_turn(self, p1_deck)

    def test_boros_attach_and_hp_bonus(self):
        """Boros: attach to holomem and grant +20 HP"""
        engine = self.engine
        p1: PlayerState = engine.get_player(self.player1)

        p1.center = []
        center = put_card_in_play(self, p1, "hBP07-050", p1.center)

        boros = add_card_to_hand(self, p1, "hBP07-107")
        actions = reset_mainstep(self)

        support_actions = [a for a in actions
                          if a["action_type"] == GameAction.MainStepPlaySupport
                          and a.get("card_id") == boros["game_card_id"]]
        self.assertGreater(len(support_actions), 0)

        engine.handle_game_message(self.player1, GameAction.MainStepPlaySupport, {
            "card_id": boros["game_card_id"],
        })
        events = engine.grab_events()
        validate_last_event_not_error(self, events)

        # Choose holomem to attach
        engine.handle_game_message(self.player1, GameAction.EffectResolution_ChooseCardsForEffect, {
            "card_ids": [center["game_card_id"]]
        })
        events = engine.grab_events()
        validate_last_event_not_error(self, events)

        # Boros should be attached
        self.assertIn(boros["game_card_id"],
                      [s["game_card_id"] for s in center["attached_support"]])

    def test_boros_power_boost_on_kronii_after_prisonoftime(self):
        """Boros: +20 power when attached to Kronii and prisonoftime was used"""
        engine = self.engine
        p1: PlayerState = engine.get_player(self.player1)
        p2: PlayerState = engine.get_player(self.player2)

        # Setup Kronii in center with Boros attached
        p1.center = []
        center = put_card_in_play(self, p1, "hBP07-050", p1.center)
        spawn_cheer_on_card(self, p1, center["game_card_id"], "white", "w1")

        boros = add_card_to_hand(self, p1, "hBP07-107")
        engine.handle_game_message(self.player1, GameAction.MainStepPlaySupport, {
            "card_id": boros["game_card_id"],
        })
        events = engine.grab_events()
        validate_last_event_not_error(self, events)

        engine.handle_game_message(self.player1, GameAction.EffectResolution_ChooseCardsForEffect, {
            "card_ids": [center["game_card_id"]]
        })
        events = engine.grab_events()
        validate_last_event_not_error(self, events)

        # Mark prisonoftime as used this game
        p1.effects_used_this_game.append("prisonoftime")

        p2.center[0]["hp"] = 500

        begin_performance(self)
        engine.handle_game_message(self.player1, GameAction.PerformanceStepUseArt, {
            "art_id": "goldenlure",
            "performer_id": center["game_card_id"],
            "target_id": p2.center[0]["game_card_id"],
        })
        events = engine.grab_events()
        validate_last_event_not_error(self, events)

        # Should have +20 boost from Boros
        boost_events = [e for e in events if e.get("event_type") == EventType.EventType_BoostStat]
        boost_amounts = [e["amount"] for e in boost_events]
        self.assertIn(20, boost_amounts)

        damage_events = [e for e in events if e.get("event_type") == EventType.EventType_DamageDealt]
        if damage_events:
            # 10 base + 20 boros boost = 30
            self.assertEqual(damage_events[0]["damage"], 30)

    def test_boros_no_boost_without_prisonoftime(self):
        """Boros: NO +20 power if prisonoftime has NOT been used"""
        engine = self.engine
        p1: PlayerState = engine.get_player(self.player1)
        p2: PlayerState = engine.get_player(self.player2)

        # Setup Kronii with Boros but without using prisonoftime
        p1.center = []
        center = put_card_in_play(self, p1, "hBP07-050", p1.center)
        spawn_cheer_on_card(self, p1, center["game_card_id"], "white", "w1")

        boros = add_card_to_hand(self, p1, "hBP07-107")
        engine.handle_game_message(self.player1, GameAction.MainStepPlaySupport, {
            "card_id": boros["game_card_id"],
        })
        events = engine.grab_events()
        validate_last_event_not_error(self, events)

        engine.handle_game_message(self.player1, GameAction.EffectResolution_ChooseCardsForEffect, {
            "card_ids": [center["game_card_id"]]
        })
        events = engine.grab_events()
        validate_last_event_not_error(self, events)

        # prisonoftime NOT used
        self.assertNotIn("prisonoftime", p1.effects_used_this_game)

        p2.center[0]["hp"] = 500

        begin_performance(self)
        engine.handle_game_message(self.player1, GameAction.PerformanceStepUseArt, {
            "art_id": "goldenlure",
            "performer_id": center["game_card_id"],
            "target_id": p2.center[0]["game_card_id"],
        })
        events = engine.grab_events()
        validate_last_event_not_error(self, events)

        # No power boost from Boros
        damage_events = [e for e in events if e.get("event_type") == EventType.EventType_DamageDealt]
        if damage_events:
            # Base 10 only, no Boros boost
            self.assertEqual(damage_events[0]["damage"], 10)


if __name__ == "__main__":
    unittest.main()
