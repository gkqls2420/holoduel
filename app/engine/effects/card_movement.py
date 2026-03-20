from __future__ import annotations
from typing import TYPE_CHECKING
from copy import deepcopy

from app.engine.constants import *
from app.engine.models import *
from app.engine.helpers import *

if TYPE_CHECKING:
    from app.engine.player_state import PlayerState


def handle_archive_cheer_from_holomem(engine, effect_player, effect):
    """Returns True if continuation was passed on, False otherwise."""
    effect_player_id = effect_player.player_id
    source_card, _, _ = effect_player.find_card(effect["source_card_id"])
    ability_source = effect.get("ability_source", "")
    engine.archive_count_required = effect["amount"]
    before_archive_effects = effect_player.get_effects_at_timing("before_archive_cheer", source_card, ability_source)

    def archive_cheer_continuation():
        amount = engine.archive_count_required
        # Handle "all" amount - calculate actual cheer count for this holomem
        if str(amount) == "all":
            from_zone = effect["from"]
            if from_zone == "self":
                src_card, _, _ = effect_player.find_card(effect["source_card_id"])
                amount = len(src_card["attached_cheer"]) if src_card else 0
            elif from_zone == "attached_owner":
                owner_holomems = effect_player.get_holomems_with_attachment(effect["source_card_id"])
                amount = len(owner_holomems[0]["attached_cheer"]) if owner_holomems else 0
            else:
                amount = sum(len(h["attached_cheer"]) for h in effect_player.get_holomem_on_stage())
        from_zone = effect["from"]
        required_colors = effect.get("required_colors", [])
        target_holomems = []
        ability_source = effect.get("ability_source", "")
        match from_zone:
            case "self":
                source_card, _, _ = effect_player.find_card(effect["source_card_id"])
                target_holomems.append(source_card)
            case "attached_owner":
                holomems = effect_player.get_holomems_with_attachment(effect["source_card_id"])
                if holomems:
                    target_holomems.append(holomems[0])
            case "holomem":
                target_holomems = effect_player.get_holomem_on_stage()
        excluded_colors = effect.get("excluded_colors", [])
        cheer_options = []
        for holomem in target_holomems:
            if required_colors:
                matched_cheer = []
                for cheer in holomem["attached_cheer"]:
                    if any(color in cheer["colors"] for color in required_colors):
                        matched_cheer.append(cheer)
                cheer_options += ids_from_cards(matched_cheer)
            elif excluded_colors:
                matched_cheer = [c for c in holomem["attached_cheer"]
                                 if not any(color in c["colors"] for color in excluded_colors)]
                cheer_options += ids_from_cards(matched_cheer)
            else:
                cheer_options += ids_from_cards(holomem["attached_cheer"])
        after_archive_check_effect = {
            "player_id": effect_player_id,
            "effect_type": EffectType.EffectType_AfterArchiveCheerCheck,
            "effect_player_id": effect_player_id,
            "previous_archive_count": len(effect_player.archive),
            "ability_source": ability_source
        }
        engine.add_effects_to_front([after_archive_check_effect])
        if amount == 0:
            engine.continue_resolving_effects()
        elif amount == len(cheer_options):
            # Do it immediately.
            effect_player.archive_attached_cards(cheer_options)
            engine.continue_resolving_effects()
        else:
            choose_event = {
                "event_type": EventType.EventType_Decision_ChooseCards,
                "desired_response": GameAction.EffectResolution_ChooseCardsForEffect,
                "effect_player_id": effect_player_id,
                "all_card_seen": cheer_options,
                "cards_can_choose": cheer_options,
                "from_zone": "holomem",
                "to_zone": "archive",
                "amount_min": amount,
                "amount_max": amount,
                "reveal_chosen": True,
                "remaining_cards_action": "nothing",
            }
            engine.broadcast_event(choose_event)
            engine.set_decision({
                "decision_type": DecisionType.DecisionEffect_ChooseCardsForEffect,
                "decision_player": effect_player_id,
                "all_card_seen": cheer_options,
                "cards_can_choose": cheer_options,
                "from_zone": "holomem",
                "to_zone": "archive",
                "amount_min": amount,
                "amount_max": amount,
                "reveal_chosen": True,
                "remaining_cards_action": "nothing",
                "source_card_id": effect["source_card_id"],
                "effect_resolution": engine.handle_choose_cards_result,
                "continuation": engine.continue_resolving_effects,
            })

    engine.begin_resolving_effects(before_archive_effects, archive_cheer_continuation)
    return True


def handle_archive_from_hand(engine, effect_player, effect):
    """Returns True if continuation was passed on, False otherwise."""
    effect_player_id = effect_player.player_id
    if "amount_min" in effect:
        amount_min = effect["amount_min"]
        amount_max = effect["amount_max"]
    else:
        amount_min = effect["amount"]
        amount_max = effect["amount"]
    ability_source = effect.get("ability_source", "")
    requirement_same_tag = effect.get("requirement_same_tag", False)
    engine.archive_count_required = amount_max
    before_archive_effects = effect_player.get_effects_at_timing("before_archive", None, ability_source)

    def archive_hand_continuation():
        if engine.archive_count_required > 0:
            cards_can_choose = []
            match effect.get("requirement"):
                case "holomem":
                    cards_can_choose = ([card["game_card_id"] for card in effect_player.hand if is_card_holomem(card)])
                case "support":
                    cards_can_choose = ([card["game_card_id"] for card in effect_player.hand if card.get("card_type") == "support"])
                case _:
                    cards_can_choose = ids_from_cards(effect_player.hand)
            if requirement_same_tag:
                holomem_cards = [card for card in effect_player.hand if is_card_holomem(card)]
                eligible_ids = set()
                for i, card_a in enumerate(holomem_cards):
                    for card_b in holomem_cards[i+1:]:
                        if set(card_a.get("tags", [])) & set(card_b.get("tags", [])):
                            eligible_ids.add(card_a["game_card_id"])
                            eligible_ids.add(card_b["game_card_id"])
                cards_can_choose = [cid for cid in cards_can_choose if cid in eligible_ids]
            actual_max = min(engine.archive_count_required, len(cards_can_choose))
            actual_min = min(amount_min, actual_max)
            if actual_max == 0:
                engine.continue_resolving_effects()
                return
            all_card_seen = ids_from_cards(effect_player.hand)
            requirement_details = {}
            if requirement_same_tag:
                requirement_details["requirement_same_tag"] = True
            choose_event = {
                "event_type": EventType.EventType_Decision_ChooseCards,
                "desired_response": GameAction.EffectResolution_ChooseCardsForEffect,
                "effect_player_id": effect_player_id,
                "all_card_seen": all_card_seen,
                "cards_can_choose": cards_can_choose,
                "from_zone": "hand",
                "to_zone": "archive",
                "amount_min": actual_min,
                "amount_max": actual_max,
                "reveal_chosen": True,
                "remaining_cards_action": "nothing",
                "requirement_details": requirement_details,
                "hidden_info_player": effect_player_id,
                "hidden_info_fields": ["all_card_seen", "cards_can_choose"],
            }
            engine.broadcast_event(choose_event)
            engine.set_decision({
                "decision_type": DecisionType.DecisionEffect_ChooseCardsForEffect,
                "decision_player": effect_player_id,
                "all_card_seen": all_card_seen,
                "cards_can_choose": cards_can_choose,
                "from_zone": "hand",
                "to_zone": "archive",
                "amount_min": actual_min,
                "amount_max": actual_max,
                "reveal_chosen": True,
                "remaining_cards_action": "nothing",
                "requirement_same_tag": requirement_same_tag,
                "source_card_id": effect["source_card_id"],
                "effect_resolution": engine.handle_choose_cards_result,
                "continuation": engine.continue_resolving_effects,
            })
        else:
            engine.continue_resolving_effects()

    engine.begin_resolving_effects(before_archive_effects, archive_hand_continuation)
    return True


