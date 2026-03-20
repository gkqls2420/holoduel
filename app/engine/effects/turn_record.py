from __future__ import annotations
from typing import TYPE_CHECKING
from copy import deepcopy

from app.engine.constants import *
from app.engine.models import *
from app.engine.helpers import *
from app.engine.models import *

if TYPE_CHECKING:
    from app.engine.player_state import PlayerState


def handle_add_turn_effect(engine, effect_player, effect):
    """Returns True if continuation was passed on, False otherwise."""
    effect_player_id = effect_player.player_id
    turn_effect = deepcopy(effect["turn_effect"])
    if "amount_per_last_card_count" in turn_effect:
        per_amount = turn_effect.pop("amount_per_last_card_count")
        turn_effect["amount"] = per_amount * engine.last_card_count
    turn_effect["source_card_id"] = effect["source_card_id"]
    effect_player.add_turn_effect(turn_effect)
    event = {
        "event_type": EventType.EventType_AddTurnEffect,
        "effect_player_id": effect_player_id,
        "turn_effect": turn_effect,
    }
    engine.broadcast_event(event)
    engine.broadcast_bonus_hp_updates()
    return False


def handle_add_turn_effect_for_holomem(engine, effect_player, effect):
    """Returns True if continuation was passed on, False otherwise."""
    effect_player_id = effect_player.player_id
    holomem_targets = effect_player.get_holomem_on_stage()
    limitation = effect.get("limitation", None)
    if limitation:
        match limitation:
            case "self":
                source_card_id = effect.get("source_card_id", "")
                holomem_targets = [holomem for holomem in holomem_targets if holomem["game_card_id"] == source_card_id]
            case "color_in":
                limitation_colors = effect["limitation_colors"]
                holomem_targets = [holomem for holomem in holomem_targets if any(color in holomem["colors"] for color in limitation_colors)]
            case "last_chosen_holomem":
                holomem_targets = [holomem for holomem in holomem_targets if holomem["game_card_id"] == engine.last_chosen_holomem_id]
            case "name_in":
                limitation_names = effect["limitation_names"]
                holomem_targets = [holomem for holomem in holomem_targets if any(name in holomem["card_names"] for name in limitation_names)]
            case "has_tag":
                limitation_tags = effect["limitation_tags"]
                holomem_targets = [holomem for holomem in holomem_targets if any(tag in holomem.get("tags", []) for tag in limitation_tags)]
            case "center_is_name":
                limitation_names = effect["limitation_names"]
                if len(effect_player.center) > 0:
                    center_card = effect_player.center[0]
                    if any(name in center_card["card_names"] for name in limitation_names):
                        holomem_targets = [center_card]
                    else:
                        holomem_targets = []
                else:
                    holomem_targets = []
    limitation_location = effect.get("limitation_location", "")
    if limitation_location:
        location_ids = set()
        match limitation_location:
            case "collab":
                location_ids = {c["game_card_id"] for c in effect_player.collab}
            case "center":
                location_ids = {c["game_card_id"] for c in effect_player.center}
            case "backstage":
                location_ids = {c["game_card_id"] for c in effect_player.backstage}
        holomem_targets = [h for h in holomem_targets if h["game_card_id"] in location_ids]
    if "limitation_attachment_tags" in effect:
        req_tags = effect["limitation_attachment_tags"]
        holomem_targets = [h for h in holomem_targets if any(
            any(tag in s.get("tags", []) for tag in req_tags)
            for s in h.get("attached_support", [])
        )]
    if "limitation_attachment_sub_types" in effect:
        req_sub_types = effect["limitation_attachment_sub_types"]
        holomem_targets = [h for h in holomem_targets if any(
            s.get("sub_type", "") in req_sub_types
            for s in h.get("attached_support", [])
        )]
    if "limitation_bloom_levels" in effect:
        allowed_levels = effect["limitation_bloom_levels"]
        holomem_targets = [h for h in holomem_targets if h.get("bloom_level", 0) in allowed_levels]
    if effect.get("limitation_bloomed_this_turn", False):
        holomem_targets = [h for h in holomem_targets if h.get("bloomed_this_turn", False)]
    all_targets = effect.get("all_targets", False)
    target_both_sides = effect.get("target_both_sides", False)

    if target_both_sides:
        opponent = engine.other_player(effect_player_id)
        opponent_holomem_targets = opponent.get_holomem_on_stage()
        if limitation:
            match limitation:
                case "name_in":
                    limitation_names = effect["limitation_names"]
                    opponent_holomem_targets = [h for h in opponent_holomem_targets if any(name in h["card_names"] for name in limitation_names)]
                case "has_tag":
                    limitation_tags = effect["limitation_tags"]
                    opponent_holomem_targets = [h for h in opponent_holomem_targets if any(tag in h.get("tags", []) for tag in limitation_tags)]

    turn_effect_copy = deepcopy(effect["turn_effect"])
    if "amount_per_last_card_count" in turn_effect_copy:
        per_amount = turn_effect_copy.pop("amount_per_last_card_count")
        turn_effect_copy["amount"] = per_amount * engine.last_card_count
    turn_effect_copy["source_card_id"] = effect["source_card_id"]
    source_from_chosen = effect.get("source_from_chosen", False)

    global_apply = effect.get("global_apply", False)
    if global_apply:
        te = deepcopy(turn_effect_copy)
        effect_player.add_turn_effect(te)
        engine.broadcast_event({
            "event_type": EventType.EventType_AddTurnEffect,
            "effect_player_id": effect_player_id,
            "turn_effect": te,
        })
        if target_both_sides:
            opponent = engine.other_player(effect_player_id)
            te2 = deepcopy(turn_effect_copy)
            opponent.add_turn_effect(te2)
            engine.broadcast_event({
                "event_type": EventType.EventType_AddTurnEffect,
                "effect_player_id": opponent.player_id,
                "turn_effect": te2,
            })
        engine.broadcast_bonus_hp_updates()
        return False

    if all_targets:
        for holomem in holomem_targets:
            te = deepcopy(turn_effect_copy)
            replace_field_in_conditions(te, "required_id", holomem["game_card_id"])
            effect_player.add_turn_effect(te)
            event = {
                "event_type": EventType.EventType_AddTurnEffect,
                "effect_player_id": effect_player_id,
                "turn_effect": te,
            }
            engine.broadcast_event(event)
        if target_both_sides:
            opponent_id = opponent.player_id
            for holomem in opponent_holomem_targets:
                te = deepcopy(turn_effect_copy)
                replace_field_in_conditions(te, "required_id", holomem["game_card_id"])
                opponent.add_turn_effect(te)
                event = {
                    "event_type": EventType.EventType_AddTurnEffect,
                    "effect_player_id": opponent_id,
                    "turn_effect": te,
                }
                engine.broadcast_event(event)
        engine.broadcast_bonus_hp_updates()
        return False

    holomem_targets = ids_from_cards(holomem_targets)
    if len(holomem_targets) == 0:
        # No effect.
        pass
    elif len(holomem_targets) == 1:
        engine.last_chosen_cards = [holomem_targets[0]]
        engine.last_chosen_holomem_id = holomem_targets[0]
        replace_field_in_conditions(turn_effect_copy, "required_id", holomem_targets[0])
        if source_from_chosen:
            turn_effect_copy["source_card_id"] = holomem_targets[0]
        effect_player.add_turn_effect(turn_effect_copy)
        event = {
            "event_type": EventType.EventType_AddTurnEffect,
            "effect_player_id": effect_player_id,
            "turn_effect": turn_effect_copy,
        }
        engine.broadcast_event(event)
    else:
        # Ask the player to choose one.
        decision_event = {
            "event_type": EventType.EventType_Decision_ChooseHolomemForEffect,
            "desired_response": GameAction.EffectResolution_ChooseCardsForEffect,
            "effect_player_id": effect_player_id,
            "cards_can_choose": holomem_targets,
            "effect": effect,
        }
        engine.broadcast_event(decision_event)
        engine.set_decision({
            "decision_type": DecisionType.DecisionEffect_ChooseCardsForEffect,
            "decision_player": effect_player_id,
            "all_card_seen": holomem_targets,
            "cards_can_choose": holomem_targets,
            "amount_min": 1,
            "amount_max": 1,
            "turn_effect": turn_effect_copy,
            "source_from_chosen": source_from_chosen,
            "effect_resolution": engine.handle_add_turn_effect_for_holomem,
            "continuation": engine.continue_resolving_effects,
        })
        return True
    return False


