from __future__ import annotations
from typing import List, TYPE_CHECKING
from copy import deepcopy
import logging

from app.engine.constants import *
from app.engine.models import *
from app.engine.helpers import *

if TYPE_CHECKING:
    from app.engine.player_state import PlayerState

logger = logging.getLogger(__name__)


class TurnMixin:
    def begin_player_turn(self, switch_active_player : bool):
        if switch_active_player:
            self.switch_active_player()
        self.phase = GamePhase.PlayerTurn
        active_player = self.get_player(self.active_player_id)

        # Send a start turn event.
        self.turn_number += 1
        start_event = {
            "event_type": EventType.EventType_TurnStart,
            "active_player": self.active_player_id,
            "turn_count": self.turn_number,
        }
        self.broadcast_event(start_event)

        # Reset Step
        if not active_player.first_turn:
            # 1. Activate resting cards.
            activated_cards = active_player.active_resting_cards()
            activation_event = {
                "event_type": EventType.EventType_ResetStepActivate,
                "active_player": self.active_player_id,
                "activated_card_ids": activated_cards,
            }
            self.broadcast_event(activation_event)

            # 2. Move and rest collab.
            rested_cards, moved_backstage_cards = active_player.reset_collab()
            reset_collab_event = {
                "event_type": EventType.EventType_ResetStepCollab,
                "active_player": self.active_player_id,
                "rested_card_ids": rested_cards,
                "moved_backstage_ids": moved_backstage_cards,
            }
            self.broadcast_event(reset_collab_event)
            self.broadcast_bonus_hp_updates()

            # 3. If Center is empty, select a non-resting backstage to be center.
            # If all are resting, select a resting one.
            self.reset_step_replace_center(self.continue_begin_turn)
        else:
            self.continue_begin_turn()

    def reset_step_replace_center(self, continuation):
        active_player = self.get_player(self.active_player_id)
        if not active_player.center:
            new_center_option_ids = []
            for card in active_player.backstage:
                if not is_card_resting(card):
                    new_center_option_ids.append(card["game_card_id"])
            if not new_center_option_ids:
                new_center_option_ids = ids_from_cards(active_player.backstage)

            if len(new_center_option_ids) == 1:
                # No decision to be made.
                new_center_id = new_center_option_ids[0]
                active_player.move_card(new_center_id, "center")
                continuation()
            else:
                decision_event = {
                    "event_type": EventType.EventType_ResetStepChooseNewCenter,
                    "desired_response": GameAction.ChooseNewCenter,
                    "active_player": self.active_player_id,
                    "center_options": new_center_option_ids,
                }
                self.broadcast_event(decision_event)
                self.set_decision({
                    "decision_type": DecisionType.DecisionChooseNewCenter,
                    "decision_player": self.active_player_id,
                    "options": new_center_option_ids,
                    "continuation": continuation,
                })
        else:
            continuation()

    def continue_begin_turn(self):
        # The Reset Step is over.

        ## Draw Step - draw a card, game over if you have none.
        active_player = self.get_player(self.active_player_id)
        if len(active_player.deck) == 0:
            # Game over, no cards to draw.
            self.end_game(loser_id=active_player.player_id, reason_id=GameOverReason.GameOverReason_DeckEmptyDraw)
            return

        active_player.draw(1)

        ## Cheer Step
        # Get the top cheer card id and send a decision.
        # Any holomem in center/collab/backstage can be the target.
        if len(active_player.cheer_deck) > 0:
            top_cheer_card_id = active_player.cheer_deck[0]["game_card_id"]
            target_options = ids_from_cards(active_player.center + active_player.collab + active_player.backstage)

            decision_event = {
                "event_type": EventType.EventType_CheerStep,
                "desired_response": GameAction.PlaceCheer,
                "active_player": self.active_player_id,
                "cheer_to_place": [top_cheer_card_id],
                "source": "cheer_deck",
                "options": target_options,
            }
            self.broadcast_event(decision_event)
            self.set_decision({
                "decision_type": DecisionType.DecisionPlaceCheer,
                "decision_player": self.active_player_id,
                "cheer_to_place": [top_cheer_card_id],
                "options": target_options,
                "continuation": self.begin_main_step,
            })
        else:
            # No cheer left!
            self.begin_main_step()

    def get_available_mainstep_actions(self):
        active_player = self.get_player(self.active_player_id)

        # Determine available actions.
        available_actions = []

        # A. Place debut/spot cards.
        on_stage_mems = active_player.get_holomem_on_stage()
        if len(on_stage_mems) < MAX_MEMBERS_ON_STAGE:
            for card in active_player.hand:
                if card["card_type"] in ["holomem_debut", "holomem_spot"]:
                    available_actions.append({
                        "action_type": GameAction.MainStepPlaceHolomem,
                        "card_id": card["game_card_id"]
                    })

        # B. Bloom
        if not active_player.first_turn:
            for mem_card in on_stage_mems:
                if mem_card["played_this_turn"]:
                    # Can't bloom if played this turn.
                    continue
                if mem_card["bloomed_this_turn"]:
                    # Can't bloom if already bloomed this turn.
                    continue

                accepted_bloom_levels = active_player.get_accepted_bloom_for_card(mem_card)
                if accepted_bloom_levels:
                    for card in active_player.hand:
                        if "bloom_blocked" in card and card["bloom_blocked"]:
                            continue
                        if card["card_type"] == "holomem_bloom" and card["bloom_level"] in accepted_bloom_levels:
                            # Check the names of the bloom card, at last one must match a name from the base card.
                            if any(name in card["card_names"] for name in mem_card["card_names"]):
                                # Check the damage, if the bloom version would die, you can't.
                                if mem_card["damage"] < active_player.get_card_hp(card):
                                    available_actions.append({
                                        "action_type": GameAction.MainStepBloom,
                                        "card_id": card["game_card_id"],
                                        "target_id": mem_card["game_card_id"],
                                    })

        # C. Collab
        # Can't have collabed this turn.
        # Must have a card in deck to move to holopower.
        # Collab spot must be empty!
        # Must have a non-resting backstage card.
        if not active_player.collabed_this_turn and len(active_player.deck) > 0 and len(active_player.collab) == 0:
            for card in active_player.backstage:
                if not is_card_resting(card):
                    available_actions.append({
                        "action_type": GameAction.MainStepCollab,
                        "card_id": card["game_card_id"],
                    })

        # D. Use Oshi skills.
        for action in active_player.oshi_card["actions"]:
            skill_id = action["skill_id"]
            if action["limit"] == "once_per_turn" and active_player.has_used_once_per_turn_effect(skill_id):
                continue

            if action["limit"] == "once_per_game" and active_player.has_used_once_per_game_effect(skill_id):
                continue

            skill_cost = action["cost"]
            if skill_cost > len(active_player.holopower):
                continue

            if "action_conditions" in action:
                if not self.are_conditions_met(active_player, active_player.oshi_card["game_card_id"], action["action_conditions"]):
                    continue

            available_actions.append({
                "action_type": GameAction.MainStepOshiSkill,
                "skill_cost": skill_cost,
                "skill_id": skill_id,
            })

        # E. Use effects from attached support cards.
        for holomem in active_player.get_holomem_on_stage():
            for attached_support in holomem["attached_support"]:
                for action in attached_support.get("special_actions", []):
                    if "conditions" in action:
                        if not self.are_conditions_met(active_player, attached_support["game_card_id"], action["conditions"]):
                            continue

                    available_actions.append({
                        "action_type": GameAction.MainStepSpecialAction,
                        "effect_id": action["effect_id"],
                        "card_id": attached_support["game_card_id"],
                        "owning_card_id": holomem["game_card_id"]
                    })

        # E2. Use gift effects with main_step_action timing.
        for holomem in active_player.get_holomem_on_stage():
            if "gift_effects" in holomem:
                for gift in holomem["gift_effects"]:
                    if gift.get("timing") == "main_step_action":
                        if "conditions" in gift:
                            if not self.are_conditions_met(active_player, holomem["game_card_id"], gift["conditions"]):
                                continue
                        available_actions.append({
                            "action_type": GameAction.MainStepSpecialAction,
                            "effect_id": gift["effect_id"],
                            "card_id": holomem["game_card_id"],
                            "owning_card_id": holomem["game_card_id"]
                        })

        # F. Use Support Cards
        for card in active_player.hand:
            if card["card_type"] == "support":
                if is_card_limited(card):
                    if active_player.limited_uses_count_this_turn >= active_player.limited_uses_allowed_this_turn:
                        continue
                    if self.first_turn_player_id == active_player.player_id and active_player.first_turn:
                        continue

                # event card whit magic tag limited can only be used once per turn
                if is_event_card_whit_magic_tag_limited(card):
                    if active_player.event_card_whit_magic_tag:
                        continue

                if "play_conditions" in card:
                    if not self.are_conditions_met(active_player, card["game_card_id"], card["play_conditions"]):
                        continue

                # Restrictions for mascots and tools with regards to attaching to holomem.
                if not self.card_has_available_target_to_attach_to(active_player, card):
                    continue

                play_requirements = {}
                if "play_requirements" in card:
                    play_requirements = card["play_requirements"]

                cheer_on_each_mem = active_player.get_cheer_on_each_holomem(exclude_empty_members=True)
                available_actions.append({
                    "action_type": GameAction.MainStepPlaySupport,
                    "card_id": card["game_card_id"],
                    "play_requirements": play_requirements,
                    "cheer_on_each_mem": cheer_on_each_mem,
                })

        # G. Pass the baton
        # If center holomem is not resting, can swap with a back who is not resting by archiving Cheer.
        # Must be able to archive that much cheer from the center.
        if len(active_player.center) > 0:
            center_mem = active_player.center[0]
            cheer_on_mem = center_mem["attached_cheer"]
            baton_cost = center_mem["baton_cost"]
            # Apply baton cost reductions from turn effects
            reduce_cost_effects = active_player.get_effects_at_timing("on_baton_cost_check", center_mem, "")
            for effect in reduce_cost_effects:
                if effect["effect_type"] == EffectType.EffectType_ReduceBatonCost:
                    # Check if this effect targets the center member
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
            if active_player.can_move_front_stage() and not active_player.baton_pass_this_turn and \
                not is_card_resting(center_mem) and len(cheer_on_mem) >= baton_cost:
                backstage_options = []
                for card in active_player.backstage:
                    if not is_card_resting(card):
                        backstage_options.append(card["game_card_id"])
                if backstage_options:
                    available_actions.append({
                        "action_type": GameAction.MainStepBatonPass,
                        "center_id": center_mem["game_card_id"],
                        "backstage_options": backstage_options,
                        "cost": baton_cost,
                        "available_cheer": ids_from_cards(cheer_on_mem),
                    })

        # H. Begin Performance
        if not (self.first_turn_player_id == active_player.player_id and active_player.first_turn):
            available_actions.append({
                "action_type": GameAction.MainStepBeginPerformance,
            })

        # I. End Turn
        available_actions.append({
            "action_type": GameAction.MainStepEndTurn,
        })

        return available_actions

    def send_main_step_actions(self):
        # Determine available actions.
        available_actions = self.get_available_mainstep_actions()

        decision_event = {
            "event_type": EventType.EventType_Decision_MainStep,
            "desired_response": GameAction.MainStepEndTurn,
            "hidden_info_player": self.active_player_id,
            "hidden_info_fields": ["available_actions"],
            "hidden_info_erase": ["available_actions"],
            "active_player": self.active_player_id,
            "available_actions": available_actions,
        }
        self.broadcast_event(decision_event)
        self.set_decision({
            "decision_type": DecisionType.DecisionMainStep,
            "decision_player": self.active_player_id,
            "available_actions": available_actions,
            "continuation": self.continue_main_step,
        })

    def begin_main_step(self):
        # Send a main step start event
        start_event = {
            "event_type": EventType.EventType_MainStepStart,
            "active_player": self.active_player_id,
        }
        self.broadcast_event(start_event)
        self.send_main_step_actions()

    def continue_main_step(self):
        self.send_main_step_actions()

    def end_player_turn(self):
        active_player = self.get_player(self.active_player_id)
        is_extra_turn = active_player.extra_turn_pending
        if is_extra_turn:
            active_player.extra_turn_pending = False

        active_player.on_my_turn_end()
        other_player = self.other_player(self.active_player_id)

        # 다음 턴 플레이어의 "직전 상대 턴에 다운됐는지" 플래그 설정
        other_player.holomem_downed_last_opponent_turn = other_player.holomem_downed_this_turn
        active_player.holomem_downed_last_opponent_turn = False

        active_player.clear_every_turn_effects()
        other_player.clear_every_turn_effects()

        # This is no longer the game's first turn.
        self.game_first_turn = False

        ending_player_id = self.active_player_id
        switch_player = not is_extra_turn
        next_turn_player_id = self.other_player(self.active_player_id).player_id if switch_player else self.active_player_id

        end_turn_event = {
            "event_type": EventType.EventType_EndTurn,
            "ending_player_id": ending_player_id,
            "next_player_id": next_turn_player_id,
        }
        self.broadcast_event(end_turn_event)

        self.reset_step_replace_center(lambda :
            self.begin_player_turn(switch_active_player=switch_player)
        )

    def send_performance_step_actions(self):
        # Determine available actions.
        available_actions = self.get_available_performance_actions()
        if len(available_actions) > 1:
            decision_event = {
                "event_type": EventType.EventType_Decision_PerformanceStep,
                "desired_response": GameAction.PerformanceStepEndTurn,
                "active_player": self.active_player_id,
                "available_actions": available_actions,
            }
            self.broadcast_event(decision_event)
            self.set_decision({
                "decision_type": DecisionType.DecisionPerformanceStep,
                "decision_player": self.active_player_id,
                "available_actions": available_actions,
                "continuation": self.begin_cleanup_art,
            })
        else:
            # Can only end the turn, do it for them.
            self.end_player_turn()

    def get_available_performance_actions(self):
        active_player = self.get_player(self.active_player_id)

        # Determine available actions.
        available_actions = []

        # Check for taregting restrictions from the opponent
        target_can_only_be_collab = False
        opponent = self.other_player(self.active_player_id)
        arts_targeting_effects = opponent.get_effects_at_timing("arts_targeting", None)
        for effect in arts_targeting_effects:
            if "conditions" not in effect or self.are_conditions_met(opponent, effect["source_card_id"], effect["conditions"]):
                # Handle these here specially.
                match effect["effect_type"]:
                    case "restrict_targets_to_collab":
                        target_can_only_be_collab = True

        # Between collab and center, they can perform an art if:
        # * That card has not performed an art this turn.
        # * That card is not resting.
        # * That card has the cheer attached that is required for the art.
        performers = active_player.get_holomem_on_stage(only_performers=True)
        for performer in performers:
            if performer["resting"] or performer["used_art_this_turn"]:
                continue

            for art in performer["arts"]:
                if active_player.is_art_requirement_met(performer, art):
                    if "art_conditions" in art and not self.are_conditions_met(active_player, performer["game_card_id"], art["art_conditions"]):
                        continue

                    can_target_backstage = art.get("can_target_backstage", False)
                    if can_target_backstage:
                        opponent_targets = opponent.get_holomem_on_stage(only_performers=False, only_collab=target_can_only_be_collab)
                    else:
                        opponent_targets = opponent.get_holomem_on_stage(only_performers=True, only_collab=target_can_only_be_collab)

                    if not opponent_targets:
                        continue

                    performer_position = "center" if active_player.is_center_holomem(performer["game_card_id"]) else "collab"
                    valid_targets = ids_from_cards(opponent_targets)
                    if "target_condition" in art:
                        match art["target_condition"]:
                            case "all_if_meets_conditions":
                                conditions = art["target_conditions"]
                                if self.are_conditions_met(active_player, performer["game_card_id"], conditions):
                                    valid_targets = ids_from_cards(opponent.get_holomem_on_stage(only_performers=False, only_collab=target_can_only_be_collab))
                            case "center_only":
                                valid_targets = ids_from_cards([target for target in opponent_targets if opponent.is_center_holomem(target["game_card_id"])])


                    if len(valid_targets) > 0:
                        available_actions.append({
                            "action_type": GameAction.PerformanceStepUseArt,
                            "performer_id": performer["game_card_id"],
                            "performer_position": performer_position,
                            "art_id": art["art_id"],
                            "power": art["power"],
                            "art_effects": art.get("art_effects", []),
                            "valid_targets": valid_targets,
                        })

        # End Performance
        available_actions.append({
            "action_type": GameAction.PerformanceStepEndTurn,
        })
        if len(available_actions) > 1 and not active_player.performance_attacked_this_turn and not active_player.performance_step_start_used_effect:
            available_actions.append({
                "action_type": GameAction.PerformanceStepCancel,
            })

        return available_actions

    def begin_performance_step(self):
        active_player = self.get_player(self.active_player_id)
        if not active_player.performance_attacked_this_turn:
            # Send a start performance event.
            start_event = {
                "event_type": EventType.EventType_PerformanceStepStart,
                "active_player": self.active_player_id,
            }
            self.broadcast_event(start_event)

            # Trigger active player's on_performance_step_start gift effects
            active_effects = []
            for holomem in active_player.get_holomem_on_stage():
                if "gift_effects" in holomem:
                    gift_effects = filter_effects_at_timing(holomem["gift_effects"], "on_performance_step_start")
                    add_ids_to_effects(gift_effects, active_player.player_id, holomem["game_card_id"])
                    active_effects.extend(gift_effects)

            # Trigger opponent's on_opponent_performance_step_start gift effects
            opponent_player = self.other_player(self.active_player_id)
            opponent_effects = []
            for holomem in opponent_player.get_holomem_on_stage():
                if "gift_effects" in holomem:
                    gift_effects = filter_effects_at_timing(holomem["gift_effects"], "on_opponent_performance_step_start")
                    add_ids_to_effects(gift_effects, opponent_player.player_id, holomem["game_card_id"])
                    opponent_effects.extend(gift_effects)

            def after_all_perf_start_effects():
                self.in_performance_step_start_effects = False
                self.continue_performance_step()

            def after_active_effects():
                if opponent_effects:
                    self.begin_resolving_effects(opponent_effects, after_all_perf_start_effects)
                else:
                    after_all_perf_start_effects()

            if active_effects or opponent_effects:
                self.in_performance_step_start_effects = True
            if active_effects:
                self.begin_resolving_effects(active_effects, after_active_effects)
                return
            elif opponent_effects:
                self.begin_resolving_effects(opponent_effects, after_all_perf_start_effects)
                return

        self.continue_performance_step()

    def continue_performance_step(self):
        if self.performance_artstatboosts.repeat_art and self.performance_target_card["damage"] < self.performance_target_player.get_card_hp(self.performance_target_card):
            self.begin_perform_art(
                self.performance_performer_card["game_card_id"],
                self.performance_art["art_id"],
                self.performance_target_card["game_card_id"],
                self.begin_cleanup_art,
                is_repeat=True
            )
        else:
            # An art is no longer being performed.
            self.performance_art = ""
            self.performance_artstatboosts.clear()
            self.performance_performer_card = None

            self.send_performance_step_actions()
