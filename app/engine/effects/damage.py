from __future__ import annotations
from typing import TYPE_CHECKING
from copy import deepcopy

from app.engine.constants import *
from app.engine.models import *
from app.engine.helpers import *

if TYPE_CHECKING:
    from app.engine.player_state import PlayerState


def handle_add_damage_taken(engine, effect_player, effect):
    """Returns True if continuation was passed on, False otherwise."""
    effect_player_id = effect_player.player_id
    amount = effect["amount"]
    engine.take_damage_state.added_damage += amount
    for_art = engine.take_damage_state.art_info
    engine.send_boost_event(engine.take_damage_state.target_card["game_card_id"], effect["source_card_id"], "damage_added", amount, for_art)
    return False


def handle_deal_damage(engine, effect_player, effect):
    """Returns True if continuation was passed on, False otherwise."""
    effect_player_id = effect_player.player_id
    special = effect.get("special", False)
    target = effect["target"]
    opponent = effect.get("opponent", False)
    amount = effect["amount"]
    prevent_life_loss = effect.get("prevent_life_loss", False)
    multiple_targets = effect.get("multiple_targets", None)
    source_player = engine.get_player(effect_player_id)
    target_player = effect_player
    if opponent:
        target_player = engine.other_player(effect_player_id)
    source_holomem_card, _, _ = source_player.find_card(effect["source_card_id"])
    if not source_holomem_card:
        # Assume this is an attachment, find it on the holomem.
        for holomem in source_player.get_holomem_on_stage():
            for attachment in holomem["attached_support"]:
                if attachment["game_card_id"] == effect["source_card_id"]:
                    source_holomem_card = holomem
                    break
    match str(amount):
        case "total_damage_on_backstage":
            amount = sum(card["damage"] for card in target_player.backstage)
        case "overflow_damage":
            target_hp = engine.performance_target_player.get_card_hp(engine.performance_target_card)
            amount = max(0, engine.performance_target_card["damage"] - target_hp)
    effect["amount"] = amount

    target_cards = []
    match target:
        case "backstage":
            target_cards = target_player.backstage
        case "center":
            target_cards = target_player.center
        case "collab":
            target_cards = target_player.collab
        case "center_or_collab":
            target_cards = target_player.center + target_player.collab
        case "center_or_backstage":
            target_cards = target_player.center + target_player.backstage
        case "current_damage_target":
            # Only valid if still on stage.
            if engine.after_damage_state.target_card in target_player.get_holomem_on_stage():
                target_cards = [engine.after_damage_state.target_card]
        case "holomem":
            target_cards = target_player.get_holomem_on_stage()
            limitation = effect.get("limitation", None)
            if limitation:
                limitation_bloom_level = effect.get("limitation_bloom_level", 0)
                if limitation == "bloom_level":
                    target_cards = [card for card in target_cards if
                        card["card_type"] == "holomem_bloom" and
                        card.get("bloom_level", 0) == limitation_bloom_level]
            if effect.get("exclude_source", False) and source_holomem_card:
                target_cards = [c for c in target_cards if c["game_card_id"] != source_holomem_card["game_card_id"]]
        case "self":
            target_cards = [source_holomem_card]
        case _:
            raise NotImplementedError("Only center is supported for now.")

    targets_allowed = 1
    if multiple_targets:
        if str(multiple_targets) == "all":
            targets_allowed = len(target_cards)
        elif str(multiple_targets) == "sequential":
            targets_allowed = 1  # sequential의 경우 정수로 설정
        elif str(multiple_targets) == "accumulated":
            targets_allowed = 1  # accumulated의 경우 한 번에 1개씩 선택
        else:
            targets_allowed = multiple_targets
    if isinstance(targets_allowed, int) and targets_allowed > len(target_cards):
        targets_allowed = len(target_cards)

    # Filter out any target cards that already have damage over their hp.
    target_cards = [card for card in target_cards if card["damage"] < target_player.get_card_hp(card)]
    if len(target_cards) == 0:
        pass
    elif multiple_targets == "sequential":
        # 순차적 대미지 처리
        repeat_count = effect.get("repeat", 1)
        for i in range(repeat_count):
            if len(target_cards) > 0:
                target_card = target_cards[i % len(target_cards)]
                engine.add_deal_damage_internal_effect(
                    source_player,
                    target_player,
                    effect["source_card_id"],
                    target_card,
                    amount,
                    special,
                    prevent_life_loss
                )
    elif multiple_targets == "accumulated":
        # 누적 대미지 처리: 3번 선택 후 합산하여 한번에 대미지 적용
        repeat_count = effect.get("repeat", 1)
        allow_pass = effect.get("allow_pass", False)
        engine.handle_accumulated_damage_selection(
            effect_player_id, effect, target_cards, repeat_count,
            target_player, source_player, amount, special, prevent_life_loss, allow_pass
        )
    elif len(target_cards) == targets_allowed:
        target_cards.reverse()
        for i in range(targets_allowed):
            engine.add_deal_damage_internal_effect(
                source_player,
                target_player,
                effect["source_card_id"],
                target_cards[i],
                amount,
                special,
                prevent_life_loss
            )
    else:
        # Player gets to choose.
        # Check if repeat is needed
        repeat_count = effect.get("repeat", 1)
        if repeat_count > 1:
            # Use repeat damage selection for multiple iterations
            engine.handle_repeat_damage_selection(effect_player_id, effect, target_cards, targets_allowed, repeat_count, target_player, source_player)
        else:
            # Single selection - use normal flow
            target_options = ids_from_cards(target_cards)
            decision_event = {
                "event_type": EventType.EventType_Decision_ChooseHolomemForEffect,
                "desired_response": GameAction.EffectResolution_ChooseCardsForEffect,
                "effect_player_id": effect_player_id,
                "cards_can_choose": target_options,
                "amount_min": targets_allowed,
                "amount_max": targets_allowed,
                "effect": effect,
            }
            engine.broadcast_event(decision_event)
            engine.set_decision({
                "decision_type": DecisionType.DecisionEffect_ChooseCardsForEffect,
                "decision_player": effect_player_id,
                "all_card_seen": target_options,
                "cards_can_choose": target_options,
                "amount_min": targets_allowed,
                "amount_max": targets_allowed,
                "effect_resolution": engine.handle_deal_damage_to_holomem,
                "effect": effect,
                "source_card_id": effect["source_card_id"],
                "target_player": target_player,
                "continuation": engine.continue_resolving_effects,
            })
    return False


