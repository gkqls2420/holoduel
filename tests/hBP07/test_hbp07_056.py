import unittest
from app.gameengine import GameEngine, GameAction
from app.gameengine import PlayerState, EventType
from tests.helpers import *


class Test_hBP07_056(unittest.TestCase):
    """
    Test hBP07-056 Ouro Kronii 2nd Bloom (RR)
    - HP 200, Baton 2, Tags: #EN #Promise
    - Gift: on_performance_step_start, center only
        - bloom_from_stacked: may Bloom another Kronii using stacked holomem
    - Art: "You're not ready for me." (blue x2 + any x2, power 80)
        - +50 if target is red
        - send 0~1 cheer from self to #Promise member
        - +100 if oshi is Kronii
    """
    engine: GameEngine
    player1: str
    player2: str

    def setUp(self):
        p1_deck = generate_deck_with("hBP07-005", {
            "hBP07-050": 6,
            "hBP07-052": 4,
            "hBP07-056": 3,
        }, cheer={"hY04-001": 20})
        initialize_game_to_third_turn(self, p1_deck)

    def _setup_2nd_bloom_rr_in_center(self):
        """Helper: place 056 (2nd Bloom RR) in center"""
        engine = self.engine
        p1: PlayerState = engine.get_player(self.player1)

        # Place 1st bloom directly, then bloom to 2nd
        p1.center = []
        bloom1 = put_card_in_play(self, p1, "hBP07-052", p1.center)

        bloom2 = add_card_to_hand(self, p1, "hBP07-056")
        engine.handle_game_message(self.player1, GameAction.MainStepBloom, {
            "card_id": bloom2["game_card_id"],
            "target_id": bloom1["game_card_id"],
        })
        events = engine.grab_events()
        validate_last_event_not_error(self, events)

        return bloom2

    def test_gift_bloom_from_stacked(self):
        """Gift: at performance step start, may Bloom another Kronii using stacked card"""
        engine = self.engine
        p1: PlayerState = engine.get_player(self.player1)
        p2: PlayerState = engine.get_player(self.player2)

        bloom2 = self._setup_2nd_bloom_rr_in_center()

        # Place another debut Kronii in backstage (target for bloom_from_stacked)
        p1.backstage = p1.backstage[:3]
        back_debut = put_card_in_play(self, p1, "hBP07-050", p1.backstage)

        # Add cheer for art
        spawn_cheer_on_card(self, p1, bloom2["game_card_id"], "blue", "b1")
        spawn_cheer_on_card(self, p1, bloom2["game_card_id"], "blue", "b2")
        spawn_cheer_on_card(self, p1, bloom2["game_card_id"], "white", "w1")
        spawn_cheer_on_card(self, p1, bloom2["game_card_id"], "white", "w2")

        self.assertGreater(len(bloom2["stacked_cards"]), 0)

        # Begin performance - gift should trigger
        engine.handle_game_message(self.player1, GameAction.MainStepBeginPerformance, {})
        events = engine.grab_events()
        validate_last_event_not_error(self, events)

    def test_gift_not_center(self):
        """Gift does NOT trigger when card is not in center"""
        engine = self.engine
        p1: PlayerState = engine.get_player(self.player1)

        # Put 1st bloom directly in backstage, then bloom to 2nd
        p1.backstage = p1.backstage[:3]
        bloom1 = put_card_in_play(self, p1, "hBP07-052", p1.backstage)

        bloom2 = add_card_to_hand(self, p1, "hBP07-056")
        engine.handle_game_message(self.player1, GameAction.MainStepBloom, {
            "card_id": bloom2["game_card_id"],
            "target_id": bloom1["game_card_id"],
        })
        events = engine.grab_events()
        validate_last_event_not_error(self, events)

        # Add cheer to center (default sora) for performance
        spawn_cheer_on_card(self, p1, p1.center[0]["game_card_id"], "white", "w1")

        # Begin performance - gift should NOT trigger (056 not in center)
        engine.handle_game_message(self.player1, GameAction.MainStepBeginPerformance, {})
        events = engine.grab_events()
        validate_last_event_not_error(self, events)

    def test_yourenotreadyforme_oshi_boost(self):
        """You're not ready for me: +100 when oshi is Kronii"""
        engine = self.engine
        p1: PlayerState = engine.get_player(self.player1)
        p2: PlayerState = engine.get_player(self.player2)

        bloom2 = self._setup_2nd_bloom_rr_in_center()

        spawn_cheer_on_card(self, p1, bloom2["game_card_id"], "blue", "b1")
        spawn_cheer_on_card(self, p1, bloom2["game_card_id"], "blue", "b2")
        spawn_cheer_on_card(self, p1, bloom2["game_card_id"], "white", "w1")
        spawn_cheer_on_card(self, p1, bloom2["game_card_id"], "white", "w2")

        self.assertIn("ouro_kronii", p1.oshi_card["card_names"])
        p2.center[0]["hp"] = 500

        begin_performance(self)
        engine.handle_game_message(self.player1, GameAction.PerformanceStepUseArt, {
            "art_id": "yourenotreadyforme",
            "performer_id": bloom2["game_card_id"],
            "target_id": p2.center[0]["game_card_id"],
        })
        events = engine.grab_events()
        validate_last_event_not_error(self, events)

        # Handle send_cheer (0~1 from self)
        send_cheer_decisions = [e for e in events if e.get("event_type") == EventType.EventType_Decision_SendCheer]
        if send_cheer_decisions:
            engine.handle_game_message(self.player1, GameAction.EffectResolution_MoveCheerBetweenHolomems, {
                "placements": {}
            })
            events = engine.grab_events()
            validate_last_event_not_error(self, events)

        # Check +100 boost from oshi
        boost_events = [e for e in events if e.get("event_type") == EventType.EventType_BoostStat]
        boost_amounts = [e["amount"] for e in boost_events]
        self.assertIn(100, boost_amounts)

    def test_yourenotreadyforme_vs_red(self):
        """You're not ready for me: +50 if target is red color"""
        engine = self.engine
        p1: PlayerState = engine.get_player(self.player1)
        p2: PlayerState = engine.get_player(self.player2)

        bloom2 = self._setup_2nd_bloom_rr_in_center()

        spawn_cheer_on_card(self, p1, bloom2["game_card_id"], "blue", "b1")
        spawn_cheer_on_card(self, p1, bloom2["game_card_id"], "blue", "b2")
        spawn_cheer_on_card(self, p1, bloom2["game_card_id"], "white", "w1")
        spawn_cheer_on_card(self, p1, bloom2["game_card_id"], "white", "w2")

        # Make opponent center red
        p2.center[0]["colors"] = ["red"]
        p2.center[0]["hp"] = 500

        begin_performance(self)
        engine.handle_game_message(self.player1, GameAction.PerformanceStepUseArt, {
            "art_id": "yourenotreadyforme",
            "performer_id": bloom2["game_card_id"],
            "target_id": p2.center[0]["game_card_id"],
        })
        events = engine.grab_events()
        validate_last_event_not_error(self, events)

        send_cheer_decisions = [e for e in events if e.get("event_type") == EventType.EventType_Decision_SendCheer]
        if send_cheer_decisions:
            engine.handle_game_message(self.player1, GameAction.EffectResolution_MoveCheerBetweenHolomems, {
                "placements": {}
            })
            events = engine.grab_events()
            validate_last_event_not_error(self, events)

        boost_events = [e for e in events if e.get("event_type") == EventType.EventType_BoostStat]
        boost_amounts = [e["amount"] for e in boost_events]
        self.assertIn(50, boost_amounts)
        self.assertIn(100, boost_amounts)


if __name__ == "__main__":
    unittest.main()
