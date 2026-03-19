from __future__ import annotations
from typing import List, TYPE_CHECKING
from copy import deepcopy
import traceback
import logging
import time

from app.engine.constants import *
from app.engine.models import *
from app.engine.helpers import *

if TYPE_CHECKING:
    from app.engine.player_state import PlayerState

logger = logging.getLogger(__name__)

class ActionHandlerMixin:
    def perform_mulligan(self, player: PlayerState, forced):
        if forced:
            revealed_card_ids = ids_from_cards(player.hand)
            mulligan_reveal_event = {
                "event_type": EventType.EventType_MulliganReveal,
                "active_player": player.player_id,
                "revealed_card_ids": revealed_card_ids,
                "forced_mulligan_count": player.forced_mulligan_count + 1,
                "max_forced_mulligans": MAX_FORCED_MULLIGANS,
            }
            self.broadcast_event(mulligan_reveal_event)

        player.mulligan(forced=forced)

    def process_forced_mulligans(self):
        for player in self.player_states:
            while not player.mulligan_hand_valid and not self.is_game_over():
                if any(card["card_type"] == "holomem_debut" for card in player.hand):
                    player.mulligan_hand_valid = True
                else:
                    if player.forced_mulligan_count >= MAX_FORCED_MULLIGANS:
                        self.end_game(player.player_id, GameOverReason.GameOverReason_MulliganToZero)
                    else:
                        self.perform_mulligan(player, forced=True)


    def make_error_event(self, player_id:str, error_id:str, error_message:str):
        return {
            "event_player_id": player_id,
            "event_type": EventType.EventType_GameError,
            "error_id": error_id,
            "error_message": error_message,
        }

    def validate_action_fields(self, action_data:dict, expected_fields:dict):
        for field_name, field_type in expected_fields.items():
            if field_name not in action_data:
                return False
            # If the field type is the list typing.
            if hasattr(field_type, '__origin__') and field_type.__origin__ == list:
                element_type = field_type.__args__[0]
                if not isinstance(action_data[field_name], list) or not all(isinstance(item, element_type) for item in action_data[field_name]):
                    return False
             # Check for dict type with specific key and value types
            elif hasattr(field_type, '__origin__') and field_type.__origin__ == dict:
                key_type, value_type = field_type.__args__
                if not isinstance(action_data[field_name], dict) or not all(isinstance(k, key_type) and isinstance(v, value_type) for k, v in action_data[field_name].items()):
                    logger.info(f"Field {field_name} is not of type {field_type}")
                    return False
        return True

    def handle_game_message(self, player_id:str, action_type:str, action_data: dict):
        self.all_game_messages.append({
            "game_message_number": len(self.all_game_messages),
            "last_event_number": len(self.all_events) - 1,
            "player_id": player_id,
            "action_type": action_type,
            "action_data": action_data
        })
        username = self.get_player(player_id).username
        #logger.info("Game Message: Player(%s) : %s" % (username, action_type))
        handled = False
        try:
            match action_type:
                case GameAction.Mulligan:
                    handled = self.handle_mulligan(player_id, action_data)
                case GameAction.InitialPlacement:
                    handled = self.handle_initial_placement(player_id, action_data)
                case GameAction.ReturnCards:
                    handled = self.handle_return_cards(player_id, action_data)
                case GameAction.BackstagePlacement:
                    handled = self.handle_backstage_placement(player_id, action_data)
                case GameAction.ChooseNewCenter:
                    handled = self.handle_choose_new_center(player_id, action_data)
                case GameAction.PlaceCheer:
                    handled = self.handle_place_cheer(player_id, action_data)
                case GameAction.MainStepPlaceHolomem:
                    handled = self.handle_main_step_place_holomem(player_id, action_data)
                case GameAction.MainStepBloom:
                    handled = self.handle_main_step_bloom(player_id, action_data)
                case GameAction.MainStepCollab:
                    handled = self.handle_main_step_collab(player_id, action_data)
                case GameAction.MainStepOshiSkill:
                    handled = self.handle_main_step_oshi_skill(player_id, action_data)
                case GameAction.MainStepSpecialAction:
                    handled = self.handle_main_step_special_action(player_id, action_data)
                case GameAction.MainStepPlaySupport:
                    handled = self.handle_main_step_play_support(player_id, action_data)
                case GameAction.MainStepBatonPass:
                    handled = self.handle_main_step_baton_pass(player_id, action_data)
                case GameAction.MainStepBeginPerformance:
                    handled = self.handle_main_step_begin_performance(player_id, action_data)
                case GameAction.MainStepEndTurn:
                    handled = self.handle_main_step_end_turn(player_id, action_data)
                case GameAction.PerformanceStepUseArt:
                    handled = self.handle_performance_step_use_art(player_id, action_data)
                case GameAction.PerformanceStepEndTurn:
                    handled = self.handle_performance_step_end_turn(player_id, action_data)
                case GameAction.PerformanceStepCancel:
                    handled = self.handle_performance_step_cancel(player_id, action_data)
                case GameAction.EffectResolution_MoveCheerBetweenHolomems:
                    handled = self.handle_effect_resolution_move_cheer_between_holomems(player_id, action_data)
                case GameAction.EffectResolution_ChooseCardsForEffect:
                    handled = self.handle_effect_resolution_choose_cards_for_effect(player_id, action_data)
                case GameAction.EffectResolution_MakeChoice:
                    handled = self.handle_effect_resolution_make_choice(player_id, action_data)
                case GameAction.EffectResolution_OrderCards:
                    handled = self.handle_effect_resolution_order_cards(player_id, action_data)
                case GameAction.Resign:
                    logger.info("Game Message: Player(%s) : %s" % (username, action_type))
                    handled = self.handle_player_resign(player_id)
                case _:
                    self.send_event(self.make_error_event(player_id, "invalid_action", "Invalid action type."))
        except Exception as e:
            error_details = traceback.format_exc()
            logger.error(f"Error processing game message {action_type} from player {username} - {player_id}: {e} Callstack: {error_details}")
            callstack_lines = error_details.strip().split("\n")
            short_callstack = "\n".join(callstack_lines[-6:]) if len(callstack_lines) > 6 else error_details.strip()
            self.broadcast_event({
                "event_type": EventType.EventType_GameError,
                "error_id": "internal_error",
                "error_message": f"Internal server error during {action_type}: {str(e)}",
                "error_action_type": action_type,
                "error_action_data": action_data,
                "error_game_phase": str(self.phase),
                "error_callstack": short_callstack,
            })
            if not self.is_game_over():
                self.end_game(player_id, GameOverReason.GameOverReason_Resign)
        if not handled:
            # Put out a warning log line with the action that was sent.
            logger.error(f"Game Message: Player({username}) - {player_id} Action {action_type} was not handled: {action_data}.")
            player_info_str = ""
            for player in self.player_states:
                player_info_str += f"{player.username}({player.player_id}),"
            logger.error(f"Player info: {player_info_str}")

    def validate_mulligan(self, player_id:str, action_data: dict):
        if self.phase != GamePhase.Mulligan:
            self.send_event(self.make_error_event(player_id, "invalid_phase", "Invalid phase for mulligan."))
            return False

        if player_id != self.active_player_id:
            self.send_event(self.make_error_event(player_id, "invalid_player", "Not your turn to mulligan."))
            return False

        if not self.validate_action_fields(action_data, GameAction.MulliganActionFields):
            self.send_event(self.make_error_event(player_id, "invalid_action", "Invalid mulligan action."))
            return False

        return True

    def handle_mulligan(self, player_id:str, action_data: dict):
        if not self.validate_mulligan(player_id, action_data):
            return False

        player_state = self.get_player(player_id)
        do_mulligan = action_data["do_mulligan"]
        if do_mulligan:
            self.perform_mulligan(player_state, forced=False)
        player_state.mulligan_completed = True
        self.switch_active_player()
        self.handle_mulligan_phase()

        return True

    def validate_initial_placement(self, player_id:str, action_data: dict):
        if self.phase != GamePhase.InitialPlacement:
            self.send_event(self.make_error_event(player_id, "invalid_phase", "Invalid phase for initial placement."))
            return False

        if player_id != self.active_player_id:
            self.send_event(self.make_error_event(player_id, "invalid_player", "Not your turn to place cards."))
            return False

        if not self.validate_action_fields(action_data, GameAction.InitialPlacementActionFields):
            self.send_event(self.make_error_event(player_id, "invalid_action", "Invalid initial placement action."))
            return False

        player_state = self.get_player(player_id)
        center_holomem_card_id = action_data["center_holomem_card_id"]

        if not player_state.are_cards_in_hand([center_holomem_card_id]):
            self.send_event(self.make_error_event(player_id, "invalid_cards", "Invalid cards for initial placement."))
            return False

        center_card = player_state.get_card_from_hand(center_holomem_card_id)
        if center_card["card_type"] != "holomem_debut":
            self.send_event(self.make_error_event(player_id, "invalid_center", "Invalid center card for initial placement."))
            return False

        return True

    def handle_initial_placement(self, player_id:str, action_data:dict):
        if not self.validate_initial_placement(player_id, action_data):
            return False

        player_state = self.get_player(player_id)
        center_holomem_card_id = action_data["center_holomem_card_id"]

        player_state.move_card(center_holomem_card_id, "center", no_events=True)

        placement_event = {
            "event_type": EventType.EventType_InitialPlacementPlaced,
            "hidden_info_player": player_id,
            "hidden_info_fields": ["center_card_id"],
            "active_player": player_id,
            "center_card_id": center_holomem_card_id,
            "hand_count": len(player_state.hand),
        }
        self.broadcast_event(placement_event)

        self.begin_return_cards()

        return True

    def validate_return_cards(self, player_id:str, action_data: dict):
        if self.phase != GamePhase.InitialPlacement:
            self.send_event(self.make_error_event(player_id, "invalid_phase", "Invalid phase for return cards."))
            return False

        if player_id != self.active_player_id:
            self.send_event(self.make_error_event(player_id, "invalid_player", "Not your turn to return cards."))
            return False

        if not self.validate_action_fields(action_data, GameAction.ReturnCardsActionFields):
            self.send_event(self.make_error_event(player_id, "invalid_action", "Invalid return cards action."))
            return False

        player_state = self.get_player(player_id)
        card_ids = action_data["card_ids"]

        if len(card_ids) != player_state.forced_mulligan_count:
            self.send_event(self.make_error_event(player_id, "invalid_count", "Must return exactly %d cards." % player_state.forced_mulligan_count))
            return False

        if len(set(card_ids)) != len(card_ids):
            self.send_event(self.make_error_event(player_id, "invalid_cards", "Duplicate cards in return list."))
            return False

        if not player_state.are_cards_in_hand(card_ids):
            self.send_event(self.make_error_event(player_id, "invalid_cards", "Cards not in hand."))
            return False

        return True

    def handle_return_cards(self, player_id:str, action_data:dict):
        if not self.validate_return_cards(player_id, action_data):
            return False

        player_state = self.get_player(player_id)
        card_ids = action_data["card_ids"]

        for card_id in card_ids:
            player_state.move_card(card_id, "deck", add_to_bottom=True, hidden_info=True)

        self.begin_backstage_placement()

        return True

    def validate_backstage_placement(self, player_id:str, action_data: dict):
        if self.phase != GamePhase.InitialPlacement:
            self.send_event(self.make_error_event(player_id, "invalid_phase", "Invalid phase for backstage placement."))
            return False

        if player_id != self.active_player_id:
            self.send_event(self.make_error_event(player_id, "invalid_player", "Not your turn to place cards."))
            return False

        if not self.validate_action_fields(action_data, GameAction.BackstagePlacementActionFields):
            self.send_event(self.make_error_event(player_id, "invalid_action", "Invalid backstage placement action."))
            return False

        player_state = self.get_player(player_id)
        backstage_holomem_card_ids = action_data["backstage_holomem_card_ids"]

        if len(backstage_holomem_card_ids) > MAX_MEMBERS_ON_STAGE - 1:
            self.send_event(self.make_error_event(player_id, "invalid_backstage", "Too many cards for backstage."))
            return False

        if len(set(backstage_holomem_card_ids)) != len(backstage_holomem_card_ids):
            self.send_event(self.make_error_event(player_id, "invalid_cards", "Duplicate cards in backstage list."))
            return False

        if len(backstage_holomem_card_ids) > 0:
            if not player_state.are_cards_in_hand(backstage_holomem_card_ids):
                self.send_event(self.make_error_event(player_id, "invalid_cards", "Cards not in hand."))
                return False

            backstage_cards = [player_state.get_card_from_hand(card_id) for card_id in backstage_holomem_card_ids]
            if any(card["card_type"] != "holomem_debut" and card["card_type"] != "holomem_spot" for card in backstage_cards):
                self.send_event(self.make_error_event(player_id, "invalid_backstage", "Invalid backstage cards for placement."))
                return False

        return True

    def handle_backstage_placement(self, player_id:str, action_data:dict):
        if not self.validate_backstage_placement(player_id, action_data):
            return False

        player_state = self.get_player(player_id)
        backstage_holomem_card_ids = action_data["backstage_holomem_card_ids"]

        for card_id in backstage_holomem_card_ids:
            player_state.move_card(card_id, "backstage", no_events=True)

        player_state.initial_placement_completed = True

        backstage_event = {
            "event_type": EventType.EventType_BackstagePlacementPlaced,
            "hidden_info_player": player_id,
            "hidden_info_fields": ["backstage_card_ids"],
            "active_player": player_id,
            "backstage_card_ids": backstage_holomem_card_ids,
            "hand_count": len(player_state.hand),
        }
        self.broadcast_event(backstage_event)

        self.continue_initial_placement()

        return True

    def validate_choose_new_center(self, player_id:str, action_data:dict):
        # The center card id must be in the current_decision options
        # The center card id has to be a card that is in the player's backstage.
        if not self.validate_decision_base(player_id, action_data, DecisionType.DecisionChooseNewCenter, GameAction.ChooseNewCenterActionFields):
            return False

        new_center_card_id = action_data["new_center_card_id"]
        if new_center_card_id not in self.current_decision["options"]:
            self.send_event(self.make_error_event(player_id, "invalid_card", "Invalid new center card."))
            return False

        player_state = self.get_player(player_id)
        if not any(card["game_card_id"] == new_center_card_id for card in player_state.backstage):
            self.send_event(self.make_error_event(player_id, "invalid_card", "New center card not in backstage."))
            return False

        return True

    def blank_continuation(self):
        raise NotImplementedError("Continuation expected.")

    def clear_decision(self):
        if self.current_clock_player_id:
            elapsed_time = time.time() - self.clock_accumulation_start_time
            active_player = self.get_player(self.current_clock_player_id)
            active_player.clock_time_used += elapsed_time
        continuation = self.blank_continuation
        if self.current_decision:
            continuation = self.current_decision["continuation"]
            self.current_decision = None
        return continuation

    def handle_choose_new_center(self, player_id:str, action_data:dict):
        if not self.validate_choose_new_center(player_id, action_data):
            return False

        continuation = self.clear_decision()

        player = self.get_player(player_id)
        new_center_card_id = action_data["new_center_card_id"]
        player.move_card(new_center_card_id, "center")

        continuation()

        return True

    def validate_place_cheer(self, player_id:str, action_data:dict):
        if not self.validate_decision_base(player_id, action_data, DecisionType.DecisionPlaceCheer, GameAction.PlaceCheerActionFields):
            return False

        placements = action_data["placements"]
        for cheer_id, target_id in placements.items():
            if cheer_id not in self.current_decision["cheer_to_place"]:
                self.send_event(self.make_error_event(player_id, "invalid_cheer", "Invalid cheer to place."))
                return False
            if target_id not in self.current_decision["options"]:
                self.send_event(self.make_error_event(player_id, "invalid_target", "Invalid target for cheer."))
                return False

        return True

    def handle_place_cheer(self, player_id:str, action_data:dict):
        if not self.validate_place_cheer(player_id, action_data):
            return False

        continuation = self.clear_decision()

        player = self.get_player(player_id)
        placements = action_data["placements"]
        for cheer_id, target_id in placements.items():
            player.move_card(cheer_id, "holomem", target_id)

        continuation()
        return True

    def validate_main_step_place_holomem(self, player_id:str, action_data:dict):
        if not self.validate_decision_base(player_id, action_data, DecisionType.DecisionMainStep, GameAction.MainStepPlaceHolomemFields):
            return False

        chosen_card_id = action_data["card_id"]
        action_found = False
        for action in self.current_decision["available_actions"]:
            if action["action_type"] == GameAction.MainStepPlaceHolomem and action["card_id"] == chosen_card_id:
                action_found = True
        if not action_found:
            self.send_event(self.make_error_event(player_id, "invalid_action", "Invalid action."))
            return False

        return True

    def validate_main_step_special_action(self, player_id: str, action_data: dict) -> bool:
        if not self.validate_decision_base(player_id, action_data, DecisionType.DecisionMainStep, GameAction.MainStepSpecialActionFields):
            return False

        player = self.get_player(player_id)

        # Validate that the card exists
        card_id = action_data["card_id"]
        card, _, _ = player.find_card(card_id, include_stacked_cards=True)
        if not card:
            self.send_event(self.make_error_event(player_id, "invalid_action", "Card not found."))
            return False

        # Validate that the action is part of the current decision's available actions
        effect_id = action_data["effect_id"]
        action_found = False
        for action in self.current_decision["available_actions"]:
            if action["action_type"] == GameAction.MainStepSpecialAction \
                and action["effect_id"] == effect_id and action["card_id"] == card_id:
                action_found = True
        if not action_found:
            self.send_event(self.make_error_event(player_id, "invalid_action", "Invalid action."))
            return False

        return True

    def handle_main_step_special_action(self, player_id: str, action_data: dict):
        if not self.validate_main_step_special_action(player_id, action_data):
            return False

        continuation = self.clear_decision()

        player = self.get_player(player_id)
        card_id = action_data["card_id"]
        effect_id = action_data["effect_id"]

        action_effects = player.get_special_action_effects(card_id, effect_id)
        add_ids_to_effects(action_effects, player_id, card_id)

        self.broadcast_event({
            "event_type": EventType.EventType_SpecialActionActivation,
            "player_id": player_id,
            "effect_id": effect_id,
            "card_id": card_id
        })
        self.begin_resolving_effects(action_effects, continuation)
        return True

    def handle_main_step_place_holomem(self, player_id:str, action_data:dict):
        if not self.validate_main_step_place_holomem(player_id, action_data):
            return False

        continuation = self.clear_decision()

        player = self.get_player(player_id)
        card_id = action_data["card_id"]
        player.move_card(card_id, "backstage")

        continuation()
        return True


    def validate_main_step_bloom(self, player_id:str, action_data:dict):
        if not self.validate_decision_base(player_id, action_data, DecisionType.DecisionMainStep, GameAction.MainStepBloomFields):
            return False

        chosen_card_id = action_data["card_id"]
        target_id = action_data["target_id"]
        action_found = False
        for action in self.current_decision["available_actions"]:
            if action["action_type"] == GameAction.MainStepBloom and action["card_id"] == chosen_card_id and action["target_id"] == target_id:
                action_found = True
        if not action_found:
            self.send_event(self.make_error_event(player_id, "invalid_action", "Invalid action."))
            return False

        return True

    def handle_main_step_bloom(self, player_id:str, action_data:dict):
        if not self.validate_main_step_bloom(player_id, action_data):
            return False

        continuation = self.clear_decision()

        player = self.get_player(player_id)
        card_id = action_data["card_id"]
        target_id = action_data["target_id"]
        
        # 일반적인 블룸은 오시 스킬로부터 온 것이 아님
        self.last_bloom_source_skill_id = ""
        
        player.bloom(card_id, target_id, continuation)

        return True

    def validate_main_step_collab(self, player_id:str, action_data:dict):
        if not self.validate_decision_base(player_id, action_data, DecisionType.DecisionMainStep, GameAction.MainStepCollabFields):
            return False

        chosen_card_id = action_data["card_id"]
        action_found = False
        for action in self.current_decision["available_actions"]:
            if action["action_type"] == GameAction.MainStepCollab and action["card_id"] == chosen_card_id:
                action_found = True
        if not action_found:
            self.send_event(self.make_error_event(player_id, "invalid_action", "Invalid action."))
            return False

        return True

    def handle_main_step_collab(self, player_id:str, action_data:dict):
        if not self.validate_main_step_collab(player_id, action_data):
            return False

        continuation = self.clear_decision()

        player = self.get_player(player_id)
        card_id = action_data["card_id"]
        player.collab_action(card_id, continuation)

        return True

    def validate_decision_base(self, player_id:str, action_data:dict, expected_decision_type, expected_action_type):
        if not isinstance(player_id, str):
            self.send_event(self.make_error_event(player_id, "invalid_player", "Invalid player id."))
            return False

        if not self.current_decision:
            self.send_event(self.make_error_event(player_id, "invalid_decision", "No current decision."))
            return False

        if not self.validate_action_fields(action_data, expected_action_type):
            self.send_event(self.make_error_event(player_id, "invalid_action", "Invalid action fields."))
            return False

        if player_id != self.current_decision["decision_player"]:
            self.send_event(self.make_error_event(player_id, "invalid_player", "Not your turn."))
            return False

        if self.current_decision["decision_type"] != expected_decision_type:
            self.send_event(self.make_error_event(player_id, "invalid_decision", "Invalid decision."))
            return False

        return True

    def validate_main_step_oshi_skill(self, player_id:str, action_data:dict):
        if not self.validate_decision_base(player_id, action_data, DecisionType.DecisionMainStep, GameAction.MainStepOshiSkillFields):
            return False

        skill_id = action_data["skill_id"]
        action_found = False
        for action in self.current_decision["available_actions"]:
            if action["action_type"] == GameAction.MainStepOshiSkill and action["skill_id"] == skill_id:
                action_found = True
        if not action_found:
            self.send_event(self.make_error_event(player_id, "invalid_action", "Invalid action."))
            return False

        return True

    def handle_main_step_oshi_skill(self, player_id:str, action_data:dict):
        if not self.validate_main_step_oshi_skill(player_id, action_data):
            return False

        continuation = self.clear_decision()

        player = self.get_player(player_id)
        skill_id = action_data["skill_id"]

        action = next(a for a in player.oshi_card["actions"] if a["skill_id"] == skill_id)
        skill_limit = action.get("limit", "")

        action_effects = player.get_oshi_action_effects(skill_id)
        add_ids_to_effects(action_effects, player_id, player.oshi_card["game_card_id"])

        def after_oshi_effects():
            gift_timing = "on_sp_oshi_skill" if skill_limit == "once_per_game" else "on_oshi_skill"
            gift_effects = []
            for holomem in player.get_holomem_on_stage():
                if "gift_effects" in holomem:
                    effects = filter_effects_at_timing(holomem["gift_effects"], gift_timing)
                    add_ids_to_effects(effects, player_id, holomem["game_card_id"])
                    gift_effects.extend(effects)
            if gift_effects:
                self.begin_resolving_effects(gift_effects, continuation)
                return
            continuation()

        self.begin_resolving_effects(action_effects, after_oshi_effects)

        return True

    def validate_main_step_play_support(self, player_id:str, action_data:dict):
        if not self.validate_decision_base(player_id, action_data, DecisionType.DecisionMainStep, GameAction.MainStepPlaySupportFields):
            return False

        player = self.get_player(player_id)
        chosen_card_id = action_data["card_id"]
        action_found = None
        for action in self.current_decision["available_actions"]:
            if action["action_type"] == GameAction.MainStepPlaySupport and action["card_id"] == chosen_card_id:
                action_found = action
                break
        if not action_found:
            self.send_event(self.make_error_event(player_id, "invalid_action", "Invalid action."))
            return False

        if "play_requirements" in action_found:
            # All fields in play_requirements must exist in action_data.
            for required_field_name, required_field_info in action_found["play_requirements"].items():
                if required_field_name not in action_data:
                    self.send_event(self.make_error_event(player_id, "invalid_action", "Invalid action."))
                    return False

                passed_in_data = action_data[required_field_name]
                if required_field_info["type"] == "list":
                    if not isinstance(passed_in_data, list) or len(passed_in_data) != required_field_info["length"]:
                        self.send_event(self.make_error_event(player_id, "invalid_action", "Invalid action."))
                        return False

                    if required_field_info["content_type"] == "cheer_in_play":
                        # Validate that all items in the list are cheer cards on holomems.
                        validated = True
                        for cheer_id in passed_in_data:
                            if not isinstance(cheer_id, str):
                                validated = False
                                break
                            if cheer_id not in player.get_cheer_ids_on_holomems():
                                validated = False
                                break

                        # The list must also be unique.
                        if len(set(passed_in_data)) != len(passed_in_data):
                            validated = False

                        if not validated:
                            self.send_event(self.make_error_event(player_id, "invalid_action", "Invalid action."))
                            return False

        return True

    def handle_main_step_play_support(self, player_id:str, action_data:dict):
        if not self.validate_main_step_play_support(player_id, action_data):
            return False

        continuation = self.clear_decision()

        player = self.get_player(player_id)
        card_id = action_data["card_id"]
        card, _, _ = player.find_card(card_id)

        # Send an event showing the card being played.
        play_event = {
            "event_type": EventType.EventType_PlaySupportCard,
            "player_id": player_id,
            "card_id": card_id,
            "limited": is_card_limited(card),
        }
        self.broadcast_event(play_event)

        # Remove the card from hand.
        card, _, _ = player.find_and_remove_card(card_id)

        # Handle any requirements to play the card.
        cheer_to_archive_from_play = action_data.get("cheer_to_archive_from_play", [])
        if cheer_to_archive_from_play:
            player.archive_attached_cards(cheer_to_archive_from_play)

        # Begin resolving the card effects.
        player.played_support_this_turn = True
        amount_of_type_played = player.played_support_types_this_turn.get(card["sub_type"], 0)
        player.played_support_types_this_turn[card["sub_type"]] = amount_of_type_played + 1
        # Record the support card names used this turn
        for card_name in card.get("card_names", []):
            if card_name not in player.support_card_names_used_this_turn:
                player.support_card_names_used_this_turn.append(card_name)
        # Record the support card tags used this turn
        for tag in card.get("tags", []):
            if tag not in player.support_card_tags_used_this_turn:
                player.support_card_tags_used_this_turn.append(tag)
        if is_card_limited(card):
            player.used_limited_this_turn = True
            player.limited_uses_count_this_turn += 1

        if is_event_card_whit_magic_tag_limited(card):
            player.event_card_whit_magic_tag = True

        card_effects = card["effects"]
        add_ids_to_effects(card_effects, player.player_id, card_id)
        self.floating_cards.append(card)
        
        # Create a new continuation that clears stage_selected_holomems after the card effect is complete
        def card_completion_continuation():
            self.stage_selected_holomems = []
            continuation()
        
        self.begin_resolving_effects(card_effects, card_completion_continuation, [card])

        return True

    def validate_main_step_baton_pass(self, player_id:str, action_data:dict):
        if not self.validate_decision_base(player_id, action_data, DecisionType.DecisionMainStep, GameAction.MainStepBatonPassFields):
            return False

        card_id = action_data["card_id"]
        cheer_ids = action_data["cheer_ids"]
        # The card must be in the options in the available action.
        action_found = False
        for action in self.current_decision["available_actions"]:
            if action["action_type"] == GameAction.MainStepBatonPass and card_id in action["backstage_options"]:
                action_found = True
        if not action_found:
            self.send_event(self.make_error_event(player_id, "invalid_action", "Invalid action."))
            return False

        # Validate that there is enough cheer in the cheer ids and the cheer are all on the center.
        player = self.get_player(player_id)
        center_mem = player.center[0]
        baton_cost = center_mem["baton_cost"]
        # Apply baton cost reductions (same logic as determine_available_actions)
        reduce_cost_effects = player.get_effects_at_timing("on_baton_cost_check", center_mem, "")
        for effect in reduce_cost_effects:
            if effect["effect_type"] == EffectType.EffectType_ReduceBatonCost:
                conditions = effect.get("conditions", [])
                target_matches = True
                for cond in conditions:
                    if cond.get("condition") == "this_card_is_target":
                        required_id = cond.get("required_id", "")
                        if required_id != center_mem["game_card_id"]:
                            target_matches = False
                            break
                if not target_matches:
                    continue
                reduction_amount = effect.get("amount", 0)
                baton_cost = max(0, baton_cost - reduction_amount)
        if len(cheer_ids) < baton_cost:
            self.send_event(self.make_error_event(player_id, "invalid_cheer", "Not enough cheer to pass the baton."))
            return False
        # Validate uniqueness of cheer.
        if len(set(cheer_ids)) != len(cheer_ids):
            self.send_event(self.make_error_event(player_id, "invalid_cheer", "Duplicate cheer to pass."))
            return False
        for cheer_id in cheer_ids:
            if not player.is_cheer_on_holomem(cheer_id, player.center[0]["game_card_id"]):
                self.send_event(self.make_error_event(player_id, "invalid_cheer", "Invalid cheer to pass."))
                return False

        return True
    def handle_main_step_baton_pass(self, player_id:str, action_data:dict):
        if not self.validate_main_step_baton_pass(player_id, action_data):
            return False

        player = self.get_player(player_id)
        new_center_id = action_data["card_id"]
        cheer_to_archive_ids = action_data["cheer_ids"]
        old_center_id = player.center[0]["game_card_id"]
        player.archive_attached_cards(cheer_to_archive_ids)
        player.swap_center_with_back(new_center_id)
        player.baton_pass_this_turn = True

        baton_effects = []
        old_center_card, _, _ = player.find_card(old_center_id)
        if old_center_card and "gift_effects" in old_center_card:
            baton_effects = filter_effects_at_timing(old_center_card["gift_effects"], "on_baton_to_back")
            add_ids_to_effects(baton_effects, player.player_id, old_center_id)

        continuation = self.clear_decision()
        if baton_effects:
            self.begin_resolving_effects(baton_effects, continuation)
            return True
        continuation()

        return True

    def validate_main_step_begin_performance(self, player_id:str, action_data:dict):
        if not self.validate_decision_base(player_id, action_data, DecisionType.DecisionMainStep, GameAction.MainStepBeginPerformanceFields):
            return False

        # Ensure this action is in the available actions.
        action_found = False
        for action in self.current_decision["available_actions"]:
            if action["action_type"] == GameAction.MainStepBeginPerformance:
                action_found = True
        if not action_found:
            self.send_event(self.make_error_event(player_id, "invalid_action", "Invalid action."))
            return False

        return True

    def handle_main_step_begin_performance(self, player_id:str, action_data:dict):
        if not self.validate_main_step_begin_performance(player_id, action_data):
            return False

        self.clear_decision()
        self.begin_performance_step()

        return True

    def handle_main_step_end_turn(self, player_id:str, action_data:dict):
        if not self.validate_decision_base(player_id, action_data, DecisionType.DecisionMainStep, GameAction.MainStepEndTurnFields):
            return False

        self.clear_decision()
        self.end_player_turn()

        return True

    def validate_performance_step_use_art(self, player_id:str, action_data:dict):
        if not self.validate_decision_base(player_id, action_data, DecisionType.DecisionPerformanceStep, GameAction.PerformanceStepUseArtFields):
            return False

        performer_id = action_data["performer_id"]
        art_id = action_data["art_id"]
        target_id = action_data["target_id"]

        # Validate that there is an available action that matches.
        action_found = False
        for action in self.current_decision["available_actions"]:
            if action["action_type"] == GameAction.PerformanceStepUseArt and action["performer_id"] == performer_id and action["art_id"] == art_id:
                if target_id in action["valid_targets"]:
                    action_found = True
        if not action_found:
            self.send_event(self.make_error_event(player_id, "invalid_action", "Invalid action."))
            return False

        return True

    def handle_performance_step_use_art(self, player_id:str, action_data:dict):
        if not self.validate_performance_step_use_art(player_id, action_data):
            return False

        continuation = self.clear_decision()

        performer_id = action_data["performer_id"]
        art_id = action_data["art_id"]
        target_id = action_data["target_id"]

        self.begin_perform_art(performer_id, art_id, target_id, continuation)

        return True

    def handle_performance_step_end_turn(self, player_id:str, action_data:dict):
        if not self.validate_decision_base(player_id, action_data, DecisionType.DecisionPerformanceStep, GameAction.PerformanceStepEndTurnFields):
            return False

        self.clear_decision()
        self.end_player_turn()

        return True

    def handle_performance_step_cancel(self, player_id:str, action_data:dict):
        if not self.validate_decision_base(player_id, action_data, DecisionType.DecisionPerformanceStep, GameAction.PerformanceStepCancelFields):
            return False

        self.clear_decision()
        self.continue_main_step()

        return True

    def validate_move_cheer_between_holomems(self, player_id:str, action_data:dict):
        if not self.validate_decision_base(player_id, action_data, DecisionType.DecisionEffect_MoveCheerBetweenHolomems, GameAction.EffectResolution_MoveCheerBetweenHolomemsFields):
            return False

        placements = action_data["placements"]
        # All placement cheer_ids must be unique.
        if len(set(placements.keys())) != len(placements):
            self.send_event(self.make_error_event(player_id, "invalid_cheer", "Duplicate cheer placements."))
            return False

        # Amount must match.
        if len(placements) < self.current_decision["amount_min"] or len(placements) > self.current_decision["amount_max"]:
            self.send_event(self.make_error_event(player_id, "invalid_amount", "Invalid amount of cheer to move."))
            return False

        for cheer_id, target_id in placements.items():
            if cheer_id not in self.current_decision["available_cheer"]:
                self.send_event(self.make_error_event(player_id, "invalid_cheer", "Invalid cheer to place."))
                return False
            if target_id not in self.current_decision["available_targets"]:
                self.send_event(self.make_error_event(player_id, "invalid_target", "Invalid target for cheer."))
                return False

        # If the cheer is already on that holomem, then it is invalid.
        player = self.get_player(player_id)
        for cheer_id, target_id in placements.items():
            if target_id == "archive":
                continue
            if player.is_cheer_on_holomem(cheer_id, target_id):
                self.send_event(self.make_error_event(player_id, "invalid_target", "Cheer already on target."))
                return False

        if not self.current_decision.get("multi_to", False):
            # There should only be one target.
            if len(set(placements.values())) != 1:
                self.send_event(self.make_error_event(player_id, "invalid_target", "Multiple targets chosen."))
                return False

        if "limit_one_per_member" in self.current_decision and self.current_decision["limit_one_per_member"]:
            # If any placement goes to the same holomem, it is invalid.
            if len(set(placements.values())) != len(placements):
                self.send_event(self.make_error_event(player_id, "invalid_target", "Multiple cheer to same target."))
                return False

        max_per_target = self.current_decision.get("max_per_target")
        if max_per_target is not None:
            target_counts = {}
            for cheer_id, target_id in placements.items():
                if target_id != "archive":
                    target_counts[target_id] = target_counts.get(target_id, 0) + 1
            for target_id, count in target_counts.items():
                if count > max_per_target:
                    self.send_event(self.make_error_event(player_id, "invalid_target", f"Target receives more than max_per_target ({max_per_target})."))
                    return False

        return True

    def handle_effect_resolution_move_cheer_between_holomems(self, player_id:str, action_data:dict):
        if not self.validate_move_cheer_between_holomems(player_id, action_data):
            return False

        player = self.get_player(player_id)
        placements = action_data["placements"]
        target_ids = set(placements.values())
        if len(target_ids) == 1:
            self.last_move_cheer_target = next(iter(target_ids))
        player.move_cheer_between_holomems(placements)
        # Could be opponent, so just try on them too.
        # All cards have unique ids so it should be fine.
        opponent = self.other_player(player_id)
        opponent.move_cheer_between_holomems(placements)

        continuation = self.clear_decision()
        continuation()

        return True

    def validate_choose_cards_for_effect(self, player_id:str, action_data:dict):
        if not self.validate_decision_base(player_id, action_data, DecisionType.DecisionEffect_ChooseCardsForEffect, GameAction.EffectResolution_ChooseCardsForEffectFields):
            return False

        chosen_cards = action_data["card_ids"]
        chosen_card_data = {}
        for card_id in chosen_cards:
            if card_id not in self.current_decision["cards_can_choose"]:
                self.send_event(self.make_error_event(player_id, "invalid_card", "Invalid card choice."))
                return False
            try:
                card = self.find_card(card_id)
            except Exception:
                card = None
            if not card:
                self.send_event(self.make_error_event(player_id, "invalid_card", "Chosen card is no longer available."))
                return False
            chosen_card_data[card_id] = card
        # Check the amounts against amount_min/max
        if len(chosen_cards) < self.current_decision["amount_min"] or len(chosen_cards) > self.current_decision["amount_max"]:
            self.send_event(self.make_error_event(player_id, "invalid_amount", "Invalid amount of cards chosen."))
            return False
        # Check for dupes.
        if len(set(chosen_cards)) != len(chosen_cards):
            self.send_event(self.make_error_event(player_id, "invalid_card", "Duplicate cards chosen."))
            return False

        # two_tone_color_pc: Check if different colors requirement is met
        if self.current_decision.get("requirement_different_colors", False):
            # Get all colors from chosen cards
            all_colors = set()
            for card_id in chosen_cards:
                card = chosen_card_data.get(card_id)
                all_colors.update(card["colors"])
            
            # Check if we have at least 2 different colors
            if len(all_colors) < 2:
                self.send_event(self.make_error_event(player_id, "invalid_colors", "Must choose holomems with different colors."))
                return False

        if self.current_decision.get("requirement_same_tag", False):
            if len(chosen_cards) >= 2:
                cards_data = [chosen_card_data.get(cid) for cid in chosen_cards]
                common_tags = set(cards_data[0].get("tags", []))
                for card_data in cards_data[1:]:
                    common_tags &= set(card_data.get("tags", []))
                if len(common_tags) == 0:
                    self.send_event(self.make_error_event(player_id, "invalid_tags", "Must choose holomems with a shared tag."))
                    return False

        return True

    def handle_effect_resolution_choose_cards_for_effect(self, player_id:str, action_data:dict):
        if not self.validate_choose_cards_for_effect(player_id, action_data):
            return False

        decision_info_copy = self.current_decision.copy()
        continuation = self.clear_decision()

        chosen_cards = action_data["card_ids"]
        resolution = decision_info_copy["effect_resolution"]
        resolution(decision_info_copy, player_id, chosen_cards, continuation)

        return True

    def validate_effect_resolution_make_choice(self, player_id:str, action_data:dict):
        if not self.validate_decision_base(player_id, action_data, DecisionType.DecisionChoice, GameAction.EffectResolution_MakeChoiceFields):
            return

        choice_index = action_data["choice_index"]
        if choice_index < self.current_decision["min_choice"] or choice_index > self.current_decision["max_choice"]:
            self.send_event(self.make_error_event(player_id, "invalid_choice", "Invalid choice."))
            return False

        return True

    def handle_effect_resolution_make_choice(self, player_id:str, action_data:dict):
        if not self.validate_effect_resolution_make_choice(player_id, action_data):
            return False

        choice_index = action_data["choice_index"]
        resolution_func = self.current_decision["resolution_func"]

        decision_info_copy = self.current_decision.copy()
        continuation = self.clear_decision()
        resolution_func(decision_info_copy, player_id, choice_index, continuation)

        return True

    def validate_effect_resolution_order_cards(self, player_id:str, action_data:dict):
        if not self.validate_decision_base(player_id, action_data, DecisionType.DecisionEffect_OrderCards, GameAction.EffectResolution_OrderCardsFields):
            return False

        card_ids = action_data["card_ids"]
        # Ensure length matches the decision cards and they are unique.
        if len(card_ids) != len(self.current_decision["card_ids"]) or len(set(card_ids)) != len(card_ids):
            self.send_event(self.make_error_event(player_id, "invalid_cards", "Invalid cards for ordering."))
            return False

        return True

    def handle_effect_resolution_order_cards(self, player_id:str, action_data:dict):
        if not self.validate_effect_resolution_order_cards(player_id, action_data):
            return False

        player = self.get_player(player_id)
        card_ids = action_data["card_ids"]
        to_zone = self.current_decision["to_zone"]
        bottom = self.current_decision["bottom"]

        # The cards are in the order they should be put at that location.
        # The ids needs to be reversed if they go on top
        if not bottom:
            card_ids = card_ids[::-1]

        for card_id in card_ids:
            player.move_card(card_id, to_zone, zone_card_id="", hidden_info=True, add_to_bottom=bottom)

        continuation = self.clear_decision()
        continuation()

        return True


    def handle_holomem_swap(self, decision_info_copy, performing_player_id:str, card_ids:List[str], continuation):
        card_id = card_ids[0]
        owner_id = get_owner_id_from_card_id(card_id)
        owner = self.get_player(owner_id)
        owner.swap_center_with_back(card_id)

        continuation()

    def handle_activate_holomem(self, decision_info_copy, performing_player_id:str, card_ids:List[str], continuation):
        card_id = card_ids[0]
        player = self.get_player(performing_player_id)
        card, _, _ = player.find_card(card_id)
        card["resting"] = False
        self.broadcast_event({
            "event_type": EventType.EventType_ActivateHolomem,
            "player_id": performing_player_id,
            "activated_card_id": card_id,
        })
        continuation()

    def handle_rest_holomem(self, decision_info_copy, performing_player_id:str, card_ids:List[str], continuation):
        card_id = card_ids[0]
        rest_target_player_id = decision_info_copy.get("rest_target_player_id", performing_player_id)
        target_player = self.get_player(rest_target_player_id)
        card, _, _ = target_player.find_card(card_id)
        card["resting"] = True
        self.broadcast_event({
            "event_type": EventType.EventType_RestHolomem,
            "player_id": rest_target_player_id,
            "rested_card_id": card_id,
        })
        continuation()

    def handle_free_arts_turn_effect_choice(self, decision_info_copy, performing_player_id:str, card_ids:List[str], continuation):
        card_id = card_ids[0]
        effect_player = self.get_player(performing_player_id)
        turn_effect = deepcopy(decision_info_copy["turn_effect"])
        turn_effect["target_limitation"] = "specific_member_id"
        turn_effect["target_member_id"] = card_id
        effect_player.add_turn_effect(turn_effect)
        event = {
            "event_type": EventType.EventType_AddTurnEffect,
            "effect_player_id": performing_player_id,
            "turn_effect": turn_effect,
        }
        self.broadcast_event(event)
        continuation()

    def move_back_to_collab_without_effect(self, player: PlayerState, card_id: str):
        """백스테이지 홀로멤을 콜라보 포지션으로 이동 (콜라보 효과 발동 없이)"""
        card, _, _ = player.find_and_remove_card(card_id)
        player.collab.append(card)
        # 콜라보로 취급하지 않으므로 collabed_this_turn 설정하지 않음
        # 홀로파워 생성하지 않음
        # 콜라보 효과 발동하지 않음
        
        move_event = {
            "event_type": EventType.EventType_MoveCard,
            "moving_player_id": player.player_id,
            "from": "backstage",
            "to_zone": "collab",
            "card_id": card_id,
        }
        self.broadcast_event(move_event)

    def handle_move_back_to_collab(self, decision_info_copy, performing_player_id:str, card_ids:List[str], continuation):
        card_id = card_ids[0]
        owner_id = get_owner_id_from_card_id(card_id)
        owner = self.get_player(owner_id)
        self.move_back_to_collab_without_effect(owner, card_id)

        continuation()

    def handle_add_turn_effect_for_holomem(self, decision_info_copy, performing_player_id:str, card_ids:List[str], continuation):
        effect_player = self.get_player(performing_player_id)
        holomem_target = card_ids[0]
        self.last_chosen_cards = card_ids
        self.last_chosen_holomem_id = holomem_target
        turn_effect = decision_info_copy["turn_effect"]
        if "amount_per_last_card_count" in turn_effect:
            per_amount = turn_effect.pop("amount_per_last_card_count")
            turn_effect["amount"] = per_amount * self.last_card_count
        replace_field_in_conditions(turn_effect, "required_id", holomem_target)
        if decision_info_copy.get("source_from_chosen", False):
            turn_effect["source_card_id"] = holomem_target
        effect_player.add_turn_effect(turn_effect)
        event = {
            "event_type": EventType.EventType_AddTurnEffect,
            "effect_player_id": performing_player_id,
            "turn_effect": turn_effect,
        }
        self.broadcast_event(event)
        self.broadcast_bonus_hp_updates()

        continuation()

    def handle_redirect_damage_choice(self, decision_info_copy, performing_player_id:str, card_ids:List[str], continuation):
        effect_player = self.get_player(performing_player_id)
        redirect_target_id = card_ids[0]
        redirect_target, _, _ = effect_player.find_card(redirect_target_id)
        self.take_damage_state.redirect_target = redirect_target
        self.take_damage_state.redirect_target_player = effect_player
        continuation()

    def handle_return_stacked_choose_cards(self, decision_info_copy, performing_player_id:str, card_ids:List[str], continuation):
        effect_player = self.get_player(performing_player_id)
        holomem_id = card_ids[0]
        holomem_card, _, _ = effect_player.find_card(holomem_id)
        if not holomem_card:
            continuation()
            return

        self.last_chosen_holomem_id = holomem_id
        stacked_holomems = [c for c in holomem_card.get("stacked_cards", []) if is_card_holomem(c)]
        if len(stacked_holomems) == 0:
            continuation()
            return

        amount_min = decision_info_copy.get("amount_min", decision_info_copy.get("amount_min_stacked", 1))
        amount_max = min(decision_info_copy.get("amount_max", decision_info_copy.get("amount_max_stacked", 2)), len(stacked_holomems))
        stacked_ids = ids_from_cards(stacked_holomems)

        decision_event = {
            "event_type": EventType.EventType_Decision_ChooseCards,
            "desired_response": GameAction.EffectResolution_ChooseCardsForEffect,
            "effect_player_id": performing_player_id,
            "all_card_seen": stacked_ids,
            "cards_can_choose": stacked_ids,
            "amount_min": amount_min,
            "amount_max": amount_max,
            "effect": decision_info_copy.get("effect", {}),
        }
        self.broadcast_event(decision_event)
        self.set_decision({
            "decision_type": DecisionType.DecisionEffect_ChooseCardsForEffect,
            "decision_player": performing_player_id,
            "all_card_seen": stacked_ids,
            "cards_can_choose": stacked_ids,
            "amount_min": amount_min,
            "amount_max": amount_max,
            "holomem_id": holomem_id,
            "effect": decision_info_copy.get("effect", {}),
            "effect_resolution": self.handle_return_stacked_result,
            "continuation": continuation,
        })

    def handle_return_stacked_result(self, decision_info_copy, performing_player_id:str, card_ids:List[str], continuation):
        effect_player = self.get_player(performing_player_id)
        holomem_id = decision_info_copy["holomem_id"]
        holomem_card, _, _ = effect_player.find_card(holomem_id)
        if not holomem_card:
            continuation()
            return

        returned_count = 0
        for card_id in card_ids:
            for stacked in holomem_card.get("stacked_cards", []):
                if stacked["game_card_id"] == card_id:
                    holomem_card["stacked_cards"].remove(stacked)
                    effect_player.hand.append(stacked)
                    effect_player.reset_card_stats(stacked)
                    move_event = {
                        "event_type": EventType.EventType_MoveCard,
                        "moving_player_id": performing_player_id,
                        "from": holomem_id,
                        "to_zone": "hand",
                        "zone_card_id": "",
                        "card_id": card_id,
                    }
                    self.broadcast_event(move_event)
                    returned_count += 1
                    break

        self.last_card_count = returned_count
        self.last_chosen_cards = card_ids
        self.broadcast_bonus_hp_updates()

        effect = decision_info_copy.get("effect", {})
        and_effects = effect.get("and", [])
        if and_effects:
            for chained in and_effects:
                turn_effect = chained.get("turn_effect", {})
                if "amount_per_last_card_count" in turn_effect:
                    per_amount = turn_effect.pop("amount_per_last_card_count")
                    turn_effect["amount"] = per_amount * returned_count

        continuation()

    def handle_choose_stacked_to_hand_result(self, decision_info_copy, performing_player_id:str, card_ids:List[str], continuation):
        # Store the chosen card IDs to be sent to hand when the holomem is processed as downed
        self.stacked_cards_to_hand_ids = card_ids
        continuation()

    def handle_deal_damage_to_holomem(self, decision_info_copy, performing_player_id:str, card_ids:List[str], continuation):
        effect = decision_info_copy["effect"]
        source_player = self.get_player(performing_player_id)
        source_card_id = decision_info_copy["source_card_id"]
        target_player = decision_info_copy["target_player"]
        card_ids.reverse()
        for card_id in card_ids:
            target_card, _, _ = target_player.find_card(card_id)
            self.add_deal_damage_internal_effect(
                source_player,
                target_player,
                source_card_id,
                target_card,
                effect["amount"],
                effect.get("special", False),
                effect.get("prevent_life_loss", False)
            )
        continuation()

    def handle_down_holomem(self, decision_info_copy, performing_player_id:str, card_ids:List[str], continuation):
        effect = decision_info_copy["effect"]
        source_player = self.get_player(performing_player_id)
        source_card_id = decision_info_copy["source_card_id"]
        source_card, _, _ = source_player.find_card(source_card_id)
        if not source_card:
            source_card = source_player.find_attachment(source_card_id)
        target_player = decision_info_copy["target_player"]
        target_card, _, _ = target_player.find_card(card_ids[0])
        self.down_holomem(source_player, target_player, source_card, target_card,
            effect.get("prevent_life_loss", False), continuation
        )

    def handle_restore_hp_for_holomem(self, decision_info_copy, performing_player_id:str, card_ids:List[str], continuation):
        effect_player = self.get_player(performing_player_id)
        holomem_target = card_ids[0]
        hp_to_restore = decision_info_copy["effect_amount"]
        source_card_id = decision_info_copy["source_card_id"]
        self.add_restore_holomem_hp_internal_effect(effect_player, holomem_target, source_card_id, hp_to_restore)
        continuation()

    def handle_run_single_effect(self, decision_info_copy, performing_player_id:str, card_ids:List[str], continuation):
        effect_player = self.get_player(performing_player_id)
        effect = decision_info_copy["effect_to_run"]
        effect["card_ids"] = card_ids
        # Assumption here is no conditions and no decisions after.
        self.do_effect(effect_player, effect)
        continuation()

    def handle_chose_bloom_now_choose_target(self, decision_info_copy, performing_player_id:str, card_ids:List[str], continuation):
        if len(card_ids) == 0:
            # The user decided to not do this.
            continuation()
            return

        effect_player = self.get_player(performing_player_id)
        effect = decision_info_copy["effect"]
        
        # Check if this is a bloom_from_archive effect
        if effect["effect_type"] == "bloom_from_archive":
            # Get the chosen card from archive
            chosen_card = None
            for card in effect_player.archive:
                if card["game_card_id"] == card_ids[0]:
                    chosen_card = card
                    break
            
            if not chosen_card:
                continuation()
                return
                
            # Get target holomems based on effect conditions
            target_holomems = []
            target_location = effect.get("target_location", "stage")
            if target_location == "stage":
                target_holomems = effect_player.get_holomem_on_stage()
            
            target_condition = effect.get("target_condition", "")
            if target_condition == "tag_in":
                target_tags = effect.get("target_tags", [])
                target_holomems = [holomem for holomem in target_holomems if any(tag in holomem["tags"] for tag in target_tags)]
            elif target_condition == "any_stage_holomem":
                # All stage holomems are valid targets
                pass
            elif target_condition == "bloomable_this_turn":
                # Filter to only holomems that can bloom this turn
                target_holomems = [holomem for holomem in target_holomems if effect_player.can_bloom_this_turn(holomem)]
            elif target_condition == "tag_in_bloomable_this_turn":
                # Filter to holomems that have the specified tags AND can bloom this turn
                target_tags = effect.get("target_tags", [])
                target_holomems = [holomem for holomem in target_holomems 
                                  if any(tag in holomem["tags"] for tag in target_tags) 
                                  and effect_player.can_bloom_this_turn(holomem)]
            
            # 스테이지 bloom 레벨 필터링
            stage_bloom_level = effect.get("stage_bloom_level", None)
            if stage_bloom_level is not None:
                if stage_bloom_level == "debut" or stage_bloom_level == 0:
                    # debut 홀로멤만 필터링 (bloom 레벨 1로 처리)
                    target_holomems = [holomem for holomem in target_holomems if holomem["card_type"] == "holomem_debut"]
                elif isinstance(stage_bloom_level, list):
                    # 배열인 경우: 여러 레벨 중 하나라도 포함되면 허용
                    filtered_holomems = []
                    for holomem in target_holomems:
                        accepted_levels = effect_player.get_accepted_bloom_for_card(holomem)
                        for level in stage_bloom_level:
                            if level == "debut" or level == 0:
                                if holomem["card_type"] == "holomem_debut":
                                    filtered_holomems.append(holomem)
                                    break
                            elif level in accepted_levels:
                                filtered_holomems.append(holomem)
                                break
                    target_holomems = filtered_holomems
                else:
                    # 단일 레벨인 경우
                    if stage_bloom_level == "debut" or stage_bloom_level == 0:
                        target_holomems = [holomem for holomem in target_holomems if holomem["card_type"] == "holomem_debut"]
                    else:
                        target_holomems = [holomem for holomem in target_holomems 
                                         if stage_bloom_level in effect_player.get_accepted_bloom_for_card(holomem)]
                
            # Find out which of these are relevant for chosen card.
            valid_targets = []
            for card in target_holomems:
                if effect_player.can_bloom_with_card(card, chosen_card):
                    valid_targets.append(card)

            # Even if there is only one target, still give the user the chance to cancel.
            decision_event = {
                "event_type": EventType.EventType_Decision_ChooseHolomemForEffect,
                "desired_response": GameAction.EffectResolution_ChooseCardsForEffect,
                "effect_player_id": effect_player.player_id,
                "cards_can_choose": ids_from_cards(valid_targets),
                "effect": effect,
            }
            self.broadcast_event(decision_event)
            self.set_decision({
                "decision_type": DecisionType.DecisionEffect_ChooseCardsForEffect,
                "decision_player": performing_player_id,
                "all_card_seen": ids_from_cards(valid_targets),
                "cards_can_choose": ids_from_cards(valid_targets),
                "amount_min": 0,
                "amount_max": 1,
                "bloom_card_id": card_ids[0],
                "effect_resolution": self.handle_bloom_into_target,
                "continuation": continuation,
            })
        elif effect["effect_type"] == "bloom_from_stacked":
            source_card, _, _ = effect_player.find_card(effect["source_card_id"])
            chosen_card = None
            if source_card:
                for card in source_card["stacked_cards"]:
                    if card["game_card_id"] == card_ids[0]:
                        chosen_card = card
                        break

            if not chosen_card:
                continuation()
                return

            target_member_names = effect.get("target_member_names", [])
            target_holomems = effect_player.get_holomem_on_stage()
            target_holomems = [h for h in target_holomems if h["game_card_id"] != effect["source_card_id"]]
            if target_member_names:
                target_holomems = [h for h in target_holomems if any(name in h["card_names"] for name in target_member_names)]
            target_holomems = [h for h in target_holomems if not h.get("played_this_turn", False)]
            target_holomems = [h for h in target_holomems if not h.get("bloomed_this_turn", False)]

            valid_targets = []
            for card in target_holomems:
                if effect_player.can_bloom_with_card(card, chosen_card):
                    valid_targets.append(card)

            decision_event = {
                "event_type": EventType.EventType_Decision_ChooseHolomemForEffect,
                "desired_response": GameAction.EffectResolution_ChooseCardsForEffect,
                "effect_player_id": effect_player.player_id,
                "cards_can_choose": ids_from_cards(valid_targets),
                "effect": effect,
            }
            self.broadcast_event(decision_event)
            self.set_decision({
                "decision_type": DecisionType.DecisionEffect_ChooseCardsForEffect,
                "decision_player": performing_player_id,
                "all_card_seen": ids_from_cards(valid_targets),
                "cards_can_choose": ids_from_cards(valid_targets),
                "amount_min": 0,
                "amount_max": 1,
                "bloom_card_id": card_ids[0],
                "effect": effect,
                "effect_resolution": self.handle_bloom_into_target,
                "continuation": continuation,
            })
        else:
            # Original logic for hand-based bloom
            chosen_card = effect_player.get_card_from_hand(card_ids[0])
            target_cards = decision_info_copy.get("target_cards", [])
            # Find out which of these are relevant for chosen card.
            valid_targets = []

            for card in target_cards:
                if effect_player.can_bloom_with_card(card, chosen_card):
                    valid_targets.append(card)

            # Even if there is only one target, still give the user the chance to cancel.
            decision_event = {
                "event_type": EventType.EventType_Decision_ChooseHolomemForEffect,
                "desired_response": GameAction.EffectResolution_ChooseCardsForEffect,
                "effect_player_id": effect_player.player_id,
                "cards_can_choose": ids_from_cards(valid_targets),
                "effect": effect,
            }
            self.broadcast_event(decision_event)
            self.set_decision({
                "decision_type": DecisionType.DecisionEffect_ChooseCardsForEffect,
                "decision_player": performing_player_id,
                "all_card_seen": ids_from_cards(valid_targets),
                "cards_can_choose": ids_from_cards(valid_targets),
                "amount_min": 0,
                "amount_max": 1,
                "bloom_card_id": card_ids[0],
                "effect_resolution": self.handle_bloom_into_target,
                "continuation": continuation,
            })

    def handle_bloom_into_target(self, decision_info_copy, performing_player_id:str, card_ids:List[str], continuation):
        if len(card_ids) == 0:
            # The user decided to not do this.
            continuation()
            return
        effect_player = self.get_player(performing_player_id)
        bloom_card_id = decision_info_copy["bloom_card_id"]
        
        # 블룸 출처 설정 (오시 스킬로부터 온 경우 스킬 ID 저장)
        if "effect" in decision_info_copy:
            self.last_bloom_source_skill_id = decision_info_copy["effect"].get("source_skill_id", "")
        else:
            self.last_bloom_source_skill_id = ""

        effect_player.bloom(bloom_card_id, card_ids[0], continuation)

    def handle_return_holomem_to_debut(self, decision_info_copy, performing_player_id:str, card_ids:List[str], continuation):
        chosen_card = self.find_card(card_ids[0])
        owner_player = self.get_player(chosen_card["owner_id"])
        self.return_holomem_to_debut(owner_player, card_ids[0])
        continuation()

    def return_holomem_to_debut(self, effect_player : PlayerState, card_id):
        card, _, _ = effect_player.find_card(card_id)
        stacked_cards = card["stacked_cards"].copy()
        attached_support = card["attached_support"].copy()
        debut = None
        for stacked_card in stacked_cards:
            if stacked_card["card_type"] == "holomem_debut":
                debut = stacked_card
                break
        if not debut:
            # No debut = no effect
            return

        # Restore the damage.
        current_damage = card["damage"]
        effect_player.restore_holomem_hp(card_id, current_damage)
        # Return all stacked and attached to hand.
        for attached_card in attached_support:
            effect_player.move_card(attached_card["game_card_id"], "hand")
        for stacked_card in stacked_cards:
            effect_player.move_card(stacked_card["game_card_id"], "hand")
        # Use player.bloom() in order to "bloom" the debut over this card.
        # This will keep all the cheer in place conveniently.
        if debut["game_card_id"] != card_id:
            effect_player.bloom(debut["game_card_id"], card_id, lambda :
                # Finally, move the debut card back to original target card back to hand
                # since it got stacked as part of the bloom.
                effect_player.move_card(card_id, "hand")
            )

    def handle_choose_cards_result(self, decision_info_copy, performing_player_id:str, card_ids:List[str], continuation):
        from_zone = decision_info_copy["from_zone"]
        to_zone = decision_info_copy["to_zone"]
        reveal_chosen = decision_info_copy["reveal_chosen"]
        # Archive is a public zone - always reveal cards moved from/to archive
        if to_zone == "archive" or from_zone == "archive":
            reveal_chosen = True
        remaining_cards_action = decision_info_copy["remaining_cards_action"]
        all_card_seen = decision_info_copy["all_card_seen"]
        source_card_id = decision_info_copy["source_card_id"]
        player = self.get_player(performing_player_id)

        valid_card_ids = []
        for card_id in card_ids:
            card, _, _ = player.find_card(card_id, include_stacked_cards=True)
            if card:
                valid_card_ids.append(card_id)
            else:
                logger.warning(
                    "Skipping missing chosen card during resolve player_id=%s card_id=%s from_zone=%s to_zone=%s",
                    performing_player_id,
                    card_id,
                    from_zone,
                    to_zone,
                )
        card_ids = valid_card_ids
        remaining_card_ids = [card_id for card_id in all_card_seen if card_id not in card_ids]

        self.last_chosen_cards = card_ids
        self.last_card_count = len(card_ids)
        if len(card_ids) > 0 and "after_choose_effect" in decision_info_copy and decision_info_copy["after_choose_effect"]:
            # Queue this effect.
            after_effects = [decision_info_copy["after_choose_effect"].copy()]
            add_ids_to_effects(after_effects, performing_player_id, source_card_id)
            self.add_effects_to_front(after_effects)

        # Deal with chosen cards.
        if to_zone == "holomem" and len(card_ids) > 0:
            to_limitation = decision_info_copy.get("to_limitation", "")
            to_limitation_colors = decision_info_copy.get("to_limitation_colors", [])
            to_limitation_tags = decision_info_copy.get("to_limitation_tags", [])
            to_limitation_name = decision_info_copy.get("to_limitation_name", "")
            attach_each_separately = decision_info_copy.get("attach_each_separately", False)
            to_exclude_performer = decision_info_copy.get("to_exclude_performer", False)
            exclude_card_id = source_card_id if to_exclude_performer else ""

            if attach_each_separately and len(card_ids) > 1:
                # Attach each card separately to potentially different holomems
                def attach_cards_sequentially(remaining_cards_to_attach):
                    if len(remaining_cards_to_attach) == 0:
                        self.choose_cards_cleanup_remaining(performing_player_id, remaining_card_ids, remaining_cards_action, from_zone, from_zone, continuation)
                        return
                    current_card_id = remaining_cards_to_attach[0]
                    next_cards = remaining_cards_to_attach[1:]
                    attach_effect = {
                        "effect_type": EffectType.EffectType_AttachCardToHolomem,
                        "source_card_id": current_card_id,
                        "to_limitation": to_limitation,
                        "to_limitation_colors": to_limitation_colors,
                        "to_limitation_tags": to_limitation_tags,
                        "to_limitation_name": to_limitation_name,
                        "exclude_card_id": exclude_card_id,
                        "attach_to_card_id": source_card_id,
                        "continuation": lambda nc=next_cards: attach_cards_sequentially(nc),
                    }
                    self.do_effect(player, attach_effect)
                attach_cards_sequentially(card_ids)
            else:
                # Original behavior: attach single card
                attach_effect = {
                    "effect_type": EffectType.EffectType_AttachCardToHolomem,
                    "source_card_id": card_ids[0],
                    "to_limitation": to_limitation,
                    "to_limitation_colors": to_limitation_colors,
                    "to_limitation_tags": to_limitation_tags,
                    "to_limitation_name": to_limitation_name,
                    "exclude_card_id": exclude_card_id,
                    "attach_to_card_id": source_card_id,
                    "continuation": lambda :
                        # Finish the cleanup of the remaining cards.
                        self.choose_cards_cleanup_remaining(performing_player_id, remaining_card_ids, remaining_cards_action, from_zone, from_zone, continuation),
                }
                self.do_effect(player, attach_effect)
        elif from_zone == "stage" and to_zone == "stage":
            # Special handling for stage selection (two_tone_color_pc)
            # Store the selected stage holomems for later use in deck searches
            self.stage_selected_holomems = card_ids.copy()
            # Don't move cards, just select them and continue with remaining cards cleanup
            self.choose_cards_cleanup_remaining(performing_player_id, remaining_card_ids, remaining_cards_action, from_zone, from_zone, continuation)
        elif to_zone in ["backstage", "stage"]:
            # Determine possible options (backstage, center, collab) depending on what's open.
            if len(card_ids) == 0:
                self.choose_cards_cleanup_remaining(performing_player_id, remaining_card_ids, remaining_cards_action, from_zone, from_zone, continuation)
            else:
                choice = [
                ]
                choice.append({
                    "effect_type": EffectType.EffectType_PlaceHolomem,
                    "player_id": performing_player_id,
                    "source_card_id": "",
                    "location": "backstage",
                    "card_id": card_ids[0],
                })
                if to_zone == "stage":
                    if len(player.center) == 0:
                        choice.append({
                            "effect_type": EffectType.EffectType_PlaceHolomem,
                            "player_id": performing_player_id,
                            "source_card_id": "",
                            "location": "center",
                            "card_id": card_ids[0],
                        })
                    if len(player.collab) == 0:
                        choice.append({
                            "effect_type": EffectType.EffectType_PlaceHolomem,
                            "player_id": performing_player_id,
                            "source_card_id": "",
                            "location": "collab",
                            "card_id": card_ids[0],
                        })

                if len(choice) == 1:
                    # Must be backstage.
                    to_zone = "backstage"
                    for card_id in card_ids:
                        player.move_card(card_id, to_zone, zone_card_id="", hidden_info=not reveal_chosen)
                    self.choose_cards_cleanup_remaining(performing_player_id, remaining_card_ids, remaining_cards_action, from_zone, from_zone, continuation)
                else:
                    decision_event = {
                        "event_type": EventType.EventType_Decision_Choice,
                        "desired_response": GameAction.EffectResolution_MakeChoice,
                        "effect_player_id": player.player_id,
                        "choice": choice,
                        "min_choice": 0,
                        "max_choice": len(choice) - 1,
                    }
                    self.broadcast_event(decision_event)
                    self.set_decision({
                        "decision_type": DecisionType.DecisionChoice,
                        "decision_player": player.player_id,
                        "choice": choice,
                        "min_choice": 0,
                        "max_choice": len(choice) - 1,
                        "resolution_func": self.handle_choice_effects,
                        "continuation": lambda :
                            self.choose_cards_cleanup_remaining(performing_player_id, remaining_card_ids, remaining_cards_action, from_zone, from_zone, continuation)
                    })
        elif to_zone == "bottom_of_deck":
            stage_zones = {"center", "collab", "backstage"}
            returned_holomem_cards = []
            include_stacked = decision_info_copy.get("include_stacked_holomems", False)
            order_chosen = decision_info_copy.get("order_chosen", False)
            cards_for_ordering = []

            for card_id in card_ids:
                card_data, _, _ = player.find_card(card_id)
                stacked_holomems_extracted = []

                if include_stacked and card_data and is_card_holomem(card_data):
                    stacked_holomems_extracted = [c for c in card_data.get("stacked_cards", []) if is_card_holomem(c)]
                    card_data["stacked_cards"] = [c for c in card_data.get("stacked_cards", []) if not is_card_holomem(c)]

                if card_data and from_zone in stage_zones and is_card_holomem(card_data):
                    returned_holomem_cards.append(card_data)

                player.move_card(card_id, "deck", hidden_info=not reveal_chosen, add_to_bottom=True)
                cards_for_ordering.append(card_id)

                for sh in stacked_holomems_extracted:
                    self.floating_cards.append(sh)
                    cards_for_ordering.append(sh["game_card_id"])

            def after_return_timing():
                if (include_stacked or order_chosen) and len(cards_for_ordering) > 1:
                    order_cards_event = {
                        "event_type": EventType.EventType_Decision_OrderCards,
                        "desired_response": GameAction.EffectResolution_OrderCards,
                        "effect_player_id": performing_player_id,
                        "card_ids": cards_for_ordering,
                        "from": from_zone,
                        "to_zone": "deck",
                        "bottom": True,
                        "hidden_info_player": performing_player_id,
                        "hidden_info_fields": ["card_ids"],
                    }
                    self.broadcast_event(order_cards_event)
                    self.set_decision({
                        "decision_type": DecisionType.DecisionEffect_OrderCards,
                        "decision_player": performing_player_id,
                        "card_ids": cards_for_ordering,
                        "from": from_zone,
                        "to_zone": "deck",
                        "bottom": True,
                        "resolution_func": self.handle_effect_resolution_order_cards,
                        "continuation": lambda:
                            self.choose_cards_cleanup_remaining(performing_player_id, remaining_card_ids, remaining_cards_action, from_zone, from_zone, continuation),
                    })
                else:
                    self.choose_cards_cleanup_remaining(performing_player_id, remaining_card_ids, remaining_cards_action, from_zone, from_zone, continuation)

            if returned_holomem_cards:
                def fire_return_timing(remaining_cards, final_continuation):
                    if not remaining_cards:
                        final_continuation()
                        return
                    returned_card = remaining_cards[0]
                    self.returned_to_deck_card = returned_card
                    timing_effects = player.get_effects_at_timing("on_holomem_return_to_deck", returned_card)
                    def after_timing():
                        self.returned_to_deck_card = None
                        fire_return_timing(remaining_cards[1:], final_continuation)
                    self.begin_resolving_effects(timing_effects, after_timing)

                fire_return_timing(returned_holomem_cards, after_return_timing)
            else:
                after_return_timing()
        elif to_zone == "cheer_deck_bottom":
            for card_id in card_ids:
                player.move_card(card_id, "cheer_deck", hidden_info=not reveal_chosen, add_to_bottom=True)
            self.choose_cards_cleanup_remaining(performing_player_id, remaining_card_ids, remaining_cards_action, from_zone, from_zone, continuation)
        else:
            for card_id in card_ids:
                player.move_card(card_id, to_zone, zone_card_id="", hidden_info=not reveal_chosen)
            if to_zone == "deck":
                player.shuffle_deck()
            self.choose_cards_cleanup_remaining(performing_player_id, remaining_card_ids, remaining_cards_action, from_zone, from_zone, continuation)

    def choose_cards_cleanup_remaining(self, performing_player_id, remaining_card_ids, remaining_cards_action, from_zone, to_zone, continuation):
        player = self.get_player(performing_player_id)
        # Deal with unchosen cards.
        if remaining_card_ids:
            match remaining_cards_action:
                case "nothing":
                    pass
                case "archive":
                    for card_id in remaining_card_ids:
                        player.move_card(card_id, "archive")
                case "shuffle":
                    if from_zone == "deck":
                        player.shuffle_deck()
                    elif from_zone == "cheer_deck":
                        player.shuffle_cheer_deck()
                    elif from_zone == "holopower":
                        self.shuffle_list(player.holopower)
                    else:
                        raise NotImplementedError(f"Unimplemented shuffle zone action: {from_zone}")
                case "order_on_bottom" | "order_on_top":
                    bottom = remaining_cards_action == "order_on_bottom"
                    order_cards_event = {
                        "event_type": EventType.EventType_Decision_OrderCards,
                        "desired_response": GameAction.EffectResolution_OrderCards,
                        "effect_player_id": performing_player_id,
                        "card_ids": remaining_card_ids,
                        "from": from_zone,
                        "to_zone": to_zone,
                        "bottom": bottom,
                        "hidden_info_player": performing_player_id,
                        "hidden_info_fields": ["card_ids"],
                    }
                    self.broadcast_event(order_cards_event)
                    self.set_decision({
                        "decision_type": DecisionType.DecisionEffect_OrderCards,
                        "decision_player": performing_player_id,
                        "card_ids": remaining_card_ids,
                        "from": from_zone,
                        "to_zone": to_zone,
                        "bottom": bottom,
                        "continuation": continuation,
                    })
                case "remove_choice_from_last_revealed_cards":
                    # Update the list of revealed cards from the remaining_card_ids
                    last_revealed_cards = []
                    for card_id in remaining_card_ids:
                        card = self.find_card(card_id)
                        if card:
                            last_revealed_cards.append(card)
                    player.last_revealed_cards = last_revealed_cards
                case _:
                    raise NotImplementedError(f"Unimplemented remaining cards action: {remaining_cards_action}")

        if not self.current_decision:
            continuation()

    def handle_choice_return_collab(self, decision_info_copy, player_id, choice_index, continuation):
        # 0 is pass, 1 is okay
        if choice_index == 1:
            player = self.get_player(player_id)
            player.return_collab()

        continuation()

    def handle_force_die_result(self, decision_info_copy, player_id, choice_index, continuation):
        # 0-5 is die result 1-6
        player = self.get_player(player_id)
        player.set_next_die_roll = choice_index + 1
        continuation()

    def handle_choice_effects(self, decision_info_copy, player_id, choice_index, continuation):
        if decision_info_copy.get("simultaneous_resolution", False):
            self.effect_resolution_state.simultaneous_choice_index = choice_index
            continuation()
        else:
            chosen_effect = decision_info_copy["choice"][choice_index]
            self.begin_resolving_effects([chosen_effect], continuation)

    def handle_player_resign(self, player_id):
        self.end_game(player_id, GameOverReason.GameOverReason_Resign)

        return True

    def handle_emote(self, player_id: str, emote_id: int):
        """감정표현 이벤트 생성 - 모든 플레이어에게 동일한 이벤트 전송"""
        emote_event = {
            "event_type": EventType.EventType_Emote,
            "event_player_id": player_id,
            "emote_id": emote_id,
            "timestamp": time.time() * 1000,
            "event_number": len(self.all_events),
            "last_game_message_number": len(self.all_game_messages) - 1,
        }
        self.all_events.append(emote_event)
        self.latest_events.append(emote_event)
        self.latest_observer_events.append(emote_event)

    def handle_power_boost(self, amount: int, source_card_id: str):
        if amount != 0:
            self.performance_artstatboosts.power += amount
            self.send_boost_event(self.performance_performer_card["game_card_id"], source_card_id, "power", amount, for_art=True)

    def holomem_can_be_attached_with_support_card(self, holomem, support_card) -> bool:
        sub_type = support_card.get("sub_type")
        match sub_type:
            case "mascot":
                mascot_count_limit = holomem.get("mascot_count_limit", 1)
                attached_mascots = get_cards_of_sub_type_from_holomems("mascot", [holomem])
                match holomem.get("mascot_count_requirement"):
                    case "unique_name":
                        # Fail if the support card's name is already present in the attached supports
                        if any([not set(mascot["card_names"]).isdisjoint(set(support_card["card_names"])) for mascot in attached_mascots]):
                            return False
                return len(attached_mascots) < mascot_count_limit
            case "tool":
                return all([card.get("sub_type") != sub_type for card in holomem["attached_support"]])

        return True # not a support card or support card sub-type has no restrictions

    def card_has_available_target_to_attach_to(self, player: PlayerState, card) -> bool:
        sub_type = card.get("sub_type")
        if sub_type not in ["mascot", "tool"]:
            return True

        for holomem in player.get_holomem_on_stage():
            if self.holomem_can_be_attached_with_support_card(holomem, card):
                return True
        return False

    def handle_repeat_damage_selection(self, effect_player_id, effect, target_cards, targets_allowed, repeat_count, target_player, source_player):
        # Start the first iteration of repeat damage selection
        self.handle_repeat_damage_target(effect_player_id, effect, target_cards, targets_allowed, repeat_count, target_player, source_player, 1)

    def handle_repeat_damage_target(self, effect_player_id, effect, target_cards, targets_allowed, repeat_count, target_player, source_player, current_repeat):
        # Filter out cards that are already at max damage
        available_targets = [card for card in target_cards if card["damage"] < target_player.get_card_hp(card)]
        
        if len(available_targets) == 0 or current_repeat > repeat_count:
            # No more targets or all repeats done
            self.continue_resolving_effects()
            return

        # Player chooses target for this iteration
        target_options = ids_from_cards(available_targets)
        decision_event = {
            "event_type": EventType.EventType_Decision_ChooseHolomemForEffect,
            "desired_response": GameAction.EffectResolution_ChooseCardsForEffect,
            "effect_player_id": effect_player_id,
            "cards_can_choose": target_options,
            "amount_min": targets_allowed,
            "amount_max": targets_allowed,
            "effect": effect,
        }
        self.broadcast_event(decision_event)
        self.set_decision({
            "decision_type": DecisionType.DecisionEffect_ChooseCardsForEffect,
            "decision_player": effect_player_id,
            "all_card_seen": target_options,
            "cards_can_choose": target_options,
            "amount_min": targets_allowed,
            "amount_max": targets_allowed,
            "effect_resolution": self.handle_repeat_damage_target_selection,
            "effect": effect,
            "source_card_id": effect["source_card_id"],
            "target_player": target_player,
            "source_player": source_player,
            "target_cards": target_cards,
            "targets_allowed": targets_allowed,
            "repeat_count": repeat_count,
            "current_repeat": current_repeat,
            "continuation": self.continue_resolving_effects,
        })

    def handle_repeat_damage_target_selection(self, decision_info_copy, performing_player_id:str, card_ids:List[str], continuation):
        # Apply damage for this iteration
        effect = decision_info_copy["effect"]
        source_player = decision_info_copy["source_player"]
        target_player = decision_info_copy["target_player"]
        source_card_id = decision_info_copy["source_card_id"]
        current_repeat = decision_info_copy["current_repeat"]
        repeat_count = decision_info_copy["repeat_count"]
        target_cards = decision_info_copy["target_cards"]
        targets_allowed = decision_info_copy["targets_allowed"]

        # Apply damage to selected targets
        card_ids.reverse()
        for card_id in card_ids:
            target_card, _, _ = target_player.find_card(card_id)
            self.add_deal_damage_internal_effect(
                source_player,
                target_player,
                source_card_id,
                target_card,
                effect["amount"],
                effect.get("special", False),
                effect.get("prevent_life_loss", False)
            )

        # Continue to next iteration or finish
        if current_repeat < repeat_count:
            # Continue to next repeat
            self.handle_repeat_damage_target(
                performing_player_id, 
                effect, 
                target_cards, 
                targets_allowed, 
                repeat_count, 
                target_player, 
                source_player, 
                current_repeat + 1
            )
        else:
            # All repeats done
            self.continue_resolving_effects()

    def handle_accumulated_damage_selection(self, effect_player_id, effect, target_cards, repeat_count, 
                                            target_player, source_player, amount, special, prevent_life_loss, allow_pass):
        """누적 대미지 선택 시작: repeat_count번 선택 후 합산하여 대미지 적용"""
        # 선택된 타겟을 저장할 리스트 초기화
        self.handle_accumulated_damage_target(
            effect_player_id, effect, target_cards, repeat_count, 
            target_player, source_player, amount, special, prevent_life_loss, allow_pass,
            current_selection=1, selected_targets=[]
        )

    def handle_accumulated_damage_target(self, effect_player_id, effect, target_cards, repeat_count,
                                         target_player, source_player, amount, special, prevent_life_loss, allow_pass,
                                         current_selection, selected_targets):
        """누적 대미지: 각 선택 처리"""
        # 대미지가 이미 HP를 초과한 카드는 제외
        available_targets = [card for card in target_cards if card["damage"] < target_player.get_card_hp(card)]
        
        if len(available_targets) == 0 or current_selection > repeat_count:
            # 타겟이 없거나 모든 선택 완료 - 대미지 적용 단계로
            self.handle_accumulated_damage_apply(
                effect_player_id, effect, target_player, source_player, 
                amount, special, prevent_life_loss, selected_targets
            )
            return

        target_options = ids_from_cards(available_targets)
        amount_min = 0 if allow_pass else 1
        amount_max = 1
        
        decision_event = {
            "event_type": EventType.EventType_Decision_ChooseHolomemForEffect,
            "desired_response": GameAction.EffectResolution_ChooseCardsForEffect,
            "effect_player_id": effect_player_id,
            "cards_can_choose": target_options,
            "amount_min": amount_min,
            "amount_max": amount_max,
            "effect": effect,
            "accumulated_selection": current_selection,
            "accumulated_total": repeat_count,
        }
        self.broadcast_event(decision_event)
        self.set_decision({
            "decision_type": DecisionType.DecisionEffect_ChooseCardsForEffect,
            "decision_player": effect_player_id,
            "all_card_seen": target_options,
            "cards_can_choose": target_options,
            "amount_min": amount_min,
            "amount_max": amount_max,
            "effect_resolution": self.handle_accumulated_damage_target_selection,
            "effect": effect,
            "source_card_id": effect["source_card_id"],
            "target_player": target_player,
            "source_player": source_player,
            "target_cards": target_cards,
            "repeat_count": repeat_count,
            "current_selection": current_selection,
            "selected_targets": selected_targets,
            "amount": amount,
            "special": special,
            "prevent_life_loss": prevent_life_loss,
            "allow_pass": allow_pass,
            "continuation": self.continue_resolving_effects,
        })

    def handle_accumulated_damage_target_selection(self, decision_info_copy, performing_player_id: str, card_ids: List[str], continuation):
        """누적 대미지: 선택 결과 처리"""
        effect = decision_info_copy["effect"]
        source_player = decision_info_copy["source_player"]
        target_player = decision_info_copy["target_player"]
        current_selection = decision_info_copy["current_selection"]
        repeat_count = decision_info_copy["repeat_count"]
        target_cards = decision_info_copy["target_cards"]
        selected_targets = decision_info_copy["selected_targets"].copy()
        amount = decision_info_copy["amount"]
        special = decision_info_copy["special"]
        prevent_life_loss = decision_info_copy["prevent_life_loss"]
        allow_pass = decision_info_copy["allow_pass"]

        # 선택된 카드 추가 (pass한 경우 빈 리스트)
        for card_id in card_ids:
            selected_targets.append(card_id)

        # 다음 선택으로 진행 또는 대미지 적용
        if current_selection < repeat_count:
            self.handle_accumulated_damage_target(
                performing_player_id, effect, target_cards, repeat_count,
                target_player, source_player, amount, special, prevent_life_loss, allow_pass,
                current_selection + 1, selected_targets
            )
        else:
            # 모든 선택 완료 - 대미지 적용
            self.handle_accumulated_damage_apply(
                performing_player_id, effect, target_player, source_player,
                amount, special, prevent_life_loss, selected_targets
            )

    def handle_accumulated_damage_apply(self, effect_player_id, effect, target_player, source_player,
                                        amount, special, prevent_life_loss, selected_targets):
        """누적 대미지: 선택 결과 집계 및 대미지 적용"""
        if len(selected_targets) == 0:
            # 선택된 타겟이 없으면 종료
            self.continue_resolving_effects()
            return

        # 타겟별 선택 횟수 집계
        target_counts = {}
        for card_id in selected_targets:
            target_counts[card_id] = target_counts.get(card_id, 0) + 1

        # 타겟별 총 대미지 계산 및 이벤트 데이터 구성
        damage_targets = []
        for card_id, count in target_counts.items():
            total_damage = amount * count
            target_card, _, _ = target_player.find_card(card_id)
            if target_card:
                damage_targets.append({
                    "card_id": card_id,
                    "definition_id": target_card.get("card_id", card_id),
                    "count": count,
                    "total_damage": total_damage,
                })

        # 선택 결과 공개 이벤트 브로드캐스트
        accumulated_event = {
            "event_type": EventType.EventType_AccumulatedDamageTargets,
            "effect_player_id": effect_player_id,
            "target_player_id": target_player.player_id,
            "damage_targets": damage_targets,
            "base_damage": amount,
        }
        self.broadcast_event(accumulated_event)

        # 각 타겟에게 합산된 대미지 적용
        for target_info in damage_targets:
            target_card, _, _ = target_player.find_card(target_info["card_id"])
            if target_card:
                self.add_deal_damage_internal_effect(
                    source_player,
                    target_player,
                    effect["source_card_id"],
                    target_card,
                    target_info["total_damage"],
                    special,
                    prevent_life_loss
                )

        self.continue_resolving_effects()