def handle_archive_revealed_cards(engine, effect_player, effect):
    """Returns True if continuation was passed on, False otherwise."""
    effect_player_id = effect_player.player_id
    engine.archive_count_required = len(effect_player.last_revealed_cards)
    before_archive_effects = effect_player.get_effects_at_timing("before_archive", None)

    def archive_revealed_cards_continuation():
        for revealed_card in effect_player.last_revealed_cards:
            effect_player.move_card(revealed_card["game_card_id"], "archive")
        engine.continue_resolving_effects()

    engine.begin_resolving_effects(before_archive_effects, archive_revealed_cards_continuation)
    return True


def handle_archive_this_attachment(engine, effect_player, effect):
    """Returns True if continuation was passed on, False otherwise."""
    effect_player_id = effect_player.player_id
    attachment_id = effect["source_card_id"]

    attachment_card = engine.find_card(attachment_id)
    attachment_holomem = None
    if attachment_card:
        for holomem in effect_player.get_holomem_on_stage():
            for attached in holomem.get("attached_support", []):
                if attached["game_card_id"] == attachment_id:
                    attachment_holomem = holomem
                    break
            if attachment_holomem:
                break

    engine.archiving_attachment_card = attachment_card
    engine.archiving_attachment_holomem = attachment_holomem
    engine.archive_attachment_replaced = False

    before_effects = effect_player.get_effects_at_timing("before_archive_attachment", attachment_card, "") if attachment_card else []
    if before_effects:
        def archive_continuation():
            if not engine.archive_attachment_replaced:
                effect_player.archive_attached_cards([attachment_id])
            engine.archiving_attachment_card = None
            engine.archiving_attachment_holomem = None
        engine.begin_resolving_effects(before_effects, archive_continuation)
        return True

    effect_player.archive_attached_cards([attachment_id])
    engine.archiving_attachment_card = None
    engine.archiving_attachment_holomem = None
    return False


def handle_replace_archive_with_move(engine, effect_player, effect):
    """Replaces an about-to-be-archived attachment by moving it to a different holomem instead."""
    if not engine.archiving_attachment_card:
        return False
    attachment_id = engine.archiving_attachment_card["game_card_id"]
    to_name = effect.get("to_limitation_name", "")
    to_zone = effect.get("to_zone", "backstage")

    target_holomems = []
    match to_zone:
        case "backstage":
            target_holomems = effect_player.backstage
        case "center":
            target_holomems = effect_player.center
        case _:
            target_holomems = effect_player.get_holomem_on_stage()
    if to_name:
        target_holomems = [h for h in target_holomems if to_name in h.get("card_names", [])]
    if not target_holomems:
        return False

    attachment_card, previous_holder_id = effect_player.find_and_remove_attached(attachment_id)
    if not attachment_card:
        return False

    target = target_holomems[0]
    target["attached_support"].append(attachment_card)
    move_event = {
        "event_type": EventType.EventType_MoveAttachedCard,
        "owning_player_id": effect_player.player_id,
        "from_holomem_id": previous_holder_id,
        "to_holomem_id": target["game_card_id"],
        "attached_id": attachment_id,
    }
    engine.broadcast_event(move_event)
    engine.archive_attachment_replaced = True
    return False


def handle_archive_attachment_from_stage_by_name(engine, effect_player, effect):
    """Returns True if continuation was passed on, False otherwise."""
    effect_player_id = effect_player.player_id
    attachment_name = effect.get("attachment_name", "")
    destination = effect.get("destination", "archive")
    holomems = effect_player.get_holomem_on_stage()
    for holomem in holomems:
        for attached in holomem.get("attached_support", []):
            if attachment_name in attached.get("card_names", []):
                if destination == "bottom_of_deck":
                    effect_player.move_card(attached["game_card_id"], "deck", add_to_bottom=True)
                else:
                    effect_player.archive_attached_cards([attached["game_card_id"]])
                break
        else:
            continue
        break
    return False


def handle_return_this_attachment_to_hand(engine, effect_player, effect):
    """Returns True if continuation was passed on, False otherwise."""
    effect_player_id = effect_player.player_id
    attachment_id = effect["source_card_id"]
    effect_player.move_card(attachment_id, "hand")
    return False


def handle_return_this_attachment_to_deck_bottom(engine, effect_player, effect):
    """Returns True if continuation was passed on, False otherwise."""
    effect_player_id = effect_player.player_id
    attachment_id = effect["source_card_id"]
    effect_player.move_card(attachment_id, "deck", add_to_bottom=True)
    return False


def handle_return_this_card_to_deck(engine, effect_player, effect):
    """Returns True if continuation was passed on, False otherwise."""
    card_id = effect["source_card_id"]
    effect_player.move_card(card_id, "deck")
    effect_player.shuffle_deck()
    return False


def handle_archive_top_stacked_holomem(engine, effect_player, effect):
    """Returns True if continuation was passed on, False otherwise."""
    effect_player_id = effect_player.player_id
    card, _, _ = effect_player.find_card(effect["source_card_id"])
    if len(card["stacked_cards"]) > 0:
        top_card = card["stacked_cards"][0]
        effect_player.archive_attached_cards([top_card["game_card_id"]])
    return False


def handle_archive_stacked_holomem(engine, effect_player, effect):
    """Archive a selected stacked holomem, with optional card_type filter and from_member_name."""
    effect_player_id = effect_player.player_id
    requirement_card_type = effect.get("requirement_card_type", "")
    from_member_name = effect.get("from_member_name", "")

    candidates = []
    if from_member_name:
        for holomem in effect_player.get_holomem_on_stage():
            if from_member_name in holomem.get("card_names", []):
                for stacked in holomem["stacked_cards"]:
                    if is_card_holomem(stacked):
                        if requirement_card_type and stacked.get("card_type", "") != requirement_card_type:
                            continue
                        candidates.append(stacked["game_card_id"])
    else:
        card, _, _ = effect_player.find_card(effect["source_card_id"])
        for stacked in card["stacked_cards"]:
            if is_card_holomem(stacked):
                if requirement_card_type and stacked.get("card_type", "") != requirement_card_type:
                    continue
                candidates.append(stacked["game_card_id"])

    if len(candidates) == 0:
        return False
    elif len(candidates) == 1:
        effect_player.archive_attached_cards([candidates[0]])
    else:
        decision_event = {
            "event_type": EventType.EventType_Decision_ChooseCards,
            "desired_response": GameAction.EffectResolution_ChooseCardsForEffect,
            "effect_player_id": effect_player_id,
            "cards_can_choose": candidates,
            "amount_min": 1,
            "amount_max": 1,
        }
        engine.broadcast_event(decision_event)
        engine.set_decision({
            "decision_type": DecisionType.DecisionEffect_ChooseCardsForEffect,
            "decision_player": effect_player_id,
            "all_card_seen": candidates,
            "cards_can_choose": candidates,
            "amount_min": 1,
            "amount_max": 1,
            "effect_resolution": lambda engine, ids: effect_player.archive_attached_cards(ids),
            "continuation": engine.continue_resolving_effects,
        })
        return True
    return False


