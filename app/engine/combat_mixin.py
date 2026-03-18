from __future__ import annotations
from typing import List, TYPE_CHECKING
from copy import deepcopy
import logging

from app.engine.constants import *
from app.engine.models import *
from app.engine.helpers import *

if TYPE_CHECKING:
    from app.engine.player_state import PlayerState

logger = logging.getLogger(__name__)


class CombatMixin:
    def begin_perform_art(self, performer_id, art_id, target_id, continuation, is_repeat=False):
        player = self.get_player(self.active_player_id)
        player.performance_attacked_this_turn = True
        performer, _, _ = player.find_card(performer_id)
        performer["used_art_this_turn"] = True
        target_owner = self.other_player(self.active_player_id)
        target, _, _ = target_owner.find_card(target_id)
        art = None
        for a in performer["arts"]:
            if a["art_id"] == art_id:
                art = a
                break
        if art is None:
            art = self._find_borrowed_art(player, performer, art_id)

        art_event = {
            "event_type": EventType.EventType_PerformArt,
            "active_player": self.active_player_id,
            "performer_id": performer["game_card_id"],
            "art_id": art["art_id"],
            "target_id": target["game_card_id"],
            "target_player": target_owner.player_id,
            "power": art["power"],
        }
        self.broadcast_event(art_event)

        self.performance_artstatboosts = ArtStatBoosts()
        self.performance_artstatboosts.is_repeat = is_repeat
        self.performance_performing_player = player
        self.performance_performer_card = performer
        self.performance_target_player = target_owner
        self.performance_target_card = target
        self.performance_art = art
        self.performance_continuation = continuation

        # Get any before effects and resolve them.
        art_effects = filter_effects_at_timing(art.get("art_effects", []), "before_art")
        add_ids_to_effects(art_effects, player.player_id, performer_id)
        card_effects = player.get_effects_at_timing("before_art", performer)
        all_effects = card_effects + art_effects
        self.begin_resolving_effects(all_effects, self.continue_perform_art)

    def _find_borrowed_art(self, player, performer, art_id):
        if "gift_effects" not in performer:
            return None
        for gift in performer["gift_effects"]:
            if gift.get("effect_type") != "use_other_holomem_arts":
                continue
            required_tags = gift.get("required_tags", [])
            for other_holomem in player.get_holomem_on_stage():
                if other_holomem["game_card_id"] == performer["game_card_id"]:
                    continue
                if required_tags and not any(
                    tag in other_holomem.get("tags", []) for tag in required_tags
                ):
                    continue
                for a in other_holomem["arts"]:
                    if a["art_id"] == art_id:
                        return a
        return None

    def continue_perform_art(self):
        # Now all before effects have been resolved.
        # Actually do the art.
        total_power = self.performance_art["power"]
        total_power += self.performance_artstatboosts.power
        target_owner = self.get_player(self.performance_target_card["owner_id"])
        is_special_damage = "special" in self.performance_art and self.performance_art["special"]

        active_player = self.get_player(self.active_player_id)

        # Deal damage.
        art_after_deal_damage_effects = filter_effects_at_timing(self.performance_art.get("art_effects", []), "after_deal_damage")
        add_ids_to_effects(art_after_deal_damage_effects, self.active_player_id, self.performance_performer_card["game_card_id"])
        art_kill_effects = self.performance_art.get("on_kill_effects", [])
        add_ids_to_effects(art_kill_effects, self.active_player_id, self.performance_performer_card["game_card_id"])
        art_info = {
            "after_deal_damage_effects": art_after_deal_damage_effects,
            "art_kill_effects": art_kill_effects,
        }
        if self.performance_artstatboosts.deal_to_center_and_collab:
            self.deal_damage_to_center_and_collab(active_player, target_owner, total_power, is_special_damage, art_info, self.performance_continuation)
        else:
            self.deal_damage(active_player, target_owner, self.performance_performer_card, self.performance_target_card, total_power, is_special_damage, False, art_info, self.performance_continuation)

    def deal_damage_to_center_and_collab(self, dealing_player, target_player, damage, special, art_info, continuation):
        """Deal full damage to both opponent's center and collab holomems."""
        center_card = target_player.center[0] if target_player.center else None
        collab_card = target_player.collab[0] if target_player.collab else None

        def deal_to_collab():
            if collab_card and collab_card in target_player.get_holomem_on_stage():
                self.deal_damage(dealing_player, target_player, self.performance_performer_card, collab_card, damage, special, False, art_info, continuation)
            else:
                continuation()

        if center_card:
            self.deal_damage(dealing_player, target_player, self.performance_performer_card, center_card, damage, special, False, art_info, deal_to_collab)
        else:
            deal_to_collab()

    def process_life_lost(self, life_lost: int, life_to_distribute: list, target_player: PlayerState, game_over: bool, game_over_reason: str, continuation):
        logger.debug(f"process_life_lost: life_lost={life_lost} game_over={game_over} game_over_reason={game_over_reason} life_to_distribute_count={len(life_to_distribute)}")
        if game_over:
            # For making logging look nice, go ahead and remove any life lost.
            for _ in range(life_lost):
                if target_player.life:
                    target_player.life.pop()
            self.end_game(target_player.player_id, game_over_reason)
        elif life_to_distribute:
            # Tell the owner to distribute this life amongst their holomems.
            remaining_holomems = ids_from_cards(target_player.get_holomem_on_stage())
            cheer_on_each_mem = target_player.get_cheer_on_each_holomem()
            decision_event = {
                "event_type": EventType.EventType_Decision_SendCheer,
                "desired_response": GameAction.EffectResolution_MoveCheerBetweenHolomems,
                "effect_player_id": target_player.player_id,
                "amount_min": len(life_to_distribute),
                "amount_max": len(life_to_distribute),
                "from_zone": "life",
                "to_zone": "holomem",
                "from_options": life_to_distribute,
                "to_options": remaining_holomems,
                "cheer_on_each_mem": cheer_on_each_mem,
                "multi_to": True,
            }
            self.broadcast_event(decision_event)
            self.set_decision({
                "decision_type": DecisionType.DecisionEffect_MoveCheerBetweenHolomems,
                "decision_player": target_player.player_id,
                "amount_min": len(life_to_distribute),
                "amount_max": len(life_to_distribute),
                "available_cheer": life_to_distribute,
                "available_targets": remaining_holomems,
                "continuation": continuation,
                "multi_to": True,
            })
        else:
            continuation()

    def deal_life_damage(self, target_player: PlayerState, dealing_card, damage: int, continuation):
        # Check if life loss by effect is blocked for this turn
        if target_player.block_life_loss_by_effect_this_turn:
            # Life damage by effect is blocked, skip the damage
            continuation()
            return

        game_over = False
        game_over_reason = ""
        life_to_distribute = []
        life_lost = damage

        current_life = len(target_player.life)
        if life_lost >= current_life:
            game_over = True
            game_over_reason = GameOverReason.GameOverReason_NoLifeLeft

        if not game_over:
            life_to_distribute = ids_from_cards(target_player.life[:life_lost])

        # Send the life damage dealt event
        life_damage_event = {
            "event_type": EventType.EventType_LifeDamageDealt,
            "target_player": target_player.player_id,
            "source_card_id": dealing_card["game_card_id"],
            "life_lost": life_lost,
            "game_over": game_over
        }
        self.broadcast_event(life_damage_event)
        self.process_life_lost(life_lost, life_to_distribute, target_player, game_over, game_over_reason, continuation)


    def deal_damage(self, dealing_player : PlayerState, target_player : PlayerState, dealing_card, target_card, damage, special, prevent_life_loss, art_info, continuation):
        logger.debug(f"deal_damage: target={target_card['game_card_id']} damage={damage} special={special} prevent_life_loss={prevent_life_loss}")
        if target_card["damage"] >= target_player.get_card_hp(target_card):
            # Damage already at or past HP threshold
            # Check if the card is still on stage - if so, trigger death processing
            if target_card in target_player.get_holomem_on_stage():
                # Card should be dead but wasn't processed - trigger death now
                self.begin_down_holomem(dealing_player, target_player, dealing_card, target_card, art_info, lambda:
                    self.complete_deal_damage(dealing_player, target_player, dealing_card, target_card, 0, special, prevent_life_loss, True, art_info, continuation))
                return
            # Already processed (in archive), just call continuation
            continuation()
            return

        target_card["damage"] += damage

        nested_state = None
        if self.take_damage_state:
            nested_state = self.take_damage_state
        self.take_damage_state = TakeDamageState()
        self.take_damage_state.nested_state = nested_state
        self.take_damage_state.incoming_base_damage = damage
        self.take_damage_state.special = special
        self.take_damage_state.prevent_life_loss = prevent_life_loss
        self.take_damage_state.source_player = dealing_player
        self.take_damage_state.source_card = dealing_card
        self.take_damage_state.target_card = target_card
        self.take_damage_state.target_card_zone = target_player.get_holomem_zone(target_card)
        self.take_damage_state.art_info = art_info
        if self.performance_artstatboosts and self.performance_artstatboosts.cannot_be_reduced:
            self.take_damage_state.cannot_be_reduced = True

        # Get on_deal_damage effects from dealing player (e.g., gift effects that boost special damage)
        on_deal_damage_effects = dealing_player.get_effects_at_timing("on_deal_damage", dealing_card)
        on_damage_effects = target_player.get_effects_at_timing("on_take_damage", target_card)
        all_damage_effects = on_deal_damage_effects + on_damage_effects
        self.begin_resolving_effects(all_damage_effects, lambda :
            self.continue_deal_damage(dealing_player, target_player, dealing_card, target_card, damage, special, prevent_life_loss, art_info, continuation)
        )

    def restore_holomem_hp(self, target_player : PlayerState, target_card_id, amount, continuation):
        target_card, _, _ = target_player.find_card(target_card_id)
        before_damage = target_card["damage"]
        target_player.restore_holomem_hp(target_card_id, amount)
        damage_healed = before_damage - target_card["damage"]
        if damage_healed > 0:
            on_restore_effects = target_player.get_effects_at_timing("on_restore_hp", target_card)
            self.begin_resolving_effects(on_restore_effects, continuation)
        else:
            continuation()

    def continue_deal_damage(self, dealing_player : PlayerState, target_player : PlayerState, dealing_card, target_card, damage, special, prevent_life_loss, art_info, continuation):
        if self.take_damage_state.added_damage:
            target_card["damage"] += self.take_damage_state.added_damage
            damage += self.take_damage_state.added_damage

        if self.take_damage_state.prevented_damage and not self.take_damage_state.cannot_be_reduced:
            target_card["damage"] -= damage
            damage = max(0, damage - self.take_damage_state.prevented_damage)
            target_card["damage"] += damage

        redirect_target = self.take_damage_state.redirect_target
        redirect_target_player = self.take_damage_state.redirect_target_player
        self.take_damage_state = self.take_damage_state.nested_state

        if redirect_target and redirect_target_player:
            target_card["damage"] -= damage
            actual_target = redirect_target
            actual_target_player = redirect_target_player
            actual_target["damage"] += damage
        else:
            actual_target = target_card
            actual_target_player = target_player

        damage_event = {
            "event_type": EventType.EventType_DamageDealt,
            "target_id": actual_target["game_card_id"],
            "target_player": actual_target_player.player_id,
            "damage": damage,
            "special": special,
        }
        self.broadcast_event(damage_event)

        died = actual_target["damage"] >= actual_target_player.get_card_hp(actual_target)
        if died:
            self.begin_down_holomem(dealing_player, actual_target_player, dealing_card, actual_target, art_info, lambda :
                self.complete_deal_damage(dealing_player, actual_target_player, dealing_card, actual_target, damage, special, prevent_life_loss, died, art_info, continuation))
        else:
            self.complete_deal_damage(dealing_player, actual_target_player, dealing_card, actual_target, damage, special, prevent_life_loss, died, art_info, continuation)

    def complete_deal_damage(self, dealing_player : PlayerState, target_player : PlayerState, dealing_card, target_card, damage, special, prevent_life_loss, died, art_info, continuation):
        if died:
            self.process_downed_holomem(target_player, target_card, prevent_life_loss, lambda :
                self.begin_after_deal_damage(dealing_player, target_player, dealing_card, target_card, damage, special, art_info, continuation)
            )
        else:
            self.begin_after_deal_damage(dealing_player, target_player, dealing_card, target_card, damage, special, art_info, continuation)

    def begin_after_deal_damage(self, dealing_player : PlayerState, target_player : PlayerState, dealing_card, target_card, damage, special, art_info, continuation):
        logger.debug(f"begin_after_deal_damage: target={target_card['game_card_id']} damage={damage} target_on_stage={target_card in target_player.get_holomem_on_stage()}")
        after_effects = []
        if damage > 0:
            art_after_deal_damage_effects = art_info.get("after_deal_damage_effects", [])
            after_deal_damage_effects = dealing_player.get_effects_at_timing("after_deal_damage", dealing_card)
            after_take_damage_effects = target_player.get_effects_at_timing("after_take_damage", target_card)
            after_effects = art_after_deal_damage_effects + after_deal_damage_effects + after_take_damage_effects
        nested_state = None
        if self.after_damage_state:
            nested_state = self.after_damage_state
        self.after_damage_state = AfterDamageState()
        self.after_damage_state.nested_state = nested_state
        self.after_damage_state.source_player = dealing_player
        self.after_damage_state.source_card = dealing_card
        self.after_damage_state.target_card = target_card
        self.after_damage_state.target_player = target_player
        self.after_damage_state.damage_dealt = damage
        self.after_damage_state.special = special
        self.after_damage_state.target_card_zone = target_player.get_holomem_zone(target_card)
        self.after_damage_state.target_still_on_stage = target_card in target_player.get_holomem_on_stage()

        self.begin_resolving_effects(after_effects, lambda :
            self.complete_after_deal_damage(continuation)
        )

    def complete_after_deal_damage(self, continuation):
        self.after_damage_state = self.after_damage_state.nested_state
        continuation()

    def begin_down_holomem(self, dealing_player : PlayerState, target_player : PlayerState, dealing_card, target_card, art_info, continuation):
        logger.debug(f"begin_down_holomem: target={target_card['game_card_id']} dealing_card={dealing_card['game_card_id'] if dealing_card else 'None'}")
        player_kill_effects = dealing_player.get_effects_at_timing("on_kill", dealing_card)
        down_effects = target_player.get_effects_at_timing("on_down", target_card)
        arts_kill_effects = []
        if art_info:
            arts_kill_effects = art_info.get("art_kill_effects", [])
        dealing_player_effects = arts_kill_effects + player_kill_effects
        target_player_effects = down_effects
        down_info = DownHolomemState()
        down_info.nested_state = self.down_holomem_state
        self.down_holomem_state = down_info
        self.down_holomem_state.holomem_card = target_card

        if self.performance_artstatboosts.repeat_art:
            # Check to see if the current performance target is being downed,
            # if so, remove repeat_art because they're dead.
            if self.performance_target_card["game_card_id"] == target_card["game_card_id"]:
                self.performance_artstatboosts.repeat_art = False

        pre_down_event = {
            "event_type": EventType.EventType_DownedHolomem_Before,
            "target_id": target_card["game_card_id"],
            "target_player": target_player.player_id,
        }
        self.broadcast_event(pre_down_event)

        def resolve_target_effects():
            self.begin_resolving_effects(target_player_effects, continuation, simultaneous_choice=True)

        self.begin_resolving_effects(dealing_player_effects, resolve_target_effects, simultaneous_choice=True)

    def down_holomem(self, dealing_player : PlayerState, target_player : PlayerState, dealing_card, target_card, prevent_life_loss, continuation):
        self.begin_down_holomem(dealing_player, target_player, dealing_card, target_card, [], lambda :
            self.process_downed_holomem(target_player, target_card, prevent_life_loss, continuation)
        )

    def process_downed_holomem(self, target_player : PlayerState, target_card, prevent_life_loss, continuation):
        logger.debug(f"process_downed_holomem: target={target_card['game_card_id']} prevent_life_loss={prevent_life_loss}")
        self.down_holomem_state = self.down_holomem_state.nested_state
        game_over = False
        game_over_reason = ""
        life_to_distribute = []
        life_lost = 0
        archived_ids = []
        hand_ids = []

        # 홀로멤이 다운됐음을 추적 (직전 상대 턴에 다운됐는지 체크용)
        target_player.holomem_downed_this_turn = True
        target_player.holomem_downed_names_this_turn.extend(target_card.get("card_names", []))

        # Move all attached and stacked cards and the card itself to the archive.
        if self.remove_downed_holomems_to_hand:
            archived_ids, hand_ids = target_player.return_holomem_to_hand(target_card["game_card_id"], include_stacked_holomem=True)
            self.remove_downed_holomems_to_hand = False
        elif len(self.stacked_cards_to_hand_ids) > 0:
            archived_ids, hand_ids = target_player.archive_holomem_from_play(target_card["game_card_id"], self.stacked_cards_to_hand_ids)
            self.stacked_cards_to_hand_ids = []
        else:
            archived_ids, hand_ids = target_player.archive_holomem_from_play(target_card["game_card_id"])
        life_lost = 1
        if "down_life_cost" in target_card:
            life_lost = target_card["down_life_cost"]

        life_lost += self.next_life_loss_modifier
        self.next_life_loss_modifier = 0

        if prevent_life_loss:
            life_lost = 0

        current_life = len(target_player.life)
        if life_lost >= current_life:
            game_over = True
            game_over_reason = GameOverReason.GameOverReason_NoLifeLeft
        elif len(target_player.get_holomem_on_stage()) == 0:
            game_over = True
            game_over_reason = GameOverReason.GameOverReason_NoHolomemsLeft

        if not game_over:
            life_to_distribute = ids_from_cards(target_player.life[:life_lost])

        # Sent the down event.
        down_event = {
            "event_type": EventType.EventType_DownedHolomem,
            "target_id": target_card["game_card_id"],
            "target_player": target_player.player_id,
            "life_lost": life_lost,
            "life_loss_prevented": prevent_life_loss,
            "game_over": game_over,
            "archived_ids": archived_ids,
            "hand_ids": hand_ids,
        }
        self.broadcast_event(down_event)
        self.broadcast_bonus_hp_updates()
        self.process_life_lost(life_lost, life_to_distribute, target_player, game_over, game_over_reason, continuation)

    def begin_cleanup_art(self):
        performer_cleanup_effects = self.performance_performing_player.get_effects_at_timing("art_cleanup", self.performance_performer_card)
        self.begin_resolving_effects(performer_cleanup_effects, self.continue_performance_step, [], simultaneous_choice=True)