def handle_record_effect_card_id_used_this_turn(engine, effect_player, effect):
    """Returns True if continuation was passed on, False otherwise."""
    effect_player_id = effect_player.player_id
    effect_player.record_card_effect_used_this_turn(effect["source_card_id"])
    return False


def handle_record_last_die_result(engine, effect_player, effect):
    """Returns True if continuation was passed on, False otherwise."""
    effect_player_id = effect_player.player_id
    effect_player.last_die_roll_results.append(engine.last_die_value)
    return False


def handle_record_used_once_per_game_effect(engine, effect_player, effect):
    """Returns True if continuation was passed on, False otherwise."""
    effect_player_id = effect_player.player_id
    effect_player.record_effect_used_this_game(effect["effect_id"])
    return False


def handle_record_used_once_per_turn_effect(engine, effect_player, effect):
    """Returns True if continuation was passed on, False otherwise."""
    effect_player_id = effect_player.player_id
    effect_player.record_effect_used_this_turn(effect["effect_id"])
    return False


def handle_recover_downed_holomem_cards(engine, effect_player, effect):
    """Returns True if continuation was passed on, False otherwise."""
    effect_player_id = effect_player.player_id
    engine.remove_downed_holomems_to_hand = True
    return False


def handle_repeat_art(engine, effect_player, effect):
    """Returns True if continuation was passed on, False otherwise."""
    effect_player_id = effect_player.player_id
    engine.performance_artstatboosts.repeat_art = True
    return False