def handle_attach_card_to_holomem(engine, effect_player, effect):
    """Returns True if continuation was passed on, False otherwise."""
    effect_player_id = effect_player.player_id
    source_card_id = effect["source_card_id"]
    continuation = engine.continue_resolving_effects
    if "continuation" in effect:
        # This effect can be called from elsewhere, so use special continuations
        # if they were added on.
        continuation = effect["continuation"]
    holomem_targets = effect_player.get_holomem_on_stage()
    to_limitation = effect.get("to_limitation", "")
    to_limitation_colors = effect.get("to_limitation_colors", [])
    to_limitation_tags = effect.get("to_limitation_tags", [])
    to_limitation_name = effect.get("to_limitation_name", "")
    match to_limitation:
        case "color_in":
            holomem_targets = [holomem for holomem in holomem_targets \
                if any(color in holomem["colors"] for color in to_limitation_colors)]
        case "specific_member_name":
            holomem_targets = [holomem for holomem in holomem_targets \
                if to_limitation_name in holomem["card_names"]]
            to_limitation_bloom_level = effect.get("to_limitation_bloom_level", None)
            if to_limitation_bloom_level is not None:
                holomem_targets = [holomem for holomem in holomem_targets \
                    if holomem.get("bloom_level", 0) == to_limitation_bloom_level]
        case "member_name_in":
            to_limitation_names = effect.get("to_limitation_names", [])
            holomem_targets = [holomem for holomem in holomem_targets \
                if any(name in holomem["card_names"] for name in to_limitation_names)]
        case "tag_in":
            holomem_targets = [holomem for holomem in holomem_targets \
                if any(tag in holomem["tags"] for tag in to_limitation_tags)]
        case "backstage":
            holomem_targets = effect_player.backstage
        case "backstage_and_tag_in":
            holomem_targets = [holomem for holomem in effect_player.backstage \
                if any(tag in holomem["tags"] for tag in to_limitation_tags)]
        case "source_card":
            attach_to_card_id = effect.get("attach_to_card_id", "")
            if attach_to_card_id:
                holomem_targets = [h for h in holomem_targets if h["game_card_id"] == attach_to_card_id]

    exclude_card_id = effect.get("exclude_card_id", "")
    if exclude_card_id:
        holomem_targets = [h for h in holomem_targets if h["game_card_id"] != exclude_card_id]

    # restriction for mascots and tools
    card_to_attach, _, _ = effect_player.find_card(source_card_id, include_stacked_cards=True)
    # filters out cards that can be attached against support card restrictions
    holomem_targets = [holomem for holomem in holomem_targets if engine.holomem_can_be_attached_with_support_card(holomem, card_to_attach)]

    if len(holomem_targets) > 0:
        attach_effect = {
            "effect_type": EffectType.EffectType_AttachCardToHolomem_Internal,
            "effect_player_id": effect_player.player_id,
            "card_id": source_card_id,
            "card_ids": [], # Filled in by the decision.
            "to_limitation": to_limitation,
            "to_limitation_colors": to_limitation_colors,
            "to_limitation_tags": to_limitation_tags,
            "to_limitation_name": to_limitation_name,
            "internal_skip_simultaneous_choice": True,
        }
        add_ids_to_effects([attach_effect], effect_player.player_id, source_card_id)
        decision_event = {
            "event_type": EventType.EventType_Decision_ChooseHolomemForEffect,
            "desired_response": GameAction.EffectResolution_ChooseCardsForEffect,
            "effect_player_id": effect_player.player_id,
            "cards_can_choose": ids_from_cards(holomem_targets),
            "effect": attach_effect,
        }
        engine.broadcast_event(decision_event)
        engine.set_decision({
            "decision_type": DecisionType.DecisionEffect_ChooseCardsForEffect,
            "decision_player": effect_player.player_id,
            "all_card_seen": ids_from_cards(holomem_targets),
            "cards_can_choose": ids_from_cards(holomem_targets),
            "amount_min": 1,
            "amount_max": 1,
            "effect_to_run": attach_effect,
            "effect_resolution": engine.handle_run_single_effect,
            "continuation": continuation,
        })
    else:
        continuation()
        return True
    return False


def handle_attach_card_to_holomem_internal(engine, effect_player, effect):
    """Returns True if continuation was passed on, False otherwise."""
    effect_player_id = effect_player.player_id
    card_to_attach_id = effect["card_id"]
    target_holomem_id = effect["card_ids"][0]
    effect_player.move_card(card_to_attach_id, "holomem", target_holomem_id)
    attached_card = effect_player.find_attachment(card_to_attach_id)
    if attached_card and "attached_effects" in attached_card:
        on_attach_effects = [deepcopy(e) for e in attached_card["attached_effects"]
                                      if e.get("timing") == "on_attach"]
        if on_attach_effects:
            add_ids_to_effects(on_attach_effects, effect_player.player_id, card_to_attach_id)
            engine.add_effects_to_front(on_attach_effects)
    return False


def handle_draw(engine, effect_player, effect):
    """Returns True if continuation was passed on, False otherwise."""
    effect_player_id = effect_player.player_id
    amount_source = effect.get("amount_source", None)
    if amount_source == "last_chosen_count_divided_by":
        divisor = effect.get("divisor", 2)
        amount = len(engine.last_chosen_cards) // divisor
    elif amount_source == "unique_tag_holomem_count":
        tag = effect.get("has_tag", "")
        holomems = [h for h in effect_player.get_holomem_on_stage() if tag in h.get("tags", [])]
        seen_names = set()
        for h in holomems:
            seen_names.add(tuple(h["card_names"]))
        amount = len(seen_names)
    else:
        amount = effect.get("amount", len(effect_player.hand))
        if str(amount) == "last_card_count":
            amount = engine.last_card_count
            engine.last_card_count = 0
    draw_to_hand_size = effect.get("draw_to_hand_size")
    if draw_to_hand_size:
        amount = max(0, draw_to_hand_size - amount)
    if amount > 0:
        target_player = effect_player
        if effect.get("opponent", False):
            target_player = engine.other_player(effect_player_id)
        from_bottom = effect.get("from_bottom", False)
        target_player.draw(amount, from_bottom=from_bottom)
    return False


def handle_generate_holopower(engine, effect_player, effect):
    """Returns True if continuation was passed on, False otherwise."""
    effect_player_id = effect_player.player_id
    amount = effect["amount"]
    effect_player.generate_holopower(amount)
    return False


