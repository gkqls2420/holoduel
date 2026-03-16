from __future__ import annotations
from typing import TYPE_CHECKING
from copy import deepcopy

from app.engine.constants import *
from app.engine.models import *
from app.engine.helpers import *

if TYPE_CHECKING:
    from app.engine.player_state import PlayerState


def handle_bloom_already_bloomed_this_turn(engine, effect_player, effect):
    """Returns True if continuation was passed on, False otherwise."""
    effect_player_id = effect_player.player_id
    bloomed_cards_this_turn = [holomem for holomem in effect_player.get_holomem_on_stage() if holomem["bloomed_this_turn"]]
    match effect.get("limitation"):
        case "tag_in":
            limitation_tags = effect.get("limitation_tags", [])
            bloomed_cards_this_turn = [h for h in bloomed_cards_this_turn if any(tag in h["tags"] for tag in limitation_tags)]
        case "bloom_level":
            limitation_bloom_level = effect.get("limitation_bloom_level")
            bloomed_cards_this_turn = [h for h in bloomed_cards_this_turn if h.get("bloom_level", 0) == limitation_bloom_level]
        case "name_in":
            limitation_names = effect.get("limitation_names", [])
            bloomed_cards_this_turn = [h for h in bloomed_cards_this_turn
                if any(name in h.get("card_names", []) for name in limitation_names)]
    valid_blooms_dict = {}
    for bloomed_card in bloomed_cards_this_turn:
        for card_in_hand in effect_player.hand:
            game_card_id = card_in_hand["game_card_id"]
            if effect_player.can_bloom_with_card(bloomed_card, card_in_hand) and game_card_id not in valid_blooms_dict:
                valid_blooms_dict[game_card_id] = card_in_hand
    valid_blooms_in_hand = list(valid_blooms_dict.values())
    if len(valid_blooms_in_hand) > 0:
        decision_event = {
            "event_type": EventType.EventType_Decision_ChooseCards,
            "desired_response": GameAction.EffectResolution_ChooseCardsForEffect,
            "effect_player_id": effect_player_id,
            "all_card_seen": ids_from_cards(valid_blooms_in_hand),
            "cards_can_choose": ids_from_cards(valid_blooms_in_hand),
            "from_zone": "hand",
            "to_zone": "holomem",
            "amount_min": 0,
            "amount_max": 1,
            "special_reason": "bloom_already_bloomed_this_turn",
            "reveal_chosen": True,
            "remaining_cards_action": "nothing"
        }
        engine.broadcast_event(decision_event)
        engine.set_decision({
            "decision_type": DecisionType.DecisionEffect_ChooseCardsForEffect,
            "decision_player": effect_player_id,
            "all_card_seen": ids_from_cards(valid_blooms_in_hand),
            "cards_can_choose": ids_from_cards(valid_blooms_in_hand),
            "amount_min": 0,
            "amount_max": 1,
            "target_cards": bloomed_cards_this_turn,
            "effect": effect,
            "effect_resolution": engine.handle_chose_bloom_now_choose_target,
            "continuation": engine.continue_resolving_effects
        })
        return True
    return False


