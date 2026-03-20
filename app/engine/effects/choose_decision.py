from __future__ import annotations
from typing import TYPE_CHECKING
from copy import deepcopy

from app.engine.constants import *
from app.engine.models import *
from app.engine.helpers import *
from app.engine.effects.card_movement import can_move_cheer_between_holomems

if TYPE_CHECKING:
    from app.engine.player_state import PlayerState

CHOICE_FEASIBILITY_CHECKERS = {
    EffectType.EffectType_MoveCheerBetweenHolomems: can_move_cheer_between_holomems,
}


def _filter_feasible_choices(engine, effect_player, choice):
    """Remove choice options that cannot resolve, return filtered list."""
    feasible = []
    for option in choice:
        checker = CHOICE_FEASIBILITY_CHECKERS.get(option.get("effect_type"))
        if checker and not checker(engine, effect_player, option):
            continue
        feasible.append(option)
    return feasible


def handle_choice(engine, effect_player, effect):
    """Returns True if continuation was passed on, False otherwise."""
    effect_player_id = effect_player.player_id
    choice = deepcopy(effect["choice"])
    if engine.take_damage_state:
        for choice_effect in choice:
            choice_effect["incoming_damage_info"] = {
                "amount": engine.take_damage_state.get_incoming_damage(),
                "source_id": engine.take_damage_state.source_card["game_card_id"],
                "target_id": engine.take_damage_state.target_card["game_card_id"],
                "special": engine.take_damage_state.special,
                "prevent_life_loss": engine.take_damage_state.prevent_life_loss,
            }
    if "choice_populate_amount_x" in effect:
        match effect["choice_populate_amount_x"]:
            case "equal_to_last_damage":
                for option in choice:
                    if "amount" in option and option["amount"] == "X":
                        option["amount"] = engine.after_damage_state.damage_dealt
    add_ids_to_effects(choice, effect_player_id, effect.get("source_card_id", None))

    choice = _filter_feasible_choices(engine, effect_player, choice)
    all_pass = all(option.get("effect_type") == EffectType.EffectType_Pass for option in choice)
    if len(choice) == 0 or all_pass:
        return False

    engine.send_choice_to_player(effect_player_id, choice)
    return False