def can_move_cheer_between_holomems(engine, effect_player, effect):
    """Check if move_cheer_between_holomems would have valid targets and cheer to move."""
    opponent = effect.get("opponent", False)
    target_player = engine.other_player(effect_player.player_id) if opponent else effect_player
    to_limitation = effect.get("to_limitation", "")
    to_limitation_tags = effect.get("to_limitation_tags", [])
    from_limitation = effect.get("from_limitation", "")
    if from_limitation == "source_card":
        source_card_id = effect.get("source_card_id", "")
        available_cheer = []
        for card in target_player.get_holomem_on_stage():
            if card["game_card_id"] == source_card_id or any(a.get("game_card_id") == source_card_id for a in card.get("stacked_cards", [])):
                for attached_card in card["attached_cheer"]:
                    if is_card_cheer(attached_card):
                        available_cheer.append(attached_card["game_card_id"])
                break
    else:
        available_cheer = target_player.get_cheer_ids_on_holomems()
    available_targets = target_player.get_holomem_on_stage()
    to_limitation_location = effect.get("to_limitation_location", "")
    if to_limitation_location == "backstage":
        available_targets = [h for h in available_targets if h["game_card_id"] != target_player.center[0]["game_card_id"]] if target_player.center else available_targets
    match to_limitation:
        case "tag_in":
            available_targets = [holomem for holomem in available_targets if any(tag in holomem["tags"] for tag in to_limitation_tags)]
        case "specific_member_name":
            to_limitation_name = effect.get("to_limitation_name", "")
            available_targets = [holomem for holomem in available_targets if to_limitation_name in holomem["card_names"]]
            to_limitation_bloom_level = effect.get("to_limitation_bloom_level", None)
            if to_limitation_bloom_level is not None:
                available_targets = [holomem for holomem in available_targets \
                    if holomem.get("bloom_level", 0) == to_limitation_bloom_level]
        case "last_chosen":
            available_targets = [card for card in available_targets if card["game_card_id"] in engine.last_chosen_cards]
    if effect.get("to_exclude_source", False):
        source_card_id = effect.get("source_card_id", "")
        available_targets = [h for h in available_targets if h["game_card_id"] != source_card_id]
    if effect.get("to_exclude_previous_target", False):
        last_target = getattr(engine, "last_move_cheer_target", None)
        if last_target:
            available_targets = [h for h in available_targets if h["game_card_id"] != last_target]
    available_targets = ids_from_cards(available_targets)

    has_to_limitation = to_limitation != "" or effect.get("to_exclude_source", False) or to_limitation_location != "" or effect.get("to_exclude_previous_target", False)
    return (has_to_limitation and len(available_targets) >= 1
        or not has_to_limitation and len(available_targets) > 1) and len(available_cheer) > 0


def handle_move_cheer_between_holomems(engine, effect_player, effect):
    """Returns True if continuation was passed on, False otherwise."""
    effect_player_id = effect_player.player_id
    opponent = effect.get("opponent", False)
    target_player = engine.other_player(effect_player_id) if opponent else effect_player
    amount_min = effect.get("amount_min", effect.get("amount", 1))
    amount_max = effect.get("amount_max", effect.get("amount", amount_min))
    to_limitation = effect.get("to_limitation", "")
    to_limitation_tags = effect.get("to_limitation_tags", [])
    from_limitation = effect.get("from_limitation", "")
    if from_limitation == "source_card":
        source_card_id = effect.get("source_card_id", "")
        available_cheer = []
        for card in target_player.get_holomem_on_stage():
            if card["game_card_id"] == source_card_id or any(a.get("game_card_id") == source_card_id for a in card.get("stacked_cards", [])):
                for attached_card in card["attached_cheer"]:
                    if is_card_cheer(attached_card):
                        available_cheer.append(attached_card["game_card_id"])
                break
    else:
        available_cheer = target_player.get_cheer_ids_on_holomems()
    available_targets = target_player.get_holomem_on_stage()
    to_limitation_location = effect.get("to_limitation_location", "")
    if to_limitation_location == "backstage":
        available_targets = [h for h in available_targets if h["game_card_id"] != target_player.center[0]["game_card_id"]] if target_player.center else available_targets
    match to_limitation:
        case "tag_in":
            available_targets = [holomem for holomem in available_targets if any(tag in holomem["tags"] for tag in to_limitation_tags)]
        case "specific_member_name":
            to_limitation_name = effect.get("to_limitation_name", "")
            available_targets = [holomem for holomem in available_targets if to_limitation_name in holomem["card_names"]]
            to_limitation_bloom_level = effect.get("to_limitation_bloom_level", None)
            if to_limitation_bloom_level is not None:
                available_targets = [holomem for holomem in available_targets \
                    if holomem.get("bloom_level", 0) == to_limitation_bloom_level]
        case "last_chosen":
            available_targets = [card for card in available_targets if card["game_card_id"] in engine.last_chosen_cards]
    if effect.get("to_exclude_source", False):
        source_card_id = effect.get("source_card_id", "")
        available_targets = [h for h in available_targets if h["game_card_id"] != source_card_id]
    if effect.get("to_exclude_previous_target", False):
        last_target = getattr(engine, "last_move_cheer_target", None)
        if last_target:
            available_targets = [h for h in available_targets if h["game_card_id"] != last_target]
    available_targets = ids_from_cards(available_targets)
    cheer_on_each_mem = target_player.get_cheer_on_each_holomem()

    has_to_limitation = to_limitation != "" or effect.get("to_exclude_source", False) or to_limitation_location != "" or effect.get("to_exclude_previous_target", False)
    if (has_to_limitation and len(available_targets) >= 1
        or not has_to_limitation and len(available_targets) > 1) and len(available_cheer) > 0:
        decision_event = {
            "event_type": EventType.EventType_Decision_SendCheer,
            "desired_response": GameAction.EffectResolution_MoveCheerBetweenHolomems,
            "effect_player_id": effect_player_id,
            "amount_min": amount_min,
            "amount_max": amount_max,
            "from_zone": "holomem",
            "to_zone": "holomem",
            "from_options": available_cheer,
            "to_options": available_targets,
            "cheer_on_each_mem": cheer_on_each_mem,
        }
        engine.broadcast_event(decision_event)
        engine.set_decision({
            "decision_type": DecisionType.DecisionEffect_MoveCheerBetweenHolomems,
            "decision_player": effect_player_id,
            "amount_min": amount_min,
            "amount_max": amount_max,
            "available_cheer": available_cheer,
            "available_targets": available_targets,
            "multi_to": effect.get("multi_to", False),
            "continuation": engine.continue_resolving_effects,
        })
    return False


