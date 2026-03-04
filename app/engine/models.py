from __future__ import annotations
from typing import List, Dict, Any, TYPE_CHECKING
from copy import deepcopy

if TYPE_CHECKING:
    from app.engine.player_state import PlayerState

class ArtStatBoosts:
    def __init__(self):
        self.power = 0
        self.repeat_art = False
        self.is_repeat = False

    def clear(self):
        self.power = 0
        self.repeat_art = False
        self.is_repeat = False

class TakeDamageState:
    def __init__(self):
        self.added_damage = 0
        self.prevented_damage = 0
        self.incoming_base_damage = 0
        self.source_player = None
        self.source_card = None
        self.target_card = None
        self.target_card_zone = ""
        self.special = False
        self.prevent_life_loss = False
        self.art_info = {}

        self.nested_state = None

    def get_incoming_damage(self):
        return max(0, self.incoming_base_damage + self.added_damage - self.prevented_damage)

class AfterDamageState:
    def __init__(self):
        self.source_player : PlayerState = None
        self.source_card = None
        self.target_player : PlayerState = None
        self.target_card = None
        self.damage_dealt = 0
        self.special = False
        self.target_card_zone = ""
        self.target_still_on_stage = False

        self.nested_state = None

class DownHolomemState:
    def __init__(self):
        self.holomem_card = None

        self.nested_state = None

class GameAction:
    Mulligan = "mulligan"
    MulliganActionFields = {
        "do_mulligan": bool,
    }

    InitialPlacement = "initial_placement"
    InitialPlacementActionFields = {
        "center_holomem_card_id": str,
    }

    ReturnCards = "return_cards"
    ReturnCardsActionFields = {
        "card_ids": List[str],
    }

    BackstagePlacement = "backstage_placement"
    BackstagePlacementActionFields = {
        "backstage_holomem_card_ids": List[str],
    }

    ChooseNewCenter = "choose_new_center"
    ChooseNewCenterActionFields = {
        "new_center_card_id": str,
    }

    PlaceCheer = "place_cheer"
    PlaceCheerActionFields = {
        "placements": Dict[str, str],
    }

    MainStepPlaceHolomem = "mainstep_place_holomem"
    MainStepPlaceHolomemFields = {
        "card_id": str,
    }

    MainStepBloom = "mainstep_bloom"
    MainStepBloomFields = {
        "card_id": str,
        "target_id": str,
    }

    MainStepCollab = "mainstep_collab"
    MainStepCollabFields = {
        "card_id": str,
    }

    MainStepOshiSkill = "mainstep_oshi_skill"
    MainStepOshiSkillFields = {
        "skill_id": str,
    }

    MainStepSpecialAction = "mainstep_special_action"
    MainStepSpecialActionFields = {
        "effect_id": str,
        "card_id": str,
    }

    MainStepPlaySupport = "mainstep_play_support"
    MainStepPlaySupportFields = {
        "card_id": str,
    }

    MainStepBatonPass = "mainstep_baton_pass"
    MainStepBatonPassFields = {
        "card_id": str,
        "cheer_ids": List[str],
    }

    MainStepBeginPerformance = "mainstep_begin_performance"
    MainStepBeginPerformanceFields = {}

    MainStepEndTurn = "mainstep_end_turn"
    MainStepEndTurnFields = {}

    PerformanceStepUseArt = "performance_step_use_art"
    PerformanceStepUseArtFields = {
        "performer_id": str,
        "art_id": str,
        "target_id": str,
    }

    PerformanceStepCancel = "performance_step_cancel"
    PerformanceStepCancelFields = {}

    PerformanceStepEndTurn = "performance_step_end_turn"
    PerformanceStepEndTurnFields = {}

    EffectResolution_MoveCheerBetweenHolomems = "effect_resolution_move_cheer_between_holomems"
    EffectResolution_MoveCheerBetweenHolomemsFields = {
        "placements": Dict[str, str],
    }

    EffectResolution_ChooseCardsForEffect = "effect_resolution_choose_card_for_effect"
    EffectResolution_ChooseCardsForEffectFields = {
        "card_ids": List[str],
    }

    EffectResolution_MakeChoice = "effect_resolution_make_choice"
    EffectResolution_MakeChoiceFields = {
        "choice_index": int,
    }

    EffectResolution_OrderCards = "effect_resolution_order_cards"
    EffectResolution_OrderCardsFields = {
        "card_ids": List[str],
    }

    Resign = "resign"
    ResignFields = {
    }

class EffectResolutionState:
    def __init__(self, effects, continuation, cards_to_cleanup = [], simultaneous_choice = False):
        self.effects_to_resolve = deepcopy(effects)
        self.effect_resolution_continuation = continuation
        self.cards_to_cleanup = cards_to_cleanup
        self.simultaneous_choice = simultaneous_choice

        self.simultaneous_choice_index = -1