def handle_choose_cards(engine, effect_player, effect):
    """Returns True if continuation was passed on, False otherwise."""
    effect_player_id = effect_player.player_id
    from_zone = effect["from"]
    destination = effect["destination"]
    look_at = effect.get("look_at", -1)
    amount_min = effect["amount_min"]
    amount_max = effect["amount_max"]
    requirement = effect.get("requirement", None)
    requirement_block_limited = effect.get("requirement_block_limited", False)
    requirement_bloom_levels = effect.get("requirement_bloom_levels", [])
    requirement_buzz_blocked = effect.get("requirement_buzz_blocked", False)
    requirement_names = effect.get("requirement_names", [])
    requirement_id = effect.get("requirement_id", "")
    requirement_card_name = effect.get("requirement_card_name", "")
    requirement_card_names = effect.get("requirement_card_names", [])
    requirement_match_oshi_color = effect.get("requirement_match_oshi_color", False)
    requirement_match_oshi_name = effect.get("requirement_match_oshi_name", False)
    requirement_only_holomems_with_any_tag = effect.get("requirement_only_holomems_with_any_tag", False)
    requirement_colors = effect.get("requirement_colors", [])
    requirement_sub_types = effect.get("requirement_sub_types", [])
    requirement_same_name_as_last_choice = effect.get("requirement_same_name_as_last_choice", False)
    requirement_name_fragment = effect.get("requirement_name_fragment", "")
    # two_tone_color_pc extra requirements
    requirement_monocolor_only = effect.get("requirement_monocolor_only", False)
    requirement_different_colors = effect.get("requirement_different_colors", False)
    requirement_match_selected_holomem_color = effect.get("requirement_match_selected_holomem_color", None)
    reveal_chosen = effect.get("reveal_chosen", False)
    remaining_cards_action = effect.get("remaining_cards_action", "nothing" if from_zone == "backstage" else "NULL")
    after_choose_effect = effect.get("after_choose_effect", None)
    requirement_details = {
        "requirement": requirement,
        "requirement_block_limited": requirement_block_limited,
        "requirement_bloom_levels": requirement_bloom_levels,
        "requirement_buzz_blocked": requirement_buzz_blocked,
        "requirement_names": requirement_names,
        "requirement_tags": effect.get("requirement_tags", []),
        "requirement_id": requirement_id,
        "requirement_card_name": requirement_card_name,
        "requirement_card_names": requirement_card_names,
        "requirement_match_oshi_color": requirement_match_oshi_color,
        "requirement_match_oshi_name": requirement_match_oshi_name,
        "requirement_only_holomems_with_any_tag": requirement_only_holomems_with_any_tag,
        "requirement_colors": requirement_colors,
        "requirement_sub_types": requirement_sub_types,
        "requirement_same_name_as_last_choice": requirement_same_name_as_last_choice,
        "requirement_name_fragment": requirement_name_fragment,
        "requirement_monocolor_only": requirement_monocolor_only,
        "requirement_different_colors": requirement_different_colors,
        "requirement_match_selected_holomem_color": requirement_match_selected_holomem_color
    }

    cards_to_choose_from = []
    match from_zone:
        case "archive":
            cards_to_choose_from = effect_player.archive
        case "attached_support":
            for holomem in effect_player.get_holomem_on_stage():
                cards_to_choose_from.extend(holomem["attached_support"])
        case "cheer_deck":
            cards_to_choose_from = effect_player.cheer_deck
        case "deck":
            cards_to_choose_from = effect_player.deck
        case "backstage":
            cards_to_choose_from = effect_player.backstage
        case "hand":
            cards_to_choose_from = effect_player.hand
        case "holopower":
            cards_to_choose_from = effect_player.holopower
        case "last_revealed_cards":
            cards_to_choose_from = effect_player.last_revealed_cards
        case "stage":
            cards_to_choose_from = effect_player.get_holomem_on_stage()
        case "stacked_holomem":
            cards_to_choose_from = effect_player.get_holomem_under(effect["source_card_id"])
        case "self_attached_support":
            source_card = engine.find_card(effect["source_card_id"])
            if source_card and "attached_support" in source_card:
                cards_to_choose_from = source_card["attached_support"]

    # If look_at is -1, look at all cards.
    if look_at == -1:
        look_at = len(cards_to_choose_from)

    # If look_at is greater than the number of cards, look at as many as you can.
    look_at = min(look_at, len(cards_to_choose_from))

    cards_to_choose_from = cards_to_choose_from[:look_at]
    cards_can_choose = cards_to_choose_from

    # Special handling for stage selection (two_tone_color_pc)
    if from_zone == "stage" and requirement_monocolor_only:
        cards_can_choose = [card for card in cards_can_choose if len(card["colors"]) == 1]

    # Skip requirement filtering for stage selection (two_tone_color_pc)
    if requirement and from_zone != "stage":
        match requirement:
            case "buzz":
                cards_can_choose = [card for card in cards_can_choose if "buzz" in card and card["buzz"]]
            case "cheer":
                # Only include cards that are cheer.
                cards_can_choose = [card for card in cards_can_choose if is_card_cheer(card)]
            case "color_in":
                requirement_colors = effect.get("requirement_colors", [])
                cards_can_choose = [card for card in cards_can_choose if any(color in card["colors"] for color in requirement_colors)]
            case "color_matches_holomems":
                # Only include cards that match the colors of the holomems on stage.
                cards_can_choose = [card for card in cards_can_choose if effect_player.matches_stage_holomems_color(card["colors"], tag_requirement=requirement_only_holomems_with_any_tag)]
            case "holomem":
                cards_can_choose = [card for card in cards_can_choose if is_card_holomem(card)]
            case "holomem_bloom":
                cards_can_choose = [card for card in cards_can_choose if card["card_type"] == "holomem_bloom"]
            case "holomem_debut":
                cards_can_choose = [card for card in cards_can_choose if card["card_type"] == "holomem_debut"]
            case "holomem_debut_unlimited":
                # Only include debut cards with special_deck_limit: 50 (extra/unlimited cards)
                cards_can_choose = [card for card in cards_can_choose
                    if card["card_type"] == "holomem_debut" and card.get("special_deck_limit", 4) == 50]
            case "holomem_debut_or_bloom":
                cards_can_choose = [card for card in cards_can_choose if card["card_type"] in ["holomem_bloom", "holomem_debut"]]
            case "holomem_named":
                # Only include cards that have a name in the requirement_names list.
                cards_can_choose = [card for card in cards_can_choose
                    if "card_names" in card and any(name in card["card_names"] for name in requirement_names)]
            case "limited":
                # only include cards that are limited
                cards_can_choose = [card for card in cards_can_choose if is_card_limited(card)]
            case "specific_card":
                if requirement_id:
                    cards_can_choose = [card for card in cards_can_choose if card["card_id"] == requirement_id]
                elif requirement_card_names:
                    cards_can_choose = [card for card in cards_can_choose
                        if "card_names" in card and any(name in card["card_names"] for name in requirement_card_names)]
                elif requirement_card_name:
                    cards_can_choose = [card for card in cards_can_choose
                        if "card_names" in card and requirement_card_name in card["card_names"]]
            case "name_contains":
                cards_can_choose = [card for card in cards_can_choose
                    if "card_names" in card and any(requirement_name_fragment in name for name in card["card_names"])]
            case "support":
                # Only include cards that are supports.
                cards_can_choose = [card for card in cards_can_choose if card["card_type"] == "support"]
            case "holomem_or_tool":
                # Only include cards that are holomem or tool (support sub_type).
                cards_can_choose = [card for card in cards_can_choose
                    if is_card_holomem(card) or card.get("sub_type") == "tool"]
            case "holomem_debut_or_support_with_tags":
                debut_tags = effect.get("requirement_debut_tags", [])
                support_tags = effect.get("requirement_support_tags", [])
                cards_can_choose = [card for card in cards_can_choose
                    if (card["card_type"] == "holomem_debut" and any(tag in card.get("tags", []) for tag in debut_tags))
                    or (card["card_type"] == "support" and any(tag in card.get("tags", []) for tag in support_tags))]
            case "has_collab_effect":
                cards_can_choose = [card for card in cards_can_choose
                    if is_card_holomem(card) and card.get("collab_effects", [])]

        # Exclude LIMITED if asked.
        if requirement_block_limited:
            cards_can_choose = [card for card in cards_can_choose if not is_card_limited(card)]

        # Exclude any based on bloom level.
        if requirement_bloom_levels:
            cards_can_choose = [card for card in cards_can_choose if "bloom_level" not in card or card["bloom_level"] in requirement_bloom_levels]

        # Exclude any buzz if required.
        if requirement_buzz_blocked:
            cards_can_choose = [card for card in cards_can_choose if "buzz" not in card or not card["buzz"]]

        # Restrict to specific colors (post-filter, skip for color_in which handles it as primary requirement).
        if requirement_colors and requirement != "color_in":
            cards_can_choose = [card for card in cards_can_choose if any(color in card.get("colors", []) for color in requirement_colors)]

        # Restrict to specific names (general post-filter, skip for holomem_named which handles it internally).
        if requirement_names and requirement != "holomem_named":
            cards_can_choose = [card for card in cards_can_choose
                if "card_names" in card and any(name in card["card_names"] for name in requirement_names)]

        # Restrict to oshi color.
        if requirement_match_oshi_color:
            cards_can_choose = [card for card in cards_can_choose if effect_player.matches_oshi_color(card["colors"])]

        # Restrict to cards sharing a name with the player's oshi.
        if requirement_match_oshi_name:
            oshi_names = effect_player.oshi_card.get("card_names", [])
            cards_can_choose = [card for card in cards_can_choose
                if "card_names" in card and any(name in card["card_names"] for name in oshi_names)]

        # Restrict to specified support sub types
        if requirement_sub_types:
            cards_can_choose = [card for card in cards_can_choose if card.get("sub_type", "") in requirement_sub_types]

        # Restrict to same name as last choice from previous choose cards effect
        if requirement_same_name_as_last_choice:
            same_names = []
            for card_id in engine.last_chosen_cards:
                try:
                    card = engine.find_card(card_id)
                except Exception:
                    card = None
                if card and "card_names" in card:
                    same_names += card["card_names"]
            if same_names:
                cards_can_choose = [card for card in cards_can_choose if any(name in card.get("card_names", []) for name in same_names)]

        # two_tone_color_pc: Filter to only monocolor holomems
        if requirement_monocolor_only:
            cards_can_choose = [card for card in cards_can_choose if len(card["colors"]) == 1]

        # two_tone_color_pc: Filter to match colors of previously selected holomems
        if requirement_match_selected_holomem_color is not None:
            # Get the colors of the specified previously selected holomem from stage selection
            if requirement_match_selected_holomem_color < len(engine.stage_selected_holomems):
                selected_card_id = engine.stage_selected_holomems[requirement_match_selected_holomem_color]
                try:
                    selected_card = engine.find_card(selected_card_id)
                except Exception:
                    selected_card = None
                if selected_card:
                    selected_colors = selected_card["colors"]
                    # Include cards that have any color in common with the selected holomem
                    cards_can_choose = [card for card in cards_can_choose if any(color in card["colors"] for color in selected_colors)]
                else:
                    cards_can_choose = []

    # Restrict to only tagged cards (applied independently of requirement).
    if effect.get("requirement_tags"):
        cards_can_choose = [card for card in cards_can_choose if any(tag in card.get("tags", []) for tag in effect["requirement_tags"])]

    if len(cards_can_choose) < amount_min:
        amount_min = len(cards_can_choose)

    if len(cards_can_choose) < amount_max:
        amount_max = len(cards_can_choose)

    # Limit amount based on available stage space for backstage destination
    if destination == "backstage":
        available_space = MAX_MEMBERS_ON_STAGE - len(effect_player.get_holomem_on_stage())
        if amount_max > available_space:
            amount_max = available_space
        if amount_min > available_space:
            amount_min = available_space

    # Auto-skip: no valid cards to choose from
    if amount_max == 0:
        decision_info = {
            "from_zone": from_zone,
            "to_zone": destination,
            "reveal_chosen": reveal_chosen,
            "remaining_cards_action": remaining_cards_action,
            "all_card_seen": ids_from_cards(cards_to_choose_from),
            "source_card_id": effect["source_card_id"],
            "after_choose_effect": after_choose_effect,
            "to_limitation": effect.get("to_limitation", ""),
            "to_limitation_colors": effect.get("to_limitation_colors", []),
            "to_limitation_tags": effect.get("to_limitation_tags", []),
            "to_limitation_name": effect.get("to_limitation_name", ""),
            "attach_each_separately": effect.get("attach_each_separately", False),
            "to_exclude_performer": effect.get("to_exclude_performer", False),
            "requirement_different_colors": requirement_different_colors,
            "include_stacked_holomems": effect.get("include_stacked_holomems", False),
        }
        engine.handle_choose_cards_result(
            decision_info, effect_player_id, [], engine.continue_resolving_effects
        )
        return True

    # Auto-resolve: no player decision needed when all choosable cards must be selected
    if amount_min > 0 and amount_min == amount_max and len(cards_can_choose) == amount_max:
        auto_card_ids = ids_from_cards(cards_can_choose)
        decision_info = {
            "from_zone": from_zone,
            "to_zone": destination,
            "reveal_chosen": reveal_chosen,
            "remaining_cards_action": remaining_cards_action,
            "all_card_seen": ids_from_cards(cards_to_choose_from),
            "source_card_id": effect["source_card_id"],
            "after_choose_effect": after_choose_effect,
            "to_limitation": effect.get("to_limitation", ""),
            "to_limitation_colors": effect.get("to_limitation_colors", []),
            "to_limitation_tags": effect.get("to_limitation_tags", []),
            "to_limitation_name": effect.get("to_limitation_name", ""),
            "attach_each_separately": effect.get("attach_each_separately", False),
            "to_exclude_performer": effect.get("to_exclude_performer", False),
            "requirement_different_colors": requirement_different_colors,
            "include_stacked_holomems": effect.get("include_stacked_holomems", False),
        }
        engine.handle_choose_cards_result(
            decision_info, effect_player_id, auto_card_ids, engine.continue_resolving_effects
        )
        return True

    choose_event = {
        "event_type": EventType.EventType_Decision_ChooseCards,
        "desired_response": GameAction.EffectResolution_ChooseCardsForEffect,
        "effect_player_id": effect_player_id,
        "all_card_seen": ids_from_cards(cards_to_choose_from),
        "cards_can_choose": ids_from_cards(cards_can_choose),
        "from_zone": from_zone,
        "to_zone": destination,
        "amount_min": amount_min,
        "amount_max": amount_max,
        "reveal_chosen": reveal_chosen,
        "remaining_cards_action": remaining_cards_action,
        "hidden_info_player": effect_player_id,
        "hidden_info_fields": ["all_card_seen", "cards_can_choose"],
        "requirement_details": requirement_details,
    }
    engine.broadcast_event(choose_event)
    engine.set_decision({
        "decision_type": DecisionType.DecisionEffect_ChooseCardsForEffect,
        "decision_player": effect_player_id,
        "all_card_seen": ids_from_cards(cards_to_choose_from),
        "cards_can_choose": ids_from_cards(cards_can_choose),
        "from_zone": from_zone,
        "to_zone": destination,
        "to_limitation": effect.get("to_limitation", ""),
        "to_limitation_colors": effect.get("to_limitation_colors", []),
        "to_limitation_tags": effect.get("to_limitation_tags", []),
        "to_limitation_name": effect.get("to_limitation_name", ""),
        "attach_each_separately": effect.get("attach_each_separately", False),
        "to_exclude_performer": effect.get("to_exclude_performer", False),
        "amount_min": amount_min,
        "amount_max": amount_max,
        "reveal_chosen": reveal_chosen,
        "remaining_cards_action": remaining_cards_action,
        "after_choose_effect": after_choose_effect,
        "source_card_id": effect["source_card_id"],
        "requirement_different_colors": requirement_different_colors,
        "include_stacked_holomems": effect.get("include_stacked_holomems", False),
        "effect_resolution": engine.handle_choose_cards_result,
        "continuation": engine.continue_resolving_effects,
    })
    return True