def handle_roll_die(engine, effect_player, effect):
    """Returns True if continuation was passed on, False otherwise."""
    effect_player_id = effect_player.player_id

    engine.die_roll_source = effect.get("source", "")
    engine.die_roll_source_card_id = effect.get("source_card_id", "")

    # Put the actual roll in front on the queue, but
    # check afterwards to see if we should add any more effects up front.
    rolldie_internal_effect = deepcopy(effect)
    rolldie_internal_effect["effect_type"] = EffectType.EffectType_RollDie_Internal
    rolldie_internal_effect["internal_skip_simultaneous_choice"] = True
    # Remove the and effects because they were already processed.
    rolldie_internal_effect["and"] = []
    engine.add_effects_to_front([rolldie_internal_effect])

    # When we roll a die, check if there are any choices to be made like oshi abilities.
    ability_effects = effect_player.get_effects_at_timing("before_die_roll", "", effect["source"])
    if ability_effects:
        engine.add_effects_to_front(ability_effects)
    return False


def handle_roll_die_choose_result(engine, effect_player, effect):
    """Returns True if continuation was passed on, False otherwise."""
    effect_player_id = effect_player.player_id
    choice_info = {
        "specific_options": ["1", "2", "3", "4", "5", "6"],
    }
    min_choice = 0
    max_choice = 5
    decision_event = {
        "event_type": EventType.EventType_ForceDieResult,
        "desired_response": GameAction.EffectResolution_MakeChoice,
        "choice_event": True,
        "effect_player_id": effect_player_id,
        "choice_info": choice_info,
        "min_choice": min_choice,
        "max_choice": max_choice,
    }
    engine.broadcast_event(decision_event)
    engine.set_decision({
        "decision_type": DecisionType.DecisionChoice,
        "decision_player": effect_player_id,
        "choice_info": choice_info,
        "min_choice": min_choice,
        "max_choice": max_choice,
        "resolution_func": engine.handle_force_die_result,
        "continuation": engine.continue_resolving_effects,
    })
    return True


def handle_roll_die_internal(engine, effect_player, effect):
    """Returns True if continuation was passed on, False otherwise."""
    effect_player_id = effect_player.player_id
    rigged = False
    if effect_player.set_next_die_roll:
        die_result = effect_player.set_next_die_roll
        if effect_player.force_die_remaining > 0:
            effect_player.force_die_remaining -= 1
            if effect_player.force_die_remaining <= 0:
                effect_player.set_next_die_roll = 0
        else:
            effect_player.set_next_die_roll = 0
        rigged = True
    else:
        die_result = engine.random_gen.randint(1, 6)
    engine.last_die_value = die_result
    effect_player.die_rolls_this_turn += 1

    die_event = {
        "event_type": EventType.EventType_RollDie,
        "effect_player_id": effect_player_id,
        "die_result": die_result,
        "rigged": rigged,
    }
    engine.broadcast_event(die_event)

    # Add the resolution to the front of the queue.
    # This will check last_die_value to see what happens.
    # However process any after die roll effects first.
    rolldie_resolution_effect = deepcopy(effect)
    rolldie_resolution_effect["effect_type"] = EffectType.EffectType_RollDie_Internal_Resolution
    rolldie_resolution_effect["internal_skip_simultaneous_choice"] = True
    engine.add_effects_to_front([rolldie_resolution_effect])

    # Check for after die roll effects.
    source_card, _, _ = effect_player.find_card(effect["source_card_id"])

    # Record holomem names when die is rolled by holomem ability
    if effect.get("source") == "holomem_ability" and source_card and "card_names" in source_card:
        for name in source_card["card_names"]:
            if name not in effect_player.die_rolled_by_holomem_names_this_turn:
                effect_player.die_rolled_by_holomem_names_this_turn.append(name)

    after_die_roll_effects = effect_player.get_effects_at_timing("after_die_roll", source_card, effect["source"])
    engine.begin_resolving_effects(after_die_roll_effects, engine.continue_resolving_effects)
    return True


