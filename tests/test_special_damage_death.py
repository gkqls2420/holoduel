import unittest
from app.gameengine import GameEngine, GameAction
from app.gameengine import PlayerState
from app.gameengine import EventType
from tests.helpers import *


class Test_SpecialDamageDeath(unittest.TestCase):
    """
    Test cases for special damage causing death when HP reaches 0.
    
    Bug report:
    - Anya Melfissa 1st (HP 150, backstage, resting) had damage 130 (20 HP remaining)
    - Kobo/Suisei effect dealt 10 damage x 2
    - Second 10 damage made damage = 150 (HP 0), but death was not triggered
    - Only after Suisei oshi skill hit, death was triggered
    - Possibly related to prevent_life_loss: true effects
    """
    engine: GameEngine
    player1: str
    player2: str

    def setUp(self):
        # Setup with Suisei oshi (hBP01-007) for player1
        # Need hBP01-079 (Suisei 1st bloom with prevent_life_loss deal_damage effect)
        p1_deck = generate_deck_with("hBP01-007", {  # Suisei oshi
            "hBP01-079": 2,  # Suisei 1st bloom - bloom effect: deal 20 damage to backstage with prevent_life_loss
            "hBP01-077": 2,  # Suisei debut
        })
        initialize_game_to_third_turn(self, p1_deck)

    def test_prevent_life_loss_damage_should_still_kill(self):
        """
        Test that deal_damage with prevent_life_loss: true still causes death when HP reaches 0.
        The prevent_life_loss flag should only prevent life loss, not prevent death itself.
        """
        engine = self.engine

        p1: PlayerState = engine.get_player(self.player1)
        p2: PlayerState = engine.get_player(self.player2)

        # Setup: Get a Suisei debut on backstage
        p1.backstage = []
        debut_card = put_card_in_play(self, p1, "hBP01-077", p1.backstage)
        debut_card_id = debut_card["game_card_id"]

        # Get a bloom card in hand
        bloom_card = add_card_to_hand(self, p1, "hBP01-079")
        bloom_card_id = bloom_card["game_card_id"]

        # Setup P2's backstage - keep only one card for auto-select
        p2_back_card = p2.backstage[0]
        p2_back_card_id = p2_back_card["game_card_id"]
        p2.backstage = [p2_back_card]  # Keep only one backstage
        
        p2_back_hp = p2.get_card_hp(p2_back_card)

        # Set damage so that the next 20 damage will exactly kill the holomem
        # For example, if HP is 60, set damage to 40, so 40 + 20 = 60 = HP (dead)
        p2_back_card["damage"] = p2_back_hp - 20

        print(f"P2 backstage card HP: {p2_back_hp}, damage: {p2_back_card['damage']}")
        print(f"P2 backstage count: {len(p2.backstage)}")

        """Test: Bloom Suisei which triggers bloom effect dealing 20 damage to backstage"""
        self.assertEqual(engine.active_player_id, self.player1)

        # Perform bloom
        engine.handle_game_message(self.player1, GameAction.MainStepBloom, {
            "card_id": bloom_card_id,
            "target_id": debut_card_id
        })

        # The bloom effect should deal 20 damage to a backstage member
        # Since there's only one backstage target, it should auto-select
        events = engine.grab_events()

        print(f"Events: {[e['event_type'] for e in events]}")
        
        # If a choice is required, make it
        if any(e["event_type"] == EventType.EventType_Decision_ChooseHolomemForEffect for e in events):
            engine.handle_game_message(self.player1, GameAction.EffectResolution_ChooseCardsForEffect, {
                "card_ids": [p2_back_card_id]
            })
            events = engine.grab_events()
            print(f"After choice events: {[e['event_type'] for e in events]}")

        # Check for downed holomem event (filter by player1 to avoid counting twice)
        downed_events = [e for e in events if e["event_type"] == EventType.EventType_DownedHolomem and e["event_player_id"] == self.player1]

        print(f"Downed events (player1): {downed_events}")

        # Verify the backstage card was killed
        self.assertEqual(len(downed_events), 1, "Holomem should be downed when damage reaches HP")
        self.assertEqual(downed_events[0]["target_id"], p2_back_card_id)
        # Verify life_loss_prevented is True (due to prevent_life_loss)
        self.assertEqual(downed_events[0]["life_loss_prevented"], True)
        self.assertEqual(downed_events[0]["life_lost"], 0)

    def test_sequential_damage_kills_on_last_hit(self):
        """
        Test that when multiple damage effects are applied sequentially,
        the one that makes damage reach HP should trigger death.
        
        Scenario simulating the bug report:
        - Target has 20 HP remaining (damage = HP - 20)
        - Apply 10 damage x 2 via separate deal_damage calls
        - Second 10 damage should trigger death
        """
        engine = self.engine

        p1: PlayerState = engine.get_player(self.player1)
        p2: PlayerState = engine.get_player(self.player2)

        # Keep only one backstage card
        p2_back_card = p2.backstage[0]
        p2_back_card_id = p2_back_card["game_card_id"]
        p2.backstage = [p2_back_card]
        
        p2_back_hp = p2.get_card_hp(p2_back_card)
        
        # Set damage so that 10 + 10 damage will exactly kill (damage = HP - 20)
        p2_back_card["damage"] = p2_back_hp - 20
        initial_damage = p2_back_card["damage"]
        
        print(f"Setup: HP={p2_back_hp}, initial damage={initial_damage}")
        print(f"Expected: After 2x10 damage, damage={initial_damage + 20} >= HP={p2_back_hp}")
        
        # Get a dealing card
        dealing_card = p1.center[0]
        
        # Track events
        continuation_called = [0]
        def track_continuation():
            continuation_called[0] += 1
        
        # First 10 damage - should NOT kill
        engine.deal_damage(
            dealing_player=p1,
            target_player=p2,
            dealing_card=dealing_card,
            target_card=p2_back_card,
            damage=10,
            special=True,
            prevent_life_loss=True,
            art_info={},
            continuation=track_continuation
        )
        
        events1 = engine.grab_events()
        damage_after_first = p2_back_card["damage"]
        print(f"After first 10 damage: damage={damage_after_first}")
        
        downed_events1 = [e for e in events1 if e["event_type"] == EventType.EventType_DownedHolomem and e["event_player_id"] == self.player1]
        self.assertEqual(len(downed_events1), 0, "Should not die after first 10 damage")
        
        # Second 10 damage - SHOULD kill
        engine.deal_damage(
            dealing_player=p1,
            target_player=p2,
            dealing_card=dealing_card,
            target_card=p2_back_card,
            damage=10,
            special=True,
            prevent_life_loss=True,
            art_info={},
            continuation=track_continuation
        )
        
        events2 = engine.grab_events()
        damage_after_second = p2_back_card["damage"]
        print(f"After second 10 damage: damage={damage_after_second}")
        print(f"Events: {[e['event_type'] for e in events2]}")
        
        downed_events2 = [e for e in events2 if e["event_type"] == EventType.EventType_DownedHolomem and e["event_player_id"] == self.player1]
        
        # The card should be dead after second damage
        self.assertEqual(len(downed_events2), 1, f"Should die after second 10 damage when damage={damage_after_second} >= HP={p2_back_hp}")
        self.assertEqual(downed_events2[0]["target_id"], p2_back_card_id)
        self.assertEqual(downed_events2[0]["life_lost"], 0)  # prevent_life_loss
        
        # Card should be in archive
        self.assertIn(p2_back_card_id, ids_from_cards(p2.archive))
        self.assertNotIn(p2_back_card_id, ids_from_cards(p2.backstage))

    def test_damage_equals_hp_with_prevent_life_loss(self):
        """
        Directly test the deal_damage function with prevent_life_loss=True
        when damage exactly equals HP.
        """
        engine = self.engine

        p1: PlayerState = engine.get_player(self.player1)
        p2: PlayerState = engine.get_player(self.player2)

        # Keep only one backstage card to simplify
        p2_back_card = p2.backstage[0]
        p2_back_card_id = p2_back_card["game_card_id"]
        p2.backstage = [p2_back_card]
        
        p2_back_hp = p2.get_card_hp(p2_back_card)
        
        # Set damage to HP - 10
        p2_back_card["damage"] = p2_back_hp - 10
        initial_damage = p2_back_card["damage"]
        
        print(f"Setup: HP={p2_back_hp}, initial damage={initial_damage}")
        print(f"Backstage before: {ids_from_cards(p2.backstage)}")
        print(f"Archive before: {ids_from_cards(p2.archive)}")
        
        # Get a dealing card (use center)
        dealing_card = p1.center[0]
        
        # Track if death occurred
        death_occurred = False
        original_life_count = len(p2.life)
        
        def check_death():
            nonlocal death_occurred
            death_occurred = True
        
        # Call deal_damage directly with prevent_life_loss=True
        engine.deal_damage(
            dealing_player=p1,
            target_player=p2,
            dealing_card=dealing_card,
            target_card=p2_back_card,
            damage=10,
            special=True,
            prevent_life_loss=True,
            art_info={},
            continuation=check_death
        )
        
        # Process any pending effects
        events = engine.grab_events()
        
        print(f"Events after deal_damage: {[e['event_type'] for e in events]}")
        print(f"Final damage on card: {p2_back_card['damage']}")
        print(f"Backstage after: {ids_from_cards(p2.backstage)}")
        print(f"Archive after: {ids_from_cards(p2.archive)}")
        
        # Check for downed holomem events (filter by player1 to avoid counting twice)
        downed_events = [e for e in events if e["event_type"] == EventType.EventType_DownedHolomem and e["event_player_id"] == self.player1]
        damage_events = [e for e in events if e["event_type"] == EventType.EventType_DamageDealt and e["event_player_id"] == self.player1]

        print(f"Number of downed events (player1): {len(downed_events)}")
        print(f"Number of damage events (player1): {len(damage_events)}")

        for i, de in enumerate(downed_events):
            print(f"Downed event {i}: target={de['target_id']}, life_lost={de['life_lost']}")

        # The card should be dead - EXACTLY once (one event per player, we filter to player1)
        self.assertEqual(len(downed_events), 1, f"Holomem should be downed exactly once, but got {len(downed_events)}")
        # Life should NOT be lost due to prevent_life_loss
        self.assertEqual(downed_events[0]["life_lost"], 0)
        self.assertEqual(downed_events[0]["life_loss_prevented"], True)
        # But death should still occur - card should be in archive
        self.assertIn(p2_back_card_id, ids_from_cards(p2.archive))
        self.assertNotIn(p2_back_card_id, ids_from_cards(p2.backstage))


    def test_damage_at_hp_should_trigger_death_on_next_damage(self):
        """
        Test the edge case: if damage == HP but card is still on stage,
        the next damage attempt should trigger death processing.
        
        This simulates the reported bug where:
        - Card has damage == HP (should be dead)
        - But card is still on stage
        - Next damage effect comes in
        - Death should be triggered
        """
        engine = self.engine

        p1: PlayerState = engine.get_player(self.player1)
        p2: PlayerState = engine.get_player(self.player2)

        # Keep only one backstage card
        p2_back_card = p2.backstage[0]
        p2_back_card_id = p2_back_card["game_card_id"]
        p2.backstage = [p2_back_card]
        
        p2_back_hp = p2.get_card_hp(p2_back_card)
        
        # Simulate the bug: Set damage == HP but card is still on stage
        p2_back_card["damage"] = p2_back_hp
        
        print(f"Setup: HP={p2_back_hp}, damage={p2_back_card['damage']}")
        print(f"Card damage == HP but still on stage")
        print(f"Backstage before: {ids_from_cards(p2.backstage)}")
        
        dealing_card = p1.center[0]
        
        # Attempt to deal damage to a card that should already be dead
        # The deal_damage function should either:
        # 1. Trigger death processing, or
        # 2. At minimum, not leave the card in an inconsistent state
        
        engine.deal_damage(
            dealing_player=p1,
            target_player=p2,
            dealing_card=dealing_card,
            target_card=p2_back_card,
            damage=10,  # Additional damage
            special=True,
            prevent_life_loss=True,
            art_info={},
            continuation=lambda: None
        )
        
        events = engine.grab_events()
        print(f"Events: {[e['event_type'] for e in events]}")
        print(f"Backstage after: {ids_from_cards(p2.backstage)}")
        print(f"Archive after: {ids_from_cards(p2.archive)}")
        
        # Check current behavior - card should be dead since damage >= HP
        # Currently, the code just returns without processing death
        # This is the bug: card remains on stage with damage >= HP
        
        # After the fix, this test should pass
        card_still_on_stage = p2_back_card_id in ids_from_cards(p2.backstage)
        card_in_archive = p2_back_card_id in ids_from_cards(p2.archive)
        
        print(f"Card still on stage: {card_still_on_stage}")
        print(f"Card in archive: {card_in_archive}")
        
        # The card should be in archive (dead), not on stage
        # This assertion will fail with current code, showing the bug
        self.assertTrue(card_in_archive, "Card with damage >= HP should be dead")
        self.assertFalse(card_still_on_stage, "Card with damage >= HP should not be on stage")


if __name__ == '__main__':
    unittest.main()