def handle_choose_stacked_to_hand(engine, effect_player, effect):
    """Returns True if continuation was passed on, False otherwise."""
    effect_player_id = effect_player.player_id
    # Choose from stacked cards (including self) of the downed holomem
    amount_min = effect.get("amount_min", 1)
    amount_max = effect.get("amount_max", 1)
    include_self = effect.get("include_self", True)
    self_only = effect.get("self_only", False)

    if self_only:
        if engine.down_holomem_state and engine.down_holomem_state.holomem_card:
            downed_card = engine.down_holomem_state.holomem_card
            engine.stacked_cards_to_hand_ids = [downed_card["game_card_id"]]
        engine.continue_resolving_effects()
        return True

    if engine.down_holomem_state and engine.down_holomem_state.holomem_card:
        downed_card = engine.down_holomem_state.holomem_card
        stacked_cards = downed_card.get("stacked_cards", [])
        stacked_holomems = [card for card in stacked_cards if is_card_holomem(card)]

        cards_to_choose_from = stacked_holomems.copy()
        if include_self:
            cards_to_choose_from.append(downed_card)

        if len(cards_to_choose_from) > 0:
            # Create a decision for the player to choose
            card_ids_to_choose = ids_from_cards(cards_to_choose_from)
            from_zone = "downed_holomem_stacked"

            choose_event = {
                "event_type": EventType.EventType_Decision_ChooseCards,
                "desired_response": GameAction.EffectResolution_ChooseCardsForEffect,
                "effect_player_id": effect_player.player_id,
                "all_card_seen": card_ids_to_choose,
                "cards_can_choose": card_ids_to_choose,
                "from_zone": from_zone,
                "to_zone": "hand",
                "amount_min": amount_min,
                "amount_max": amount_max,
                "reveal_chosen": False,
                "remaining_cards_action": "nothing",
            }
            engine.broadcast_event(choose_event)
            engine.set_decision({
                "decision_type": DecisionType.DecisionEffect_ChooseCardsForEffect,
                "decision_player": effect_player.player_id,
                "all_card_seen": card_ids_to_choose,
                "cards_can_choose": card_ids_to_choose,
                "from_zone": from_zone,
                "to_zone": "hand",
                "amount_min": amount_min,
                "amount_max": amount_max,
                "reveal_chosen": False,
                "remaining_cards_action": "nothing",
                "source_card_id": effect["source_card_id"],
                "effect_resolution": engine.handle_choose_stacked_to_hand_result,
                "continuation": engine.continue_resolving_effects,
            })
            return True
    return False


