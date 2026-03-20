from typing import List, Dict, Any
from app.card_database import CardDatabase
import random
from copy import deepcopy
import traceback
import time
import logging
logger = logging.getLogger(__name__)

from app.engine.constants import *
from app.engine.models import *
from app.engine.helpers import *
from app.engine.player_state import PlayerState
from app.engine.game_flow_mixin import GameFlowMixin
from app.engine.turn_mixin import TurnMixin
from app.engine.combat_mixin import CombatMixin
from app.engine.condition_mixin import ConditionMixin
from app.engine.effect_mixin import EffectMixin
from app.engine.action_handler_mixin import ActionHandlerMixin


class GameEngine(GameFlowMixin, TurnMixin, CombatMixin, ConditionMixin, EffectMixin, ActionHandlerMixin):
    def __init__(self,
        card_db:CardDatabase,
        game_type : str,
        player_infos : List[Dict[str, Any]],
    ):
        self.phase = GamePhase.Initializing
        self.game_first_turn = True
        self.card_db = card_db
        self.latest_events = []
        self.latest_observer_events = []
        self.all_game_messages = []
        self.all_events = []
        self.game_over_event = {}
        self.current_decision = None
        self.effect_resolution_state = None
        self.test_random_override = None
        self.turn_number = 0
        self.floating_cards = []
        self.down_holomem_state : DownHolomemState = None
        self.returned_to_deck_card = None
        self.last_die_value = 0
        self.die_roll_source = ""
        self.die_roll_source_card_id = ""
        self.archive_count_required = 0
        self.remove_downed_holomems_to_hand = False
        self.stacked_cards_to_hand_ids = []
        self.after_damage_state : AfterDamageState = None
        self.last_chosen_cards = []
        self.stage_selected_holomems = []
        self.last_card_count = 0
        self.archiving_attachment_card = None
        self.archiving_attachment_holomem = None
        self.archive_attachment_replaced = False
        self.next_life_loss_modifier = 0
        self.current_clock_player_id = None
        self.clock_accumulation_start_time = 0
        self.match_player_info = player_infos
        self.last_chosen_holomem_id = ""
        
        # 블룸 출처 추적을 위한 변수
        self.last_bloom_source_skill_id = ""
        self.in_performance_step_start_effects = False

        self.take_damage_state : TakeDamageState = None
        self.performance_artstatboosts = ArtStatBoosts()
        self.performance_performing_player = None
        self.performance_performer_card = None
        self.performance_target_player = None
        self.performance_target_card = None
        self.performance_art = None
        self.performance_continuation = self.blank_continuation

        self.seed = random.randint(0, 2**32 - 1)
        self.game_type = game_type
        self.player_ids = [player_info["player_id"] for player_info in player_infos]
        self.player_states = [PlayerState(card_db, player_info, self) for player_info in player_infos]
        self.starting_player_id = None
        self.first_turn_player_id = None

        # Combine all game card mappings into a single dict.
        self.all_game_cards_map = {}
        for player_state in self.player_states:
            self.all_game_cards_map.update(player_state.game_cards_map)

    def get_match_log(self):
        winner = "none"
        game_over_reason = GameOverReason.GameOverReason_Unset
        if self.game_over_event:
            winner_id = self.game_over_event["winner_id"]
            game_over_reason = self.game_over_event["reason_id"]
            winner = self.get_player(winner_id).username
        match_data = {
            "all_events": self.all_events,
            "all_game_messages": self.all_game_messages,
            "all_game_cards_map": self.all_game_cards_map,
            "game_type": self.game_type,
            "game_over_event": self.game_over_event,
            "game_over_reason": game_over_reason,
            "player_info": self.match_player_info,
            "player_clocks": [player_state.clock_time_used for player_state in self.player_states],
            "player_final_life": [str(len(player_state.life)) for player_state in self.player_states],
            "seed": self.seed,
            "starting_player": self.get_player(self.starting_player_id).username,
            "first_turn_player": self.get_player(self.first_turn_player_id).username if self.first_turn_player_id else "",
            "turn_number": self.turn_number,
            "winner": winner,
        }
        return match_data

    def set_random_test_hook(self, random_override):
        self.test_random_override = random_override

    def grab_events(self):
        events = self.latest_events
        self.latest_events = []
        return events

    def grab_observer_events(self):
        events = self.latest_observer_events
        self.latest_observer_events = []
        return events

    def get_player(self, player_id:str):
        return self.player_states[self.player_ids.index(player_id)]

    def other_player(self, player_id:str) -> PlayerState:
        return self.player_states[1 - self.player_ids.index(player_id)]

    def shuffle_list(self, lst):
        self.random_gen.shuffle(lst)

    def random_pick_list(self, lst):
        return self.random_gen.choice(lst)

    def switch_active_player(self):
        self.active_player_id = self.other_player(self.active_player_id).player_id

    def is_game_over(self):
        return self.phase == GamePhase.GameOver

    def find_card(self, game_card_id):
        for player_state in self.player_states:
            card, _, _ = player_state.find_card(game_card_id)
            if not card:
                for holomem in player_state.get_holomem_on_stage():
                    for attachment in holomem["attached_support"]:
                        if attachment["game_card_id"] == game_card_id:
                            card = attachment
                            return card
                    for cheer in holomem["attached_cheer"]:
                        if cheer["game_card_id"] == game_card_id:
                            card = cheer
                            return card
                    for stacked in holomem["stacked_cards"]:
                        if stacked["game_card_id"] == game_card_id:
                            card = stacked
                            return card
            else:
                return card
        if not card:
            raise Exception(f"Card not found: {game_card_id}")