def handle_deal_damage_internal(engine, effect_player, effect):
    """Returns True if continuation was passed on, False otherwise."""
    effect_player_id = effect_player.player_id
    source_player = effect["source_player"]
    target_player = effect["target_player"]
    source_card_id = effect["source_card_id"]
    dealing_card, _, _ = source_player.find_card(source_card_id)
    if not dealing_card:
        dealing_card = source_player.find_attachment(source_card_id)
    target_card = effect["target_card"]
    amount = effect["amount"]
    special = effect["special"]
    prevent_life_loss = effect["prevent_life_loss"]
    engine.deal_damage(source_player, target_player, dealing_card, target_card, amount, special, prevent_life_loss, {}, engine.continue_resolving_effects)
    return True


def handle_deal_damage_per_cheer_in_archive(engine, effect_player, effect):
    """Returns True if continuation was passed on, False otherwise."""
    amount_per = effect["amount_per"]
    cheer_count = sum(1 for card in effect_player.archive if is_card_cheer(card))
    effect_copy = deepcopy(effect)
    effect_copy["amount"] = amount_per * cheer_count
    effect_copy["effect_type"] = EffectType.EffectType_DealDamage
    engine.add_effects_to_front([effect_copy])
    return False


def handle_deal_damage_per_holomem_on_stage(engine, effect_player, effect):
    """Returns True if continuation was passed on, False otherwise."""
    amount_per = effect["amount_per"]
    has_tag = effect.get("has_tag", None)
    holomems = effect_player.get_holomem_on_stage()
    if has_tag:
        holomems = [h for h in holomems if has_tag in h.get("tags", [])]
    effect_copy = deepcopy(effect)
    effect_copy["amount"] = amount_per * len(holomems)
    effect_copy["effect_type"] = EffectType.EffectType_DealDamage
    engine.add_effects_to_front([effect_copy])
    return False


def handle_deal_damage_per_support_in_archive(engine, effect_player, effect):
    """Returns True if continuation was passed on, False otherwise."""
    amount_per = effect["amount_per"]
    support_count = sum(1 for card in effect_player.archive if card.get("card_type") == "support")
    effect_copy = deepcopy(effect)
    effect_copy["amount"] = amount_per * support_count
    effect_copy["effect_type"] = EffectType.EffectType_DealDamage
    engine.add_effects_to_front([effect_copy])
    return False


