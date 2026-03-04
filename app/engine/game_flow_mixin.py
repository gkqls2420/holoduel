from __future__ import annotations
from typing import List, TYPE_CHECKING
from copy import deepcopy
import logging
import random
import time

from app.engine.constants import *
from app.engine.models import *
from app.engine.helpers import *

if TYPE_CHECKING:
    from app.engine.player_state import PlayerState

logger = logging.getLogger(__name__)


class GameFlowMixin:
    def begin_game(self):
        # Set the seed.
        self.random_gen = random.Random(self.seed)
        if self.test_random_override:
            self.random_gen = self.test_random_override

        # Shuffle decks.
        for player_state in self.player_states:
            self.shuffle_list(player_state.deck)
            self.shuffle_list(player_state.cheer_deck)

        # Determine first player.
        self.starting_player_id = self.random_pick_list(self.player_ids)

        # Send initial game info.
        for player_state in self.player_states:
            player_id = player_state.player_id
            self.send_event({
                "event_player_id": player_id,
                "event_type": EventType.EventType_GameStartInfo,
                "event_number": -1,
                "starting_player": self.starting_player_id,
                "your_id": player_id,
                "opponent_id": self.other_player(player_id).player_id,
                "your_username": player_state.username,
                "opponent_username": self.other_player(player_state.player_id).username,
                "game_card_map": self.all_game_cards_map,
            })

        # Reveal oshi cards before first turn choice.
        reveal_event = {
            "event_type": EventType.EventType_OshiReveal,
            "oshi_info": [
                {
                    "player_id": ps.player_id,
                    "oshi_id": ps.oshi_id,
                }
                for ps in self.player_states
            ]
        }
        self.broadcast_event(reveal_event)

        self.active_player_id = self.starting_player_id
        self.send_first_turn_choice()

    def send_first_turn_choice(self):
        choices = [
            {
                "effect_type": EffectType.EffectType_GoFirst,
                "first": True,
            },
            {
                "effect_type": EffectType.EffectType_GoFirst,
                "first": False,
            },
        ]
        add_ids_to_effects(choices, self.starting_player_id, "")
        self.send_choice_to_player(self.starting_player_id, choices, False, self.after_first_turn_choice)

    def after_first_turn_choice(self):
        self.active_player_id = self.first_turn_player_id

        # Draw starting hands
        for player_state in self.player_states:
            player_state.draw(STARTING_HAND_SIZE)

        self.phase = GamePhase.Mulligan
        self.handle_mulligan_phase()

    def get_observer_catchup_events(self):
        observer_events = [{
            "event_player_id": "observer",
            "event_type": EventType.EventType_GameStartInfo,
            "event_number": -1,
            "starting_player": self.starting_player_id,
            "your_id": self.player_ids[0],
            "opponent_id": self.player_ids[1],
            "your_username": self.player_states[0].username,
            "opponent_username": self.player_states[1].username,
            "game_card_map": self.all_game_cards_map,
        }]
        for i in range(len(self.all_events)):
            event = self.all_events[i]
            observer_events.append(self.create_observer_event(event))
        return observer_events

    def create_observer_event(self, event):
        event_copy = event.copy()
        event_copy["event_player_id"] = "observer"
        event_copy["your_clock_used"] = self.player_states[0].clock_time_used
        event_copy["opponent_clock_used"] = self.player_states[1].clock_time_used
        # Always sanitize.
        hidden_fields = event.get("hidden_info_fields", [])
        hidden_erase = event.get("hidden_info_erase", [])
        for field in hidden_fields:
            if field in hidden_erase:
                event_copy[field] = None
            else:
                # If the field is a single id, replace it.
                # If it is a list, replace them all.
                if isinstance(event_copy[field], str):
                    event_copy[field] = UNKNOWN_CARD_ID
                elif isinstance(event_copy[field], list):
                    event_copy[field] = [UNKNOWN_CARD_ID] * len(event_copy[field])
        return event_copy

    def handle_mulligan_phase(self):
        # Are both players done mulliganing?
        # If so, move on to the next phase.
        if all(player_state.mulligan_completed for player_state in self.player_states):
            self.process_forced_mulligans()
            if self.is_game_over():
                return
            self.begin_initial_placement()
        else:
            active_player = self.get_player(self.active_player_id)
            if active_player.mulligan_count == 0:
                # Tell the active player we're waiting on them to mulligan.
                decision_event = {
                    "event_type": EventType.EventType_MulliganDecision,
                    "desired_response": GameAction.Mulligan,
                    "active_player": self.active_player_id,
                    "first_player": self.first_turn_player_id,
                }
                self.broadcast_event(decision_event)
            else:
                raise Exception("Unexpected: Player has already mulliganed.")

    def send_event(self, event):
        self.latest_events.append(event)

    def broadcast_event(self, event):
        event["event_number"] = len(self.all_events)
        event["last_game_message_number"] = len(self.all_game_messages) - 1
        self.latest_observer_events.append(self.create_observer_event(event))
        self.all_events.append(event)
        hidden_fields = event.get("hidden_info_fields", [])
        hidden_erase = event.get("hidden_info_erase", [])
        for player_state in self.player_states:
            should_sanitize = not (player_state.player_id == event.get("hidden_info_player"))
            new_event = {
                "event_player_id": player_state.player_id,
                **event,
                "your_clock_used": player_state.clock_time_used,
                "opponent_clock_used": self.other_player(player_state.player_id).clock_time_used,
            }
            if should_sanitize:
                for field in hidden_fields:
                    if field in hidden_erase:
                        new_event[field] = None
                    else:
                        # If the field is a single id, replace it.
                        # If it is a list, replace them all.
                        if isinstance(new_event[field], str):
                            new_event[field] = UNKNOWN_CARD_ID
                        elif isinstance(new_event[field], list):
                            new_event[field] = [UNKNOWN_CARD_ID] * len(new_event[field])
            self.latest_events.append(new_event)

    def broadcast_bonus_hp_updates(self):
        for player in self.player_states:
            updates = {}
            for card in player.get_holomem_on_stage():
                bonus = player.get_card_bonus_hp(card)
                updates[card["game_card_id"]] = bonus
            event = {
                "event_type": EventType.EventType_BonusHpUpdate,
                "player_id": player.player_id,
                "bonus_hp_updates": updates,
            }
            self.broadcast_event(event)

    def set_decision(self, new_decision):
        if self.current_decision:
            raise Exception("Decision already set.")
        self.current_decision = new_decision
        self.current_clock_player_id = new_decision["decision_player"]
        self.clock_accumulation_start_time = time.time()

    def begin_initial_placement(self):
        self.phase = GamePhase.InitialPlacement
        self.active_player_id = self.first_turn_player_id

        # The player must now choose their center holomem and any backstage holomems from hand.
        self.send_initial_placement_event()

    def send_initial_placement_event(self):
        active_player = self.get_player(self.active_player_id)
        debut_options = []
        for card in active_player.hand:
            if card["card_type"] == "holomem_debut":
                debut_options.append(card["game_card_id"])

        decision_event = {
            "event_type": EventType.EventType_InitialPlacementBegin,
            "desired_response": GameAction.InitialPlacement,
            "active_player": self.active_player_id,
            "debut_options": debut_options,
            "hidden_info_player": self.active_player_id,
            "hidden_info_fields": ["debut_options"],
            "hidden_info_erase": ["debut_options"],
        }
        self.broadcast_event(decision_event)

    def begin_return_cards(self):
        active_player = self.get_player(self.active_player_id)
        if active_player.forced_mulligan_count == 0:
            self.begin_backstage_placement()
            return

        hand_card_ids = ids_from_cards(active_player.hand)
        decision_event = {
            "event_type": EventType.EventType_ReturnCardsBegin,
            "desired_response": GameAction.ReturnCards,
            "active_player": self.active_player_id,
            "return_count": active_player.forced_mulligan_count,
            "hand_card_ids": hand_card_ids,
            "hidden_info_player": self.active_player_id,
            "hidden_info_fields": ["hand_card_ids"],
            "hidden_info_erase": ["hand_card_ids"],
        }
        self.broadcast_event(decision_event)

    def begin_backstage_placement(self):
        active_player = self.get_player(self.active_player_id)
        debut_options = []
        spot_options = []
        for card in active_player.hand:
            if card["card_type"] == "holomem_debut":
                debut_options.append(card["game_card_id"])
            elif card["card_type"] == "holomem_spot":
                spot_options.append(card["game_card_id"])

        decision_event = {
            "event_type": EventType.EventType_BackstagePlacementBegin,
            "desired_response": GameAction.BackstagePlacement,
            "active_player": self.active_player_id,
            "debut_options": debut_options,
            "spot_options": spot_options,
            "hidden_info_player": self.active_player_id,
            "hidden_info_fields": ["debut_options", "spot_options"],
            "hidden_info_erase": ["debut_options", "spot_options"],
        }
        self.broadcast_event(decision_event)

    def continue_initial_placement(self):
        self.switch_active_player()
        if all(player_state.initial_placement_completed for player_state in self.player_states):

            # Initialize life.
            for player_state in self.player_states:
                player_state.initialize_life()

            # Reveal center and backstage cards.
            reveal_event = {
                "event_type": EventType.EventType_InitialPlacementReveal,
                "placement_info": [
                    {
                        "player_id": player_state.player_id,
                        "center_card_id": player_state.center[0]["game_card_id"],
                        "backstage_card_ids": ids_from_cards(player_state.backstage),
                        "hand_count": len(player_state.hand),
                        "cheer_deck_count": len(player_state.cheer_deck),
                        "life_count": len(player_state.life),
                    }
                    for player_state in self.player_states
                ]
            }
            self.broadcast_event(reveal_event)
            self.broadcast_bonus_hp_updates()

            # Move on to the first player's turn.
            self.active_player_id = self.first_turn_player_id
            self.begin_player_turn(switch_active_player=False)
        else:
            self.send_initial_placement_event()