def handle_order_cards(engine, effect_player, effect):
    """Returns True if continuation was passed on, False otherwise."""
    effect_player_id = effect_player.player_id
    for_opponent = effect.get("opponent", False)
    from_zone = effect["from"]
    to_zone = effect["destination"]
    bottom = effect.get("bottom", False)
    amount = effect.get("amount", -1)
    order_player = effect_player
    if for_opponent:
        order_player = engine.other_player(effect_player_id)
    cards_to_order = []
    match from_zone:
        case "hand":
            cards_to_order = ids_from_cards(order_player.hand)
        case "deck":
            cards_to_order = ids_from_cards(order_player.deck)

    amount = len(cards_to_order) if amount == -1 else min(amount, len(cards_to_order))
    cards_to_order = cards_to_order[:amount]
    engine.last_card_count = len(cards_to_order)
    order = "order_on_bottom" if bottom else "order_on_top"
    engine.choose_cards_cleanup_remaining(order_player.player_id, cards_to_order, order, from_zone, to_zone,
        engine.continue_resolving_effects
    )
    return True


def handle_generate_choice_template(engine, effect_player, effect):
    """Returns True if continuation was passed on, False otherwise."""
    effect_player_id = effect_player.player_id
    template_choice = effect["template_choice"]
    starts_at = effect["starts_at"]
    ends_at = effect["ends_at"]
    usage_count_restriction = effect["usage_count_restriction"]
    can_pass = effect.get("can_pass", False)
    max_count = ends_at
    multi_value = effect.get("multi_value", 1)
    match ends_at:
        case "archive_count_required":
            max_count = engine.archive_count_required
            # Check to see if the starts_at and pass have to change.
            holopower_available = len(effect_player.holopower)
            cards_in_hand = len(effect_player.hand)
            must_pay_with_holo = engine.archive_count_required - cards_in_hand
            if must_pay_with_holo > 0:
                starts_at = max(starts_at, must_pay_with_holo)
                can_pass = False
    match usage_count_restriction:
        case "available_archive_from_hand":
            ability_source = effect.get("ability_source", "")
            max_count = min(max_count, effect_player.get_can_archive_from_hand_count(ability_source))
        case "cheer_deck":
            max_count = min(len(effect_player.cheer_deck), max_count)
        case "holopower":
            max_count = min(len(effect_player.holopower), max_count)
        case "performer_cheer":
            performer = engine.performance_performer_card
            if performer:
                cheer_count = len(performer.get("attached_cheer", []))
                max_count = min(cheer_count, max_count)
            else:
                max_count = 0
            max_count = min(max_count, len(effect_player.cheer_deck))
    choices = []
    for i in range(starts_at, max_count + 1):
        # Populate the "amount": "X"/"multiX" fields.
        new_choice = deepcopy(template_choice)
        if "amount" in new_choice:
            match new_choice["amount"]:
                case "multiX":
                    new_choice["amount"] = i * multi_value
                case "X":
                    new_choice["amount"] = i
        if "cost" in new_choice:
            match new_choice["cost"]:
                case "X":
                    new_choice["cost"] = i
        if "pre_effects" in new_choice:
            for pre_effect in new_choice["pre_effects"]:
                if "amount" in pre_effect:
                    match pre_effect["amount"]:
                        case "multiX":
                            pre_effect["amount"] = i * multi_value
                        case "X":
                            pre_effect["amount"] = i
        if "look_at" in new_choice and new_choice["look_at"] == "X":
            new_choice["look_at"] = i
        if "amount_min" in new_choice and new_choice["amount_min"] == "X":
            new_choice["amount_min"] = i
        if "amount_max" in new_choice and new_choice["amount_max"] == "X":
            new_choice["amount_max"] = i
        if "and" in new_choice:
            for and_effect in new_choice["and"]:
                if "amount" in and_effect:
                    match and_effect["amount"]:
                        case "multiX":
                            and_effect["amount"] = i * multi_value
                        case "X":
                            and_effect["amount"] = i
        choices.append(new_choice)
    if can_pass:
        choices.append({ "effect_type": EffectType.EffectType_Pass })
    # Now do this as a choice effect.
    add_ids_to_effects(choices, effect_player_id, effect.get("source_card_id", None))
    if len(choices) == 1:
        # There is no choice, the player has to do the effect.
        return engine.do_effect(effect_player, choices[0])
    else:
        engine.send_choice_to_player(effect_player_id, choices)
        return True


