import unittest
from app.gameengine import GameEngine, GameAction
from app.gameengine import PlayerState, EventType
from tests.helpers import *


class Test_hBP07_109(unittest.TestCase):
    """
    Test hBP07-109 Support Fan "Kronies" (C)
    - Play condition: Kronii must be on stage
    - Effect: attach to Kronii only (specific_member_name)
    - Attached: +10 power
    """
    engine: GameEngine
    player1: str
    player2: str

    def setUp(self):
        p1_deck = generate_deck_with("hBP07-005", {
            "hBP07-050": 4,
            "hBP07-109": 3,
        }, cheer={"hY04-001": 20})
        initialize_game_to_third_turn(self, p1_deck)

    def test_play_condition_kronii_on_stage(self):
        """Kronies can only be played if Kronii is on stage"""
        engine = self.engine
        p1: PlayerState = engine.get_player(self.player1)

        # Default center is sora starter (not Kronii)
        kronies = add_card_to_hand(self, p1, "hBP07-109")
        actions = reset_mainstep(self)

        support_actions = [a for a in actions
                          if a["action_type"] == GameAction.MainStepPlaySupport
                          and a.get("card_id") == kronies["game_card_id"]]
        # No Kronii on stage -> not playable
        self.assertEqual(len(support_actions), 0)

    def test_play_condition_met_kronii_on_stage(self):
        """Kronies CAN be played when Kronii is on stage"""
        engine = self.engine
        p1: PlayerState = engine.get_player(self.player1)

        # Put Kronii on stage
        p1.center = []
        center = put_card_in_play(self, p1, "hBP07-050", p1.center)

        kronies = add_card_to_hand(self, p1, "hBP07-109")
        actions = reset_mainstep(self)

        support_actions = [a for a in actions
                          if a["action_type"] == GameAction.MainStepPlaySupport
                          and a.get("card_id") == kronies["game_card_id"]]
        self.assertGreater(len(support_actions), 0)

    def test_attach_to_kronii_only(self):
        """Kronies attaches only to Kronii (specific_member_name limitation)"""
        engine = self.engine
        p1: PlayerState = engine.get_player(self.player1)

        p1.center = []
        center = put_card_in_play(self, p1, "hBP07-050", p1.center)

        kronies = add_card_to_hand(self, p1, "hBP07-109")
        engine.handle_game_message(self.player1, GameAction.MainStepPlaySupport, {
            "card_id": kronies["game_card_id"],
        })
        events = engine.grab_events()
        validate_last_event_not_error(self, events)

        # Check if there's a choose holomem decision
        choose_events = [e for e in events
                        if e.get("event_type") == EventType.EventType_Decision_ChooseHolomemForEffect]
        if choose_events:
            # Available targets should only include Kronii members
            available = choose_events[0].get("cards_can_choose", [])
            for card_id in available:
                card, _, _ = p1.find_card(card_id)
                if card:
                    self.assertIn("ouro_kronii", card.get("card_names", []))

            engine.handle_game_message(self.player1, GameAction.EffectResolution_ChooseCardsForEffect, {
                "card_ids": [center["game_card_id"]]
            })
            events = engine.grab_events()
            validate_last_event_not_error(self, events)

        # Kronies should be attached to the Kronii card
        self.assertIn(kronies["game_card_id"],
                      [s["game_card_id"] for s in center["attached_support"]])

    def test_power_boost(self):
        """Kronies: +10 power when attached"""
        engine = self.engine
        p1: PlayerState = engine.get_player(self.player1)
        p2: PlayerState = engine.get_player(self.player2)

        p1.center = []
        center = put_card_in_play(self, p1, "hBP07-050", p1.center)
        spawn_cheer_on_card(self, p1, center["game_card_id"], "white", "w1")

        # Attach Kronies
        kronies = add_card_to_hand(self, p1, "hBP07-109")
        engine.handle_game_message(self.player1, GameAction.MainStepPlaySupport, {
            "card_id": kronies["game_card_id"],
        })
        events = engine.grab_events()
        validate_last_event_not_error(self, events)

        # Handle attachment
        choose_events = [e for e in events
                        if e.get("event_type") == EventType.EventType_Decision_ChooseHolomemForEffect]
        if choose_events:
            engine.handle_game_message(self.player1, GameAction.EffectResolution_ChooseCardsForEffect, {
                "card_ids": [center["game_card_id"]]
            })
            events = engine.grab_events()
            validate_last_event_not_error(self, events)

        p2.center[0]["hp"] = 500

        begin_performance(self)
        engine.handle_game_message(self.player1, GameAction.PerformanceStepUseArt, {
            "art_id": "goldenlure",
            "performer_id": center["game_card_id"],
            "target_id": p2.center[0]["game_card_id"],
        })
        events = engine.grab_events()
        validate_last_event_not_error(self, events)

        # Should have +10 boost from Kronies
        boost_events = [e for e in events if e.get("event_type") == EventType.EventType_BoostStat]
        boost_amounts = [e["amount"] for e in boost_events]
        self.assertIn(10, boost_amounts)

        damage_events = [e for e in events if e.get("event_type") == EventType.EventType_DamageDealt]
        if damage_events:
            # 10 base + 10 kronies = 20
            self.assertEqual(damage_events[0]["damage"], 20)


if __name__ == "__main__":
    unittest.main()