def handle_return_cheer_and_draw(engine, effect_player, effect):
    """Returns cheer from this holomem to cheer deck bottom, then draws to match returned count.
    Returns True if continuation was passed on, False otherwise."""
    effect_player_id = effect_player.player_id
    source_card_id = effect.get("source_card_id", "")
    return_from = effect.get("return_from", "this_holomem")
    return_to = effect.get("return_to", "cheer_deck_bottom")
    use_order = effect.get("order", False)
    draw_to_match = effect.get("draw_to_match_returned_count", False)

    # Get this holomem and its attached cheer
    source_card, _, _ = effect_player.find_card(source_card_id)
    if not source_card:
        owner_holomems = effect_player.get_holomems_with_attachment(source_card_id)
        source_card = owner_holomems[0] if owner_holomems else None
    if not source_card:
        return False

    cheer_cards = [c for c in source_card.get("attached_cheer", []) if is_card_cheer(c)]
    cheer_ids = ids_from_cards(cheer_cards)
    returned_count = len(cheer_ids)

    if returned_count == 0:
        return False

    def do_draw_and_continue():
        if draw_to_match:
            draw_count = max(0, returned_count - len(effect_player.hand))
            if draw_count > 0:
                effect_player.draw(draw_count)
        engine.continue_resolving_effects()

    if use_order and returned_count > 1:
        engine.choose_cards_cleanup_remaining(
            effect_player_id,
            cheer_ids,
            "order_on_bottom",
            "holomem",
            "cheer_deck",
            do_draw_and_continue,
        )
        return True
    else:
        placements = {cid: "cheer_deck_bottom" for cid in cheer_ids}
        effect_player.move_cheer_between_holomems(placements)
        if draw_to_match:
            draw_count = max(0, returned_count - len(effect_player.hand))
            if draw_count > 0:
                effect_player.draw(draw_count)
        return False


def handle_return_revealed_to_holopower_bottom(engine, effect_player, effect):
    """Returns True if continuation was passed on, False otherwise."""
    revealed = getattr(effect_player, "last_revealed_cards", [])
    for card in revealed:
        if card in effect_player.holopower:
            effect_player.holopower.remove(card)
            effect_player.holopower.append(card)
    effect_player.last_revealed_cards = []
    return False


def handle_reveal_top_deck(engine, effect_player, effect):
    """Returns True if continuation was passed on, False otherwise."""
    effect_player_id = effect_player.player_id
    if len(effect_player.deck) > 0:
        amount = effect.get("amount", 1)
        top_cards = effect_player.deck[:amount]
        effect_player.last_revealed_cards = top_cards
        reveal_event = {
            "event_type": EventType.EventType_RevealCards,
            "effect_player_id": effect_player_id,
            "card_ids": ids_from_cards(top_cards),
            "source": "topdeck"
        }
        engine.broadcast_event(reveal_event)
        after_reveal_effects = effect_player.get_effects_at_timing("after_reveal", None)
        engine.add_effects_to_front(after_reveal_effects)
    return False


def handle_reveal_top_holopower(engine, effect_player, effect):
    """Returns True if continuation was passed on, False otherwise."""
    effect_player_id = effect_player.player_id
    if len(effect_player.holopower) > 0:
        amount = effect.get("amount", 1)
        top_cards = effect_player.holopower[:amount]
        effect_player.last_revealed_cards = top_cards
        reveal_event = {
            "event_type": EventType.EventType_RevealCards,
            "effect_player_id": effect_player_id,
            "card_ids": ids_from_cards(top_cards),
            "source": "topholopower"
        }
        engine.broadcast_event(reveal_event)
    else:
        effect_player.last_revealed_cards = []
    return False