def handle_multiple_die_roll(engine, effect_player, effect):
    """Returns True if continuation was passed on, False otherwise."""
    effect_player_id = effect_player.player_id
    effect_player.last_die_roll_results = [] # reset the results

    amount = effect["amount"]
    match amount:
        case "per_two_mascots":
            mascots = get_cards_of_sub_type_from_holomems("mascot", effect_player.get_holomem_on_stage())
            amount = len(mascots) // 2
        case "per_stacked":
            source_card, _, _ = effect_player.find_card(effect["source_card_id"])
            if source_card:
                amount = len(source_card.get("stacked_cards", []))
            else:
                amount = 0
        case "per_mascot_and_fan":
            holomems = effect_player.get_holomem_on_stage()
            mascots = get_cards_of_sub_type_from_holomems("mascot", holomems)
            fans = get_cards_of_sub_type_from_holomems("fan", holomems)
            amount = min(len(mascots) + len(fans), effect.get("limit", 999))
        case "per_unique_tag_members":
            tag = effect["tag"]
            holomems = [h for h in effect_player.get_holomem_on_stage() if tag in h.get("tags", [])]
            seen_names = set()
            for h in holomems:
                seen_names.add(tuple(h["card_names"]))
            amount = len(seen_names)

    die_effects = effect["die_effects"]
    roll_effects = []
    for _ in range(amount):
        roll_effects.extend(deepcopy(die_effects))

    add_ids_to_effects(roll_effects, effect_player_id, effect["source_card_id"])
    engine.add_effects_to_front(roll_effects)
    return False