def handle_deal_damage_per_stacked(engine, effect_player, effect):
    """Returns True if continuation was passed on, False otherwise."""
    effect_player_id = effect_player.player_id
    holomems = []
    match effect.get("stack_source"):
        case "center":
            holomems = effect_player.center
        case "all":
            holomems = effect_player.get_holomem_on_stage()
    num_of_stacked_cards = len([card for holomem in holomems for card in holomem["stacked_cards"] if is_card_holomem(card)])
    effect_copy = deepcopy(effect)
    effect_copy["amount"] *= num_of_stacked_cards
    effect_copy["effect_type"] = EffectType.EffectType_DealDamage
    engine.add_effects_to_front([effect_copy])
    return False


def handle_deal_life_damage(engine, effect_player, effect):
    """Returns True if continuation was passed on, False otherwise."""
    effect_player_id = effect_player.player_id
    amount = effect["amount"]
    opponent = effect.get("opponent", False)
    source_player = engine.get_player(effect_player_id)
    target_player = engine.other_player(effect_player_id) if opponent else effect_player
    source_holomem_card, _, _ = source_player.find_card(effect["source_card_id"])
    if not source_holomem_card:
        # Assume this is an attachment, find it on the holomem.
        for holomem in source_player.get_holomem_on_stage():
            for attachment in holomem["attached_support"]:
                if attachment["game_card_id"] == effect["source_card_id"]:
                    source_holomem_card = holomem
                    break
    engine.deal_life_damage(target_player, source_holomem_card, amount, engine.continue_resolving_effects)
    return True


def handle_down_holomem(engine, effect_player, effect):
    """Returns True if continuation was passed on, False otherwise."""
    effect_player_id = effect_player.player_id
    target = effect["target"]
    required_damage = effect["required_damage"]
    prevent_life_loss = effect.get("prevent_life_loss", False)
    source_player = engine.get_player(effect_player_id)
    target_player = engine.other_player(effect_player_id)
    source_card, _, _ = source_player.find_card(effect["source_card_id"])
    if not source_card:
        # Assume this is an attachment, find it on the holomem.
        source_card = source_player.find_attachment(effect["source_card_id"])

    target_cards = []
    match target:
        case "backstage":
            target_cards = target_player.backstage
        case "center":
            target_cards = target_player.center
        case "collab":
            target_cards = target_player.collab
        case "center_or_collab":
            target_cards = target_player.center + target_player.collab
        case "center_or_backstage":
            target_cards = target_player.center + target_player.backstage
        case "holomem":
            target_cards = target_player.get_holomem_on_stage()
        case _:
            raise NotImplementedError("Missing target type")
    # Restrict to the required damage
    target_cards = [card for card in target_cards if card["damage"] >= required_damage]
    if len(target_cards) == 0:
        pass
    elif len(target_cards) == 1:
        engine.down_holomem(source_player, target_player, source_card, target_cards[0], prevent_life_loss, engine.continue_resolving_effects)
        return True
    else:
        # Player gets to choose.
        # Choose holomem for effect.
        target_options = ids_from_cards(target_cards)
        decision_event = {
            "event_type": EventType.EventType_Decision_ChooseHolomemForEffect,
            "desired_response": GameAction.EffectResolution_ChooseCardsForEffect,
            "effect_player_id": effect_player_id,
            "cards_can_choose": target_options,
            "effect": effect,
        }
        engine.broadcast_event(decision_event)
        engine.set_decision({
            "decision_type": DecisionType.DecisionEffect_ChooseCardsForEffect,
            "decision_player": effect_player_id,
            "all_card_seen": target_options,
            "cards_can_choose": target_options,
            "amount_min": 1,
            "amount_max": 1,
            "effect_resolution": engine.handle_down_holomem,
            "effect": effect,
            "source_card_id": effect["source_card_id"],
            "target_player": target_player,
            "continuation": engine.continue_resolving_effects,
        })
        return True
    return False


def handle_redirect_damage(engine, effect_player, effect):
    """Returns True if continuation was passed on, False otherwise."""
    effect_player_id = effect_player.player_id
    requirement_colors = effect.get("redirect_requirement_colors", [])
    require_buzz_or_2nd = effect.get("redirect_requirement_buzz_or_2nd", False)

    original_target_id = engine.take_damage_state.target_card["game_card_id"]
    candidates = effect_player.get_holomem_on_stage()
    candidates = [h for h in candidates if h["game_card_id"] != original_target_id]
    if requirement_colors:
        candidates = [h for h in candidates if any(c in h["colors"] for c in requirement_colors)]
    if require_buzz_or_2nd:
        candidates = [h for h in candidates if h.get("buzz", False) or h.get("bloom_level", 0) == 2]

    candidate_ids = ids_from_cards(candidates)
    if len(candidate_ids) == 0:
        return False

    decision_event = {
        "event_type": EventType.EventType_Decision_ChooseHolomemForEffect,
        "desired_response": GameAction.EffectResolution_ChooseCardsForEffect,
        "effect_player_id": effect_player_id,
        "cards_can_choose": candidate_ids,
        "effect": effect,
    }
    engine.broadcast_event(decision_event)
    engine.set_decision({
        "decision_type": DecisionType.DecisionEffect_ChooseCardsForEffect,
        "decision_player": effect_player_id,
        "cards_can_choose": candidate_ids,
        "amount_min": 1,
        "amount_max": 1,
        "effect_resolution": engine.handle_redirect_damage_choice,
        "continuation": engine.continue_resolving_effects,
    })
    return True