def handle_send_cheer(engine, effect_player, effect):
    """Returns True if continuation was passed on, False otherwise."""
    effect_player_id = effect_player.player_id
    # Compute amount_min/amount_max (may be overridden by dynamic sources)
    amount_min = effect.get("amount_min")
    amount_max = effect.get("amount_max")
    if amount_min is None:
        amount_min = effect.get("amount", 1)
    if amount_max is None:
        amount_max = amount_min

    # Dynamic amount from last_card_count (choose_cards chain)
    if effect.get("amount_from_last_card_count", False):
        computed_amount = engine.last_card_count
        if computed_amount <= 0:
            return False
        amount_min = computed_amount
        amount_max = computed_amount

    # Dynamic amount from overflow damage (on_kill timing)
    if effect.get("amount_from_overflow", False):
        overflow_damage = 0
        if engine.down_holomem_state and engine.down_holomem_state.holomem_card:
            downed_card = engine.down_holomem_state.holomem_card
            target_player = engine.get_player(downed_card["owner_id"])
            target_hp = target_player.get_card_hp(downed_card)
            overflow_damage = max(0, downed_card["damage"] - target_hp)
        overflow_per = effect.get("overflow_per", 30)
        computed_amount = overflow_damage // overflow_per
        if computed_amount <= 0:
            return False
        amount_min = computed_amount
        amount_max = computed_amount

    # Dynamic amount from bloom count
    if effect.get("amount_from_bloom_count", False):
        bloom_count_tags = effect.get("bloom_count_tags", [])
        holomems = effect_player.get_holomem_on_stage()
        bloom_count = sum(
            1 for h in holomems
            if h.get("bloomed_this_turn", False)
            and (not bloom_count_tags or any(tag in h.get("tags", []) for tag in bloom_count_tags))
        )
        if bloom_count <= 0:
            return False
        amount_min = bloom_count
        amount_max = bloom_count

    from_zone = effect["from"]
    to_zone = effect["to"]
    # Optional
    from_limitation = effect.get("from_limitation", "")
    from_limitation_colors = effect.get("from_limitation_colors", [])
    from_limitation_tags = effect.get("from_limitation_tags", [])
    to_limitation = effect.get("to_limitation", "")
    to_limitation_colors = effect.get("to_limitation_colors", [])
    to_limitation_tags = effect.get("to_limitation_tags", [])
    to_limitation_exclude_name = effect.get("to_limitation_exclude_name", "")
    multi_to = effect.get("multi_to", False)
    limit_one_per_member = effect.get("limit_one_per_member", False)
    to_count = effect.get("to_count")
    max_per_target = effect.get("max_per_target")

    # Determine options
    from_options = []
    to_options = []
    remove_from_to_options = []

    match from_zone:
        case "archive":
            # Get archive cheer cards.
            relevant_archive_cards = [card for card in effect_player.archive if is_card_cheer(card)]
            if from_limitation:
                match from_limitation:
                    case "color_in":
                        from_options = [card for card in relevant_archive_cards if any(color in card["colors"] for color in from_limitation_colors)]
                    case "cheer":
                        from_options = relevant_archive_cards
                    case _:
                        raise NotImplementedError(f"Unimplemented from limitation: {from_limitation}")
            else:
                from_options = relevant_archive_cards
            from_options = ids_from_cards(from_options)
        case "cheer_deck":
            # Cheer deck is from top.
            cheer_count = amount_max if isinstance(amount_max, int) else len(effect_player.cheer_deck)
            from_options = effect_player.cheer_deck[:cheer_count]
            from_options = ids_from_cards(from_options)
        case "downed_holomem":
            holomem = engine.down_holomem_state.holomem_card
            if from_limitation:
                match from_limitation:
                    case "color_in":
                        from_options = [card for card in holomem["attached_cheer"] \
                            if any(color in card["colors"] for color in from_limitation_colors)]
            else:
                from_options = holomem["attached_cheer"]
            from_options = ids_from_cards(from_options)
        case "holomem":
            holomem_options = effect_player.get_holomem_on_stage()
            if from_limitation:
                match from_limitation:
                    case "tag_in":
                        holomem_options = [card for card in holomem_options if any(tag in card["tags"] for tag in from_limitation_tags)]
            for holomem in holomem_options:
                for cheer in holomem["attached_cheer"]:
                    from_options.append(cheer)
            from_options = ids_from_cards(from_options)
        case "opponent_holomem":
            opponent = engine.other_player(effect_player_id)
            holomem_options = opponent.get_holomem_on_stage()
            if from_limitation:
                match from_limitation:
                    case "center":
                        holomem_options = opponent.center
                    case "center_or_collab":
                        holomem_options = opponent.center + opponent.collab
                    case _:
                        raise NotImplementedError(f"Unimplemented from limitation: {from_limitation}")
            for holomem in holomem_options:
                from_options.extend(holomem["attached_cheer"])
            from_options = ids_from_cards(from_options)
        case "opponent_archive":
            opponent = engine.other_player(effect_player_id)
            relevant_archive_cards = [card for card in opponent.archive if is_card_cheer(card)]
            if from_limitation:
                match from_limitation:
                    case "color_in":
                        from_options = [card for card in relevant_archive_cards
                            if any(color in card["colors"] for color in from_limitation_colors)]
                    case _:
                        raise NotImplementedError(f"Unimplemented from limitation: {from_limitation}")
            else:
                from_options = relevant_archive_cards
            from_options = ids_from_cards(from_options)
        case "self":
            from_zone = "holomem"
            source_card, _, _ = effect_player.find_card(effect["source_card_id"])
            from_options = ids_from_cards(source_card["attached_cheer"])
            remove_from_to_options = [effect["source_card_id"]]
        case _:
            raise NotImplementedError(f"Unimplemented from zone: {from_zone}")

    match to_zone:
        case "archive":
            to_options = ["archive"]
            # Add the after archive effect unless we're moving opponent cheer.
            if from_zone != "opponent_holomem":
                after_archive_check_effect = {
                    "player_id": effect_player_id,
                    "effect_type": EffectType.EffectType_AfterArchiveCheerCheck,
                    "effect_player_id": effect_player_id,
                    "previous_archive_count": len(effect_player.archive),
                    "ability_source": effect.get("ability_source", ""),
                }
                engine.add_effects_to_front([after_archive_check_effect])
        case "holomem":
            if to_limitation:
                match to_limitation:
                    case "attached_owner":
                        source_card = engine.find_card(effect["source_card_id"])
                        owner_player = engine.get_player(source_card["owner_id"])
                        to_options = owner_player.get_holomems_with_attachment(effect["source_card_id"])
                    case "color_in":
                        to_options = [card for card in effect_player.get_holomem_on_stage() if any(color in card["colors"] for color in to_limitation_colors)]
                    case "backstage":
                        to_options = effect_player.backstage
                    case "center":
                        to_options = effect_player.center
                    case "center_or_collab":
                        to_options = effect_player.center + effect_player.collab
                    case "specific_member_name":
                        to_limitation_name = effect.get("to_limitation_name", "")
                        holomems = effect_player.get_holomem_on_stage()
                        to_options = [card for card in holomems if to_limitation_name in card["card_names"]]
                        to_limitation_bloom_level = effect.get("to_limitation_bloom_level", None)
                        if to_limitation_bloom_level is not None:
                            to_options = [card for card in to_options \
                                if card.get("bloom_level", 0) == to_limitation_bloom_level]
                    case "member_name_in":
                        to_limitation_names = effect.get("to_limitation_names", [])
                        holomems = effect_player.get_holomem_on_stage()
                        to_options = [card for card in holomems if any(name in card["card_names"] for name in to_limitation_names)]
                    case "tag_in":
                        to_options = [card for card in effect_player.get_holomem_on_stage() if any(tag in card["tags"] for tag in to_limitation_tags)]
                    case "card_type":
                        to_limitation_card_type = effect.get("to_limitation_card_type", "")
                        holomems = effect_player.get_holomem_on_stage()
                        to_options = [card for card in holomems if to_limitation_card_type == card["card_type"]]
                    case "tag_and_bloom_level":
                        to_limitation_bloom_level = effect.get("to_limitation_bloom_level", 0)
                        holomems = effect_player.get_holomem_on_stage()
                        to_options = [card for card in holomems if 
                            card["card_type"] == "holomem_bloom" and 
                            card.get("bloom_level", 0) == to_limitation_bloom_level and
                            any(tag in card["tags"] for tag in to_limitation_tags)]
                    case "has_attachment_of_name":
                        to_limitation_attachment_name = effect.get("to_limitation_attachment_name", "")
                        holomems = effect_player.get_holomem_on_stage()
                        to_options = [card for card in holomems
                            if any(to_limitation_attachment_name in attached["card_names"]
                                for attached in card["attached_support"])]
                    case "backstage_and_tag_in":
                        to_options = [card for card in effect_player.backstage
                            if any(tag in card["tags"] for tag in to_limitation_tags)]
                    case "backstage_and_specific_member_name":
                        to_limitation_name = effect.get("to_limitation_name", "")
                        to_options = [card for card in effect_player.backstage if to_limitation_name in card["card_names"]]
                    case "source_card":
                        source_card_id = effect.get("source_card_id", "")
                        holomems = effect_player.get_holomem_on_stage()
                        to_options = [card for card in holomems if card["game_card_id"] == source_card_id]
                    case "last_chosen":
                        holomems = effect_player.get_holomem_on_stage()
                        to_options = [card for card in holomems if card["game_card_id"] in engine.last_chosen_cards]
                    case "collab":
                        to_options = effect_player.collab
                    case "buzz_or_name_bloomed_from_buzz":
                        to_limitation_name = effect.get("to_limitation_name", "")
                        holomems = effect_player.get_holomem_on_stage()
                        buzz_holomems = [h for h in holomems if h.get("buzz", False)]
                        bloomed_from_buzz = [h for h in holomems
                            if to_limitation_name in h.get("card_names", [])
                            and len(h.get("stacked_cards", [])) > 0
                            and h["stacked_cards"][0].get("buzz", False)]
                        seen = set()
                        to_options = []
                        for h in buzz_holomems + bloomed_from_buzz:
                            if h["game_card_id"] not in seen:
                                seen.add(h["game_card_id"])
                                to_options.append(h)
                    case _:
                        raise NotImplementedError(f"Unimplemented to limitation: {to_limitation}")
            else:
                to_options = effect_player.get_holomem_on_stage()
            if to_limitation_exclude_name:
                to_options = [card for card in to_options if to_limitation_exclude_name not in card["card_names"]]
            if effect.get("to_limitation_buzz_only", False):
                to_options = [card for card in to_options if card.get("buzz", False)]

            # Remove any to_options where the holomem is downed.
            if engine.down_holomem_state:
                to_options = [card for card in to_options if card["game_card_id"] != engine.down_holomem_state.holomem_card["game_card_id"]]
            to_options = ids_from_cards(to_options)
        case "opponent_holomem":
            opponent = engine.other_player(effect_player_id)
            if to_limitation:
                match to_limitation:
                    case "center":
                        to_options = opponent.center
                    case "center_or_collab":
                        to_options = opponent.center + opponent.collab
                    case _:
                        raise NotImplementedError(f"Unimplemented to limitation for opponent_holomem: {to_limitation}")
            else:
                to_options = opponent.get_holomem_on_stage()
            if engine.down_holomem_state:
                to_options = [card for card in to_options if card["game_card_id"] != engine.down_holomem_state.holomem_card["game_card_id"]]
            to_options = ids_from_cards(to_options)
        case "cheer_deck_bottom":
            to_options = ["cheer_deck_bottom"]
        case "this_holomem":
            source_card_id = effect["source_card_id"]
            source_card, _, _ = effect_player.find_card(source_card_id)
            if source_card:
                to_options = [source_card_id]
            else:
                owner_holomems = effect_player.get_holomems_with_attachment(source_card_id)
                if owner_holomems:
                    to_options = [owner_holomems[0]["game_card_id"]]
                else:
                    to_options = [source_card_id]
            to_zone = "holomem"
    if str(amount_min) == "all":
        amount_min = len(from_options)
    if str(amount_max) == "all":
        amount_max = len(from_options)

    if remove_from_to_options:
        for card_id in remove_from_to_options:
            if card_id in to_options:
                to_options.remove(card_id)
    if len(to_options) == 0 or len(from_options) == 0:
        # No effect.
        pass
    elif len(to_options) == 1 and len(from_options) == 1 and amount_min == len(from_options) and amount_max == amount_min:
        # Do it automatically.
        placements = {}
        for from_id in from_options:
            placements[from_id] = to_options[0]
        # Do both players as the cheer could be opponent targeted.
        effect_player.move_cheer_between_holomems(placements)
        opponent = engine.other_player(effect_player.player_id)
        opponent.move_cheer_between_holomems(placements)
    else:
        if len(from_options) < amount_min:
            # If there's less cheer than the min, do as many as you can.
            amount_min = len(from_options)

        if from_zone in ["opponent_holomem", "opponent_archive"]:
            opponent = engine.other_player(effect_player_id)
            cheer_on_each_mem = opponent.get_cheer_on_each_holomem()
        else:
            cheer_on_each_mem = effect_player.get_cheer_on_each_holomem()
        decision_event = {
            "event_type": EventType.EventType_Decision_SendCheer,
            "desired_response": GameAction.EffectResolution_MoveCheerBetweenHolomems,
            "effect_player_id": effect_player_id,
            "amount_min": amount_min,
            "amount_max": amount_max,
            "from_zone": from_zone,
            "from_limitation": from_limitation,
            "from_limitation_colors": from_limitation_colors,
            "to_zone": to_zone,
            "to_limitation": to_limitation,
            "to_limitation_colors": to_limitation_colors,
            "from_options": from_options,
            "to_options": to_options,
            "cheer_on_each_mem": cheer_on_each_mem,
            "multi_to": multi_to,
            "limit_one_per_member": limit_one_per_member,
            "max_per_target": max_per_target,
            "to_count": to_count,
        }
        engine.broadcast_event(decision_event)
        engine.set_decision({
            "decision_type": DecisionType.DecisionEffect_MoveCheerBetweenHolomems,
            "decision_player": effect_player_id,
            "amount_min": amount_min,
            "amount_max": amount_max,
            "available_cheer": from_options,
            "available_targets": to_options,
            "multi_to": multi_to,
            "limit_one_per_member": limit_one_per_member,
            "max_per_target": max_per_target,
            "to_count": to_count,
            "continuation": engine.continue_resolving_effects,
        })
    return False