def handle_roll_die_internal_resolution(engine, effect_player, effect):
    """Returns True if continuation was passed on, False otherwise."""
    effect_player_id = effect_player.player_id
    die_effects = effect["die_effects"]
    effects_to_resolve = []
    for die_effects_option in die_effects:
        activate_on_values = die_effects_option["activate_on_values"]
        if engine.last_die_value in activate_on_values:
            effects_to_resolve = die_effects_option["effects"]
            break
    if effects_to_resolve:
        # Push these effects onto the front of the effect list.
        add_ids_to_effects(effects_to_resolve, effect_player_id, effect["source_card_id"])
        engine.add_effects_to_front(effects_to_resolve)
    return False


def handle_reroll_die(engine, effect_player, effect):
    """Returns True if continuation was passed on, False otherwise."""
    effect_player_id = effect_player.player_id
    rigged = False
    if effect_player.set_next_die_roll:
        die_result = effect_player.set_next_die_roll
        effect_player.set_next_die_roll = 0
        rigged = True
    else:
        die_result = engine.random_gen.randint(1, 6)
    engine.last_die_value = die_result

    die_event = {
        "event_type": EventType.EventType_RollDie,
        "effect_player_id": effect_player_id,
        "die_result": die_result,
        "rigged": rigged,
    }
    engine.broadcast_event(die_event)
    return False


def handle_force_die_result(engine, effect_player, effect):
    """Returns True if continuation was passed on, False otherwise."""
    effect_player_id = effect_player.player_id
    die_result = effect["die_result"]
    effect_player.set_next_die_roll = die_result
    return False


def handle_go_first(engine, effect_player, effect):
    """Returns True if continuation was passed on, False otherwise."""
    effect_player_id = effect_player.player_id
    first = effect["first"]
    if first:
        engine.first_turn_player_id = effect_player_id
    else:
        engine.first_turn_player_id = engine.other_player(effect_player_id).player_id
    return False


def handle_oshi_activation(engine, effect_player, effect):
    """Returns True if continuation was passed on, False otherwise."""
    effect_player_id = effect_player.player_id
    skill_id = effect["skill_id"]
    if effect["limit"] == "once_per_game":
        effect_player.sp_oshi_skill_used_this_turn = True
    oshi_skill_event = {
        "event_type": EventType.EventType_OshiSkillActivation,
        "oshi_player_id": effect_player.player_id,
        "skill_id": skill_id,
        "limit": effect["limit"]
    }
    engine.broadcast_event(oshi_skill_event)
    return False


def handle_pass(engine, effect_player, effect):
    """Returns True if continuation was passed on, False otherwise."""
    effect_player_id = effect_player.player_id
    pass
    return False


def handle_take_extra_turn(engine, effect_player, effect):
    """Returns True if continuation was passed on, False otherwise."""
    effect_player_id = effect_player.player_id
    effect_player.extra_turn_pending = True
    return False


def handle_choose_stacked_to_hand_internal(engine, effect_player, effect):
    """Returns True if continuation was passed on, False otherwise.
    Note: EffectType_ChooseStackedToHand_Internal was not found in do_effect;
    this is a placeholder for the Internal resolution path."""
    effect_player_id = effect_player.player_id
    # Internal resolution - not dispatched from do_effect in gameengine.py
    pass
    return False


def handle_force_multiple_die_result(engine, effect_player, effect):
    """Forces all dice in subsequent multiple_die_roll to a specific value for this turn."""
    die_result = effect["die_result"]
    count = effect.get("count", 999)
    effect_player.set_next_die_roll = die_result
    effect_player.force_die_remaining = count
    return False