def handle_reduce_damage(engine, effect_player, effect):
    """Returns True if continuation was passed on, False otherwise."""
    effect_player_id = effect_player.player_id
    amount = effect["amount"]
    if str(amount) == "all":
        amount_num = 9999
    else:
        amount_num = amount
    engine.take_damage_state.prevented_damage += amount_num
    from_art = engine.take_damage_state.art_info
    engine.send_boost_event(engine.take_damage_state.target_card["game_card_id"], effect["source_card_id"], "damage_prevented", amount, from_art)
    return False


def handle_reduce_required_archive_count(engine, effect_player, effect):
    """Returns True if continuation was passed on, False otherwise."""
    effect_player_id = effect_player.player_id
    amount = effect["amount"]
    engine.archive_count_required -= amount
    return False


def handle_restore_hp(engine, effect_player, effect):
    """Returns True if continuation was passed on, False otherwise."""
    effect_player_id = effect_player.player_id
    target = effect["target"]
    amount = effect["amount"]
    limitation = effect.get("limitation", "")
    limitation_colors = effect.get("limitation_colors", [])
    hit_all_targets = effect.get("hit_all_targets", False)
    target_options = []
    match target:
        case "attached_owner":
            holomems = effect_player.get_holomems_with_attachment(effect["source_card_id"])
            if holomems:
                target_options = ids_from_cards(holomems)
        case "backstage":
            target_options = ids_from_cards(effect_player.backstage)
        case "center":
            target_options = ids_from_cards(effect_player.center)
        case "holomem":
            holomems = effect_player.get_holomem_on_stage()
            match limitation:
                case "color_in":
                    holomems = [holomem for holomem in holomems if any(color in holomem["colors"] for color in limitation_colors)]
                case "tag_in":
                    limitation_tags = effect.get("limitation_tags", [])
                    holomems = [holomem for holomem in holomems if any(color in holomem["tags"] for color in limitation_tags)]
                case "name_in":
                    limitation_names = effect.get("limitation_names", [])
                    holomems = [holomem for holomem in holomems if any(name in holomem["card_names"] for name in limitation_names)]
                case "has_attachment_of_type":
                    limitation_type = effect.get("limitation_type", "")
                    holomems = [holomem for holomem in holomems if any(
                        attachment.get("sub_type", "") == limitation_type
                        for attachment in holomem.get("attached_support", [])
                    )]
            target_options = ids_from_cards(holomems)
        case "self":
            target_options = [effect["source_card_id"]]
        case "last_chosen_holomem":
            if engine.last_chosen_holomem_id:
                target_options = [engine.last_chosen_holomem_id]
    targets_allowed = 1
    if hit_all_targets:
        targets_allowed = len(target_options)
    if len(target_options) == 0:
        pass
    elif len(target_options) == targets_allowed:
        target_options.reverse()
        for i in range(targets_allowed):
            engine.add_restore_holomem_hp_internal_effect(
                effect_player,
                target_options[i],
                effect["source_card_id"],
                amount
            )
    else:
        # Choose holomem for effect.
        decision_event = {
            "event_type": EventType.EventType_Decision_ChooseHolomemForEffect,
            "desired_response": GameAction.EffectResolution_ChooseCardsForEffect,
            "effect_player_id": effect_player_id,
            "cards_can_choose": target_options,
            "effect": effect,
        }
        engine.broadcast_event(decision_event)
        engine.set_decision({
            "decision_type": DecisionType.DecisionEffect_ChooseCardsForEffect,
            "decision_player": effect_player_id,
            "all_card_seen": target_options,
            "cards_can_choose": target_options,
            "amount_min": 1,
            "amount_max": 1,
            "source_card_id": effect["source_card_id"],
            "effect_resolution": engine.handle_restore_hp_for_holomem,
            "effect_amount": amount,
            "continuation": engine.continue_resolving_effects,
        })
        return True
    return False


