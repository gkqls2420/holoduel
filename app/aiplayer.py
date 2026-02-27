from typing import Dict
from app.gameengine import EventType, GameAction
import random
import logging
import json
import os

logger = logging.getLogger(__name__)

# AI가 사용할 덱 설정 (환경 변수 우선, 기본값은 whale)
AI_DECK_NAME = os.getenv("AI_DECK_NAME", "whale")

def load_ai_deck(deck_name=None):
    """덱 파일에서 AI 덱을 로드합니다. Railway 환경에서도 안전하게 작동합니다."""
    if deck_name is None:
        deck_name = AI_DECK_NAME
    
    logger.info(f"Attempting to load AI deck: {deck_name}")
    
    # 1. 먼저 내장 덱 목록 확인
    builtin_decks = get_builtin_decks()
    if deck_name in builtin_decks:
        logger.info(f"Using builtin deck: {deck_name}")
        return builtin_decks[deck_name]
    
    # 2. 파일 시스템에서 덱 로드 시도
    deck_data = try_load_deck_from_file(deck_name)
    if deck_data:
        return deck_data
    
    # 3. 모든 시도 실패 시 기본 덱 사용
    logger.warning(f"Failed to load deck '{deck_name}', using default deck")
    return get_default_ai_deck()

def try_load_deck_from_file(deck_name):
    """파일 시스템에서 덱을 로드하려고 시도합니다."""
    try:
        # 여러 가능한 경로 시도
        possible_paths = [
            os.path.join(os.path.dirname(__file__), "..", "decks", f"{deck_name}.json"),
            os.path.join(os.getcwd(), "decks", f"{deck_name}.json"),
            os.path.join(os.path.dirname(__file__), "..", "..", "decks", f"{deck_name}.json"),
        ]
        
        for deck_file in possible_paths:
            if os.path.exists(deck_file):
                logger.info(f"Found deck file at: {deck_file}")
                try:
                    with open(deck_file, "r", encoding='utf-8') as f:
                        deck_data = json.load(f)
                    
                    # HoloDelta 형식인지 확인
                    if "cheerDeck" in deck_data:
                        converted_deck = convert_holodelta_to_simple_format(deck_data)
                        logger.info(f"Successfully loaded and converted deck: {deck_name}")
                        return converted_deck
                    else:
                        logger.info(f"Successfully loaded deck: {deck_name}")
                        return deck_data
                        
                except Exception as e:
                    logger.error(f"Failed to load deck file {deck_file}: {e}")
                    continue
        
        logger.warning(f"Deck file {deck_name}.json not found in any expected location")
        return None
        
    except Exception as e:
        logger.error(f"Unexpected error while loading deck {deck_name}: {e}")
        return None

