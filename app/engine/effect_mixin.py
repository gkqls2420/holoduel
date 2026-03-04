from __future__ import annotations
from typing import TYPE_CHECKING
from copy import deepcopy

from app.engine.constants import *
from app.engine.models import *
from app.engine.helpers import *

if TYPE_CHECKING:
    from app.engine.player_state import PlayerState

class EffectMixin:
    def begin_resolving_effects(self, effects, continuation, cards_to_cleanup = [], simultaneous_choice = False):
        effect_continuation = continuation
        if self.effect_resolution_state:
            # There is already an effects resolution going down.
            # The current resolution will continue after this one.
            outer_resolution_state = self.effect_resolution_state
            def new_continuation():
                # Reset the previous effect resolution state before calling the continuation.
                self.effect_resolution_state = outer_resolution_state
                continuation()
            effect_continuation = new_continuation
        self.effect_resolution_state = EffectResolutionState(effects, effect_continuation, cards_to_cleanup, simultaneous_choice)
        self.continue_resolving_effects()

    def continue_resolving_effects(self):
        if not self.effect_resolution_state.effects_to_resolve:
            for cleanup_card in self.effect_resolution_state.cards_to_cleanup:
                # The card may have been removed from play by some effect (like attaching).
                if cleanup_card in self.floating_cards:
                    self.floating_cards.remove(cleanup_card)
                    owner = self.get_player(cleanup_card["owner_id"])
                    owner.archive.insert(0, cleanup_card)
                    cleanup_event = {
                        "event_type": EventType.EventType_MoveCard,
                        "moving_player_id": owner.player_id,
                        "from": "floating",
                        "to_zone": "archive",
                        "zone_card_id": "",
                        "card_id": cleanup_card["game_card_id"],
                    }
                    self.broadcast_event(cleanup_event)

            continuation = self.effect_resolution_state.effect_resolution_continuation
            self.effect_resolution_state = None
            # Don't clear stage_selected_holomems here - wait until the entire card effect is complete
            if not self.is_game_over():
                continuation()
            return

        passed_on_continuation = False
        while len(self.effect_resolution_state.effects_to_resolve) > 0 and not self.current_decision:
            multiple_simulatenous_choices = len(self.effect_resolution_state.effects_to_resolve) > 1 and self.effect_resolution_state.simultaneous_choice
            if "internal_skip_simultaneous_choice" in self.effect_resolution_state.effects_to_resolve[0] and self.effect_resolution_state.effects_to_resolve[0]["internal_skip_simultaneous_choice"]:
                # Ignore simultaneous resolution for internal effects, they should happen next no matter what.
                multiple_simulatenous_choices = False

            if multiple_simulatenous_choices and self.effect_resolution_state.simultaneous_choice_index == -1:
                # There are multiple choices and the player has to make a decision, send the decision then break out.
                choice = self.effect_resolution_state.effects_to_resolve
                self.send_choice_to_player(choice[0]["player_id"], choice, simultaneous_resolution=True)
                break
            elif multiple_simulatenous_choices:
                # The player decided on the choice, so pop that one.
                effect = self.effect_resolution_state.effects_to_resolve.pop(self.effect_resolution_state.simultaneous_choice_index)
                self.effect_resolution_state.simultaneous_choice_index = -1
            else:
                # Pop the effect from the front of the list.
                effect = self.effect_resolution_state.effects_to_resolve.pop(0)
            effect_player_id = effect["player_id"]
            effect_player = self.get_player(effect_player_id)
            if "conditions" not in effect or self.are_conditions_met(effect_player, effect["source_card_id"], effect["conditions"]):
                # Add any "and" effects to the front of the queue.
                if "and" in effect:
                    and_effects = effect["and"]
                    add_ids_to_effects(and_effects, effect_player_id, effect.get("source_card_id", None))
                    for and_effect in and_effects:
                        and_effect["internal_skip_simultaneous_choice"] = True
                    self.effect_resolution_state.effects_to_resolve = and_effects + self.effect_resolution_state.effects_to_resolve
                passed_on_continuation = self.do_effect(effect_player, effect)
                if passed_on_continuation:
                    return
            else:
                # Failed conditions, add any negative condition effects to the front of the queue.
                if "negative_condition_effects" in effect:
                    negative_effects = effect["negative_condition_effects"]
                    add_ids_to_effects(negative_effects, effect_player_id, effect.get("source_card_id", None))
                    self.effect_resolution_state.effects_to_resolve = negative_effects + self.effect_resolution_state.effects_to_resolve

        if not self.current_decision:
            self.continue_resolving_effects()

    def do_effect(self, effect_player : PlayerState, effect):
        from app.engine.effects import EFFECT_HANDLERS
        effect_player_id = effect_player.player_id
        if "pre_effects" in effect:
            do_before_effects = effect["pre_effects"]
            add_ids_to_effects(do_before_effects, effect_player_id, effect.get("source_card_id", None))
            for do_before in do_before_effects:
                self.do_effect(effect_player, do_before)

        effect_type = effect["effect_type"]
        handler = EFFECT_HANDLERS.get(effect_type)
        if handler:
            passed_on_continuation = handler(self, effect_player, effect)
        else:
            raise NotImplementedError(f"Unimplemented effect type: {effect_type}")

        return passed_on_continuation

    def add_effects_to_front(self, new_effects):
        self.effect_resolution_state.effects_to_resolve = new_effects + self.effect_resolution_state.effects_to_resolve

    def add_effects_to_rear(self, new_effects):
        self.effect_resolution_state.effects_to_resolve = self.effect_resolution_state.effects_to_resolve + new_effects

    def add_deal_damage_internal_effect(self, source_player : PlayerState, target_player : PlayerState, source_card_id, target_card, amount, special, prevent_life_loss):
        effects = [{
            "effect_type": EffectType.EffectType_DealDamage_Internal,
            "source_player": source_player,
            "target_player": target_player,
            "target_card": target_card,
            "amount": amount,
            "special": special,
            "prevent_life_loss": prevent_life_loss,
            "internal_skip_simultaneous_choice": True,
        }]
        add_ids_to_effects(effects, source_player.player_id, source_card_id)
        self.add_effects_to_front(effects)

    def add_restore_holomem_hp_internal_effect(self, target_player : PlayerState, target_card, source_card_id, amount):
        effects = [{
            "effect_type": EffectType.EffectType_RestoreHp_Internal,
            "target_player": target_player,
            "target_card": target_card,
            "amount": amount,
            "internal_skip_simultaneous_choice": True,
        }]
        add_ids_to_effects(effects, target_player.player_id, source_card_id)
        self.add_effects_to_front(effects)

    def send_choice_to_player(self, effect_player_id, choice, simultaneous_resolution = False, continuation = None):
        if not continuation:
            continuation = self.continue_resolving_effects
        min_choice = 0
        max_choice = len(choice) - 1
        decision_event = {
            "event_type": EventType.EventType_Decision_Choice,
            "desired_response": GameAction.EffectResolution_MakeChoice,
            "effect_player_id": effect_player_id,
            "choice": choice,
            "min_choice": min_choice,
            "max_choice": max_choice,
            "simultaneous_resolution": simultaneous_resolution,
        }
        self.broadcast_event(decision_event)
        self.set_decision({
            "decision_type": DecisionType.DecisionChoice,
            "decision_player": effect_player_id,
            "choice": choice,
            "min_choice": min_choice,
            "max_choice": max_choice,
            "simultaneous_resolution": simultaneous_resolution,
            "resolution_func": self.handle_choice_effects,
            "continuation": continuation,
        })

    def end_game(self, loser_id, reason_id):
        if not self.is_game_over():
            self.phase = GamePhase.GameOver

            gameover_event = {
                "event_type": EventType.EventType_GameOver,
                "loser_id": loser_id,
                "winner_id": self.other_player(loser_id).player_id,
                "reason_id": reason_id,
            }
            self.broadcast_event(gameover_event)
            self.game_over_event = gameover_event

    def send_boost_event(self, card_id, source_card_id, stat:str, amount:int, for_art):
        boost_event = {
            "event_type": EventType.EventType_BoostStat,
            "card_id": card_id,
            "stat": stat,
            "amount": amount,
            "for_art": for_art,
            "source_card_id": source_card_id
        }
        self.broadcast_event(boost_event)
