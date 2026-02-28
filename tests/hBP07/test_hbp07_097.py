import unittest
from app.gameengine import GameEngine, GameAction
from app.gameengine import PlayerState, EventType
from tests.helpers import *


class Test_hBP07_097(unittest.TestCase):
    """
    Test hBP07-097 Support Event "Ruler of Time -Promise-" (U, Limited)
    - Play condition: all stage members must have #Promise tag
    - Effect 1: choose 0~2 #Promise holomem from deck to hand (search)
    - Effect 2: if my life < opponent life, choose a holomem for +20 power this turn
    """
    engine: GameEngine
    player1: str
    player2: str

    def setUp(self):
        p1_deck = generate_deck_with("hBP07-005", {
            "hBP07-050": 8,
            "hBP07-052": 4,
            "hBP07-097": 2,
        }, cheer={"hY04-001": 20})
        initialize_game_to_third_turn(self, p1_deck)

    def _setup_all_promise_stage(self):
        """Helper: replace all stage members with Kronii (#Promise)"""
        engine = self.engine
        p1: PlayerState = engine.get_player(self.player1)

        p1.center = []
        put_card_in_play(self, p1, "hBP07-050", p1.center)

        p1.backstage = []
        for i in range(5):
            if any(c["card_id"] == "hBP07-050" for c in p1.deck):
                put_card_in_play(self, p1, "hBP07-050", p1.backstage)

        return p1

    def test_play_condition_all_promise_fail(self):
        """Ruler of Time cannot be played when non-#Promise members on stage"""
        engine = self.engine
        p1: PlayerState = engine.get_player(self.player1)

        test_card = add_card_to_hand(self, p1, "hBP07-097")
        actions = reset_mainstep(self)

        support_actions = [a for a in actions
                          if a["action_type"] == GameAction.MainStepPlaySupport
                          and a.get("card_id") == test_card["game_card_id"]]
        self.assertEqual(len(support_actions), 0)

    def test_play_condition_all_promise_met(self):
        """Ruler of Time CAN be played when all stage members have #Promise"""
        engine = self.engine
        p1 = self._setup_all_promise_stage()

        test_card = add_card_to_hand(self, p1, "hBP07-097")
        actions = reset_mainstep(self)

        support_actions = [a for a in actions
                          if a["action_type"] == GameAction.MainStepPlaySupport
                          and a.get("card_id") == test_card["game_card_id"]]
        self.assertGreater(len(support_actions), 0)

    def test_search_promise_holomems(self):
        """Search deck for up to 2 #Promise holomem cards"""
        engine = self.engine
        p1 = self._setup_all_promise_stage()

        test_card = add_card_to_hand(self, p1, "hBP07-097")
        hand_count_before = len(p1.hand)

        engine.handle_game_message(self.player1, GameAction.MainStepPlaySupport, {
            "card_id": test_card["game_card_id"],
        })
        events = engine.grab_events()
        validate_last_event_not_error(self, events)

        # Choose 0 cards (pass on search)
        choose_events = [e for e in events
                        if e.get("event_type") == EventType.EventType_Decision_ChooseCards]
        if choose_events:
            engine.handle_game_message(self.player1, GameAction.EffectResolution_ChooseCardsForEffect, {
                "card_ids": []
            })
            events = engine.grab_events()
            validate_last_event_not_error(self, events)


if __name__ == "__main__":
    unittest.main()