def handle_bloom_from_special(engine, effect_player, effect):
    """Returns True if continuation was passed on, False otherwise."""
    effect_player_id = effect_player.player_id
    target_location = effect.get("target_location", "backstage")
    bloom_level = effect.get("bloom_level", 1)
    target_played_this_turn = effect.get("target_played_this_turn", False)
    target_card_type = effect.get("target_card_type", None)
    target_names = effect.get("target_names", None)

    targets = []
    match target_location:
        case "backstage":
            targets = list(effect_player.backstage)
        case "center":
            targets = list(effect_player.center)
        case "stage":
            targets = effect_player.get_holomem_on_stage()

    if target_played_this_turn:
        targets = [h for h in targets if h.get("played_this_turn", False)]
    if target_card_type:
        targets = [h for h in targets if h["card_type"] == target_card_type]
    if target_names:
        targets = [h for h in targets if any(n in h.get("card_names", []) for n in target_names)]

    valid_blooms_in_hand = []
    for card in effect_player.hand:
        if card["card_type"] == "holomem_bloom" and card["bloom_level"] == bloom_level:
            for target in targets:
                if effect_player.can_bloom_with_card(target, card):
                    valid_blooms_in_hand.append(card)
                    break
    if len(valid_blooms_in_hand) > 0:
        decision_event = {
            "event_type": EventType.EventType_Decision_ChooseCards,
            "desired_response": GameAction.EffectResolution_ChooseCardsForEffect,
            "effect_player_id": effect_player_id,
            "all_card_seen": ids_from_cards(valid_blooms_in_hand),
            "cards_can_choose": ids_from_cards(valid_blooms_in_hand),
            "from_zone": "hand",
            "to_zone": "holomem",
            "amount_min": 0,
            "amount_max": 1,
            "special_reason": "bloom_from_special",
            "reveal_chosen": True,
            "remaining_cards_action": "nothing",
        }
        engine.broadcast_event(decision_event)
        engine.set_decision({
            "decision_type": DecisionType.DecisionEffect_ChooseCardsForEffect,
            "decision_player": effect_player_id,
            "all_card_seen": ids_from_cards(valid_blooms_in_hand),
            "cards_can_choose": ids_from_cards(valid_blooms_in_hand),
            "amount_min": 0,
            "amount_max": 1,
            "target_cards": targets,
            "effect": effect,
            "effect_resolution": engine.handle_chose_bloom_now_choose_target,
            "continuation": engine.continue_resolving_effects,
        })
        return True
    return False


def handle_bloom_from_archive(engine, effect_player, effect):
    """Returns True if continuation was passed on, False otherwise."""
    effect_player_id = effect_player.player_id
    target_condition = effect.get("target_condition", "")
    target_tags = effect.get("target_tags", [])
    target_location = effect.get("target_location", "stage")
    # bloom_source는 자동으로 "archive"로 설정
    bloom_source = "archive"
    is_optional = effect.get("optional", False)

    # 아카이브 bloom 레벨 제한
    archive_bloom_level = effect.get("archive_bloom_level", None)
    stage_bloom_level = effect.get("stage_bloom_level", None)

    # Get target holomems based on condition
    target_holomems = []
    if target_location == "stage":
        target_holomems = effect_player.get_holomem_on_stage()

    if target_condition == "tag_in":
        target_holomems = [holomem for holomem in target_holomems if any(tag in holomem["tags"] for tag in target_tags)]
    elif target_condition == "bloomable_this_turn":
        # Filter to only holomems that can bloom this turn
        target_holomems = [holomem for holomem in target_holomems if effect_player.can_bloom_this_turn(holomem)]
    elif target_condition == "tag_in_bloomable_this_turn":
        # Filter to holomems that have the specified tags AND can bloom this turn
        target_holomems = [holomem for holomem in target_holomems
                          if any(tag in holomem["tags"] for tag in target_tags)
                          and effect_player.can_bloom_this_turn(holomem)]

    # 스테이지 bloom 레벨 필터링
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

    # Get bloom candidates from archive - 자동으로 bloom 가능한 카드만 필터링
    bloom_candidates = []
    for card in effect_player.archive:
        if not is_card_holomem(card):
            continue
        if card["card_type"] != "holomem_bloom":
            continue

        # 아카이브 bloom 레벨 필터링
        if archive_bloom_level is not None:
            if isinstance(archive_bloom_level, list):
                # 배열인 경우: 여러 레벨 중 하나라도 일치하면 허용
                level_match = False
                for level in archive_bloom_level:
                    if level == "debut" or level == 0:
                        if card["bloom_level"] == 1:
                            level_match = True
                            break
                    elif card["bloom_level"] == level:
                        level_match = True
                        break
                if not level_match:
                    continue
            else:
                # 단일 레벨인 경우
                if archive_bloom_level == "debut" or archive_bloom_level == 0:
                    if card["bloom_level"] != 1:
                        continue
                elif card["bloom_level"] != archive_bloom_level:
                    continue

        # 스테이지의 홀로멤 중 하나라도 이 bloom 카드로 bloom할 수 있는지 확인
        can_bloom_with_any = False
        for holomem in target_holomems:
            if effect_player.can_bloom_with_card(holomem, card):
                can_bloom_with_any = True
                break

        if can_bloom_with_any:
            bloom_candidates.append(card)

    if len(target_holomems) == 0 or len(bloom_candidates) == 0:
        # No effect.
        pass
    elif len(target_holomems) == 1 and len(bloom_candidates) == 1 and not is_optional:
        # Do it automatically.
        effect_player.bloom(bloom_candidates[0]["game_card_id"], target_holomems[0]["game_card_id"], engine.continue_resolving_effects)
        return True
    else:
        # Ask for a decision.
        amount_min = 0 if is_optional else 1
        decision_event = {
            "event_type": EventType.EventType_Decision_ChooseCards,
            "desired_response": GameAction.EffectResolution_ChooseCardsForEffect,
            "effect_player_id": effect_player_id,
            "all_card_seen": ids_from_cards(bloom_candidates),
            "cards_can_choose": ids_from_cards(bloom_candidates),
            "amount_min": amount_min,
            "amount_max": 1,
            "effect": effect,
        }
        engine.broadcast_event(decision_event)
        engine.set_decision({
            "decision_type": DecisionType.DecisionEffect_ChooseCardsForEffect,
            "decision_player": effect_player_id,
            "all_card_seen": ids_from_cards(bloom_candidates),
            "cards_can_choose": ids_from_cards(bloom_candidates),
            "amount_min": amount_min,
            "amount_max": 1,
            "effect": effect,
            "effect_resolution": engine.handle_chose_bloom_now_choose_target,
            "continuation": engine.continue_resolving_effects,
        })
        return True
    return False