def get_builtin_decks():
    """내장 덱들을 반환합니다. 파일 시스템에 의존하지 않습니다."""
    return {
        "whale": {
            "deck_id": "Whale",
            "oshi_id": "hBP01-001",
            "deck": {
                "hBP01-012": 4,
                "hBP01-013": 4,
                "hBP01-009": 10,
                "hBP01-010": 1,
                "hBP01-014": 1,
                "hBP02-035": 2,
                "hBP02-038": 4,
                "hSD01-016": 4,
                "hSD01-017": 2,
                "hBP01-104": 4,
                "hBP02-084": 4,
                "hSD01-018": 2,
                "hBP02-079": 2,
                "hBP01-114": 3,
                "hBP01-116": 3
            },
            "cheer_deck": {
                "hY01-001": 20
            }
        },
        "starter_azki": {
    "deck_id": "starter_azki",
    "oshi_id": "hSD01-002",
    "deck": {
        "hSD01-003": 4,
        "hSD01-004": 3,
        "hSD01-005": 3,
        "hSD01-006": 2,
        "hSD01-007": 2,
        "hSD01-008": 4,
        "hSD01-009": 3,
        "hSD01-010": 3,
        "hSD01-011": 2,
        "hSD01-012": 2,
        "hSD01-013": 2,
        "hSD01-014": 2,
        "hSD01-015": 2,
        "hSD01-016": 3,
        "hSD01-017": 3,
        "hSD01-018": 3,
        "hSD01-019": 3,
        "hSD01-020": 2,
        "hSD01-021": 2
    },
    "cheer_deck": {
        "hY01-001": 10,
        "hY02-001": 10
    }
        },
        "starter_sora": {
            "deck_id": "starter_sora",
            "oshi_id": "hSD01-001",
            "deck": {
                "hSD01-003": 4,
                "hSD01-004": 3,
                "hSD01-005": 3,
                "hSD01-006": 2,
                "hSD01-007": 2,
                "hSD01-008": 4,
                "hSD01-009": 3,
                "hSD01-010": 3,
                "hSD01-011": 2,
                "hSD01-012": 2,
                "hSD01-013": 2,
                "hSD01-014": 2,
                "hSD01-015": 2,
                "hSD01-016": 3,
                "hSD01-017": 3,
                "hSD01-018": 3,
                "hSD01-019": 3,
                "hSD01-020": 2,
                "hSD01-021": 2
            },
            "cheer_deck": {
                "hY01-001": 10,
                "hY02-001": 10
            }
        }
    }

def convert_holodelta_to_simple_format(holodelta_deck):
    """HoloDelta 형식의 덱을 단순 형식으로 변환합니다"""
    simple_deck = {
        "deck_id": holodelta_deck.get("deckName", "unknown"),
        "oshi_id": "",
        "deck": {},
        "cheer_deck": {}
    }
    
    # Oshi 처리
    if "oshi" in holodelta_deck and len(holodelta_deck["oshi"]) >= 2:
        oshi_id = holodelta_deck["oshi"][0]
        oshi_alt = holodelta_deck["oshi"][1]
        if oshi_alt > 0:
            # 대체 아트가 있는 경우 처리 (간단히 원본 ID 사용)
            simple_deck["oshi_id"] = oshi_id
        else:
            simple_deck["oshi_id"] = oshi_id
    
    # 메인 덱 처리
    if "deck" in holodelta_deck:
        for card_entry in holodelta_deck["deck"]:
            if len(card_entry) >= 2:
                card_id = card_entry[0]
                card_count = card_entry[1]
                card_alt = card_entry[2] if len(card_entry) > 2 else 0
                
                # 대체 아트가 있는 경우 처리 (간단히 원본 ID 사용)
                if card_alt > 0:
                    # 실제로는 대체 아트 ID를 생성해야 하지만, 여기서는 원본 사용
                    final_card_id = card_id
                else:
                    final_card_id = card_id
                
                simple_deck["deck"][final_card_id] = card_count
    
    # 치어 덱 처리
    if "cheerDeck" in holodelta_deck:
        for cheer_entry in holodelta_deck["cheerDeck"]:
            if len(cheer_entry) >= 2:
                cheer_id = cheer_entry[0]
                cheer_count = cheer_entry[1]
                simple_deck["cheer_deck"][cheer_id] = cheer_count
    
    return simple_deck

def get_default_ai_deck():
    """기본 AI 덱을 반환합니다"""
    return get_builtin_decks()["starter_azki"]

# AI 덱을 동적으로 로드
DefaultAIDeck = load_ai_deck(AI_DECK_NAME)


def _get_ai_pool_paths():
    """ai_pool 폴더의 가능한 경로들을 반환합니다."""
    return [
        os.path.join(os.path.dirname(__file__), "..", "decks", "ai_pool"),
        os.path.join(os.getcwd(), "decks", "ai_pool"),
    ]

