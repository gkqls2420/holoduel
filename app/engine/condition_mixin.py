from __future__ import annotations
from typing import TYPE_CHECKING
from copy import deepcopy

from app.engine.constants import *
from app.engine.models import *
from app.engine.helpers import *

if TYPE_CHECKING:
    from app.engine.player_state import PlayerState

class ConditionMixin:
    def are_conditions_met(self, effect_player: PlayerState, source_card_id, conditions):
        for condition in conditions:
           if not self.is_condition_met(effect_player, source_card_id, condition):
               return False
        return True
    def is_condition_met(self, effect_player: PlayerState, source_card_id, condition):
        match condition["condition"]:
            case Condition.Condition_Or:
                or_conditions = condition.get("or_conditions", [])
                for or_cond in or_conditions:
                    if self.is_condition_met(effect_player, source_card_id, or_cond):
                        return True
                return False
            case Condition.Condition_AnyHolomemBloomedThisTurn:
                return any(holomem.get("bloomed_this_turn", False) for holomem in effect_player.get_holomem_on_stage())
            case Condition.Condition_AnyTagHolomemHasCheer:
                valid_tags = condition["condition_tags"]
                for card in effect_player.get_holomem_on_stage():
                    for tag in card["tags"]:
                        if tag in valid_tags and len(card["attached_cheer"]) > 0:
                            return True
                return False
            case Condition.Condition_AttachedTo:
                required_member_name = condition["required_member_name"]
                required_bloom_levels = condition.get("required_bloom_levels", [])
                # Determine if source_card_id is attached to a holomem with the required name.
                source_card = self.find_card(source_card_id)
                owner_player = self.get_player(source_card["owner_id"])
                holomems = owner_player.get_holomem_on_stage()
                for holomem in holomems:
                    if source_card_id in ids_from_cards(holomem["attached_support"]):
                        if required_member_name in holomem["card_names"]:
                            if not required_bloom_levels or holomem.get("bloom_level", -1) in required_bloom_levels:
                                return True
                # Check if there is an after damage state and if this the target card had this attached.
                if self.after_damage_state and source_card_id in ids_from_cards(self.after_damage_state.target_card["attached_when_downed"]):
                    if required_member_name in self.after_damage_state.target_card["card_names"]:
                        if not required_bloom_levels or self.after_damage_state.target_card.get("bloom_level", -1) in required_bloom_levels:
                            return True
                return False
            case Condition.Condition_AttachedToHasTags:
                inverse = condition.get("inverse", False) # XOR the result to get the inverse
                required_bloom_levels = condition.get("required_bloom_levels", [])
                source_card = self.find_card(source_card_id)
                owner_player = self.get_player(source_card["owner_id"])
                holomems = owner_player.get_holomem_on_stage()
                for holomem in holomems:
                    if source_card_id in ids_from_cards(holomem["attached_support"]):
                        has_tag = len(set(holomem["tags"]) & set(condition["required_tags"])) > 0
                        bloom_ok = not required_bloom_levels or holomem.get("bloom_level", -1) in required_bloom_levels
                        return (has_tag and bloom_ok) ^ inverse
                return False ^ inverse
            case Condition.Condition_AttachedToIsCardType:
                condition_card_types = condition["condition_card_types"]
                source_card = self.find_card(source_card_id)
                owner_player = self.get_player(source_card["owner_id"])
                holomems = owner_player.get_holomem_on_stage()
                for holomem in holomems:
                    if source_card_id in ids_from_cards(holomem["attached_support"]):
                        if holomem["card_type"] in condition_card_types:
                            return True
                return False
            case Condition.Condition_AttachedOwnerIsLocation:
                required_location = condition["condition_location"]
                holomems = effect_player.get_holomems_with_attachment(source_card_id)
                if holomems:
                    match required_location:
                        case "backstage":
                            return holomems[0] in effect_player.backstage
                        case "center":
                            return holomems[0] in effect_player.center
                        case "collab":
                            return holomems[0] in effect_player.collab
                        case "center_or_collab":
                            if holomems[0] in effect_player.center + effect_player.collab:
                                return True
                return False
            case Condition.Condition_AttachedOwnerIsPerforming:
                holomems = effect_player.get_holomems_with_attachment(source_card_id)
                return self.performance_performer_card and self.performance_performer_card["game_card_id"] in ids_from_cards(holomems)
            case Condition.Condition_AttachedOwnerIsBuzz:
                holomems = effect_player.get_holomems_with_attachment(source_card_id)
                if holomems:
                    return holomems[0].get("buzz", False)
                return False
            case Condition.Condition_AttachedOwnerHasCheer:
                amount_min = condition.get("amount_min", 1)
                condition_colors = condition.get("condition_colors", ["any"])
                holomems = effect_player.get_holomems_with_attachment(source_card_id)
                if holomems:
                    owner = holomems[0]
                    cheer_count = 0
                    for cheer in owner.get("attached_cheer", []):
                        if "any" in condition_colors or any(color in cheer["colors"] for color in condition_colors):
                            cheer_count += 1
                    return cheer_count >= amount_min
                return False
            case Condition.Condition_AttachedOwnerUsedArtThisTurn:
                holomems = effect_player.get_holomems_with_attachment(source_card_id)
                if holomems:
                    return holomems[0].get("used_art_this_turn", False)
                return False
            case Condition.Condition_BloomFromBuzz:
                source_card, _, _ = effect_player.find_card(source_card_id)
                if source_card and len(source_card.get("stacked_cards", [])) > 0:
                    return source_card["stacked_cards"][0].get("buzz", False)
                return False
            case Condition.Condition_BloomTargetIsDebut:
                bloom_card, _, _ = effect_player.find_card(source_card_id)
                # Bloom target is always in the 0 slot.
                target_card = bloom_card["stacked_cards"][0]
                return target_card["card_type"] == "holomem_debut"
            case Condition.Condition_CanArchiveFromHand:
                amount_min = condition.get("amount_min", 1)
                requirement = condition.get("requirement", None)
                requirement_same_tag = condition.get("requirement_same_tag", False)
                condition_source = condition["condition_source"]
                return effect_player.can_archive_from_hand(amount_min, condition_source, requirement, requirement_same_tag)
            case Condition.Condition_CanMoveFrontStage:
                return effect_player.can_move_front_stage()
            case Condition.Condition_CardsInDeck:
                amount_min = condition.get("amount_min", -1)
                amount_max = condition.get("amount_max", -1)
                if amount_max == -1:
                    amount_max = UNLIMITED_SIZE
                return amount_min <= len(effect_player.deck) <= amount_max
            case Condition.Condition_CardsInHand:
                amount_min = condition.get("amount_min", -1)
                amount_max = condition.get("amount_max", -1)
                if amount_max == -1:
                    amount_max = UNLIMITED_SIZE
                return amount_min <= len(effect_player.hand) <= amount_max
            case Condition.Condition_CardTypeInHand:
                card_types = condition["condition_card_types"]
                return any(card["card_type"] in card_types for card in effect_player.hand)
            case Condition.Condition_CenterHasDamage:
                if len(effect_player.center) == 0:
                    return False
                return effect_player.center[0].get("damage", 0) > 0
            case Condition.Condition_CenterIsColor:
                if len(effect_player.center) == 0:
                    return False
                condition_colors = condition["condition_colors"]
                center_colors = effect_player.center[0]["colors"]
                if any(color in center_colors for color in condition_colors):
                    return True
            case Condition.Condition_CenterHasAnyTag:
                valid_tags = condition["condition_tags"]
                if len(effect_player.center) == 0:
                    return False
                center_card = effect_player.center[0]
                for tag in center_card["tags"]:
                    if tag in valid_tags:
                        return True
                return False
            case Condition.Condition_CenterIsMemberName:
                if len(effect_player.center) == 0:
                    return False
                required_member_names = condition["required_member_names"]
                center_card = effect_player.center[0]
                return any(name in center_card["card_names"] for name in required_member_names)
            case Condition.Condition_CenterBloomLevel:
                target_player = effect_player
                if condition.get("opponent", False):
                    target_player = self.other_player(effect_player.player_id)
                if len(target_player.center) == 0:
                    return False
                required_bloom_level = condition["required_bloom_level"]
                center_card = target_player.center[0]
                return center_card.get("bloom_level", 0) == required_bloom_level
            case Condition.Condition_CenterHasCheerCount:
                if len(effect_player.center) == 0:
                    return False
                amount_min = condition["amount_min"]
                center_card = effect_player.center[0]
                condition_colors = condition.get("condition_colors", ["any"])
                cheer_count = 0
                for cheer in center_card.get("attached_cheer", []):
                    if "any" in condition_colors or any(color in cheer["colors"] for color in condition_colors):
                        cheer_count += 1
                return amount_min <= cheer_count
            case Condition.Condition_CheerInPlay:
                amount_min = condition["amount_min"]
                amount_max = condition["amount_max"]
                if amount_max == -1:
                    amount_max = UNLIMITED_SIZE
                return amount_min <= len(effect_player.get_cheer_ids_on_holomems()) <= amount_max
            case Condition.Condition_CheerOnBothStages:
                amount_min = condition.get("amount_min", 0)
                amount_max = condition.get("amount_max", -1)
                if amount_max == -1:
                    amount_max = UNLIMITED_SIZE
                cheer_color = condition.get("cheer_color", "any")
                count = 0
                for player in self.player_states:
                    for holomem in player.get_holomem_on_stage():
                        for cheer in holomem["attached_cheer"]:
                            if cheer_color == "any" or cheer_color in cheer.get("colors", []):
                                count += 1
                return amount_min <= count <= amount_max
            case Condition.Condition_ChosenCardHasTag:
                if len(self.last_chosen_cards) == 0:
                    return False
                chosen_card_id = self.last_chosen_cards[0]
                chosen_card = self.find_card(chosen_card_id)
                valid_tags = condition["condition_tags"]
                return any(tag in chosen_card["tags"] for tag in valid_tags)
            case Condition.Condition_ChosenCardCount:
                amount_min = condition.get("amount_min", 0)
                return len(self.last_chosen_cards) >= amount_min
            case Condition.Condition_CollabWith:
                required_member_name = condition["required_member_name"]
                holomems = effect_player.get_holomem_on_stage(only_performers=True)
                return any(required_member_name in holomem["card_names"] for holomem in holomems)
            case Condition.Condition_DamageAbilityIsColor:
                condition_color = condition["condition_color"]
                include_oshi_ability = condition.get("include_oshi_ability", False)
                damage_source = self.after_damage_state.source_card
                if damage_source["card_type"] == "oshi":
                    return include_oshi_ability
                return condition_color in damage_source["colors"]
            case Condition.Condition_DamagedHolomemIsBackstage:
                still_on_stage_required = condition.get("still_on_stage", False)
                if still_on_stage_required and not self.after_damage_state.target_still_on_stage:
                    return False
                return self.after_damage_state.target_card_zone == "backstage"
            case Condition.Condition_DamagedHolomemIsCenterOrCollab:
                return self.after_damage_state.target_card_zone in ["center", "collab"]
            case Condition.Condition_DamageTargetIsCenterOrCollab:
                return self.take_damage_state.target_card_zone in ["center", "collab"]
            case Condition.Condition_DamageSourceIsOpponent:
                return self.take_damage_state.source_player.player_id != effect_player.player_id
            case Condition.Condition_DamageIsSpecial:
                return self.take_damage_state.special
            case Condition.Condition_DamageIsNotSpecial:
                return not self.take_damage_state.special
            case Condition.Condition_DamageNotFromArt:
                return not bool(self.take_damage_state.art_info)
            case Condition.Condition_DamageSourceHasNameIn:
                required_names = condition["condition_names"]
                source_card = self.take_damage_state.source_card
                if source_card and "card_names" in source_card:
                    return any(name in source_card["card_names"] for name in required_names)
                return False
            case Condition.Condition_DamageTargetIsCenter:
                target_zone = self.take_damage_state.target_card_zone
                return target_zone == "center"
            case Condition.Condition_DamageTargetIsBackstage:
                target_zone = self.take_damage_state.target_card_zone
                return target_zone == "backstage"
            case Condition.Condition_DamageTargetIsDebut:
                target_card = self.take_damage_state.target_card
                return target_card and target_card.get("card_type") == "holomem_debut"
            case Condition.Condition_DamageSourceBloomLevel:
                required_bloom_level = condition.get("condition_bloom_level", 1)
                source_card = self.take_damage_state.source_card
                if source_card and source_card.get("card_type") == "holomem_bloom":
                    return source_card.get("bloom_level", 0) == required_bloom_level
                return False
            case Condition.Condition_DownedCardBelongsToOpponent:
                source_card = self.find_card(source_card_id)
                owner_player = self.get_player(source_card["owner_id"])
                return owner_player.player_id != self.down_holomem_state.holomem_card["owner_id"]
            case Condition.Condition_DownedCardIsColor:
                downed_card = self.down_holomem_state.holomem_card
                condition_color = condition["condition_color"]
                return condition_color in downed_card["colors"]
            case Condition.Condition_DownedCardIsThis:
                # Check if the downed card is the source card (the card with this effect)
                if self.down_holomem_state and self.down_holomem_state.holomem_card:
                    downed_card = self.down_holomem_state.holomem_card
                    return source_card_id == downed_card["game_card_id"]
                return False
            case Condition.Condition_DownedCardHasAnyTag:
                # Check if the downed card has any of the specified tags
                if self.down_holomem_state and self.down_holomem_state.holomem_card:
                    downed_card = self.down_holomem_state.holomem_card
                    condition_tags = condition.get("condition_tags", [])
                    card_tags = downed_card.get("tags", [])
                    return any(tag in card_tags for tag in condition_tags)
                return False
            case Condition.Condition_DownedCardNameIs:
                if self.down_holomem_state and self.down_holomem_state.holomem_card:
                    downed_card = self.down_holomem_state.holomem_card
                    required_name = condition["required_member_name"]
                    return required_name in downed_card.get("card_names", [])
                return False
            case Condition.Condition_DownedCardIsBuzzOr2nd:
                # Check if the downed card is buzz or bloom_level 2
                if self.down_holomem_state and self.down_holomem_state.holomem_card:
                    downed_card = self.down_holomem_state.holomem_card
                    is_buzz = downed_card.get("buzz", False)
                    bloom_level = downed_card.get("bloom_level", 0)
                    return is_buzz or bloom_level == 2
                return False
            case Condition.Condition_DownedCardWasBackstage:
                if self.down_holomem_state and self.down_holomem_state.holomem_card:
                    downed_card = self.down_holomem_state.holomem_card
                    downed_player = self.get_player(downed_card["owner_id"])
                    return downed_player.get_holomem_zone(downed_card) == "backstage"
                return False
            case Condition.Condition_DownedCardWasCenter:
                if self.down_holomem_state and self.down_holomem_state.holomem_card:
                    downed_card = self.down_holomem_state.holomem_card
                    downed_player = self.get_player(downed_card["owner_id"])
                    return downed_player.get_holomem_zone(downed_card) == "center"
                return False
            case Condition.Condition_EffectCardIdNotUsedThisTurn:
                return not effect_player.has_used_card_effect_this_turn(source_card_id)
            case Condition.Condition_HasAttachedCard:
                required_card_name = condition["required_card_name"]
                amount_min = condition.get("amount_min", 0)
                source_card = self.find_card(source_card_id)
                if amount_min > 0:
                    count = sum(1 for support in source_card["attached_support"]
                                if required_card_name in support["card_names"])
                    return count >= amount_min
                for support in source_card["attached_support"]:
                    if required_card_name in support["card_names"]:
                        return True
                return False
            case Condition.Condition_HasAttachmentWithAnyTag:
                condition_tags = condition["condition_tags"]
                source_card = self.find_card(source_card_id)
                for support in source_card["attached_support"]:
                    if any(tag in support.get("tags", []) for tag in condition_tags):
                        return True
                return False
            case Condition.Condition_HasAttachmentOfType:
                attachment_type = condition["condition_type"]
                card, _, _ = effect_player.find_card(source_card_id)
                for attachment in card["attached_support"]:
                    if "sub_type" in attachment and attachment["sub_type"] == attachment_type:
                        return True
                return False
            case Condition.Condition_HasAttachmentOfTypesAny:
                attachment_types: list = condition["condition_types"]
                card, _, _ = effect_player.find_card(source_card_id)
                for attachment in card["attached_support"]:
                    if attachment.get("sub_type") in attachment_types:
                        return True
                return False
            case Condition.Condition_HasStackedHolomem:
                amount_max = condition.get("amount_max", 999)
                default_min = 0 if "amount_max" in condition else 1
                amount_min = condition.get("amount_min", default_min)
                card, _, _ = effect_player.find_card(source_card_id)
                if card is None:
                    holomems = effect_player.get_holomems_with_attachment(source_card_id)
                    card = holomems[0] if holomems else None
                if card is None:
                    return False
                stacked_holomems = [c for c in card.get("stacked_cards", []) if is_card_holomem(c)]
                count = len(stacked_holomems)
                return amount_min <= count <= amount_max
            case Condition.Condition_HolomemInArchive:
                holomems = [holomem for holomem in effect_player.archive if is_card_holomem(holomem)]
                if "tag_in" in condition:
                    tags = condition["tag_in"]
                    holomems = [holomem for holomem in holomems if any(tag in holomem["tags"] for tag in tags)]

                amount_min = condition.get("amount_min", 1)
                amount_max = condition.get("amount_max", len(holomems))
                return amount_min <= len(holomems) <= amount_max
            case Condition.Condition_HolomemOnStage:
                target_player = self.other_player(effect_player.player_id) if condition.get("opponent", False) else effect_player
                holomems = []
                match condition.get("location"):
                    case "center":
                        holomems = target_player.center
                    case "collab":
                        holomems = target_player.collab
                    case _:
                        holomems = target_player.get_holomem_on_stage()

                if condition.get("is_buzz", False):
                    holomems = [h for h in holomems if h.get("buzz", False)]

                if "required_bloom_levels" in condition:
                    required_bloom_levels = condition["required_bloom_levels"]
                    holomems = [h for h in holomems if h.get("bloom_level", -1) in required_bloom_levels]

                if "required_member_name_in" in condition:
                    required_names_in = condition["required_member_name_in"]
                    return any(member_name in holomem["card_names"] for member_name in required_names_in for holomem in holomems)
                elif "exclude_member_name_in" in condition:
                    exclude_names_in = condition["exclude_member_name_in"]
                    if "tag_in" in condition:
                        tags = condition["tag_in"]
                        for holomem in holomems:
                            if any(exclude_name in holomem["card_names"] for exclude_name in exclude_names_in):
                                continue
                            if any(tag in holomem["tags"] for tag in tags):
                                return True
                else:
                    # No specific member needed, but still check tags (bloom_levels already filtered above).
                    filtered_holomems = holomems
                    if "tag_in" in condition:
                        tags = condition["tag_in"]
                        filtered_holomems = [h for h in filtered_holomems if any(tag in h["tags"] for tag in tags)]

                    # Check amount_min if specified
                    if "amount_min" in condition:
                        amount_min = condition["amount_min"]
                        return len(filtered_holomems) >= amount_min
                    else:
                        # Original behavior: return True if any holomem matches
                        return len(filtered_holomems) > 0
                return False
            case Condition.Condition_IsGoingSecondAndFirstTurn:
                is_going_second = effect_player.player_id != self.first_turn_player_id
                is_first_turn = effect_player.first_turn
                return is_going_second and is_first_turn
            case Condition.Condition_IsNotArtRepeat:
                return not self.performance_artstatboosts.is_repeat
            case Condition.Condition_LastDieRolls:
                match condition.get("roll_results"):
                    case "any_odd":
                        return any([value % 2 == 1 for value in effect_player.last_die_roll_results])
                return False
            case Condition.Condition_DieRolledByHolomemName:
                # Check if any of the specified holomem names rolled a die this turn
                condition_names = condition.get("condition_names", [])
                for name in condition_names:
                    if name in effect_player.die_rolled_by_holomem_names_this_turn:
                        return True
                return False
            case Condition.Condition_LastDieSumIsOdd:
                # Check if sum of last die roll results is odd
                if not effect_player.last_die_roll_results:
                    return False
                return sum(effect_player.last_die_roll_results) % 2 == 1
            case Condition.Condition_LastDieSumIsEven:
                # Check if sum of last die roll results is even
                if not effect_player.last_die_roll_results:
                    return False
                return sum(effect_player.last_die_roll_results) % 2 == 0
            case Condition.Condition_DieRolledThisArt:
                # Check if any die was rolled during this art (last_die_roll_results is not empty)
                return len(effect_player.last_die_roll_results) > 0
            case Condition.Condition_HolopowerAtLeast:
                amount = condition["amount"]
                return len(effect_player.holopower) >= amount
            case Condition.Condition_NotUsedOncePerGameEffect:
                condition_effect_id = condition["condition_effect_id"]
                return not effect_player.has_used_once_per_game_effect(condition_effect_id)
            case Condition.Condition_UsedOncePerGameEffect:
                condition_effect_id = condition["condition_effect_id"]
                return effect_player.has_used_once_per_game_effect(condition_effect_id)
            case Condition.Condition_NotUsedOncePerTurnEffect:
                condition_effect_id = condition["condition_effect_id"]
                max_uses = 1
                for holomem in effect_player.get_holomem_on_stage():
                    for attached_card in holomem.get("attached_support", []):
                        for ae in attached_card.get("attached_effects", []):
                            if not isinstance(ae, dict):
                                continue
                            if ae.get("effect_type") == EffectType.EffectType_ModifyOshiSkillLimit:
                                if ae.get("target_skill_id") == condition_effect_id:
                                    ae_conditions = ae.get("conditions", [])
                                    if self.are_conditions_met(effect_player, attached_card["game_card_id"], ae_conditions):
                                        max_uses = max(max_uses, ae["new_max_uses"])
                current_uses = effect_player.effects_used_this_turn.get(condition_effect_id, 0)
                return current_uses < max_uses
            case Condition.Condition_UsedOncePerTurnEffect:
                condition_effect_id = condition["condition_effect_id"]
                return effect_player.has_used_once_per_turn_effect(condition_effect_id)
            case Condition.Condition_OpponentTurn:
                return self.active_player_id != effect_player.player_id
            case Condition.Condition_OpponentMainStep:
                if self.active_player_id == effect_player.player_id:
                    return False
                return self.current_decision is not None and self.current_decision.get("decision_type") == DecisionType.DecisionMainStep
            case Condition.Condition_OshiIs:
                required_member_name = condition["required_member_name"]
                return required_member_name in effect_player.oshi_card["card_names"]
            case Condition.Condition_OshiIsColor:
                condition_colors = condition["condition_colors"]
                for color in condition_colors:
                    if color in effect_player.oshi_card["colors"]:
                        return True
                return False
            case Condition.Condition_PerformanceTargetHasDamageOverHp:
                if not self.performance_target_card or not self.performance_target_player:
                    return False
                amount = condition["amount"]
                return self.performance_target_card["damage"] >= self.performance_target_player.get_card_hp(self.performance_target_card) + amount
            case Condition.Condition_PerformerIsCenter:
                performing_player = self.performance_performing_player or effect_player
                performer_card_id = self.performance_performer_card["game_card_id"] if self.performance_performer_card else source_card_id
                if len(performing_player.center) == 0:
                    return False
                return performing_player.center[0]["game_card_id"] == performer_card_id
            case Condition.Condition_PerformerIsCollab:
                performing_player = self.performance_performing_player or effect_player
                performer_card_id = self.performance_performer_card["game_card_id"] if self.performance_performer_card else source_card_id
                if len(performing_player.collab) == 0:
                    return False
                return performing_player.collab[0]["game_card_id"] == performer_card_id
            case Condition.Condition_PerformerIsColor:
                if not self.performance_performer_card:
                    return False
                condition_colors = condition["condition_colors"]
                for color in self.performance_performer_card["colors"]:
                    if color in condition_colors:
                        return True
                return False
            case Condition.Condition_PerformerIsSpecificId:
                if not self.performance_performer_card:
                    return False
                required_id = condition["required_id"]
                return self.performance_performer_card["game_card_id"] == required_id
            case Condition.Condition_PerformerHasAnyTag:
                if not self.performance_performer_card:
                    return False
                valid_tags = condition["condition_tags"]
                for tag in self.performance_performer_card["tags"]:
                    if tag in valid_tags:
                        return True
                return False
            case Condition.Condition_PerformerHasAttachmentOfType:
                if not self.performance_performer_card:
                    return False
                attachment_type = condition["condition_type"]
                for attachment in self.performance_performer_card["attached_support"]:
                    if attachment.get("sub_type") == attachment_type:
                        return True
                return False
            case Condition.Condition_PerformerBloomLevel:
                if not self.performance_performer_card:
                    return False
                required_bloom_level = condition["condition_bloom_level"]
                performer_bloom_level = self.performance_performer_card.get("bloom_level", -1)
                return performer_bloom_level == required_bloom_level
            case Condition.Condition_PerformerHasDamage:
                if not self.performance_performer_card:
                    return False
                return self.performance_performer_card.get("damage", 0) > 0
            case Condition.Condition_PerformerIsMemberName:
                if not self.performance_performer_card:
                    return False
                required_member_names = condition["required_member_names"]
                return any(name in self.performance_performer_card["card_names"] for name in required_member_names)
            case Condition.Condition_PerformerIsBuzz:
                if not self.performance_performer_card:
                    return False
                return self.performance_performer_card.get("buzz", False)
            case Condition.Condition_PlayedSupportThisTurn:
                if "condition_sub_types" in condition:
                    required_types = condition["condition_sub_types"]
                    return any(effect_player.played_support_types_this_turn.get(t, 0) > 0 for t in required_types)
                return effect_player.played_support_this_turn
            case Condition.Condition_SupportCardNameUsedThisTurn:
                condition_card_names = condition.get("condition_card_names", [])
                for card_name in condition_card_names:
                    if card_name in effect_player.support_card_names_used_this_turn:
                        return True
                return False
            case Condition.Condition_SupportCardTagUsedThisTurn:
                condition_tags = condition.get("condition_tags", [])
                for tag in condition_tags:
                    if tag in effect_player.support_card_tags_used_this_turn:
                        return True
                return False
            case Condition.Condition_RevealedCardsCount:
                amount_min = condition["amount_min"]
                return len(effect_player.last_revealed_cards) >= amount_min
            case Condition.Condition_RevealedCardsHaveSameType:
                revealed_cards = effect_player.last_revealed_cards
                if len(revealed_cards) == 0:
                    return False
                match condition.get("condition_same_type"):
                    case "holomem_same_bloom":
                        # Cards should be holomem and of the same bloom level (Debut is level 0)
                        base_card = revealed_cards[0] # the card that the rest of the cards will be compared to
                        if not is_card_holomem(base_card):
                            return False
                        card_type = base_card["card_type"]
                        bloom_level = base_card.get("bloom_level", 0)
                        return all([card["card_type"] == card_type and card.get("bloom_level", 0) == bloom_level for card in revealed_cards[1:]])
                return False
            case Condition.Condition_SelfStageHasCheerColorTypes:
                amount_min = condition["amount_min"]
                source_card, _, _ = effect_player.find_card(source_card_id)
                if source_card:
                    return amount_min <= len(effect_player.get_cheer_color_types_on_holomems())
                return False
            case Condition.Condition_SelfHasCheerColor:
                condition_colors = condition["condition_colors"]
                amount_min = condition["amount_min"]
                exclude = condition.get("exclude", False)
                source_card, _, _ = effect_player.find_card(source_card_id)
                if source_card:
                    cheer_of_matched_colors = 0
                    for cheer in source_card["attached_cheer"]:
                        if exclude:
                            if not any(color in cheer["colors"] for color in condition_colors):
                                cheer_of_matched_colors += 1
                        else:
                            if "any" in condition_colors or any(color in cheer["colors"] for color in condition_colors):
                                cheer_of_matched_colors += 1
                    return amount_min <= cheer_of_matched_colors
                return False
            case Condition.Condition_SelfStageCheerLessThanOpponent:
                self_cheer = sum(len(h["attached_cheer"]) for h in effect_player.get_holomem_on_stage())
                opponent = self.other_player(effect_player.player_id)
                opponent_cheer = sum(len(h["attached_cheer"]) for h in opponent.get_holomem_on_stage())
                return self_cheer < opponent_cheer
            case Condition.Condition_SelfZoneHasHolomem:
                zone = condition["condition_zone"]
                match zone:
                    case "center":
                        return len(effect_player.center) > 0
                    case "collab":
                        return len(effect_player.collab) > 0
                    case "backstage":
                        return len(effect_player.backstage) > 0
                return False
            case Condition.Condition_OpponentZoneHasHolomem:
                zone = condition["condition_zone"]
                opponent = self.other_player(effect_player.player_id)
                match zone:
                    case "center":
                        return len(opponent.center) > 0
                    case "collab":
                        return len(opponent.collab) > 0
                    case "backstage":
                        return len(opponent.backstage) > 0
                return False
            case Condition.Condition_StageAllMembersHaveTag:
                required_tags = condition["required_tags"]
                holomems = effect_player.get_holomem_on_stage()
                if len(holomems) == 0:
                    return False
                for holomem in holomems:
                    if not any(tag in holomem.get("tags", []) for tag in required_tags):
                        return False
                return True
            case Condition.Condition_StageHasSpace:
                return len(effect_player.get_holomem_on_stage()) < MAX_MEMBERS_ON_STAGE
            case Condition.Condition_StageHasAttachmentsOfTypesCount:
                condition_types = condition.get("condition_types", [])
                amount_min = condition.get("amount_min", 1)
                target_player = effect_player
                if condition.get("opponent", False):
                    target_player = self.other_player(effect_player.player_id)
                condition_zone = condition.get("condition_zone", "stage")
                match condition_zone:
                    case "center":
                        holomems = target_player.center
                    case "collab":
                        holomems = target_player.collab
                    case _:
                        holomems = target_player.get_holomem_on_stage()
                total_count = 0
                for sub_type in condition_types:
                    total_count += len(get_cards_of_sub_type_from_holomems(sub_type, holomems))
                return total_count >= amount_min
            case Condition.Condition_StageHasAttachmentOfName:
                attachment_name = condition.get("attachment_name", "")
                inverse = condition.get("inverse", False)
                holomems = effect_player.get_holomem_on_stage()
                found = False
                for holomem in holomems:
                    for attached in holomem.get("attached_support", []):
                        if attachment_name in attached.get("card_names", []):
                            found = True
                            break
                    if found:
                        break
                return not found if inverse else found
            case Condition.Condition_TargetColor:
                if not self.performance_target_card:
                    return False
                color_requirement = condition["color_requirement"]
                return color_requirement in self.performance_target_card["colors"]
            case Condition.Condition_TargetHasDamage:
                if not self.performance_target_card:
                    return False
                return self.performance_target_card.get("damage", 0) > 0
            case Condition.Condition_TargetHasAnyTag:
                valid_tags = condition["condition_tags"]
                for tag in self.take_damage_state.target_card["tags"]:
                    if tag in valid_tags:
                        return True
                return False
            case Condition.Condition_TargetIsMemberName:
                valid_names = condition["condition_names"]
                for name in self.take_damage_state.target_card["card_names"]:
                    if name in valid_names:
                        return True
                return False
            case Condition.Condition_TargetHasAttachedCard:
                required_card_name = condition["required_card_name"]
                target_card = self.take_damage_state.target_card
                for support in target_card.get("attached_support", []):
                    if required_card_name in support["card_names"]:
                        return True
                return False
            case Condition.Condition_TargetIsBackstage:
                if not self.performance_target_card or not self.performance_target_player:
                    return False
                return self.performance_target_card in self.performance_target_player.backstage
            case Condition.Condition_TargetIsNotBackstage:
                if not self.performance_target_card or not self.performance_target_player:
                    return False
                return self.performance_target_card not in self.performance_target_player.backstage
            case Condition.Condition_TargetBloomLevel:
                if not self.performance_target_card:
                    return False
                required_bloom_level = condition["condition_bloom_level"]
                target_bloom_level = self.performance_target_card.get("bloom_level", -1)
                return target_bloom_level == required_bloom_level
            case Condition.Condition_ThisCardIsCenter:
                if len(effect_player.center) == 0:
                    return False
                return effect_player.center[0]["game_card_id"] == source_card_id
            case Condition.Condition_ThisCardIsCenterOrCollab:
                in_center = len(effect_player.center) > 0 and effect_player.center[0]["game_card_id"] == source_card_id
                in_collab = len(effect_player.collab) > 0 and effect_player.collab[0]["game_card_id"] == source_card_id
                return in_center or in_collab
            case Condition.Condition_ThisCardIsCollab:
                if len(effect_player.collab) == 0:
                    return False
                return effect_player.collab[0]["game_card_id"] == source_card_id
            case Condition.Condition_ThisCardIsBackstage:
                return source_card_id in ids_from_cards(effect_player.backstage)
            case Condition.Condition_ThisCardIsPerforming:
                return self.performance_performer_card and (self.performance_performer_card["game_card_id"] == source_card_id)
            case Condition.Condition_TopDeckCardHasAnyCardType:
                if len(effect_player.deck) == 0:
                    return False
                amount = condition.get("amount", 1)
                valid_card_types = condition["condition_card_types"]
                top_card_types = [card["card_type"] for card in effect_player.deck[:amount]]
                return any(valid_card_type in top_card_types for valid_card_type in valid_card_types)
            case Condition.Condition_TopDeckCardHasAnyTag:
                valid_tags = condition["condition_tags"]
                if len(effect_player.deck) == 0:
                    return False
                top_card = effect_player.deck[0]
                if "tags" in top_card:
                    for tag in top_card["tags"]:
                        if tag in valid_tags:
                            return True
                return False
            case Condition.Condition_ColorOnStage:
                holomems = effect_player.get_holomem_on_stage()
                condition_colors = condition["condition_colors"]
                return any(True for color in condition_colors for holomem in holomems if color in holomem["colors"])
            case Condition.Condition_LifeAtMost:
                amount = condition["amount"]
                return len(effect_player.life) <= amount
            case Condition.Condition_MonocolorDifferentColorsOnStage:
                # Check if stage has at least 2 monocolor holomems with different colors
                holomems = effect_player.get_holomem_on_stage()

                # Filter to only monocolor (single color) holomems
                monocolor_holomems = [h for h in holomems if len(h["colors"]) == 1]

                # Need at least 2 monocolor holomems
                if len(monocolor_holomems) < 2:
                    return False

                # Check if monocolor holomems have at least 2 different colors
                monocolor_colors = set()
                for holomem in monocolor_holomems:
                    monocolor_colors.update(holomem["colors"])

                return len(monocolor_colors) >= 2
            case Condition.Condition_OpponentBackstageHpReducedCount:
                opponent_player = self.other_player(effect_player.player_id)
                reduced_count = 0
                for holomem in opponent_player.backstage:
                    damage = holomem.get("damage", 0)
                    if damage > 0:
                        reduced_count += 1
                amount_min = condition.get("amount_min", 1)
                return reduced_count >= amount_min
            case Condition.Condition_OpponentBackstageTotalDamage:
                # 상대방 백스테이지 홀로멤 전원의 총 데미지가 amount_min 이상인지 확인
                opponent_player = self.other_player(effect_player.player_id)
                total_damage = 0
                for holomem in opponent_player.backstage:
                    total_damage += holomem.get("damage", 0)
                amount_min = condition.get("amount_min", 0)
                return total_damage >= amount_min
            case Condition.Condition_BloomFromOshiSkill:
                # 오시 스킬로 블룸했는지 확인 (특정 스킬 ID 지정 가능)
                required_skill_id = condition.get("skill_id", "")
                if required_skill_id:
                    return self.last_bloom_source_skill_id == required_skill_id
                return self.last_bloom_source_skill_id != ""
            case Condition.Condition_MyLifeLessThanOpponent:
                # 자신의 라이프가 상대보다 적은지 확인
                opponent = self.other_player(effect_player.player_id)
                return len(effect_player.life) < len(opponent.life)
            case Condition.Condition_OpponentHasNoCollab:
                opponent = self.other_player(effect_player.player_id)
                return len(opponent.collab) == 0
            case Condition.Condition_OpponentHasCollab:
                opponent = self.other_player(effect_player.player_id)
                return len(opponent.collab) > 0
            case Condition.Condition_MyHolomemDownedLastOpponentTurn:
                # 직전 상대의 턴에 자신의 홀로멤이 다운됐었는지 확인
                return effect_player.holomem_downed_last_opponent_turn
            case Condition.Condition_MyHolomemDownedLastOpponentTurnNamed:
                condition_names = condition.get("condition_names", [])
                return any(name in effect_player.holomem_downed_names_last_opponent_turn for name in condition_names)
            case Condition.Condition_HasRestingHolomem:
                requirement_tags = condition.get("requirement_tags", [])
                for holomem in effect_player.get_holomem_on_stage():
                    if is_card_resting(holomem):
                        if not requirement_tags or any(tag in holomem.get("tags", []) for tag in requirement_tags):
                            return True
                return False
            case Condition.Condition_MyLifeLessThanEqualOpponent:
                opponent = self.other_player(effect_player.player_id)
                return len(effect_player.life) <= len(opponent.life)
            case Condition.Condition_PlayedLimitedSupportThisTurn:
                return effect_player.limited_uses_count_this_turn > 0
            case Condition.Condition_LastDieGteLife:
                return self.last_die_value >= len(effect_player.life)
            case Condition.Condition_LastDieLteLife:
                return self.last_die_value <= len(effect_player.life)
            case Condition.Condition_DieRollSourceCardNameIs:
                required_member_name = condition["required_member_name"]
                source_id = getattr(self, 'die_roll_source_card_id', '')
                if source_id:
                    source_card = self.find_card(source_id)
                    if source_card:
                        return required_member_name in source_card.get("card_names", [])
                return False
            case Condition.Condition_DieRollSourceIsOshi:
                return getattr(self, 'die_roll_source', '') == "oshi_skill"
            case Condition.Condition_DieRollSourceHasTag:
                condition_tags = condition.get("condition_tags", [])
                source_card_id = getattr(self, 'die_roll_source_card_id', '')
                if source_card_id:
                    source_card = self.find_card(source_card_id)
                    if source_card:
                        return any(tag in source_card.get("tags", []) for tag in condition_tags)
                return False
            case Condition.Condition_RevealedCardHasAnyTag:
                condition_tags = condition.get("condition_tags", [])
                revealed = getattr(effect_player, "last_revealed_cards", [])
                return any(
                    any(tag in card.get("tags", []) for tag in condition_tags)
                    for card in revealed
                )
            case Condition.Condition_RevealedCardIsHolomem:
                revealed = getattr(effect_player, "last_revealed_cards", [])
                return all(is_card_holomem(card) for card in revealed) if revealed else False
            case Condition.Condition_RevealedCardsHasEvent:
                revealed = getattr(effect_player, "last_revealed_cards", [])
                return any(is_card_sub_type(card, "event") for card in revealed)
            case Condition.Condition_StageAllMembersHaveTag:
                required_tags = condition.get("required_tags", [])
                holomems = effect_player.get_holomem_on_stage()
                if not holomems:
                    return False
                return all(
                    any(tag in holomem.get("tags", []) for tag in required_tags)
                    for holomem in holomems
                )
            case Condition.Condition_CheerInArchive:
                required_colors = condition.get("required_colors", [])
                amount_min = condition.get("amount_min", 1)
                cheer_count = 0
                for card in effect_player.archive:
                    if is_card_cheer(card):
                        if required_colors:
                            if any(color in card.get("colors", []) for color in required_colors):
                                cheer_count += 1
                        else:
                            cheer_count += 1
                return cheer_count >= amount_min
            case Condition.Condition_SupportInArchive:
                amount_min = condition.get("amount_min", 1)
                support_count = sum(1 for card in effect_player.archive if card.get("card_type") == "support")
                return support_count >= amount_min
            case Condition.Condition_HolomemUsedArtThisTurn:
                required_names = condition.get("required_member_name_in", [])
                for holomem in effect_player.get_holomem_on_stage():
                    if holomem.get("used_art_this_turn", False):
                        if any(name in holomem["card_names"] for name in required_names):
                            return True
                return False
            case Condition.Condition_OshiSkillUsedThisTurn:
                required_skill_id = condition.get("required_skill_id", "")
                return effect_player.has_used_once_per_turn_effect(required_skill_id)
            case Condition.Condition_CardNamesInArchive:
                required_names = condition.get("card_names", [])
                amount_min = condition.get("amount_min", 1)
                count = sum(1 for card in effect_player.archive
                            if any(name in card.get("card_names", []) for name in required_names))
                return count >= amount_min
            case Condition.Condition_SupportCardNameNotUsedThisTurn:
                condition_card_names = condition.get("condition_card_names", [])
                for card_name in condition_card_names:
                    if card_name in effect_player.support_card_names_used_this_turn:
                        return False
                return True
            case Condition.Condition_HolomemReturnedToDeckThisTurn:
                return effect_player.holomem_returned_to_deck_this_turn
            case Condition.Condition_ReturnedToDeckCardHasName:
                condition_names = condition.get("condition_names", [])
                returned_card = self.returned_to_deck_card
                if returned_card:
                    return any(name in returned_card.get("card_names", []) for name in condition_names)
                return False
            case Condition.Condition_AllStageCheerIsColor:
                condition_color = condition["condition_color"]
                holomems = effect_player.get_holomem_on_stage()
                total_cheer = 0
                matching_cheer = 0
                for holomem in holomems:
                    for cheer in holomem.get("attached_cheer", []):
                        total_cheer += 1
                        if condition_color in cheer.get("colors", []):
                            matching_cheer += 1
                return total_cheer > 0 and total_cheer == matching_cheer
            case Condition.Condition_MyTurn:
                return self.active_player_id == effect_player.player_id
            case Condition.Condition_UsedSpOshiSkillThisTurn:
                return effect_player.sp_oshi_skill_used_this_turn
            case Condition.Condition_ArchivingAttachmentName:
                if not self.archiving_attachment_card:
                    return False
                required_name = condition["required_card_name"]
                return required_name in self.archiving_attachment_card.get("card_names", [])
            case Condition.Condition_ArchivingFromCenter:
                if not self.archiving_attachment_holomem:
                    return False
                return self.archiving_attachment_holomem in effect_player.center
            case _:
                raise NotImplementedError(f"Unimplemented condition: {condition['condition']}")
        return False
    def get_condition_count(self, effect_player: PlayerState, source_card_id, condition_type):
        """조건에 따른 카운트를 반환하는 함수 (power_boost_per_condition용)"""
        match condition_type:
            case Condition.Condition_OpponentBackstageHpReducedCount:
                # 상대방 백스테이지에서 HP가 감소된 홀로멤의 수를 반환
                opponent_player = self.other_player(effect_player.player_id)
                reduced_count = 0
                print(f"DEBUG: Checking opponent backstage for HP reduced holomems")
                print(f"DEBUG: Opponent backstage count: {len(opponent_player.backstage)}")
                for holomem in opponent_player.backstage:
                    damage = holomem.get("damage", 0)
                    print(f"DEBUG: Holomem {holomem.get('card_id', 'unknown')} - Damage: {damage}")
                    if damage > 0:
                        reduced_count += 1
                        print(f"DEBUG: Found damaged holomem! Count: {reduced_count}")
                print(f"DEBUG: Final reduced count: {reduced_count}")
                return reduced_count
            case _:
                # 기본적으로는 is_condition_met의 결과를 boolean에서 int로 변환
                result = self.is_condition_met(effect_player, source_card_id, {"condition": condition_type})
                return 1 if result else 0
