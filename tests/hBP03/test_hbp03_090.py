import unittest
from app.gameengine import GameEngine, GameAction
from app.gameengine import PlayerState
from app.gameengine import EventType, ids_from_cards
from tests.helpers import *


class Test_hbp03_090(unittest.TestCase):
  engine: GameEngine
  player1: str
  player2: str


  def setUp(self):
    p1_deck = generate_deck_with("", {
      "hBP03-090": 2, # support event - 홀로라이브 말할 수 있을까?
      "hSD01-003": 4, # debut Tokino Sora
      "hSD01-004": 4, # debut AZKi
    })
    initialize_game_to_third_turn(self, p1_deck)


  def test_hbp03_090_effect(self):
    """Test basic effect: choose debut holomems from top 4 cards and add to hand"""
    engine = self.engine
  
    p1: PlayerState = engine.get_player(self.player1)
    
    # Setup Event card in hand
    _, event_card_id = unpack_game_id(add_card_to_hand(self, p1, "hBP03-090"))

    # Put debut holomem cards on top of the deck
    debut_cards = [card for card in p1.deck if card["card_type"] == "holomem_debut"][:4]
    for card in debut_cards:
      p1.deck.remove(card)
    p1.deck = debut_cards + p1.deck
    debut_card_ids = ids_from_cards(p1.deck[:4])

    hand_count_before = len(p1.hand)

    
    """Test"""
    self.assertEqual(engine.active_player_id, self.player1)

    engine.handle_game_message(self.player1, GameAction.MainStepPlaySupport, { "card_id": event_card_id })
    
    # Verify decision to choose cards is presented with correct choosable cards
    events = engine.grab_events()
    choose_event = [e for e in events if e["event_type"] == EventType.EventType_Decision_ChooseCards][0]
    self.assertEqual(set(choose_event["cards_can_choose"]), set(debut_card_ids))
    
    # Choose all 4 debut cards
    engine.handle_game_message(self.player1, GameAction.EffectResolution_ChooseCardsForEffect, { "card_ids": debut_card_ids })

    events = engine.grab_events()
    validate_last_event_not_error(self, events)

    # Verify cards were added to hand (4 chosen - 1 played event = +3)
    self.assertEqual(len(p1.hand), hand_count_before + 3)
    
    # Verify all chosen cards are now in hand
    hand_ids = ids_from_cards(p1.hand)
    for card_id in debut_card_ids:
      self.assertIn(card_id, hand_ids)


  def test_hbp03_090_effect_choose_no_cards(self):
    """Test choosing no cards: all cards go to bottom of deck in chosen order"""
    engine = self.engine
  
    p1: PlayerState = engine.get_player(self.player1)

    # Setup Event card in hand
    _, event_card_id = unpack_game_id(add_card_to_hand(self, p1, "hBP03-090"))

    # Put debut holomem cards on top of the deck
    debut_cards = [card for card in p1.deck if card["card_type"] == "holomem_debut"][:4]
    for card in debut_cards:
      p1.deck.remove(card)
    p1.deck = debut_cards + p1.deck
    debut_card_ids = ids_from_cards(p1.deck[:4])

    hand_count_before = len(p1.hand)
    deck_count_before = len(p1.deck)

    
    """Test"""
    self.assertEqual(engine.active_player_id, self.player1)

    engine.handle_game_message(self.player1, GameAction.MainStepPlaySupport, { "card_id": event_card_id })
    engine.handle_game_message(self.player1, GameAction.EffectResolution_ChooseCardsForEffect, { "card_ids": [] })
    
    # Should get order cards decision
    events = engine.grab_events()
    order_events = [e for e in events if e["event_type"] == EventType.EventType_Decision_OrderCards]
    self.assertGreaterEqual(len(order_events), 1)
    
    engine.handle_game_message(self.player1, GameAction.EffectResolution_OrderCards, { "card_ids": debut_card_ids })

    events = engine.grab_events()
    validate_last_event_not_error(self, events)

    # Verify no cards were added to hand (only -1 for played event)
    self.assertEqual(len(p1.hand), hand_count_before - 1)
    
    # Verify cards are at bottom of deck
    bottom_4_ids = ids_from_cards(p1.deck[-4:])
    for card_id in debut_card_ids:
      self.assertIn(card_id, bottom_4_ids)


  def test_hbp03_090_partial_selection(self):
    """Test choosing only some cards: selected go to hand, rest go to bottom of deck"""
    engine = self.engine
  
    p1: PlayerState = engine.get_player(self.player1)

    # Setup Event card in hand
    _, event_card_id = unpack_game_id(add_card_to_hand(self, p1, "hBP03-090"))

    # Put debut holomem cards on top of the deck
    debut_cards = [card for card in p1.deck if card["card_type"] == "holomem_debut"][:4]
    for card in debut_cards:
      p1.deck.remove(card)
    p1.deck = debut_cards + p1.deck
    debut_card_ids = ids_from_cards(p1.deck[:4])

    # Choose only 2 cards
    cards_to_choose = debut_card_ids[:2]
    remaining_cards = debut_card_ids[2:]

    hand_count_before = len(p1.hand)

    
    """Test"""
    self.assertEqual(engine.active_player_id, self.player1)

    engine.handle_game_message(self.player1, GameAction.MainStepPlaySupport, { "card_id": event_card_id })
    engine.handle_game_message(self.player1, GameAction.EffectResolution_ChooseCardsForEffect, { "card_ids": cards_to_choose })
    engine.handle_game_message(self.player1, GameAction.EffectResolution_OrderCards, { "card_ids": remaining_cards })

    events = engine.grab_events()
    validate_last_event_not_error(self, events)

    # Verify 2 cards were added to hand (-1 for event + 2 chosen = +1)
    self.assertEqual(len(p1.hand), hand_count_before + 1)
    
    # Verify chosen cards are in hand
    hand_ids = ids_from_cards(p1.hand)
    for card_id in cards_to_choose:
      self.assertIn(card_id, hand_ids)
    
    # Verify remaining cards are at bottom of deck
    bottom_2_ids = ids_from_cards(p1.deck[-2:])
    for card_id in remaining_cards:
      self.assertIn(card_id, bottom_2_ids)


  def test_hbp03_090_no_valid_targets(self):
    """Test when there are no debut holomems in top 4 cards"""
    engine = self.engine
  
    p1: PlayerState = engine.get_player(self.player1)
    
    # Setup Event card in hand
    _, event_card_id = unpack_game_id(add_card_to_hand(self, p1, "hBP03-090"))

    # Remove all debut cards from top of deck and put non-debut cards there
    non_debut_cards = [card for card in p1.deck if card["card_type"] != "holomem_debut"][:4]
    
    if len(non_debut_cards) >= 4:
      for card in non_debut_cards:
        p1.deck.remove(card)
      p1.deck = non_debut_cards + p1.deck

    top_4_ids = ids_from_cards(p1.deck[:4])


    """Test"""
    self.assertEqual(engine.active_player_id, self.player1)

    engine.handle_game_message(self.player1, GameAction.MainStepPlaySupport, { "card_id": event_card_id })
    
    # Verify decision shows no choosable cards
    events = engine.grab_events()
    choose_event = [e for e in events if e["event_type"] == EventType.EventType_Decision_ChooseCards][0]
    self.assertEqual(choose_event["cards_can_choose"], [])
    
    engine.handle_game_message(self.player1, GameAction.EffectResolution_ChooseCardsForEffect, { "card_ids": [] })
    engine.handle_game_message(self.player1, GameAction.EffectResolution_OrderCards, { "card_ids": top_4_ids })

    events = engine.grab_events()
    validate_last_event_not_error(self, events)


  def test_hbp03_090_not_limited(self):
    """Test that this card is NOT limited - used_limited_this_turn should remain False"""
    engine = self.engine
  
    p1: PlayerState = engine.get_player(self.player1)

    # Setup Event cards in hand
    _, event_card_id1 = unpack_game_id(add_card_to_hand(self, p1, "hBP03-090"))
    _, event_card_id2 = unpack_game_id(add_card_to_hand(self, p1, "hBP03-090"))

    # Put debut holomem cards on top of the deck
    debut_cards = [card for card in p1.deck if card["card_type"] == "holomem_debut"][:4]
    for card in debut_cards:
      p1.deck.remove(card)
    p1.deck = debut_cards + p1.deck
    debut_card_ids = ids_from_cards(p1.deck[:4])

    
    """Test"""
    self.assertEqual(engine.active_player_id, self.player1)

    # Check both event cards are playable
    actions = reset_mainstep(self)
    playable_support_count = len([action for action in actions \
                          if action["action_type"] == GameAction.MainStepPlaySupport and action["card_id"] in [event_card_id1, event_card_id2]])
    self.assertEqual(playable_support_count, 2)

    # Use first card
    engine.handle_game_message(self.player1, GameAction.MainStepPlaySupport, { "card_id": event_card_id1 })
    engine.handle_game_message(self.player1, GameAction.EffectResolution_ChooseCardsForEffect, { "card_ids": [] })
    engine.handle_game_message(self.player1, GameAction.EffectResolution_OrderCards, { "card_ids": debut_card_ids })

    events = engine.grab_events()
    validate_last_event_not_error(self, events)

    # Verify the card is NOT marked as limited (used_limited_this_turn should be False)
    self.assertFalse(p1.used_limited_this_turn)


  def test_hbp03_090_only_selects_debut_holomems(self):
    """Test that only debut holomems can be selected, not bloom or other cards"""
    engine = self.engine
  
    p1: PlayerState = engine.get_player(self.player1)
    
    # Setup Event card in hand
    _, event_card_id = unpack_game_id(add_card_to_hand(self, p1, "hBP03-090"))

    # Mix debut and non-debut cards on top of deck
    # First, find one debut and put non-debuts around it
    debut_card = None
    for card in p1.deck:
      if card["card_type"] == "holomem_debut":
        debut_card = card
        break
    
    non_debut_cards = [card for card in p1.deck if card["card_type"] != "holomem_debut"][:3]
    
    if debut_card and len(non_debut_cards) >= 3:
      p1.deck.remove(debut_card)
      for card in non_debut_cards:
        p1.deck.remove(card)
      # Put 1 debut and 3 non-debut on top
      p1.deck = [debut_card] + non_debut_cards + p1.deck
      
      top_4_ids = ids_from_cards(p1.deck[:4])
      debut_card_id = debut_card["game_card_id"]

      """Test"""
      self.assertEqual(engine.active_player_id, self.player1)

      engine.handle_game_message(self.player1, GameAction.MainStepPlaySupport, { "card_id": event_card_id })
      
      # Verify only the debut card can be chosen
      events = engine.grab_events()
      choose_event = [e for e in events if e["event_type"] == EventType.EventType_Decision_ChooseCards][0]
      self.assertEqual(choose_event["cards_can_choose"], [debut_card_id])


if __name__ == '__main__':
  unittest.main()