def handle_send_collab_back(engine, effect_player, effect):
    """Returns True if continuation was passed on, False otherwise."""
    effect_player_id = effect_player.player_id
    optional = effect.get("optional", False)
    if optional:
        # Ask the user if they want to send this collab back to the backstage.
        choice_info = {
            "specific_options": ["pass", "ok"]
        }
        min_choice = 0
        max_choice = 1
        decision_event = {
            "event_type": EventType.EventType_Choice_SendCollabBack,
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
            "resolution_func": engine.handle_choice_return_collab,
            "continuation": engine.continue_resolving_effects,
        })
    else:
        effect_player.return_collab()
    return False


def handle_shuffle_archive_to_deck(engine, effect_player, effect):
    """Returns True if continuation was passed on, False otherwise."""
    effect_player_id = effect_player.player_id
    archived_cards = list(effect_player.archive)
    match effect.get("limitation"):
        case "holomem":
            archived_cards = [card for card in archived_cards if is_card_holomem(card)]
    for card in archived_cards:
        effect_player.move_card(card["game_card_id"], "deck", hidden_info=False)
    effect_player.shuffle_deck()
    return False


def handle_shuffle_hand_to_deck(engine, effect_player, effect):
    """Returns True if continuation was passed on, False otherwise."""
    effect_player_id = effect_player.player_id
    target_player = effect_player
    if effect.get("opponent", False):
        target_player = engine.other_player(effect_player_id)
    engine.last_card_count = len(target_player.hand)
    target_player.shuffle_hand_to_deck()
    return False


def handle_spend_holopower(engine, effect_player, effect):
    """Returns True if continuation was passed on, False otherwise."""
    effect_player_id = effect_player.player_id
    amount = min(effect["amount"], len(effect_player.holopower))
    effect_player.spend_holopower(amount)
    if "oshi_skill_id" in effect:
        oshi_skill_event = {
            "event_type": EventType.EventType_OshiSkillActivation,
            "oshi_player_id": effect_player.player_id,
            "skill_id": effect["oshi_skill_id"],
        }
        engine.broadcast_event(oshi_skill_event)
    return False


def handle_switch_center_with_collab(engine, effect_player, effect):
    """Swaps center and collab positions. Supports opponent parameter."""
    effect_player_id = effect_player.player_id
    target_player = effect_player
    swap_opponent_cards = effect.get("opponent", False)
    if swap_opponent_cards:
        target_player = engine.other_player(effect_player_id)
    if len(target_player.center) == 0 or len(target_player.collab) == 0:
        return False
    target_player.swap_center_with_collab()
    return False


def handle_switch_center_with_back(engine, effect_player, effect):
    """Returns True if continuation was passed on, False otherwise."""
    effect_player_id = effect_player.player_id
    target_player = effect_player
    swap_opponent_cards = "opponent" in effect and effect["opponent"]
    skip_resting = effect.get("skip_resting", False)
    required_damage = effect.get("required_damage", 0)
    if swap_opponent_cards:
        target_player = engine.other_player(effect_player_id)
    available_backstage_ids = []
    for card in target_player.backstage:
        if skip_resting and card["resting"]:
            continue
        if card["damage"] < required_damage:
            continue
        available_backstage_ids.append(card["game_card_id"])
    if len(available_backstage_ids) == 0 or (not swap_opponent_cards and not target_player.can_move_front_stage()):
        # No effect.
        pass
    elif len(available_backstage_ids) == 1:
        # Do it right away.
        target_player.swap_center_with_back(available_backstage_ids[0])
    else:
        # Ask for a decision.
        decision_event = {
            "event_type": EventType.EventType_Decision_SwapHolomemToCenter,
            "desired_response": GameAction.EffectResolution_ChooseCardsForEffect,
            "effect_player_id": effect_player_id,
            "cards_can_choose": available_backstage_ids,
            "swap_opponent_cards": swap_opponent_cards,
        }
        engine.broadcast_event(decision_event)
        engine.set_decision({
            "decision_type": DecisionType.DecisionEffect_ChooseCardsForEffect,
            "decision_player": effect_player_id,
            "all_card_seen": available_backstage_ids,
            "cards_can_choose": available_backstage_ids,
            "amount_min": 1,
            "amount_max": 1,
            "effect_resolution": engine.handle_holomem_swap,
            "continuation": engine.continue_resolving_effects,
        })
    return False