def load_ai_deck_pool():
    """내장 덱 + decks/ai_pool/ 폴더의 모든 덱을 합산하여 {이름: 덱데이터} dict로 반환합니다."""
    pool = {}

    for name, deck_data in get_builtin_decks().items():
        pool[name] = deck_data

    for pool_dir in _get_ai_pool_paths():
        if not os.path.isdir(pool_dir):
            continue
        for filename in os.listdir(pool_dir):
            if not filename.endswith(".json"):
                continue
            deck_key = filename[:-5]
            if deck_key in pool:
                continue
            filepath = os.path.join(pool_dir, filename)
            try:
                with open(filepath, "r", encoding="utf-8") as f:
                    deck_data = json.load(f)
                if "cheerDeck" in deck_data:
                    deck_data = convert_holodelta_to_simple_format(deck_data)
                pool[deck_key] = deck_data
                logger.info(f"AI pool: loaded deck '{deck_key}' from {filepath}")
            except Exception as e:
                logger.error(f"AI pool: failed to load {filepath}: {e}")
        break

    if not pool:
        logger.warning("AI pool is empty, falling back to DefaultAIDeck")
        pool["default"] = DefaultAIDeck

    return pool

def get_ai_deck_names():
    """풀 내 모든 덱의 {key, deck_id} 리스트를 반환합니다 (클라이언트 전송용)."""
    pool = load_ai_deck_pool()
    result = []
    for key, deck_data in pool.items():
        result.append({
            "deck_name": key,
            "deck_id": deck_data.get("deck_id", key),
        })
    return result

def get_random_ai_deck():
    """풀에서 무작위로 덱 하나를 반환합니다."""
    pool = load_ai_deck_pool()
    chosen_key = random.choice(list(pool.keys()))
    logger.info(f"Random AI deck selected: {chosen_key}")
    return pool[chosen_key]

def get_ai_deck_by_name(name):
    """이름으로 특정 덱을 반환합니다. 없으면 랜덤 폴백."""
    if name == "random":
        return get_random_ai_deck()
    pool = load_ai_deck_pool()
    if name in pool:
        logger.info(f"AI deck selected by name: {name}")
        return pool[name]
    logger.warning(f"AI deck '{name}' not found in pool, falling back to random")
    return get_random_ai_deck()