def handle_bloom_from_stacked(engine, effect_player, effect):
    """Returns True if continuation was passed on, False otherwise."""
    effect_player_id = effect_player.player_id
    target_member_names = effect.get("target_member_names", [])
    is_optional = effect.get("optional", False)
    source_card, _, _ = effect_player.find_card(effect["source_card_id"])

    stacked_holomems = []
    if source_card:
        stacked_holomems = [c for c in source_card["stacked_cards"] if is_card_holomem(c) and c["card_type"] == "holomem_bloom"]

    target_holomems = effect_player.get_holomem_on_stage()
    target_holomems = [h for h in target_holomems if h["game_card_id"] != effect["source_card_id"]]
    if target_member_names:
        target_holomems = [h for h in target_holomems if any(name in h["card_names"] for name in target_member_names)]
    target_holomems = [h for h in target_holomems if not h.get("played_this_turn", False)]
    target_holomems = [h for h in target_holomems if not h.get("bloomed_this_turn", False)]

    bloom_candidates = []
    for stacked_card in stacked_holomems:
        can_bloom_with_any = False
        for holomem in target_holomems:
            if effect_player.can_bloom_with_card(holomem, stacked_card):
                can_bloom_with_any = True
                break
        if can_bloom_with_any:
            bloom_candidates.append(stacked_card)

    if len(target_holomems) == 0 or len(bloom_candidates) == 0:
        pass
    else:
        amount_min = 0 if is_optional else 1
        decision_event = {
            "event_type": EventType.EventType_Decision_ChooseCards,
            "desired_response": GameAction.EffectResolution_ChooseCardsForEffect,
            "effect_player_id": effect_player_id,
            "all_card_seen": ids_from_cards(bloom_candidates),
            "cards_can_choose": ids_from_cards(bloom_candidates),
            "amount_min": amount_min,
            "amount_max": 1,
            "effect": effect,
        }
        engine.broadcast_event(decision_event)
        engine.set_decision({
            "decision_type": DecisionType.DecisionEffect_ChooseCardsForEffect,
            "decision_player": effect_player_id,
            "all_card_seen": ids_from_cards(bloom_candidates),
            "cards_can_choose": ids_from_cards(bloom_candidates),
            "amount_min": amount_min,
            "amount_max": 1,
            "effect": effect,
            "effect_resolution": engine.handle_chose_bloom_now_choose_target,
            "continuation": engine.continue_resolving_effects,
        })
        return True
    return False


