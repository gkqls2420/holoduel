from __future__ import annotations
from typing import TYPE_CHECKING

from app.engine.constants import *
from app.engine.models import *
from app.engine.helpers import *

if TYPE_CHECKING:
    from app.engine.player_state import PlayerState


def handle_power_boost(engine, effect_player, effect):
    """Returns True if continuation was passed on, False otherwise."""
    amount = effect["amount"]
    multiplier = 1
    if "multiplier" in effect:
        match effect["multiplier"]:
            case "last_die_value":
                multiplier = engine.last_die_value
            case "die_roll_sum":
                multiplier = sum(effect_player.last_die_roll_results)
            case "last_chosen_count":
                multiplier = len(engine.last_chosen_cards)
    amount *= multiplier
    engine.handle_power_boost(amount, effect["source_card_id"])
    return False


def handle_power_boost_per_all_fans(engine, effect_player, effect):
    """Returns True if continuation was passed on, False otherwise."""
    per_amount = effect["amount"]
    fans = get_cards_of_sub_type_from_holomems("fan", effect_player.get_holomem_on_stage())
    total = per_amount * len(fans)
    engine.handle_power_boost(total, effect["source_card_id"])
    return False


def handle_power_boost_per_all_mascots(engine, effect_player, effect):
    """Returns True if continuation was passed on, False otherwise."""
    per_amount = effect["amount"]
    mascots = get_cards_of_sub_type_from_holomems("mascot", effect_player.get_holomem_on_stage())
    total = per_amount * len(mascots)
    engine.handle_power_boost(total, effect["source_card_id"])
    return False


def handle_power_boost_per_attachment_name_on_stage(engine, effect_player, effect):
    """Returns True if continuation was passed on, False otherwise."""
    per_amount = effect["amount"]
    attachment_name = effect["attachment_name"]
    performer_only = effect.get("performer_only", False)
    if performer_only:
        holomems = [engine.performance_performer_card]
    else:
        holomems = effect_player.get_holomem_on_stage()
    count = 0
    for holomem in holomems:
        for attachment in holomem["attached_support"]:
            if attachment_name in attachment.get("card_names", []):
                count += 1
    total = per_amount * count
    engine.handle_power_boost(total, effect["source_card_id"])
    return False


def handle_power_boost_per_archived_holomem(engine, effect_player, effect):
    """Returns True if continuation was passed on, False otherwise."""
    per_amount = effect["amount"]
    holomems_in_archive = [card for card in effect_player.archive if is_card_holomem(card)]
    total = per_amount * len(holomems_in_archive)
    engine.handle_power_boost(total, effect["source_card_id"])
    return False


def handle_power_boost_per_cheer_on_both_stages(engine, effect_player, effect):
    """Returns True if continuation was passed on, False otherwise."""
    per_amount = effect["amount"]
    cheer_color = effect.get("cheer_color", "any")
    limit = effect.get("limit", 999)
    # 양측 스테이지의 홀로멤에 부착된 응원 수 세기
    count = 0
    for player in engine.player_states:
        for holomem in player.get_holomem_on_stage():
            for cheer in holomem["attached_cheer"]:
                if cheer_color == "any" or cheer_color in cheer.get("colors", []):
                    count += 1
    multiplier = min(count, limit)
    total = per_amount * multiplier
    engine.handle_power_boost(total, effect["source_card_id"])
    return False


def handle_power_boost_per_all_cheer_color_types(engine, effect_player, effect):
    """Returns True if continuation was passed on, False otherwise."""
    per_amount = effect["amount"]
    multiplier = len(effect_player.get_cheer_color_types_on_holomems())
    total = per_amount * multiplier
    engine.handle_power_boost(total, effect["source_card_id"])
    return False


def handle_power_boost_per_cheer_color_types(engine, effect_player, effect):
    """Returns True if continuation was passed on, False otherwise."""
    per_amount = effect["amount"]
    match effect.get("oshi_effect_target", ""):
        case "center":
            source_card = effect_player.center
        case "collab":
            source_card = effect_player.collab
        case _:
            source_card, _, _ = effect_player.find_card(effect["source_card_id"])
    cheer_color_types = set()
    for card in source_card:
        for attached_card in card["attached_cheer"]:
            if is_card_cheer(attached_card):
                cheer_color_types.update(attached_card["colors"])
    multiplier = len(cheer_color_types)
    total = per_amount * multiplier
    engine.handle_power_boost(total, effect["source_card_id"])
    return False


def handle_power_boost_per_attached_cheer(engine, effect_player, effect):
    """Returns True if continuation was passed on, False otherwise."""
    per_amount = effect["amount"]
    limit = effect.get("limit", 999)
    source_card, _, _ = effect_player.find_card(effect["source_card_id"])
    cheer_count = len(source_card["attached_cheer"])
    multiplier = min(cheer_count, limit)
    total = per_amount * multiplier
    engine.handle_power_boost(total, effect["source_card_id"])
    return False


