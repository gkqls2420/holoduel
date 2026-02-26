import traceback
import json
import os
import time
from typing import List
from app.playermanager import Player
from app.gameengine import GameEngine, GameAction, EventType
from app.card_database import CardDatabase
from app.aiplayer import AIPlayer, DefaultAIDeck, get_ai_deck_by_name
from app.dbaccess import upload_match_to_blob_storage
import logging
logger = logging.getLogger(__name__)

# 감정표현 관련 상수
EMOTE_COOLDOWN_MS = 2000  # 2초 쿨다운
VALID_EMOTE_IDS = [0, 1, 2, 3, 4]  # 허용된 감정표현 ID

class GameRoom:
    def __init__(self, room_id : str, room_name : str, players : List[Player], game_type : str, queue_name : str):
        self.room_id = room_id
        self.room_name = room_name
        self.players = players
        self.observers : List[Player] = []
        self.ai_player = None
        self.game_type = game_type
        self.queue_name = queue_name
        self.cleanup_room = False
        # 감정표현 쿨다운 추적
        self.player_emote_cooldowns = {}
        for player in self.players:
            player.current_game_room = self

    def is_ai_game(self):
        return self.game_type == "ai"

    def get_room_name(self):
        return self.room_name

    def get_room_info(self):
        return {
            "room_id": self.room_id,
            "room_name": self.room_name,
            "queue_name": self.queue_name,
            "game_type": self.game_type,
            "players": [player.get_public_player_info() for player in self.players],
        }

    async def start(self, card_db: CardDatabase):
        logger.info(f"GAME: Starting game ({self.room_id}) Players ({[player.get_username() for player in self.players]}) Ids ({[player.player_id for player in self.players]})")
        player_info = [player.get_player_game_info() for player in self.players]
        if self.is_ai_game():
            logger.info(f"AI GAME: Creating AI player for game {self.room_id}")
            self.ai_player = AIPlayer(player_id="aiplayer" + self.players[0].player_id)
            ai_deck_name = getattr(self.players[0], "ai_deck_name", "random")
            ai_deck = get_ai_deck_by_name(ai_deck_name)
            self.ai_player.set_deck(ai_deck)
            player_info.append(self.ai_player.get_player_game_info())
            logger.info(f"AI GAME: AI player created with ID {self.ai_player.player_id}, deck: {ai_deck.get('deck_id', 'unknown')}")

        self.engine = GameEngine(
            card_db=card_db,
            player_infos=player_info,
            game_type=self.game_type
        )

        self.engine.begin_game()
        events = self.engine.grab_events()
        await self.send_events(events)
        observer_events = self.engine.grab_observer_events()
        await self.send_observer_events(observer_events)

        if self.is_ai_game():
            logger.info(f"AI GAME: Processing AI actions for game {self.room_id}")
            # In case the AI has to mulligan first!
            ai_performing_action, ai_action = self.ai_player.ai_process_events(events)
            logger.info(f"AI GAME: AI action result - performing: {ai_performing_action}, action: {ai_action}")
            #logger.info("AI Action: %s %s" % (ai_performing_action, ai_action))
            if ai_performing_action:
                player_id = self.ai_player.player_id
                action_type = ai_action["action_type"]
                action_data = ai_action["action_data"]

                await self.handle_game_message(player_id, action_type, action_data)

    async def send_events(self, events):
        for event in events:
            for player in self.players:
                if player.connected and player.player_id == event["event_player_id"]:
                    await player.send_game_event(event)

    async def send_observer_events(self, events):
        for event in events:
            for player in self.observers:
                if player.connected:
                    await player.send_game_event(event)

    async def send_emote_events(self, events):
        """감정표현 이벤트를 모든 플레이어에게 전송"""
        for event in events:
            for player in self.players:
                if player.connected:
                    await player.send_game_event(event)

    async def handle_game_message(self, player_id: str, action_type:str, action_data: dict):
        for observer in self.observers:
            if player_id == observer.player_id:
                # Assume any message from an observer is them leaving.
                observer.current_game_room = None
                self.observers.remove(observer)
                return

        if self.engine.is_game_over():
            logger.info(f"Room {self.room_id} already game over, ignoring message player {player_id} action {action_type} data {action_data}")
            return

        # If the game is receiving messages, everyone playing/watching should not idle out.
        for player in self.observers + self.players:
            player.last_seen = time.time()

        done_processing = False
        while not done_processing and not self.engine.is_game_over():
            self.engine.handle_game_message(player_id, action_type, action_data)
            events = self.engine.grab_events()
            await self.send_events(events)
            observer_events = self.engine.grab_observer_events()
            await self.send_observer_events(observer_events)
            if self.is_ai_game():
                ai_performing_action, ai_action = self.ai_player.ai_process_events(events)
                #logger.info("AI Action: %s %s" % (ai_performing_action, ai_action))
                if ai_performing_action:
                    player_id = self.ai_player.player_id
                    action_type = ai_action["action_type"]
                    action_data = ai_action["action_data"]
                else:
                    done_processing = True
            else:
                done_processing = True

        if self.engine.is_game_over():
            logger.info("ROOM: %s Game over!" % self.room_id)
            if not self.is_ai_game() and not os.getenv("DONT_UPLOAD_MATCHES"):
                match_data = self.engine.get_match_log()
                if match_data["turn_number"] >= 0:
                    match_data["queue_name"] = self.queue_name
                    upload_match_to_blob_storage(match_data)
            self.cleanup_room = True

    async def handle_emote_message(self, player_id: str, emote_id: int):
        """감정표현 메시지 처리"""
        current_time = time.time() * 1000  # 밀리초 단위
        
        # 유효성 검증
        if emote_id not in VALID_EMOTE_IDS:
            logger.warning(f"Invalid emote_id {emote_id} from player {player_id}")
            return
        
        # 쿨다운 검증
        if player_id in self.player_emote_cooldowns:
            last_emote_time = self.player_emote_cooldowns[player_id]
            if current_time - last_emote_time < EMOTE_COOLDOWN_MS:
                logger.info(f"Emote cooldown active for player {player_id}")
                return
        
        # 쿨다운 업데이트
        self.player_emote_cooldowns[player_id] = current_time
        
        # 게임 엔진을 통해 감정표현 이벤트 생성
        self.engine.handle_emote(player_id, emote_id)
        
        # 게임 엔진에서 생성된 이벤트들을 가져와서 브로드캐스트
        events = self.engine.grab_events()
        await self.send_emote_events(events)  # 감정표현 전용 전송 메서드 사용
        observer_events = self.engine.grab_observer_events()
        await self.send_observer_events(observer_events)
        
        logger.info(f"Emote sent: player {player_id} sent emote {emote_id}")

    def is_ready_for_cleanup(self):
        return self.cleanup_room

    async def join_as_observer(self, player: Player):
        self.observers.append(player)
        player.current_game_room = self

        await self.observer_request_next_events(player, 0)

    async def observer_request_next_events(self, player: Player, starting_event_index):
        events = self.engine.get_observer_catchup_events()

        # Only send the next 50 events.
        ending_event_index = starting_event_index + 50
        for event in events[starting_event_index:ending_event_index]:
            await player.send_game_event(event)

        # If this is the end, send the catch up event.
        if ending_event_index >= len(events):
            await player.send_game_event({"event_type": EventType.EventType_ObserverCaughtUp})


    async def handle_player_quit(self, player: Player):
        try:
            logger.info(f"Player quit message: {player.get_username()} - {player.player_id} from Room {self.room_id}")
            await self.handle_game_message(player.player_id, GameAction.Resign, {})
        except Exception as e:
            error_details = traceback.format_exc()
            logger.error(f"Error processing handle_player_quitplayer {player.get_username()} - {player.player_id} from Room {self.room_id}: {e} Callstack: {error_details}")

    async def handle_player_disconnect(self, player : Player):
        try:
            logger.info(f"Player disconnect message: {player.get_username()} - {player.player_id} from Room {self.room_id}")
            await self.handle_game_message(player.player_id, GameAction.Resign, {})
        except Exception as e:
            error_details = traceback.format_exc()
            logger.error(f"Error processing handle_player_quitplayer {player.get_username()} - {player.player_id} from Room {self.room_id}: {e} Callstack: {error_details}")

        # TODO: Reconnect logic.
        # all_players_disconnected = all([not player.connected for player in self.players])
        # if all_players_disconnected:
        #     self.cleanup_room = True