def handle_block_opponent_movement(engine, effect_player, effect):
    """Returns True if continuation was passed on, False otherwise."""
    effect_player_id = effect_player.player_id
    other_player = engine.other_player(effect_player_id)
    other_player.block_movement_for_turn = True
    return False


def handle_block_life_loss_by_effect(engine, effect_player, effect):
    """Returns True if continuation was passed on, False otherwise."""
    effect_player_id = effect_player.player_id
    effect_player.block_life_loss_by_effect_this_turn = True
    return False


def handle_place_holomem(engine, effect_player, effect):
    """Returns True if continuation was passed on, False otherwise."""
    effect_player_id = effect_player.player_id
    card_id = effect["card_id"]
    to_zone = effect["location"]
    effect_player.move_card(card_id, to_zone)
    return False


def handle_activate_holomem(engine, effect_player, effect):
    """Returns True if continuation was passed on, False otherwise."""
    effect_player_id = effect_player.player_id
    requirement_tags = effect.get("requirement_tags", [])
    requirement_names = effect.get("requirement_names", [])
    resting_holomem_ids = []
    for holomem in effect_player.get_holomem_on_stage():
        if is_card_resting(holomem):
            if not requirement_tags or any(tag in holomem.get("tags", []) for tag in requirement_tags):
                if not requirement_names or any(name in holomem.get("card_names", []) for name in requirement_names):
                    resting_holomem_ids.append(holomem["game_card_id"])
    if len(resting_holomem_ids) == 0:
        pass
    elif len(resting_holomem_ids) == 1:
        card, _, _ = effect_player.find_card(resting_holomem_ids[0])
        card["resting"] = False
        engine.broadcast_event({
            "event_type": EventType.EventType_ActivateHolomem,
            "player_id": effect_player_id,
            "activated_card_id": resting_holomem_ids[0],
        })
    else:
        decision_event = {
            "event_type": EventType.EventType_Decision_ChooseHolomemForEffect,
            "desired_response": GameAction.EffectResolution_ChooseCardsForEffect,
            "effect_player_id": effect_player_id,
            "cards_can_choose": resting_holomem_ids,
        }
        engine.broadcast_event(decision_event)
        engine.set_decision({
            "decision_type": DecisionType.DecisionEffect_ChooseCardsForEffect,
            "decision_player": effect_player_id,
            "all_card_seen": resting_holomem_ids,
            "cards_can_choose": resting_holomem_ids,
            "amount_min": 1,
            "amount_max": 1,
            "effect_resolution": engine.handle_activate_holomem,
            "continuation": engine.continue_resolving_effects,
        })
        return True
    return False


def handle_return_holomem_to_debut(engine, effect_player, effect):
    """Returns True if continuation was passed on, False otherwise."""
    effect_player_id = effect_player.player_id
    target_player = effect_player
    if effect.get("opponent", False):
        target_player = engine.other_player(effect_player_id)
    target = effect["target"]
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
        case "holomem":
            target_cards = target_player.get_holomem_on_stage()
        case _:
            raise NotImplementedError("Only center is supported for now.")

    if len(target_cards) == 0:
        pass
    elif len(target_cards) == 1:
        engine.return_holomem_to_debut(target_player, target_cards[0]["game_card_id"])
    else:
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
            "effect_resolution": engine.handle_return_holomem_to_debut,
            "target_player": target_player,
            "continuation": engine.continue_resolving_effects,
        })
        return True
    return False