def handle_power_boost_per_backstage(engine, effect_player, effect):
    """Returns True if continuation was passed on, False otherwise."""
    per_amount = effect["amount"]
    backstage_mems = len(effect_player.backstage)
    total = per_amount * backstage_mems
    engine.handle_power_boost(total, effect["source_card_id"])
    return False


def handle_power_boost_per_cards_in_hand(engine, effect_player, effect):
    """Returns True if continuation was passed on, False otherwise."""
    per_amount = effect["amount"]
    hand_count = len(effect_player.hand)
    total = per_amount * hand_count
    engine.handle_power_boost(total, effect["source_card_id"])
    return False


def handle_power_boost_per_lost_life(engine, effect_player, effect):
    """Returns True if continuation was passed on, False otherwise."""
    per_amount = effect["amount"]
    initial_life = effect_player.oshi_card["life"]
    current_life = len(effect_player.life)
    lost_life = initial_life - current_life
    total = per_amount * lost_life
    engine.handle_power_boost(total, effect["source_card_id"])
    return False


def handle_power_boost_per_holomem(engine, effect_player, effect):
    """Returns True if continuation was passed on, False otherwise."""
    per_amount = effect["amount"]
    holomems = effect_player.get_holomem_on_stage()
    match effect.get("exclude"):
        case "self":
            holomems = [h for h in holomems if h["game_card_id"] != effect["source_card_id"]]
    if "has_tag" in effect:
        holomems = [holomem for holomem in holomems if effect["has_tag"] in holomem["tags"]]
    if "bloom_level" in effect:
        holomems = [h for h in holomems if h.get("bloom_level", -1) == effect["bloom_level"]]
    # unique_names: count only unique card names
    if effect.get("unique_names"):
        seen_names = set()
        unique_holomems = []
        for h in holomems:
            name_tuple = tuple(h["card_names"])
            if name_tuple not in seen_names:
                seen_names.add(name_tuple)
                unique_holomems.append(h)
        holomems = unique_holomems
    total = per_amount * min(len(holomems), effect.get("limit", 99))
    engine.handle_power_boost(total, effect["source_card_id"])
    return False


def handle_power_boost_per_revealed_card(engine, effect_player, effect):
    """Returns True if continuation was passed on, False otherwise."""
    per_amount = effect["amount"]
    revealed_cards = effect_player.last_revealed_cards
    match effect.get("limitation"):
        case "holomem":
            revealed_cards = [card for card in revealed_cards if is_card_holomem(card)]
        case "support":
            revealed_cards = [card for card in revealed_cards if card["card_type"] == "support"]
    total = per_amount * len(revealed_cards)
    engine.handle_power_boost(total, effect["source_card_id"])
    return False


def handle_power_boost_per_stacked(engine, effect_player, effect):
    """Returns True if continuation was passed on, False otherwise."""
    per_amount = effect["amount"]
    stacked_cards = engine.performance_performer_card.get("stacked_cards", [])
    stacked_holomems = [card for card in stacked_cards if is_card_holomem(card)]
    total = per_amount * len(stacked_holomems)
    engine.handle_power_boost(total, effect["source_card_id"])
    return False


def handle_power_boost_per_played_support(engine, effect_player, effect):
    """Returns True if continuation was passed on, False otherwise."""
    per_amount = effect["amount"]
    sub_type = effect["support_sub_type"]
    limit = effect.get("limit", 999)
    if sub_type == "all":
        num_played = sum(effect_player.played_support_types_this_turn.values())
    elif sub_type == "limited":
        num_played = effect_player.limited_uses_count_this_turn
    else:
        num_played = effect_player.played_support_types_this_turn.get(sub_type, 0)
    multiplier = min(num_played, limit)
    total = per_amount * multiplier
    engine.handle_power_boost(total, effect["source_card_id"])
    return False


def handle_power_boost_per_condition(engine, effect_player, effect):
    """Returns True if continuation was passed on, False otherwise."""
    amount_per = effect["amount_per"]
    per_condition = effect["per"]
    print(f"DEBUG: PowerBoostPerCondition - amount_per: {amount_per}, per_condition: {per_condition}")
    # 조건에 따라 카운트를 계산
    condition_count = engine.get_condition_count(effect_player, effect["source_card_id"], per_condition)
    total = amount_per * condition_count
    print(f"DEBUG: PowerBoostPerCondition - condition_count: {condition_count}, total: {total}")
    engine.handle_power_boost(total, effect["source_card_id"])
    return False


