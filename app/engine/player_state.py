from __future__ import annotations
from typing import Dict, Any, TYPE_CHECKING
from copy import deepcopy
import logging

from app.engine.constants import *
from app.engine.models import *
from app.engine.helpers import *

if TYPE_CHECKING:
    from app.card_database import CardDatabase

logger = logging.getLogger(__name__)


class PlayerState:
    def __init__(self, card_db:CardDatabase, player_info:Dict[str, Any], engine: 'GameEngine'):
        self.engine = engine
        self.player_id = player_info["player_id"]
        self.username = player_info["username"]

        self.first_turn = True
        self.baton_pass_this_turn = False
        self.collabed_this_turn = False
        self.mulligan_completed = False
        self.mulligan_hand_valid = False
        self.mulligan_count = 0
        self.forced_mulligan_count = 0
        self.initial_placement_completed = False
        self.life = []
        self.hand = []
        self.archive = []
        self.backstage = []
        self.center = []
        self.collab = []
        self.holopower = []
        self.effects_used_this_turn = {}
        self.effects_used_this_game = []
        self.used_limited_this_turn = False
        self.limited_uses_count_this_turn = 0
        self.limited_uses_allowed_this_turn = 1
        self.event_card_whit_magic_tag = False
        self.played_support_this_turn = False
        self.played_support_types_this_turn = {}
        self.support_card_names_used_this_turn = []
        self.support_card_tags_used_this_turn = []
        self.turn_effects = []
        self.set_next_die_roll = 0
        self.force_die_remaining = 0
        self.card_effects_used_this_turn = []
        self.block_movement_for_turn = False
        self.last_archived_count = 0
        self.clock_time_used = 0
        self.performance_cleanup_effects_pending = []
        self.performance_attacked_this_turn = False
        self.performance_step_start_used_effect = False
        self.last_revealed_cards = []
        self.last_die_roll_results = []
        self.die_rolled_by_holomem_names_this_turn = []
        self.holomem_downed_this_turn = False
        self.holomem_downed_names_this_turn = []
        self.holomem_downed_last_opponent_turn = False
        self.holomem_downed_names_last_opponent_turn = []
        self.holomem_returned_to_deck_this_turn = False
        self.block_life_loss_by_effect_this_turn = False
        self.sp_oshi_skill_used_this_turn = False
        self.die_rolls_this_turn = 0
        self.extra_turn_pending = False

        # Set up Oshi.
        self.oshi_id = player_info["oshi_id"]
        self.oshi_card = card_db.get_card_by_id(self.oshi_id)
        self.oshi_card["game_card_id"] = self.player_id + "_oshi"

        self.deck_list = player_info["deck"]
        # Generate unique cards for all cards in the deck.
        self.deck = []
        card_number = 1
        for card_id, count in self.deck_list.items():
            card = card_db.get_card_by_id(card_id)
            for _ in range(int(count)):
                generated_card = deepcopy(card)
                generated_card["owner_id"] = self.player_id
                generated_card["game_card_id"] = self.player_id + "_" + str(card_number)
                generated_card["played_this_turn"] = False
                generated_card["bloomed_this_turn"] = False
                generated_card["attached_cheer"] = []
                generated_card["attached_support"] = []
                generated_card["stacked_cards"] = []
                generated_card["zone_when_downed"] = ""
                generated_card["zone_when_returned_to_hand"] = ""
                generated_card["attached_when_downed"] = []
                generated_card["damage"] = 0
                generated_card["resting"] = False
                generated_card["rest_extra_turn"] = False
                generated_card["used_art_this_turn"] = False
                card_number += 1
                self.deck.append(generated_card)

        self.cheer_deck_list = player_info["cheer_deck"]
        # Generate unique cards for all cards in the cheer deck.
        self.cheer_deck = []
        card_number = 1001
        for card_id, count in player_info["cheer_deck"].items():
            card = card_db.get_card_by_id(card_id)
            for _ in range(int(count)):
                generated_card = deepcopy(card)
                generated_card["owner_id"] = self.player_id
                generated_card["game_card_id"] = self.player_id + "_" + str(card_number)
                card_number += 1
                self.cheer_deck.append(generated_card)

        self.game_cards_map = {card["game_card_id"]: card["card_id"] for card in self.deck + self.cheer_deck}
        self.game_cards_map[self.oshi_card["game_card_id"]] = self.oshi_card["card_id"]

    def initialize_life(self):
        # Move cards from the cheer deck to the life area equal to the oshi's life.
        self.life = self.cheer_deck[:self.oshi_card["life"]]
        # Remove them from the cheer deck.
        self.cheer_deck = self.cheer_deck[self.oshi_card["life"]:]

    def draw(self, amount: int, from_bottom: bool = False):
        amount = min(amount, len(self.deck))
        if from_bottom:
            drawn_cards = self.deck[-amount:]
            drawn_cards.reverse()
            self.deck = self.deck[:-amount]
        else:
            drawn_cards = self.deck[:amount]
            self.deck = self.deck[amount:]
        self.hand += drawn_cards

        draw_event = {
            "event_type": EventType.EventType_Draw,
            "drawing_player_id": self.player_id,
            "hidden_info_player": self.player_id,
            "hidden_info_fields": ["drawn_card_ids"],
            "drawn_card_ids": ids_from_cards(drawn_cards),
            "deck_count": len(self.deck),
            "hand_count": len(self.hand),
            "from_bottom": from_bottom,
        }
        self.engine.broadcast_event(draw_event)

    def mulligan(self, forced=False):
        self.mulligan_count += 1
        self.shuffle_hand_to_deck()
        if forced:
            self.forced_mulligan_count += 1
        self.draw(STARTING_HAND_SIZE)

    def shuffle_hand_to_deck(self):
        while len(self.hand) > 0:
            self.move_card(self.hand[0]["game_card_id"], "deck", hidden_info=True)
        self.shuffle_deck()

    def shuffle_deck(self):
        self.engine.shuffle_list(self.deck)
        shuffle_event = {
            "event_type": EventType.EventType_ShuffleDeck,
            "shuffling_player_id": self.player_id,
        }
        self.engine.broadcast_event(shuffle_event)

    def shuffle_cheer_deck(self):
        self.engine.shuffle_list(self.cheer_deck)

    def matches_oshi_color(self, colors):
        for color in colors:
            if color in self.oshi_card["colors"]:
                return True
        return False

    def matches_stage_holomems_color(self, colors, tag_requirement = []):
        holomems_to_check = self.get_holomem_on_stage()
        if tag_requirement:
            holomems_to_check = [holomem for holomem in holomems_to_check if any(tag in holomem["tags"] for tag in tag_requirement)]
        for card in holomems_to_check:
            for color in colors:
                if color in card["colors"]:
                    return True
        return False

    def is_art_requirement_met(self, card, art):
        attached_cheer_cards = [attached_card for attached_card in card["attached_cheer"] if is_card_cheer(attached_card)]

        white_cheer = 0
        green_cheer = 0
        blue_cheer = 0
        red_cheer = 0
        purple_cheer = 0
        yellow_cheer = 0

        check_cheer_effects = self.get_effects_at_timing("check_cheer", card, "")
        for effect in check_cheer_effects:
            if check_cheer_effects and self.engine.are_conditions_met(self, effect["source_card_id"], effect.get("conditions", [])):
                match effect["effect_type"]:
                    case "bonus_cheer":
                        amount = effect["amount"]
                        match effect["color"]:
                            case "blue":
                                blue_cheer += amount
                            case "green":
                                green_cheer += amount
                            case "red":
                                red_cheer += amount
                            case "purple":
                                purple_cheer += amount
                            case "white":
                                white_cheer += amount
                            case "yellow":
                                yellow_cheer += amount

        for attached_cheer_card in attached_cheer_cards:
            if "white" in attached_cheer_card["colors"]:
                white_cheer += 1
            elif "green" in attached_cheer_card["colors"]:
                green_cheer += 1
            elif "blue" in attached_cheer_card["colors"]:
                blue_cheer += 1
            elif "red" in attached_cheer_card["colors"]:
                red_cheer += 1
            elif "purple" in attached_cheer_card["colors"]:
                purple_cheer += 1
            elif "yellow" in attached_cheer_card["colors"]:
                yellow_cheer += 1

        # Calculate cost reductions and color conversions from on_art_cost_check effects
        convert_all_to_any = False
        cost_reductions = {"white": 0, "green": 0, "blue": 0, "red": 0, "purple": 0, "yellow": 0, "any": 0}
        reduce_cost_effects = self.get_effects_at_timing("on_art_cost_check", card, "")
        for effect in reduce_cost_effects:
            if effect["effect_type"] == EffectType.EffectType_ConvertArtCostColors:
                if self.engine.are_conditions_met(self, effect["source_card_id"], effect.get("conditions", [])):
                    convert_all_to_any = True
                continue
            if effect["effect_type"] == EffectType.EffectType_ReduceArtCost:
                if not self.engine.are_conditions_met(self, effect["source_card_id"], effect.get("conditions", [])):
                    continue
                # Check target art_id restriction
                target_art_id = effect.get("target_art_id", "")
                if target_art_id and art.get("art_id", "") != target_art_id:
                    continue
                # Check target limitations
                target_limitation = effect.get("target_limitation", "")
                if target_limitation == "center":
                    if card not in self.center:
                        continue
                elif target_limitation == "collab":
                    if card not in self.collab:
                        continue
                elif target_limitation == "center_or_collab":
                    if card not in self.center and card not in self.collab:
                        continue
                elif target_limitation == "self":
                    if card["game_card_id"] != effect["source_card_id"]:
                        continue
                elif target_limitation == "specific_member_id":
                    if card["game_card_id"] != effect.get("target_member_id", ""):
                        continue
                # Check target member name
                target_member_name = effect.get("target_member_name", "")
                if target_member_name and target_member_name not in card.get("card_names", []):
                    continue
                # Check target has attachment
                target_has_attachment_name = effect.get("target_has_attachment_name", "")
                if target_has_attachment_name:
                    has_attachment = False
                    for attached in card.get("attached_support", []):
                        if target_has_attachment_name in attached.get("card_names", []):
                            has_attachment = True
                            break
                    if not has_attachment:
                        continue
                if effect.get("free_cost", False):
                    return True
                # Apply cost reduction
                reduction_color = effect.get("color", "")
                reduction_amount = effect.get("amount", 0)
                # Dynamic amount: count named attachments on a specified zone
                per_attachment_name = effect.get("amount_per_attachment_name", "")
                if per_attachment_name:
                    per_zone = effect.get("amount_per_attachment_zone", "self")
                    count_holomems = []
                    match per_zone:
                        case "center":
                            count_holomems = self.center
                        case "collab":
                            count_holomems = self.collab
                        case "self":
                            src, _, _ = self.find_card(effect["source_card_id"])
                            count_holomems = [src] if src else []
                        case _:
                            count_holomems = self.get_holomem_on_stage()
                    attachment_count = 0
                    for h in count_holomems:
                        for attached in h.get("attached_support", []):
                            if per_attachment_name in attached.get("card_names", []):
                                attachment_count += 1
                    reduction_amount = attachment_count * effect.get("amount_per_unit", 1)
                if reduction_color in cost_reductions:
                    cost_reductions[reduction_color] += reduction_amount
                continue
            if effect["effect_type"] == EffectType.EffectType_ReduceArtCostPerCheerColorTypesInBothArchives:
                if not self.engine.are_conditions_met(self, effect["source_card_id"], effect.get("conditions", [])):
                    continue
                target_limitation = effect.get("target_limitation", "")
                if target_limitation == "self" and card["game_card_id"] != effect["source_card_id"]:
                    continue
                all_colors = set()
                for player in self.engine.player_states:
                    for archive_card in player.archive:
                        if is_card_cheer(archive_card):
                            for color in archive_card.get("colors", []):
                                all_colors.add(color)
                reduction_per = effect.get("amount", 1)
                total_reduction = len(all_colors) * reduction_per
                cost_reductions["any"] += total_reduction
                continue

        # Apply cost reductions to create effective costs
        cheer_costs = []
        for cost in art["costs"]:
            new_cost = dict(cost)
            color = cost["color"]
            if color in cost_reductions and cost_reductions[color] > 0:
                reduction = min(cost_reductions[color], cost["amount"])
                new_cost["amount"] = cost["amount"] - reduction
                cost_reductions[color] -= reduction
            cheer_costs.append(new_cost)

        if convert_all_to_any:
            total = sum(c["amount"] for c in cheer_costs)
            cheer_costs = [{"color": "any", "amount": total}]

        any_cost = 0
        # First go through all the costs and subtract any from the color counts.
        for cost in cheer_costs:
            color_required = cost["color"]
            color_amount = cost["amount"]
            if color_required == "any":
                any_cost += color_amount
            else:
                if color_required == "white":
                    white_cheer -= color_amount
                elif color_required == "green":
                    green_cheer -= color_amount
                elif color_required == "blue":
                    blue_cheer -= color_amount
                elif color_required == "red":
                    red_cheer -= color_amount
                elif color_required == "purple":
                    purple_cheer -= color_amount
                elif color_required == "yellow":
                    yellow_cheer -= color_amount

        # If any cheer is negative, the requirement is not met.
        if white_cheer < 0 or green_cheer < 0 or blue_cheer < 0 or red_cheer < 0 or purple_cheer < 0 or yellow_cheer < 0:
            return False

        total_cheer_left = white_cheer + green_cheer + blue_cheer + red_cheer + purple_cheer + yellow_cheer
        if total_cheer_left < any_cost:
            return False

        passed_requirement = False
        if "art_requirement" in art:
            match art["art_requirement"]:
                case "has_attached":
                    required_definition_id = art.get("art_requirement_attached_id", "")
                    required_card_name = art.get("art_requirement_attached_name", "")
                    for attached in card["attached_support"]:
                        if required_definition_id and attached["card_id"] == required_definition_id:
                            passed_requirement = True
                            break
                        elif required_card_name and required_card_name in attached.get("card_names", []):
                            passed_requirement = True
                            break
        else:
            passed_requirement = True

        return passed_requirement

    def add_performance_cleanup(self, effects):
        self.performance_cleanup_effects_pending.extend(effects)

    def can_archive_from_hand(self, amount, condition_source, requirement = None, requirement_same_tag = False):
        return self.get_can_archive_from_hand_count(condition_source, requirement, requirement_same_tag) >= amount

    def get_can_archive_from_hand_count(self, condition_source, requirement = None, requirement_same_tag = False):
        available_to_archive = len(self.hand)
        if requirement:
            match requirement:
                case "holomem":
                    available_to_archive = 0
                    for card in self.hand:
                        if is_card_holomem(card):
                            available_to_archive += 1
        if requirement_same_tag:
            holomem_cards = [card for card in self.hand if is_card_holomem(card)]
            eligible = set()
            for i, card_a in enumerate(holomem_cards):
                for card_b in holomem_cards[i+1:]:
                    if set(card_a.get("tags", [])) & set(card_b.get("tags", [])):
                        eligible.add(card_a["game_card_id"])
                        eligible.add(card_b["game_card_id"])
            available_to_archive = min(available_to_archive, len(eligible))
        if "special_hand_archive_skill_per_turn" in self.oshi_card and self.oshi_card["special_hand_archive_skill_per_turn"] == "executivesorder":
            if condition_source == "holomem_red" and not self.has_used_once_per_turn_effect("executivesorder"):
                # Lui can use holopower as well.
                available_to_archive += len(self.holopower)
        return available_to_archive

    def get_and_reset_last_archived_count(self):
        last_archived_count = self.last_archived_count
        self.last_archived_count = 0
        return last_archived_count

    def can_move_front_stage(self):
        return not self.block_movement_for_turn

    def get_accepted_bloom_for_card(self, card):
        accepted_bloom_levels = []
        if card["card_type"] == "holomem_debut":
            accepted_bloom_levels = [1]
        elif card["card_type"] == "holomem_bloom":
            current_bloom_level = card["bloom_level"]
            accepted_bloom_levels = [current_bloom_level, current_bloom_level+1]

        if "bloom_level_skip" in card:
            meets_req = False
            if "bloom_level_skip_requirement" in card:
                match card["bloom_level_skip_requirement"]:
                    case "3lifeorless":
                        meets_req = len(self.life) <= 3
            if meets_req:
                accepted_bloom_levels.append(card["bloom_level_skip"])
        return accepted_bloom_levels


    def can_bloom_with_card(self, target_card, bloom_card):
        if "bloom_blocked" in target_card and target_card["bloom_blocked"]:
            return False

        accepted_bloom_levels = self.get_accepted_bloom_for_card(target_card)
        if accepted_bloom_levels:
            if bloom_card["card_type"] == "holomem_bloom" and bloom_card["bloom_level"] in accepted_bloom_levels:
                # Check the names of the bloom card, at last one must match a name from the base card.
                if any(name in bloom_card["card_names"] for name in target_card["card_names"]):
                    # Check the damage, if the bloom version would die, you can't.
                    if target_card["damage"] < self.get_card_hp(bloom_card):
                        return True
        return False

    def can_bloom_this_turn(self, holomem):
        # Check if this holomem can bloom this turn
        # A holomem can bloom if it has accepted bloom levels and is not blocked
        if "bloom_blocked" in holomem and holomem["bloom_blocked"]:
            return False
        
        # 이번 턴에 플레이된 홀로멤은 bloom할 수 없음
        if "played_this_turn" in holomem and holomem["played_this_turn"]:
            return False
        
        accepted_bloom_levels = self.get_accepted_bloom_for_card(holomem)
        return len(accepted_bloom_levels) > 0

    def get_card_bonus_hp(self, card):
        effects = self.get_effects_at_timing("check_hp", card, "")
        bonus_hp = 0
        for effect in effects:
            if self.engine.are_conditions_met(self, effect["source_card_id"], effect.get("conditions", [])):
                match effect["effect_type"]:
                    case EffectType.EffectType_BonusHp:
                        bonus_hp += effect["amount"]
                    case EffectType.EffectType_BonusHpPerAttachedCheer:
                        if effect["source_card_id"] == card["game_card_id"]:
                            per_amount = effect["amount"]
                            attached_cheers = [c for c in card.get("attached_cheer", []) if c["card_type"] == "cheer"]
                            bonus_hp += per_amount * len(attached_cheers)
                    case EffectType.EffectType_BonusHpPerStacked:
                        if effect["source_card_id"] == card["game_card_id"]:
                            per_amount = effect["amount"]
                            stacked_cards = card.get("stacked_cards", [])
                            stacked_holomems = [c for c in stacked_cards if is_card_holomem(c)]
                            bonus_hp += per_amount * len(stacked_holomems)
        return bonus_hp

    def get_card_hp(self, card):
        return card["hp"] + self.get_card_bonus_hp(card)

    def get_holomem_zone(self, card):
        if card in self.archive:
            return card["zone_when_downed"]
        elif card in self.hand:
            return card["zone_when_returned_to_hand"]
        elif card in self.center:
            return "center"
        elif card in self.collab:
            return "collab"
        elif card in self.backstage:
            return "backstage"
        return ""

    def record_card_effect_used_this_turn(self, card_id):
        if card_id not in self.card_effects_used_this_turn:
            self.card_effects_used_this_turn.append(card_id)

    def has_used_card_effect_this_turn(self, card_id):
        return card_id in self.card_effects_used_this_turn

    def record_effect_used_this_turn(self, effect_id):
        self.effects_used_this_turn[effect_id] = self.effects_used_this_turn.get(effect_id, 0) + 1

    def has_used_once_per_turn_effect(self, effect_id):
        return self.effects_used_this_turn.get(effect_id, 0) > 0

    def record_effect_used_this_game(self, effect_id):
        if effect_id not in self.effects_used_this_game:
            self.effects_used_this_game.append(effect_id)

    def has_used_once_per_game_effect(self, effect_id):
        return effect_id in self.effects_used_this_game

    def get_effects_at_timing(self, timing, card, timing_source_requirement = ""):
        effects = []

        if timing == "art_cleanup":
            effects.extend(self.performance_cleanup_effects_pending)
            self.performance_cleanup_effects_pending = []

        # For now, prioritize Gift effects before oshi effects
        # due to zeta's reduce damage gift that can fail which wants to go first.
        # If needed, on_take_damage will have to become a simultaneous decision resolution.
        for holomem in self.get_holomem_on_stage():
            if "gift_effects" in holomem:
                gift_effects = filter_effects_at_timing(holomem["gift_effects"], timing)
                add_ids_to_effects(gift_effects, self.player_id, holomem["game_card_id"])
                effects.extend(gift_effects)

        for oshi_effect in self.oshi_card.get("effects", []):
            oshi_timing = oshi_effect.get("timing")
            if not oshi_timing:
                logger.debug("Skipping oshi effect without timing for card_id=%s", self.oshi_card.get("card_id"))
                continue
            if oshi_timing == timing:
                if "timing_source_requirement" in oshi_effect and oshi_effect["timing_source_requirement"] != timing_source_requirement:
                    continue
                add_ids_to_effects([oshi_effect], self.player_id, self.oshi_card["game_card_id"])
                effects.append(oshi_effect)

        turn_effects = filter_effects_at_timing(self.turn_effects, timing)
        add_ids_to_effects(turn_effects, self.player_id, "")
        effects.extend(turn_effects)

        if timing == "before_die_roll" and not card:
            for holomem in self.get_holomem_on_stage():
                for attached_card in holomem.get("attached_support", []):
                    attached_effects = attached_card.get("attached_effects", [])
                    for attached_effect in attached_effects:
                        if not isinstance(attached_effect, dict):
                            continue
                        if attached_effect.get("timing") == timing:
                            if "timing_source_requirement" in attached_effect and attached_effect["timing_source_requirement"] != timing_source_requirement:
                                continue
                            ae_copy = deepcopy(attached_effect)
                            add_ids_to_effects([ae_copy], self.player_id, attached_card["game_card_id"])
                            effects.append(ae_copy)

        for holomem in self.get_holomem_on_stage():
            for attached_card in holomem.get("attached_support", []):
                for ae in attached_card.get("attached_effects", []):
                    if not isinstance(ae, dict):
                        continue
                    if ae.get("timing") == timing and ae.get("global_trigger", False):
                        ae_copy = deepcopy(ae)
                        add_ids_to_effects([ae_copy], self.player_id, attached_card["game_card_id"])
                        effects.append(ae_copy)

        if card and card["card_type"] not in ["support", "oshi"]:
            card_effects = filter_effects_at_timing(card.get("effects", []), timing)
            add_ids_to_effects(card_effects, self.player_id, card["game_card_id"])
            effects.extend(card_effects)

            attachments_to_check = card["attached_support"]
            if card["attached_when_downed"]:
                attachments_to_check = card["attached_when_downed"]
            for attached_card in attachments_to_check:
                attached_effects = attached_card.get("attached_effects", [])
                for attached_effect in attached_effects:
                    if attached_effect.get("global_trigger", False):
                        continue
                    if attached_effect["timing"] == timing:
                        if "timing_source_requirement" in attached_effect and attached_effect["timing_source_requirement"] != timing_source_requirement:
                            continue
                        add_ids_to_effects([attached_effect], self.player_id, attached_card["game_card_id"])
                        effects.append(attached_effect)
        return effects

    def get_cheer_color_types_on_holomems(self):
        cheer_color_types = set()
        for card in self.get_holomem_on_stage():
            for attached_card in card["attached_cheer"]:
                if is_card_cheer(attached_card):
                    cheer_color_types.update(attached_card["colors"])
        return cheer_color_types

    def get_cheer_ids_on_holomems(self):
        cheer_ids = []
        for card in self.get_holomem_on_stage():
            for attached_card in card["attached_cheer"]:
                if is_card_cheer(attached_card):
                    cheer_ids.append(attached_card["game_card_id"])
        return cheer_ids

    def get_cheer_on_each_holomem(self, exclude_empty_members = False):
        cheer = {}
        for card in self.get_holomem_on_stage():
            cheer[card["game_card_id"]] = [attached_card["game_card_id"] for attached_card in card["attached_cheer"]]
            if exclude_empty_members and len(cheer[card["game_card_id"]]) == 0:
                del cheer[card["game_card_id"]]
        return cheer

    def get_holomems_with_cheer(self):
        holomems = []
        for card in self.get_holomem_on_stage():
            if card["attached_cheer"]:
                holomems.append(card["game_card_id"])
        return holomems

    def is_cheer_on_holomem(self, cheer_id, target_id):
        holomem_card, _, _ = self.find_card(target_id)
        if holomem_card:
            for attached_card in holomem_card["attached_cheer"]:
                if attached_card["game_card_id"] == cheer_id:
                    return True
        return False

    def add_to_deck(self, card, top: bool):
        if top:
            self.deck.insert(0, card)
        else:
            self.deck.append(card)

    def are_cards_in_hand(self, card_ids):
        hand_card_ids = ids_from_cards(self.hand)
        for card_id in card_ids:
            if card_id not in hand_card_ids:
                return False
        return True

    def get_card_from_hand(self, card_id):
        for card in self.hand:
            if card["game_card_id"] == card_id:
                return card
        return None

    def get_holomem_on_stage(self, only_performers = False, only_collab = False, only_backstage = False):
        on_stage = []
        if only_collab:
            on_stage = self.collab.copy()
        elif only_backstage:
            on_stage = self.backstage.copy()
        else:
            on_stage = self.center + self.collab
            if not only_performers:
                on_stage += self.backstage
        return on_stage

    def get_holomem_under(self, card_id):
        source_card, _, _ = self.find_card(card_id)
        holomems = []
        if source_card:
            for stacked_card in source_card["stacked_cards"]:
                if is_card_holomem(stacked_card):
                    holomems.append(stacked_card)
        return holomems


    def get_holomems_with_attachment(self, attachment_id):
        for card in self.get_holomem_on_stage():
            if attachment_id in ids_from_cards(card["attached_cheer"] + card["attached_support"]):
                return [card]
        return []

    def is_center_holomem(self, card_id):
        return card_id in ids_from_cards(self.center)

    def get_zone_name(self, zone):
        match zone:
            case self.hand: return "hand"
            case self.archive: return "archive"
            case self.backstage: return "backstage"
            case self.center: return "center"
            case self.collab: return "collab"
            case self.deck: return "deck"
            case self.cheer_deck: return "cheer_deck"
            case self.holopower: return "holopower"
            case _: return "unknown"

    def find_card(self, card_id, include_stacked_cards = False):
        zones = [self.hand, self.archive, self.backstage, self.center, self.collab, self.deck, self.cheer_deck, self.holopower]
        for zone in zones:
            for card in zone:
                if card["game_card_id"] == card_id:
                    zone_name = self.get_zone_name(zone)
                    return card, zone, zone_name
        for card in self.engine.floating_cards:
            if card["game_card_id"] == card_id:
                return card, self.engine.floating_cards, "floating"
        if self.oshi_card["game_card_id"] == card_id:
            return self.oshi_card, None, "oshi"

        if include_stacked_cards:
            attached_card = self.find_attachment(card_id)
            return attached_card, None, None

        # Card, Zone, Zone Name
        return None, None, None

    def find_attachment(self, attachment_id):
        for holomem in self.get_holomem_on_stage():
            for attachment in holomem["attached_support"]:
                if attachment["game_card_id"] == attachment_id:
                    return attachment
            for attachment in holomem["attached_cheer"]:
                if attachment["game_card_id"] == attachment_id:
                    return attachment
            for attachment in holomem["stacked_cards"]:
                if attachment["game_card_id"] == attachment_id:
                    return attachment
        return None

    def find_and_remove_card(self, card_id):
        card, zone, zone_name = self.find_card(card_id)
        if card and zone:
            zone.remove(card)
        return card, zone, zone_name

    def move_card(self, card_id, to_zone, zone_card_id="", hidden_info=False, add_to_bottom=False, no_events=False):
        card, _, from_zone_name = self.find_and_remove_card(card_id)
        if not card:
            card, previous_holder_id = self.find_and_remove_attached(card_id)
            from_zone_name = previous_holder_id

        if not card:
            logger.warning(
                "move_card skipped missing card_id=%s player_id=%s to_zone=%s",
                card_id,
                self.player_id,
                to_zone,
            )
            return False

        if to_zone in ["archive", "deck", "top_of_deck", "cheer_deck", "holopower"] and is_card_holomem(card):
            all_attached = (
                card.get("stacked_cards", [])
                + card.get("attached_cheer", [])
                + card.get("attached_support", [])
            )
            for attached in all_attached:
                self.archive.insert(0, attached)
                if not no_events:
                    self.engine.broadcast_event({
                        "event_type": EventType.EventType_MoveAttachedCard,
                        "owning_player_id": self.player_id,
                        "from_holomem_id": card_id,
                        "to_holomem_id": "archive",
                        "attached_id": attached["game_card_id"],
                    })
            card["stacked_cards"] = []
            card["attached_cheer"] = []
            card["attached_support"] = []

        match to_zone:
            case "archive":
                if add_to_bottom:
                    self.archive.append(card)
                else:
                    self.archive.insert(0, card)
            case "backstage":
                self.backstage.append(card)
            case "center":
                self.center.append(card)
            case "cheer_deck":
                if add_to_bottom:
                    self.cheer_deck.append(card)
                else:
                    self.cheer_deck.insert(0, card)
                    self.engine.shuffle_list(self.cheer_deck)
            case "collab":
                self.collab.append(card)
            case "deck":
                if add_to_bottom:
                    self.deck.append(card)
                else:
                    self.deck.insert(0, card)
            case "top_of_deck":
                self.deck.insert(0, card)
            case "hand":
                self.hand.append(card)
                # Reset any card stats when returning to hand.
                self.reset_card_stats(card)
            case "holomem":
                holomem_card, _, _ = self.find_card(zone_card_id)
                attach_card(card, holomem_card)
            case "holopower":
                self.holopower.insert(0, card)

        if to_zone in ["center", "backstage", "collab", "holomem"] and from_zone_name in ["hand", "deck"]:
            card["played_this_turn"] = True

        stage_zones = {"center", "collab", "backstage"}
        if to_zone in ["deck", "top_of_deck"] and from_zone_name in stage_zones and is_card_holomem(card):
            self.holomem_returned_to_deck_this_turn = True

        move_card_event = {
            "event_type": EventType.EventType_MoveCard,
            "moving_player_id": self.player_id,
            "from": from_zone_name,
            "to_zone": to_zone,
            "zone_card_id": zone_card_id,
            "card_id": card_id,
        }
        if hidden_info:
            move_card_event["hidden_info_player"] = self.player_id
            move_card_event["hidden_info_fields"] = ["card_id"]
        if not no_events:
            self.engine.broadcast_event(move_card_event)
            self.engine.broadcast_bonus_hp_updates()
        return True

    def reset_card_stats(self, card):
        if is_card_holomem(card):
            card["played_this_turn"] = False
            card["bloomed_this_turn"] = False
            card["attached_cheer"] = []
            card["attached_support"] = []
            card["stacked_cards"] = []
            card["damage"] = 0
            card["resting"] = False
            card["rest_extra_turn"] = False
            card["used_art_this_turn"] = False
            card["zone_when_downed"] = ""
            card["attached_when_downed"] = []

    def active_resting_cards(self):
        # For each card in the center, backstage, and collab zones, check if they are resting.
        # If so, set resting to false.
        activated_card_ids = []
        for card in self.get_holomem_on_stage():
            if is_card_resting(card):
                if card["rest_extra_turn"]:
                    card["rest_extra_turn"] = False
                else:
                    card["resting"] = False
                    activated_card_ids.append(card["game_card_id"])
        return activated_card_ids

    def on_my_turn_end(self):
        self.first_turn = False
        self.block_movement_for_turn = False

    def clear_every_turn_effects(self):
        self.baton_pass_this_turn = False
        self.collabed_this_turn = False
        remaining_effects = []
        for effect in self.turn_effects:
            if "duration" in effect:
                effect["duration"] -= 1
                if effect["duration"] > 0:
                    remaining_effects.append(effect)
        self.turn_effects = remaining_effects
        self.performance_attacked_this_turn = False
        self.performance_step_start_used_effect = False
        self.used_limited_this_turn = False
        self.limited_uses_count_this_turn = 0
        self.limited_uses_allowed_this_turn = 1
        self.event_card_whit_magic_tag = False
        self.played_support_this_turn = False
        self.played_support_types_this_turn = {}
        self.support_card_names_used_this_turn = []
        self.support_card_tags_used_this_turn = []
        self.effects_used_this_turn = {}
        self.card_effects_used_this_turn = []
        self.set_next_die_roll = 0
        self.force_die_remaining = 0
        self.last_revealed_cards = []
        self.die_rolled_by_holomem_names_this_turn = []
        self.holomem_downed_this_turn = False
        self.holomem_downed_names_this_turn = []
        self.holomem_returned_to_deck_this_turn = False
        self.block_life_loss_by_effect_this_turn = False
        self.sp_oshi_skill_used_this_turn = False
        self.die_rolls_this_turn = 0
        for card in self.get_holomem_on_stage():
            card["used_art_this_turn"] = False
            card["played_this_turn"] = False
            card["bloomed_this_turn"] = False

    def reset_collab(self, skip_rest_ids=None):
        if skip_rest_ids is None:
            skip_rest_ids = set()
        rested_card_ids = []
        moved_backstage_card_ids = []
        if self.can_move_front_stage():
            for card in self.collab:
                if card["game_card_id"] not in skip_rest_ids:
                    card["resting"] = True
                    rested_card_ids.append(card["game_card_id"])

                self.backstage.append(card)
                moved_backstage_card_ids.append(card["game_card_id"])
            self.collab = []

        return rested_card_ids, moved_backstage_card_ids

    def return_collab(self):
        # For all cards in collab, move them back to backstage and rest them.
        collab_card_ids = ids_from_cards(self.collab)
        for card_id in collab_card_ids:
            self.move_card(card_id, "backstage")

    def bloom(self, bloom_card_id, target_card_id, continuation):
        logger.debug(f"bloom: bloom_card_id={bloom_card_id} target_card_id={target_card_id}")
        if self.engine.in_performance_step_start_effects:
            self.performance_step_start_used_effect = True

        bloom_card, _, bloom_from_zone_name = self.find_and_remove_card(bloom_card_id)
        if bloom_card is None:
            for holomem in self.get_holomem_on_stage():
                for i, stacked in enumerate(holomem["stacked_cards"]):
                    if stacked["game_card_id"] == bloom_card_id:
                        bloom_card = stacked
                        holomem["stacked_cards"].pop(i)
                        bloom_from_zone_name = "stacked"
                        break
                if bloom_card:
                    break
        target_card, zone, _ = self.find_and_remove_card(target_card_id)

        previous_bloom_level = 0
        if "bloom_level" in target_card:
            previous_bloom_level = target_card["bloom_level"]
        next_bloom_level = 0
        if "bloom_level" in bloom_card:
            next_bloom_level = bloom_card["bloom_level"]

        # Add any stacked cards on the target to this too.
        bloom_card["stacked_cards"].append(target_card)
        bloom_card["stacked_cards"] += target_card["stacked_cards"]
        target_card["stacked_cards"] = []

        bloom_card["attached_cheer"] += target_card["attached_cheer"]
        target_card["attached_cheer"] = []
        bloom_card["attached_support"] += target_card["attached_support"]
        target_card["attached_support"] = []

        bloom_card["bloomed_this_turn"] = True
        # 아카이브에서 bloom할 때는 대미지를 초기화
        if bloom_from_zone_name == "archive":
            bloom_card["damage"] = 0
        else:
            bloom_card["damage"] = target_card["damage"]
        bloom_card["resting"] = target_card["resting"]

        # Put the bloom card where the target card was.
        zone.append(bloom_card)

        # For any ongoing turn effects, make sure to point them at the new card.
        for effect in self.turn_effects:
            for condition in effect.get("conditions", []):
                if condition.get("required_id", "") == target_card_id:
                    condition["required_id"] = bloom_card_id
            if effect.get("source_card_id", "") == target_card_id:
                effect["source_card_id"] = bloom_card_id

        bloom_event = {
            "event_type": EventType.EventType_Bloom,
            "bloom_player_id": self.player_id,
            "bloom_card_id": bloom_card_id,
            "target_card_id": target_card_id,
            "bloom_from": bloom_from_zone_name,
        }
        self.engine.broadcast_event(bloom_event)
        self.engine.broadcast_bonus_hp_updates()

        # Check if any attached cards must now be archived.
        attachments = bloom_card["attached_support"].copy()
        for attached_card in attachments:
            if is_card_equipment(attached_card) and not is_card_attach_requirements_meant(attached_card, bloom_card):
                self.move_card(attached_card["game_card_id"], "archive")

        # Extra bloom effects that happen on bloom (like from attachments).
        on_bloom_extra_effects = self.get_effects_at_timing("on_bloom", bloom_card, "")

        # Extra bloom effects that happen on bloom (like from attachments), but require level up.
        on_bloom_level_up_effects = []
        if next_bloom_level > previous_bloom_level:
            on_bloom_level_up_effects = self.get_effects_at_timing("on_bloom_level_up", bloom_card, "")

        # Handle any bloom effects.
        all_bloom_effects = []
        all_bloom_effects.extend(on_bloom_extra_effects)
        all_bloom_effects.extend(on_bloom_level_up_effects)
        if "bloom_effects" in bloom_card:
            effects = deepcopy(bloom_card["bloom_effects"])
            add_ids_to_effects(effects, self.player_id, bloom_card_id)
            all_bloom_effects.extend(effects)
        if len(all_bloom_effects) > 0:
            simultaneous_effects = len(on_bloom_level_up_effects) > 0 or len(on_bloom_extra_effects) > 0
            self.engine.begin_resolving_effects(all_bloom_effects, continuation, [], simultaneous_effects)
        else:
            continuation()

    def generate_holopower(self, amount, skip_event=False):
        generated_something = False
        for _ in range(amount):
            if len(self.deck) > 0:
                self.holopower.insert(0, self.deck.pop(0))
                generated_something = True
        if generated_something and not skip_event:
            generate_hp_event = {
                "event_type": EventType.EventType_GenerateHolopower,
                "generating_player_id": self.player_id,
                "holopower_generated": amount,
            }
            self.engine.broadcast_event(generate_hp_event)

    def collab_action(self, collab_card_id, continuation):
        # Move the card and generate holopower.
        collab_card, _, _ = self.find_and_remove_card(collab_card_id)
        self.collab.append(collab_card)
        self.collabed_this_turn = True
        self.generate_holopower(1, skip_event=True)

        collab_event = {
            "event_type": EventType.EventType_Collab,
            "collab_player_id": self.player_id,
            "collab_card_id": collab_card_id,
            "holopower_generated": 1,
        }
        self.engine.broadcast_event(collab_event)
        self.engine.broadcast_bonus_hp_updates()

        # Extra collab effects that happen on collabs (like from attachments).
        on_collab_extra_effects = self.get_effects_at_timing("on_collab", collab_card, "")

        # Handle collab effects.
        collab_effects = deepcopy(collab_card["collab_effects"]) if "collab_effects" in collab_card else []
        add_ids_to_effects(collab_effects, self.player_id, collab_card_id)

        # Handle all collab effects
        all_collab_effects = on_collab_extra_effects + collab_effects
        oshi_id = self.oshi_card["game_card_id"]
        non_oshi_source_ids = set()
        for e in all_collab_effects:
            sid = e.get("source_card_id", "")
            if sid and sid != oshi_id:
                non_oshi_source_ids.add(sid)
        simultaneous = len(non_oshi_source_ids) > 1
        self.engine.begin_resolving_effects(all_collab_effects, continuation, simultaneous_choice=simultaneous)

    def spend_holopower(self, amount):
        for _ in range(amount):
            if not self.holopower:
                logger.warning("spend_holopower: not enough holopower (requested %d)", amount)
                break
            top_holopower_id = self.holopower[0]["game_card_id"]
            self.move_card(top_holopower_id, "archive")

    def get_oshi_action_effects(self, skill_id):
        action = next(action for action in self.oshi_card["actions"] if action["skill_id"] == skill_id)
        return deepcopy(action["effects"])

    def get_special_action_effects(self, card_id: str, effect_id: str):
        card, _, _ = self.find_card(card_id, include_stacked_cards=True)
        for action in card.get("special_actions", []):
            if action["effect_id"] == effect_id:
                return deepcopy(action["effects"])
        for gift in card.get("gift_effects", []):
            if gift.get("effect_id") == effect_id:
                return deepcopy(gift["effects"])
        raise StopIteration(f"Special action {effect_id} not found on card {card_id}")
    def find_and_remove_attached(self, attached_id):
        previous_holder_id = None
        found_card = None
        for card in self.get_holomem_on_stage():
            if attached_id in ids_from_cards(card["attached_cheer"]):
                found_card = next(c for c in card["attached_cheer"] if c["game_card_id"] == attached_id)
                previous_holder_id = card["game_card_id"]
                card["attached_cheer"].remove(found_card)
                break
            if attached_id in ids_from_cards(card["attached_support"]):
                found_card = next(c for c in card["attached_support"] if c["game_card_id"] == attached_id)
                previous_holder_id = card["game_card_id"]
                card["attached_support"].remove(found_card)
                break
            if attached_id in ids_from_cards(card["stacked_cards"]):
                found_card = next(c for c in card["stacked_cards"] if c["game_card_id"] == attached_id)
                previous_holder_id = card["game_card_id"]
                card["stacked_cards"].remove(found_card)
                break
        if not previous_holder_id:
            if attached_id in ids_from_cards(self.life):
                found_card = next(c for c in self.life if c["game_card_id"] == attached_id)
                self.life.remove(found_card)
                previous_holder_id = "life"
            elif attached_id in ids_from_cards(self.archive):
                found_card = next(c for c in self.archive if c["game_card_id"] == attached_id)
                self.archive.remove(found_card)
                previous_holder_id = "archive"
            elif attached_id in ids_from_cards(self.cheer_deck):
                found_card = next(c for c in self.cheer_deck if c["game_card_id"] == attached_id)
                self.cheer_deck.remove(found_card)
                previous_holder_id = "cheer_deck"
        return found_card, previous_holder_id

    def find_and_remove_support(self, support_id):
        previous_holder_id = None
        support_card = None
        for card in self.get_holomem_on_stage():
            if support_id in ids_from_cards(card["attached_support"]):
                support_card = next(c for c in card["attached_support"] if c["game_card_id"] == support_id)
                previous_holder_id = card["game_card_id"]
                card["attached_support"].remove(support_card)
                break
        return support_card, previous_holder_id

    def move_cheer_between_holomems(self, placements):
        for cheer_id, target_id in placements.items():
            # Find and remove the cheer from its current spot.
            if target_id == "archive":
                self.archive_attached_cards([cheer_id])
            elif target_id == "cheer_deck_bottom":
                cheer_card, previous_holder_id = self.find_and_remove_attached(cheer_id)
                if cheer_card:
                    self.cheer_deck.append(cheer_card)
                    move_cheer_event = {
                        "event_type": EventType.EventType_MoveAttachedCard,
                        "owning_player_id": self.player_id,
                        "from_holomem_id": previous_holder_id,
                        "to_holomem_id": "cheer_deck",
                        "attached_id": cheer_id,
                    }
                    self.engine.broadcast_event(move_cheer_event)
            else:
                cheer_card, previous_holder_id = self.find_and_remove_attached(cheer_id)
                if cheer_card:
                    # Attach to the target.
                    target_card, _, _ = self.find_card(target_id)
                    target_card["attached_cheer"].append(cheer_card)

                    move_cheer_event = {
                        "event_type": EventType.EventType_MoveAttachedCard,
                        "owning_player_id": self.player_id,
                        "from_holomem_id": previous_holder_id,
                        "to_holomem_id": target_card["game_card_id"],
                        "attached_id": cheer_id,
                    }
                    self.engine.broadcast_event(move_cheer_event)

    def archive_attached_cards(self, attached_ids):
        for attached_id in attached_ids:
            attached_card, previous_holder_id = self.find_and_remove_attached(attached_id)
            if attached_card:
                self.archive.insert(0, attached_card)
                move_attached_event = {
                    "event_type": EventType.EventType_MoveAttachedCard,
                    "owning_player_id": self.player_id,
                    "from_holomem_id": previous_holder_id,
                    "to_holomem_id": "archive",
                    "attached_id": attached_id,
                }
                self.engine.broadcast_event(move_attached_event)

    def archive_holomem_from_play(self, card_id, stacked_cards_to_hand_ids=None):
        if stacked_cards_to_hand_ids is None:
            stacked_cards_to_hand_ids = []
        card, _, zone_name = self.find_and_remove_card(card_id)
        attached_cheer = card["attached_cheer"]
        attached_support = card["attached_support"]
        stacked_cards = card["stacked_cards"]
        card["zone_when_downed"] = zone_name
        card["attached_when_downed"] = attached_support.copy()
        card["attached_cheer"] = []
        card["attached_support"] = []
        card["stacked_cards"] = []

        to_archive = attached_cheer + attached_support
        to_hand = []
        hand_ids = []

        # Separate stacked cards: some go to hand, rest to archive
        for stacked_card in stacked_cards:
            if stacked_card["game_card_id"] in stacked_cards_to_hand_ids:
                to_hand.append(stacked_card)
            else:
                to_archive.append(stacked_card)

        # Check if the downed card itself should go to hand
        if card_id in stacked_cards_to_hand_ids:
            to_hand.append(card)
        else:
            self.archive.insert(0, card)

        for extra_card in to_archive:
            self.archive.insert(0, extra_card)
        for hand_card in to_hand:
            self.hand.append(hand_card)
            self.reset_card_stats(hand_card)

        hand_ids = ids_from_cards(to_hand)
        return ids_from_cards(to_archive), hand_ids

    def return_holomem_to_hand(self, card_id, include_stacked_holomem = False):
        returning_card, _, zone_name = self.find_and_remove_card(card_id)
        returning_card["zone_when_returned_to_hand"] = zone_name
        attached_cheer = returning_card["attached_cheer"]
        attached_support = returning_card["attached_support"]
        stacked_cards = returning_card["stacked_cards"]

        archived_ids = []
        hand_ids = []

        to_archive = attached_cheer + attached_support
        to_hand = [returning_card] # Make sure to grab the actual card itself.

        if include_stacked_holomem:
            to_hand += stacked_cards
        else:
            to_archive += stacked_cards

        for card in to_archive:
            self.archive.insert(0, card)
        for card in to_hand:
            self.hand.append(card)
            self.reset_card_stats(card)
        archived_ids = ids_from_cards(to_archive)
        hand_ids = ids_from_cards(to_hand)

        return archived_ids, hand_ids

    def swap_center_with_back(self, back_id):
        if len(self.center) == 0:
            return

        self.move_card(self.center[0]["game_card_id"], "backstage")
        self.move_card(back_id, "center")

    def swap_center_with_collab(self):
        if len(self.center) == 0 or len(self.collab) == 0:
            return
        center_id = self.center[0]["game_card_id"]
        collab_id = self.collab[0]["game_card_id"]
        self.move_card(center_id, "collab")
        self.move_card(collab_id, "center")

    def add_turn_effect(self, turn_effect):
        self.turn_effects.append(turn_effect)

    def set_holomem_hp(self, card_id, target_hp):
        card, _, _ = self.find_card(card_id)
        # TODO: 추후 "HP 변화 불가" 효과 체크 로직 추가 예정
        previous_damage = card["damage"]
        new_damage = self.get_card_hp(card) - target_hp
        if new_damage > previous_damage:
            card["damage"] = new_damage
            modify_hp_event = {
                "event_type": EventType.EventType_ModifyHP,
                "target_player_id": self.player_id,
                "card_id": card_id,
                "damage_done": new_damage - previous_damage,
                "new_damage": new_damage,
                "current_hp": target_hp,
            }
            self.engine.broadcast_event(modify_hp_event)

    def restore_holomem_hp(self, card_id, amount):
        card, _, _ = self.find_card(card_id)
        healed_amount = 0
        if amount == "all":
            healed_amount = card["damage"]
        elif amount == "damage_dealt_floor_round_to_10s":
            if self.engine.after_damage_state:
                damage_dealt = self.engine.after_damage_state.damage_dealt
                healed_amount = 10 * (damage_dealt // 10)
                healed_amount = min(healed_amount, card["damage"])
        elif amount == "restore_hp_per_cheer_color_types_10s":
            multiplier = len(self.get_cheer_color_types_on_holomems())
            healed_amount = 10 * multiplier
            healed_amount = min(healed_amount, card["damage"])
        else:
            healed_amount = min(amount, card["damage"])
        if healed_amount > 0:
            card["damage"] -= healed_amount
            modify_hp_event = {
                "event_type": EventType.EventType_RestoreHP,
                "target_player_id": self.player_id,
                "card_id": card_id,
                "healed_amount": healed_amount,
                "new_damage": card["damage"],
            }
            self.engine.broadcast_event(modify_hp_event)