def handle_opponent_move_back_to_collab(engine, effect_player, effect):
    """Returns True if continuation was passed on, False otherwise."""
    effect_player_id = effect_player.player_id
    # 상대가 자신의 백스테이지 홀로멤 1명을 콜라보 포지션으로 이동 (콜라보로 취급하지 않음)
    opponent = engine.other_player(effect_player_id)
    # 상대 콜라보가 이미 있으면 효과 없음
    if len(opponent.collab) > 0:
        pass
    else:
        available_backstage_ids = [card["game_card_id"] for card in opponent.backstage]
        if len(available_backstage_ids) == 0:
            # 백스테이지에 홀로멤이 없으면 효과 없음
            pass
        elif len(available_backstage_ids) == 1:
            # 백스테이지에 1명만 있으면 자동으로 이동
            engine.move_back_to_collab_without_effect(opponent, available_backstage_ids[0])
        else:
            # 상대가 선택
            decision_event = {
                "event_type": EventType.EventType_Decision_MoveBackToCollab,
                "desired_response": GameAction.EffectResolution_ChooseCardsForEffect,
                "effect_player_id": opponent.player_id,
                "cards_can_choose": available_backstage_ids,
            }
            engine.broadcast_event(decision_event)
            engine.set_decision({
                "decision_type": DecisionType.DecisionEffect_ChooseCardsForEffect,
                "decision_player": opponent.player_id,
                "all_card_seen": available_backstage_ids,
                "cards_can_choose": available_backstage_ids,
                "amount_min": 1,
                "amount_max": 1,
                "effect_resolution": engine.handle_move_back_to_collab,
                "continuation": engine.continue_resolving_effects,
            })
            return True
    return False


def handle_rest_holomem(engine, effect_player, effect):
    """Rests (sets resting=True) an opponent's backstage holomem."""
    effect_player_id = effect_player.player_id
    target_player = effect_player
    if effect.get("opponent", False):
        target_player = engine.other_player(effect_player_id)

    active_holomem_ids = []
    for holomem in target_player.backstage:
        if not is_card_resting(holomem):
            active_holomem_ids.append(holomem["game_card_id"])

    if len(active_holomem_ids) == 0:
        pass
    elif len(active_holomem_ids) == 1:
        card, _, _ = target_player.find_card(active_holomem_ids[0])
        card["resting"] = True
        engine.broadcast_event({
            "event_type": EventType.EventType_RestHolomem,
            "player_id": target_player.player_id,
            "rested_card_id": active_holomem_ids[0],
        })
    else:
        choosing_player_id = effect_player_id
        decision_event = {
            "event_type": EventType.EventType_Decision_ChooseHolomemForEffect,
            "desired_response": GameAction.EffectResolution_ChooseCardsForEffect,
            "effect_player_id": choosing_player_id,
            "cards_can_choose": active_holomem_ids,
        }
        engine.broadcast_event(decision_event)
        engine.set_decision({
            "decision_type": DecisionType.DecisionEffect_ChooseCardsForEffect,
            "decision_player": choosing_player_id,
            "all_card_seen": active_holomem_ids,
            "cards_can_choose": active_holomem_ids,
            "amount_min": 1,
            "amount_max": 1,
            "rest_target_player_id": target_player.player_id,
            "effect_resolution": engine.handle_rest_holomem,
            "continuation": engine.continue_resolving_effects,
        })
        return True
    return False


BLOOM_HOLOMEM_HANDLERS = {
    EffectType.EffectType_BloomAlreadyBloomedThisTurn: handle_bloom_already_bloomed_this_turn,
    EffectType.EffectType_BloomFromSpecial: handle_bloom_from_special,
    EffectType.EffectType_BloomFromArchive: handle_bloom_from_archive,
    EffectType.EffectType_BloomFromStacked: handle_bloom_from_stacked,
    EffectType.EffectType_BlockOpponentMovement: handle_block_opponent_movement,
    EffectType.EffectType_BlockLifeLossByEffect: handle_block_life_loss_by_effect,
    EffectType.EffectType_PlaceHolomem: handle_place_holomem,
    EffectType.EffectType_ActivateHolomem: handle_activate_holomem,
    EffectType.EffectType_ReturnHolomemToDebut: handle_return_holomem_to_debut,
    EffectType.EffectType_OpponentMoveBackToCollab: handle_opponent_move_back_to_collab,
    EffectType.EffectType_RestHolomem: handle_rest_holomem,
}