def handle_set_center_hp(engine, effect_player, effect):
    """Returns True if continuation was passed on, False otherwise."""
    effect_player_id = effect_player.player_id
    amount = effect["amount"]
    is_opponent = "opponent" in effect and effect["opponent"]
    affected_player = effect_player
    if is_opponent:
        affected_player = engine.other_player(effect_player_id)
    if len(affected_player.center) > 0:
        affected_player.set_holomem_hp(affected_player.center[0]["game_card_id"], amount)
    return False


def handle_after_archive_cheer_check(engine, effect_player, effect):
    """Returns True if continuation was passed on, False otherwise."""
    effect_player_id = effect_player.player_id
    previous_archive_count = effect["previous_archive_count"]
    current_archive_count = len(effect_player.archive)
    ability_source = effect.get("ability_source", "")
    if previous_archive_count < current_archive_count:
        # The player archived some amount of cheer.
        after_archive_effects = effect_player.get_effects_at_timing("after_archive_cheer", None, ability_source)
        if engine.performance_art:
            # Queue to cleanup effects.
            effect_player.add_performance_cleanup(after_archive_effects)
        else:
            # Add it to the rear of the queue.
            engine.add_effects_to_rear(after_archive_effects)
    return False


def handle_archive_from_both_cheer_decks(engine, effect_player, effect):
    """Archives top card(s) from both players' cheer decks.
    Sets engine.last_card_count to the number of unique colors among archived cheer."""
    amount = effect.get("amount", 1)
    archived_colors = set()

    for _ in range(amount):
        if len(effect_player.cheer_deck) > 0:
            card = effect_player.cheer_deck[0]
            for color in card.get("colors", []):
                archived_colors.add(color)
            effect_player.move_card(card["game_card_id"], "archive")

    opponent = engine.other_player(effect_player.player_id)
    for _ in range(amount):
        if len(opponent.cheer_deck) > 0:
            card = opponent.cheer_deck[0]
            for color in card.get("colors", []):
                archived_colors.add(color)
            opponent.move_card(card["game_card_id"], "archive")

    engine.last_card_count = len(archived_colors)
    return False


def handle_draw_per_cheer_on_both_stages(engine, effect_player, effect):
    """Draws cards equal to the total cheer count on both players' stages."""
    per_amount = effect.get("amount", 1)
    count = 0
    for player in engine.player_states:
        for holomem in player.get_holomem_on_stage():
            count += len(holomem["attached_cheer"])
    draw_amount = per_amount * count
    if draw_amount > 0:
        effect_player.draw(draw_amount)
    return False


def handle_archive_hand(engine, effect_player, effect):
    """Archives all cards from hand. Sets engine.last_card_count to number of archived cards."""
    engine.last_card_count = len(effect_player.hand)
    while len(effect_player.hand) > 0:
        effect_player.move_card(effect_player.hand[0]["game_card_id"], "archive")
    return False


def handle_shuffle_cheer_deck(engine, effect_player, effect):
    """Shuffles the effect player's cheer deck."""
    effect_player.shuffle_cheer_deck()
    return False


def handle_send_cheer_per_named_cards_in_archive(engine, effect_player, effect):
    """Counts cards with specific card_names in archive, then delegates to send_cheer with that amount."""
    count_card_names = effect["count_card_names"]
    count = sum(1 for card in effect_player.archive
                if any(name in card.get("card_names", []) for name in count_card_names))
    if count == 0:
        return False
    effect_copy = deepcopy(effect)
    effect_copy["amount_min"] = count
    effect_copy["amount_max"] = count
    effect_copy["effect_type"] = EffectType.EffectType_SendCheer
    del effect_copy["count_card_names"]
    engine.add_effects_to_front([effect_copy])
    return False


CARD_MOVEMENT_HANDLERS = {
    EffectType.EffectType_ArchiveCheerFromHolomem: handle_archive_cheer_from_holomem,
    EffectType.EffectType_ArchiveFromBothCheerDecks: handle_archive_from_both_cheer_decks,
    EffectType.EffectType_ArchiveFromHand: handle_archive_from_hand,
    EffectType.EffectType_ArchiveHand: handle_archive_hand,
    EffectType.EffectType_ArchiveRevealedCards: handle_archive_revealed_cards,
    EffectType.EffectType_ArchiveThisAttachment: handle_archive_this_attachment,
    EffectType.EffectType_ReplaceArchiveWithMove: handle_replace_archive_with_move,
    EffectType.EffectType_ArchiveAttachmentFromStageByName: handle_archive_attachment_from_stage_by_name,
    EffectType.EffectType_ReturnThisAttachmentToHand: handle_return_this_attachment_to_hand,
    EffectType.EffectType_ReturnThisAttachmentToDeckBottom: handle_return_this_attachment_to_deck_bottom,
    EffectType.EffectType_ReturnThisCardToDeck: handle_return_this_card_to_deck,
    EffectType.EffectType_ArchiveTopStackedHolomem: handle_archive_top_stacked_holomem,
    EffectType.EffectType_ArchiveStackedHolomem: handle_archive_stacked_holomem,
    EffectType.EffectType_AttachCardToHolomem: handle_attach_card_to_holomem,
    EffectType.EffectType_AttachCardToHolomem_Internal: handle_attach_card_to_holomem_internal,
    EffectType.EffectType_Draw: handle_draw,
    EffectType.EffectType_DrawPerCheerOnBothStages: handle_draw_per_cheer_on_both_stages,
    EffectType.EffectType_GenerateHolopower: handle_generate_holopower,
    EffectType.EffectType_MoveCheerBetweenHolomems: handle_move_cheer_between_holomems,
    EffectType.EffectType_ReturnCheerAndDraw: handle_return_cheer_and_draw,
    EffectType.EffectType_ReturnRevealedToHolopowerBottom: handle_return_revealed_to_holopower_bottom,
    EffectType.EffectType_RevealTopDeck: handle_reveal_top_deck,
    EffectType.EffectType_RevealTopHolopower: handle_reveal_top_holopower,
    EffectType.EffectType_SendCheer: handle_send_cheer,
    EffectType.EffectType_SendCheerPerNamedCardsInArchive: handle_send_cheer_per_named_cards_in_archive,
    EffectType.EffectType_SendCollabBack: handle_send_collab_back,
    EffectType.EffectType_ShuffleArchiveToDeck: handle_shuffle_archive_to_deck,
    EffectType.EffectType_ShuffleCheerDeck: handle_shuffle_cheer_deck,
    EffectType.EffectType_ShuffleHandToDeck: handle_shuffle_hand_to_deck,
    EffectType.EffectType_SpendHolopower: handle_spend_holopower,
    EffectType.EffectType_SwitchCenterWithBack: handle_switch_center_with_back,
    EffectType.EffectType_SwitchCenterWithCollab: handle_switch_center_with_collab,
    EffectType.EffectType_SetCenterHP: handle_set_center_hp,
    EffectType.EffectType_AfterArchiveCheerCheck: handle_after_archive_cheer_check,
}