def handle_power_boost_per_opponent_archive_cheer(engine, effect_player, effect):
    """Power boost based on cheer count in opponent's archive."""
    per_amount = effect["amount"]
    limit = effect.get("limit", 999)
    opponent = engine.other_player(effect_player.player_id)
    cheer_count = sum(1 for card in opponent.archive if is_card_cheer(card))
    multiplier = min(cheer_count, limit)
    total = per_amount * multiplier
    engine.handle_power_boost(total, effect["source_card_id"])
    return False


def handle_power_boost_per_cheer_in_archive(engine, effect_player, effect):
    """Power boost based on cheer count in player's own archive."""
    per_amount = effect["amount"]
    limit = effect.get("limit", 999)
    cheer_count = sum(1 for card in effect_player.archive if is_card_cheer(card))
    multiplier = min(cheer_count, limit)
    total = per_amount * multiplier
    engine.handle_power_boost(total, effect["source_card_id"])
    return False


def handle_power_boost_per_holopower(engine, effect_player, effect):
    """Power boost based on the number of cards in the player's holopower zone."""
    per_amount = effect["amount"]
    holopower_count = len(effect_player.holopower)
    total = per_amount * holopower_count
    engine.handle_power_boost(total, effect["source_card_id"])
    return False


def handle_power_boost_per_resting_opponent_holomem(engine, effect_player, effect):
    """Power boost based on the number of resting holomems on opponent's stage."""
    per_amount = effect["amount"]
    opponent = engine.other_player(effect_player.player_id)
    resting_count = sum(1 for card in opponent.get_holomem_on_stage() if is_card_resting(card))
    total = per_amount * resting_count
    engine.handle_power_boost(total, effect["source_card_id"])
    return False


def handle_set_damage_cannot_be_reduced(engine, effect_player, effect):
    """Returns True if continuation was passed on, False otherwise."""
    engine.performance_artstatboosts.cannot_be_reduced = True
    return False


def handle_set_deal_damage_to_center_and_collab(engine, effect_player, effect):
    """Sets the flag to deal full damage to both opponent's center and collab."""
    engine.performance_artstatboosts.deal_to_center_and_collab = True
    return False


POWER_BOOST_HANDLERS = {
    EffectType.EffectType_PowerBoost: handle_power_boost,
    EffectType.EffectType_PowerBoostPerAllFans: handle_power_boost_per_all_fans,
    EffectType.EffectType_PowerBoostPerAllMascots: handle_power_boost_per_all_mascots,
    EffectType.EffectType_PowerBoostPerAttachmentNameOnStage: handle_power_boost_per_attachment_name_on_stage,
    EffectType.EffectType_PowerBoostPerArchivedHolomem: handle_power_boost_per_archived_holomem,
    EffectType.EffectType_PowerBoostPerCheerOnBothStages: handle_power_boost_per_cheer_on_both_stages,
    EffectType.EffectType_PowerBoostPerAllCheerColorTypes: handle_power_boost_per_all_cheer_color_types,
    EffectType.EffectType_PowerBoostPerCheerColorTypes: handle_power_boost_per_cheer_color_types,
    EffectType.EffectType_PowerBoostPerAttachedCheer: handle_power_boost_per_attached_cheer,
    EffectType.EffectType_PowerBoostPerBackstage: handle_power_boost_per_backstage,
    EffectType.EffectType_PowerBoostPerCardsInHand: handle_power_boost_per_cards_in_hand,
    EffectType.EffectType_PowerBoostPerLostLife: handle_power_boost_per_lost_life,
    EffectType.EffectType_PowerBoostPerHolomem: handle_power_boost_per_holomem,
    EffectType.EffectType_PowerBoostPerRevealedCard: handle_power_boost_per_revealed_card,
    EffectType.EffectType_PowerBoostPerStacked: handle_power_boost_per_stacked,
    EffectType.EffectType_PowerBoostPerPlayedSupport: handle_power_boost_per_played_support,
    EffectType.EffectType_PowerBoostPerCondition: handle_power_boost_per_condition,
    EffectType.EffectType_PowerBoostPerOpponentArchiveCheer: handle_power_boost_per_opponent_archive_cheer,
    EffectType.EffectType_PowerBoostPerCheerInArchive: handle_power_boost_per_cheer_in_archive,
    EffectType.EffectType_PowerBoostPerHolopower: handle_power_boost_per_holopower,
    EffectType.EffectType_PowerBoostPerRestingOpponentHolomem: handle_power_boost_per_resting_opponent_holomem,
    EffectType.EffectType_SetDamageCannotBeReduced: handle_set_damage_cannot_be_reduced,
    EffectType.EffectType_SetDealDamageToCenterAndCollab: handle_set_deal_damage_to_center_and_collab,
}