def handle_return_stacked_to_hand(engine, effect_player, effect):
    """Returns True if continuation was passed on, False otherwise.
    Phase 1: choose a holomem on stage that has stacked cards.
    Phase 2 (in action_handler): choose which stacked cards to return to hand."""
    effect_player_id = effect_player.player_id
    amount_min = effect.get("amount_min", 1)
    amount_max = effect.get("amount_max", 2)

    holomem_targets = effect_player.get_holomem_on_stage()
    holomem_targets = [h for h in holomem_targets
        if len([c for c in h.get("stacked_cards", []) if is_card_holomem(c)]) > 0]

    if len(holomem_targets) == 0:
        return False

    holomem_ids = ids_from_cards(holomem_targets)
    if len(holomem_ids) == 1:
        engine.handle_return_stacked_choose_cards(
            {"effect": effect, "amount_min": amount_min, "amount_max": amount_max},
            effect_player_id,
            holomem_ids,
            engine.continue_resolving_effects,
        )
        return True

    decision_event = {
        "event_type": EventType.EventType_Decision_ChooseHolomemForEffect,
        "desired_response": GameAction.EffectResolution_ChooseCardsForEffect,
        "effect_player_id": effect_player_id,
        "cards_can_choose": holomem_ids,
        "effect": effect,
    }
    engine.broadcast_event(decision_event)
    engine.set_decision({
        "decision_type": DecisionType.DecisionEffect_ChooseCardsForEffect,
        "decision_player": effect_player_id,
        "cards_can_choose": holomem_ids,
        "amount_min": 1,
        "amount_max": 1,
        "effect": effect,
        "amount_min_stacked": amount_min,
        "amount_max_stacked": amount_max,
        "effect_resolution": engine.handle_return_stacked_choose_cards,
        "continuation": engine.continue_resolving_effects,
    })
    return True


CHOOSE_DECISION_HANDLERS = {
    EffectType.EffectType_Choice: handle_choice,
    EffectType.EffectType_ChooseCards: handle_choose_cards,
    EffectType.EffectType_ChooseStackedToHand: handle_choose_stacked_to_hand,
    EffectType.EffectType_OrderCards: handle_order_cards,
    EffectType.EffectType_GenerateChoiceTemplate: handle_generate_choice_template,
    EffectType.EffectType_MultipleDieRoll: handle_multiple_die_roll,
    EffectType.EffectType_ReturnStackedToHand: handle_return_stacked_to_hand,
}