class AIPlayer:

    def __init__(self, player_id: str):
        self.player_id = player_id
        self.connected = True

        self.oshi_id = None
        self.deck = []
        self.cheer_deck = []

        self.event_handlers = {
            EventType.EventType_AddTurnEffect: self._handle_event_ignore,
            EventType.EventType_LifeDamageDealt: self._handle_event_ignore,
            EventType.EventType_SpecialActionActivation: self._handle_event_ignore,
            EventType.EventType_Bloom: self._handle_event_ignore,
            EventType.EventType_BoostStat: self._handle_event_ignore,
            EventType.EventType_CheerStep: self._handle_cheer_step,
            EventType.EventType_Choice_SendCollabBack: self._handle_choice,
            EventType.EventType_Collab: self._handle_event_ignore,
            EventType.EventType_DamageDealt: self._handle_event_ignore,
            EventType.EventType_Decision_Choice: self._handle_choice,
            EventType.EventType_Decision_ChooseCards: self._handle_choose_cards,
            EventType.EventType_Decision_ChooseHolomemForEffect: self._handle_choose_holomem_for_effect,
            EventType.EventType_Decision_MainStep: self._handle_main_step,
            EventType.EventType_Decision_OrderCards: self._handle_order_cards,
            EventType.EventType_Decision_PerformanceStep: self._handle_performance_step,
            EventType.EventType_Decision_SendCheer: self._handle_send_cheer,
            EventType.EventType_Decision_SwapHolomemToCenter: self._handle_swap_holomem_to_center,
            EventType.EventType_DownedHolomem: self._handle_event_ignore,
            EventType.EventType_DownedHolomem_Before: self._handle_event_ignore,
            EventType.EventType_Draw: self._handle_event_ignore,
            EventType.EventType_EndTurn: self._handle_event_ignore,
            EventType.EventType_ForceDieResult: self._handle_choice,
            EventType.EventType_GameError: self._handle_event_ignore,
            EventType.EventType_GameOver: self._handle_event_ignore,
            EventType.EventType_GameStartInfo: self._handle_event_ignore,
            EventType.EventType_GenerateHolopower: self._handle_event_ignore,
            EventType.EventType_InitialPlacementBegin: self._handle_initial_placement_begin,
            EventType.EventType_InitialPlacementPlaced: self._handle_event_ignore,
            EventType.EventType_InitialPlacementReveal: self._handle_event_ignore,
            EventType.EventType_ReturnCardsBegin: self._handle_return_cards_begin,
            EventType.EventType_BackstagePlacementBegin: self._handle_backstage_placement_begin,
            EventType.EventType_BackstagePlacementPlaced: self._handle_event_ignore,
            EventType.EventType_MainStepStart: self._handle_event_ignore,
            EventType.EventType_ModifyHP: self._handle_event_ignore,
            EventType.EventType_MoveCard: self._handle_event_ignore,
            EventType.EventType_MoveAttachedCard: self._handle_event_ignore,
            EventType.EventType_MulliganDecision: self._handle_mulligan_decision,
            EventType.EventType_MulliganReveal: self._handle_event_ignore,
            EventType.EventType_OshiSkillActivation: self._handle_event_ignore,
            EventType.EventType_PerformanceStepStart: self._handle_event_ignore,
            EventType.EventType_PerformArt: self._handle_event_ignore,
            EventType.EventType_PlaySupportCard: self._handle_event_ignore,
            EventType.EventType_ResetStepActivate: self._handle_event_ignore,
            EventType.EventType_ResetStepChooseNewCenter: self._handle_choose_new_center,
            EventType.EventType_ResetStepCollab: self._handle_event_ignore,
            EventType.EventType_RestoreHP: self._handle_event_ignore,
            EventType.EventType_RevealCards: self._handle_event_ignore,
            EventType.EventType_RollDie: self._handle_event_ignore,
            EventType.EventType_ShuffleDeck: self._handle_event_ignore,
            EventType.EventType_TurnStart: self._handle_event_ignore,
        }

    def set_deck(self, deck_info : dict):
        self.oshi_id = deck_info["oshi_id"]
        self.deck = deck_info["deck"]
        self.cheer_deck = deck_info["cheer_deck"]

    def get_player_game_info(self):
        return {
            "player_id": self.player_id,
            "username": "Weak AI",
            "oshi_id": self.oshi_id,
            "deck": self.deck,
            "cheer_deck": self.cheer_deck
        }

    def ai_process_events(self, events):
        # Process game events and issue actions.
        ai_performing_action = False
        ai_action_type = None
        ai_action_data = None

        for event in events:
            # Only look at events meant for me.
            if self.player_id == event["event_player_id"]:
                event_type = event["event_type"]
                if event_type in self.event_handlers:
                    ai_performing_action, ai_action_type, ai_action_data = self.event_handlers[event_type](event)
                else:
                    logger.error(f"AI: Unhandled event type: {event_type}")

        return ai_performing_action, {
            "action_type": ai_action_type,
            "action_data": ai_action_data
        }

    def _handle_event_ignore(self, _event):
        return False, None, None

    def _handle_cheer_step(self, event):
        if self.player_id != event["active_player"]:
            # Skip events that aren't meant for me to act.
            return False, None, None

        cheer_to_place = event["cheer_to_place"]
        target_options = event["options"]
        placements = {}
        for cheer_id in cheer_to_place:
            placements[cheer_id] = target_options[0]

        return True, event["desired_response"], {
            "placements": placements
        }

    def _handle_choice(self, event):
        if self.player_id != event["effect_player_id"]:
            # Skip events that aren't meant for me to act.
            return False, None, None

        min_choice = event["min_choice"]
        max_choice = event["max_choice"]

        return True, event["desired_response"], {
            "choice_index": min_choice
        }

    def _handle_choose_cards(self, event):
        if self.player_id != event["effect_player_id"]:
            # Skip events that aren't meant for me to act.
            return False, None, None

        all_card_seen = event.get("all_card_seen", [])
        cards_can_choose = event["cards_can_choose"]
        amount_min = event["amount_min"]
        amount_max = event["amount_max"]
        desired_card_count = min(amount_max, len(cards_can_choose))

        card_ids = []
        for i in range(desired_card_count):
            card_ids.append(cards_can_choose[i])

        return True, event["desired_response"], {
            "card_ids": card_ids
        }

    def _handle_choose_holomem_for_effect(self, event):
        if self.player_id != event["effect_player_id"]:
            # Skip events that aren't meant for me to act.
            return False, None, None

        cards_can_choose : list = event["cards_can_choose"]
        amount_min = event.get("amount_min", 1)
        amount_max = event.get("amount_max", 1)
        
        # 게임 엔진에서 제공하는 순서를 그대로 사용 (이미 center > collab > backstage 순서)
        chosen_cards = []
        # 요청된 수만큼 순서대로 선택
        for i in range(min(amount_max, len(cards_can_choose))):
            chosen_cards.append(cards_can_choose[i])

        return True, event["desired_response"], {
            "card_ids": chosen_cards
        }

    def _handle_main_step(self, event):
        if self.player_id != event["active_player"]:
            # Skip events that aren't meant for me to act.
            return False, None, None

        available_actions = event["available_actions"]

        # Split available actions by action type.
        all_actions = {}
        all_actions[GameAction.MainStepPlaceHolomem] = [action for action in available_actions if action["action_type"] == GameAction.MainStepPlaceHolomem]
        all_actions[GameAction.MainStepBloom] = [action for action in available_actions if action["action_type"] == GameAction.MainStepBloom]
        all_actions[GameAction.MainStepCollab] = [action for action in available_actions if action["action_type"] == GameAction.MainStepCollab]
        all_actions[GameAction.MainStepOshiSkill] = [action for action in available_actions if action["action_type"] == GameAction.MainStepOshiSkill]
        all_actions[GameAction.MainStepPlaySupport] = [action for action in available_actions if action["action_type"] == GameAction.MainStepPlaySupport]
        all_actions[GameAction.MainStepBatonPass] = [action for action in available_actions if action["action_type"] == GameAction.MainStepBatonPass]
        all_actions[GameAction.MainStepBeginPerformance] = [action for action in available_actions if action["action_type"] == GameAction.MainStepBeginPerformance]

        chosen_action = GameAction.MainStepEndTurn
        card_id = None
        target_id = None
        skill_id = None
        play_requirements = None
        if all_actions[GameAction.MainStepPlaceHolomem]:
            # Just try to place all mems
            chosen_action = GameAction.MainStepPlaceHolomem
            card_id = all_actions[GameAction.MainStepPlaceHolomem][0]["card_id"]
        elif all_actions[GameAction.MainStepBloom]:
            # Always bloom if we can.
            chosen_action = GameAction.MainStepBloom
            card_id = all_actions[GameAction.MainStepBloom][0]["card_id"]
            target_id = all_actions[GameAction.MainStepBloom][0]["target_id"]
        elif all_actions[GameAction.MainStepCollab]:
            # Always collab if we can.
            chosen_action = GameAction.MainStepCollab
            # Pick a random one though.
            collab_index = random.randint(0, len(all_actions[GameAction.MainStepCollab]) - 1)
            card_id = all_actions[GameAction.MainStepCollab][collab_index]["card_id"]
        elif all_actions[GameAction.MainStepOshiSkill]:
            # Always oshi skill if we can.
            chosen_action = GameAction.MainStepOshiSkill
            # Start with the 2nd skill since it's the once per game.
            skill_id = all_actions[GameAction.MainStepOshiSkill][-1]["skill_id"]
        elif all_actions[GameAction.MainStepPlaySupport]:
            # Always play all support cards.
            chosen_action = GameAction.MainStepPlaySupport
            play_support_action = all_actions[GameAction.MainStepPlaySupport][0]
            card_id = play_support_action["card_id"]
            if "play_requirements" in play_support_action and play_support_action["play_requirements"]:
                cheer_on_each_mem = play_support_action["cheer_on_each_mem"]
                all_cheer = []
                for holomem in cheer_on_each_mem:
                    all_cheer.extend(cheer_on_each_mem[holomem])
                for requirement_name in play_support_action["play_requirements"]:
                    requirement_detail = play_support_action["play_requirements"][requirement_name]
                    length = requirement_detail["length"]
                    content_type = requirement_detail["content_type"]
                    match requirement_name:
                        case "cheer_to_archive_from_play":
                            spent_cheer = []
                            for i in range(length):
                                spent_cheer.append(all_cheer[i])
                            play_requirements = {
                                requirement_name: spent_cheer
                            }
                        case _:
                            raise NotImplementedError("Unimplemented play requirement")

        # Skip baton pass for now.
        #elif all_actions[GameAction.MainStepBatonPass]:
        elif all_actions[GameAction.MainStepBeginPerformance]:
            # Always perform.
            chosen_action = GameAction.MainStepBeginPerformance
        else:
            # Just end turn.
            chosen_action = GameAction.MainStepEndTurn


        match chosen_action:
            case GameAction.MainStepPlaceHolomem:
                return True, GameAction.MainStepPlaceHolomem, {
                    "card_id": card_id,
                }
            case GameAction.MainStepBloom:
                return True, GameAction.MainStepBloom, {
                    "card_id": card_id,
                    "target_id": target_id,
                }
            case GameAction.MainStepCollab:
                return True, GameAction.MainStepCollab, {
                    "card_id": card_id,
                }
            case GameAction.MainStepOshiSkill:
                return True, GameAction.MainStepOshiSkill, {
                    "skill_id": skill_id,
                }
            case GameAction.MainStepPlaySupport:
                action_response = {
                    "card_id": card_id,
                }
                if play_requirements:
                    for req in play_requirements:
                        action_response[req] = play_requirements[req]
                return True, GameAction.MainStepPlaySupport, action_response
            case GameAction.MainStepBatonPass:
                return True, GameAction.MainStepBatonPass, {
                    "card_id": card_id,
                }
            case GameAction.MainStepBeginPerformance:
                return True, GameAction.MainStepBeginPerformance, {
                }
            case GameAction.MainStepEndTurn:
                return True, GameAction.MainStepEndTurn, {
                }
            case _:
                raise NotImplementedError("Unimplemented action")

    def _handle_move_cheer_between_holomems(self, event):
        if self.player_id != event["effect_player_id"]:
            # Skip events that aren't meant for me to act.
            return False, None, None

        amount_min = event["amount_min"]
        amount_max = event["amount_max"]
        available_cheer = event["available_cheer"]
        available_targets = event["available_targets"]
        cheer_on_each_mem = event["cheer_on_each_mem"]

        placements = {}
        for i in range(amount_min):
            cheer_to_send = available_cheer[i]
            for i in range(len(available_targets)):
                target = available_targets[i]
                if cheer_to_send not in cheer_on_each_mem[target]:
                    placements[cheer_to_send] = target
                    break

        return True, event["desired_response"], {
            "placements": placements
        }

    def _handle_order_cards(self, event):
        if self.player_id != event["effect_player_id"]:
            # Skip events that aren't meant for me to act.
            return False, None, None

        remaining_card_ids = event["card_ids"]

        return True, event["desired_response"], {
            "card_ids": remaining_card_ids
        }

    def _handle_performance_step(self, event):
        if self.player_id != event["active_player"]:
            # Skip events that aren't meant for me to act.
            return False, None, None

        available_actions = event["available_actions"]

        # Split available actions by action type.
        all_actions = {}
        all_actions[GameAction.PerformanceStepUseArt] = [action for action in available_actions if action["action_type"] == GameAction.PerformanceStepUseArt]

        chosen_action = GameAction.PerformanceStepEndTurn
        performer_id = None
        art_id = None
        target_id = None
        if all_actions[GameAction.PerformanceStepUseArt]:
            # Do the last one, so we use the most powerful moves.
            chosen_action = GameAction.PerformanceStepUseArt
            performer_id = all_actions[GameAction.PerformanceStepUseArt][-1]["performer_id"]
            art_id = all_actions[GameAction.PerformanceStepUseArt][-1]["art_id"]
            target_id = all_actions[GameAction.PerformanceStepUseArt][-1]["valid_targets"][0]
        else:
            # Just end turn.
            chosen_action = GameAction.PerformanceStepEndTurn

        match chosen_action:
            case GameAction.PerformanceStepUseArt:
                return True, GameAction.PerformanceStepUseArt, {
                    "performer_id": performer_id,
                    "art_id": art_id,
                    "target_id": target_id,
                }
            case GameAction.PerformanceStepEndTurn:
                return True, GameAction.PerformanceStepEndTurn, {
                }
            case _:
                raise NotImplementedError("Unimplemented performance action")

    def _handle_send_cheer(self, event):
        if self.player_id != event["effect_player_id"]:
            # Skip events that aren't meant for me to act.
            return False, None, None

        amount_min = event["amount_min"]
        amount_max = event["amount_max"]
        from_options = event["from_options"]
        to_options = event["to_options"]
        cheer_on_each_mem = event["cheer_on_each_mem"]

        placements = {}
        for i in range(amount_min):
            cheer_to_send = from_options[i]
            for i in range(len(to_options)):
                target = to_options[i]
                if target not in cheer_on_each_mem or \
                cheer_to_send not in cheer_on_each_mem[target]:
                    placements[cheer_to_send] = target
                    break

        return True, event["desired_response"], {
            "placements": placements
        }

    def _handle_swap_holomem_to_center(self, event):
        if self.player_id != event["effect_player_id"]:
            # Skip events that aren't meant for me to act.
            return False, None, None

        cards_can_choose = event["cards_can_choose"]
        chosen = [cards_can_choose[0]]

        return True, event["desired_response"], {
            "card_ids": chosen
        }

    def _handle_initial_placement_begin(self, event):
        if self.player_id != event["active_player"]:
            return False, None, None

        debut_options = event["debut_options"]
        center = debut_options[0]

        return True, event["desired_response"], {
            "center_holomem_card_id": center,
        }

    def _handle_return_cards_begin(self, event):
        if self.player_id != event["active_player"]:
            return False, None, None

        return_count = event["return_count"]
        hand_card_ids = event["hand_card_ids"]

        chosen = random.sample(hand_card_ids, min(return_count, len(hand_card_ids)))

        return True, event["desired_response"], {
            "card_ids": chosen,
        }

    def _handle_backstage_placement_begin(self, event):
        if self.player_id != event["active_player"]:
            return False, None, None

        debut_options = event["debut_options"]
        spot_options = event["spot_options"]

        backstage = (debut_options + spot_options)[:5]

        return True, event["desired_response"], {
            "backstage_holomem_card_ids": backstage,
        }

    def _handle_mulligan_decision(self, event):
        if self.player_id != event["active_player"]:
            # Skip events that aren't meant for me to act.
            return False, None, None

        return True, event["desired_response"], {
            "do_mulligan": False,
        }

    def _handle_choose_new_center(self, event):
        if self.player_id != event["active_player"]:
            # Skip events that aren't meant for me to act.
            return False, None, None

        center_options = event["center_options"]
        chosen_center = center_options[0]

        return True, event["desired_response"], {
            "new_center_card_id": chosen_center,
        }