def handle_restore_hp_internal(engine, effect_player, effect):
    """Returns True if continuation was passed on, False otherwise."""
    effect_player_id = effect_player.player_id
    target_player = effect["target_player"]
    target_card = effect["target_card"]
    amount = effect["amount"]
    engine.last_chosen_holomem_id = target_card
    engine.restore_holomem_hp(target_player, target_card, amount, engine.continue_resolving_effects)
    return True


def handle_modify_next_life_loss(engine, effect_player, effect):
    """Returns True if continuation was passed on, False otherwise."""
    effect_player_id = effect_player.player_id
    engine.next_life_loss_modifier += effect["amount"]
    return False


def handle_performance_life_lost_increase(engine, effect_player, effect):
    """Returns True if continuation was passed on, False otherwise."""
    effect_player_id = effect_player.player_id
    amount = effect["amount"]
    engine.next_life_loss_modifier += amount
    return False


def handle_deal_damage_per_tagged_holomem_and_cheer_in_archive(engine, effect_player, effect):
    """Counts #tagged holomems + all cheer in own archive, deals damage per count."""
    amount_per = effect["amount_per"]
    required_tags = effect.get("required_tags", [])
    count = 0
    for card in effect_player.archive:
        if is_card_cheer(card):
            count += 1
        elif is_card_holomem(card) and required_tags:
            if any(tag in card.get("tags", []) for tag in required_tags):
                count += 1
    effect_copy = deepcopy(effect)
    effect_copy["amount"] = amount_per * count
    effect_copy["effect_type"] = EffectType.EffectType_DealDamage
    engine.add_effects_to_front([effect_copy])
    return False


def handle_deal_damage_per_opponent_center_cheer(engine, effect_player, effect):
    """Deals damage based on the number of cheer attached to opponent's center holomem."""
    amount_per = effect["amount_per"]
    opponent = engine.other_player(effect_player.player_id)
    cheer_count = 0
    if len(opponent.center) > 0:
        cheer_count = len(opponent.center[0].get("attached_cheer", []))
    effect_copy = deepcopy(effect)
    effect_copy["amount"] = amount_per * cheer_count
    effect_copy["effect_type"] = EffectType.EffectType_DealDamage
    engine.add_effects_to_front([effect_copy])
    return False


def handle_deal_damage_per_die_rolls_this_turn(engine, effect_player, effect):
    """Deals special damage based on the number of dice rolled this turn."""
    amount_per = effect["amount_per"]
    die_roll_count = effect_player.die_rolls_this_turn
    effect_copy = deepcopy(effect)
    effect_copy["amount"] = amount_per * die_roll_count
    effect_copy["effect_type"] = EffectType.EffectType_DealDamage
    engine.add_effects_to_front([effect_copy])
    return False


DAMAGE_HANDLERS = {
    EffectType.EffectType_AddDamageTaken: handle_add_damage_taken,
    EffectType.EffectType_DealDamage: handle_deal_damage,
    EffectType.EffectType_DealDamage_Internal: handle_deal_damage_internal,
    EffectType.EffectType_DealDamagePerCheerInArchive: handle_deal_damage_per_cheer_in_archive,
    EffectType.EffectType_DealDamagePerHolomemOnStage: handle_deal_damage_per_holomem_on_stage,
    EffectType.EffectType_DealDamagePerOpponentCenterCheer: handle_deal_damage_per_opponent_center_cheer,
    EffectType.EffectType_DealDamagePerStacked: handle_deal_damage_per_stacked,
    EffectType.EffectType_DealDamagePerSupportInArchive: handle_deal_damage_per_support_in_archive,
    EffectType.EffectType_DealDamagePerTaggedHolomemAndCheerInArchive: handle_deal_damage_per_tagged_holomem_and_cheer_in_archive,
    EffectType.EffectType_DealDamagePerDieRollsThisTurn: handle_deal_damage_per_die_rolls_this_turn,
    EffectType.EffectType_DealLifeDamage: handle_deal_life_damage,
    EffectType.EffectType_DownHolomem: handle_down_holomem,
    EffectType.EffectType_RedirectDamage: handle_redirect_damage,
    EffectType.EffectType_ReduceDamage: handle_reduce_damage,
    EffectType.EffectType_ReduceRequiredArchiveCount: handle_reduce_required_archive_count,
    EffectType.EffectType_RestoreHp: handle_restore_hp,
    EffectType.EffectType_RestoreHp_Internal: handle_restore_hp_internal,
    EffectType.EffectType_ModifyNextLifeLoss: handle_modify_next_life_loss,
    EffectType.EffectType_PerformanceLifeLostIncrease: handle_performance_life_lost_increase,
}