def handle_free_arts_turn_effect(engine, effect_player, effect):
    """Adds a turn effect that makes a chosen holomem's arts free (zero cost)."""
    effect_player_id = effect_player.player_id
    holomem_targets = effect_player.get_holomem_on_stage()
    requirement_tags = effect.get("requirement_tags", [])
    if requirement_tags:
        holomem_targets = [h for h in holomem_targets if any(tag in h.get("tags", []) for tag in requirement_tags)]

    turn_effect = {
        "timing": "on_art_cost_check",
        "effect_type": EffectType.EffectType_ReduceArtCost,
        "source_card_id": effect["source_card_id"],
        "free_cost": True,
    }
    holomem_ids = ids_from_cards(holomem_targets)

    if len(holomem_ids) == 0:
        pass
    elif len(holomem_ids) == 1:
        turn_effect["target_limitation"] = "specific_member_id"
        turn_effect["target_member_id"] = holomem_ids[0]
        effect_player.add_turn_effect(turn_effect)
        event = {
            "event_type": EventType.EventType_AddTurnEffect,
            "effect_player_id": effect_player_id,
            "turn_effect": turn_effect,
        }
        engine.broadcast_event(event)
    else:
        decision_event = {
            "event_type": EventType.EventType_Decision_ChooseHolomemForEffect,
            "desired_response": GameAction.EffectResolution_ChooseCardsForEffect,
            "effect_player_id": effect_player_id,
            "cards_can_choose": holomem_ids,
        }
        engine.broadcast_event(decision_event)
        engine.set_decision({
            "decision_type": DecisionType.DecisionEffect_ChooseCardsForEffect,
            "decision_player": effect_player_id,
            "all_card_seen": holomem_ids,
            "cards_can_choose": holomem_ids,
            "amount_min": 1,
            "amount_max": 1,
            "turn_effect": turn_effect,
            "effect_resolution": engine.handle_free_arts_turn_effect_choice,
            "continuation": engine.continue_resolving_effects,
        })
        return True
    return False


def handle_set_limited_uses_allowed(engine, effect_player, effect):
    """Returns True if continuation was passed on, False otherwise."""
    effect_player.limited_uses_allowed_this_turn = effect["amount"]
    return False


def handle_count_cheer_on_stage(engine, effect_player, effect):
    """Returns True if continuation was passed on, False otherwise."""
    engine.last_card_count = len(effect_player.get_cheer_ids_on_holomems())
    return False


TURN_RECORD_HANDLERS = {
    EffectType.EffectType_AddTurnEffect: handle_add_turn_effect,
    EffectType.EffectType_AddTurnEffectForHolomem: handle_add_turn_effect_for_holomem,
    EffectType.EffectType_RecordEffectCardIdUsedThisTurn: handle_record_effect_card_id_used_this_turn,
    EffectType.EffectType_RecordLastDieResult: handle_record_last_die_result,
    EffectType.EffectType_RecordUsedOncePerGameEffect: handle_record_used_once_per_game_effect,
    EffectType.EffectType_RecordUsedOncePerTurnEffect: handle_record_used_once_per_turn_effect,
    EffectType.EffectType_RecoverDownedHolomemCards: handle_recover_downed_holomem_cards,
    EffectType.EffectType_RepeatArt: handle_repeat_art,
    EffectType.EffectType_RollDie: handle_roll_die,
    EffectType.EffectType_RollDie_ChooseResult: handle_roll_die_choose_result,
    EffectType.EffectType_RollDie_Internal: handle_roll_die_internal,
    EffectType.EffectType_RollDie_Internal_Resolution: handle_roll_die_internal_resolution,
    EffectType.EffectType_RerollDie: handle_reroll_die,
    EffectType.EffectType_ForceDieResult: handle_force_die_result,
    EffectType.EffectType_ForceMultipleDieResult: handle_force_multiple_die_result,
    EffectType.EffectType_FreeArtsTurnEffect: handle_free_arts_turn_effect,
    EffectType.EffectType_GoFirst: handle_go_first,
    EffectType.EffectType_OshiActivation: handle_oshi_activation,
    EffectType.EffectType_Pass: handle_pass,
    EffectType.EffectType_TakeExtraTurn: handle_take_extra_turn,
    EffectType.EffectType_ChooseStackedToHand_Internal: handle_choose_stacked_to_hand_internal,
    EffectType.EffectType_SetLimitedUsesAllowed: handle_set_limited_uses_allowed,
    EffectType.EffectType_CountCheerOnStage: handle_count_cheer_on_stage,
}
