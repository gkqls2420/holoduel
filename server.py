import traceback
import os
import uuid
import time
from typing import List
from contextlib import asynccontextmanager
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from app.matchmaking import Matchmaking
import app.message_types as message_types
from app.playermanager import PlayerManager, Player
from app.gameengine import GamePhase
from app.gameroom import GameRoom
from app.card_database import CardDatabase
from app.dbaccess import extract_game_package
from app.aiplayer import get_ai_deck_names
import logging
from dotenv import load_dotenv

# Set the player timeout to 15 minutes.
PLAYER_TIMEOUT_THRESHOLD = 15 * 60
IDLE_TASK_TIMER = 60

# Load the .env file
load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
logger.info("Server started")

skip_hosting_game = os.getenv("SKIP_HOSTING_GAME", "false").lower() == "true"

# FastAPI application with lifespan context
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Actions to perform during startup
    if not skip_hosting_game:
        unpacked_dir = os.path.join("data", "game_package", "unpacked")
        success = await extract_game_package(unpacked_dir)
        if success:
            logger.info(f"Game package ready at {unpacked_dir}, serving static files.")
            app.mount("/game", StaticFiles(directory=unpacked_dir), name="game")
        else:
            logger.warning("Game package extraction failed. Game hosting disabled.")
            @app.get("/game")
            async def game_not_available():
                return {"message": "Game package not available. Place game.zip in data/game_package/"}

    yield  # Application runs here

    # Actions to perform during shutdown (if needed)
    # Clean up or additional teardown actions can be added here if necessary.

app = FastAPI(lifespan=lifespan)

# CORS 설정 추가 (HTML5 export용)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 모든 origin 허용 (개발용)
    allow_credentials=True,
    allow_methods=["*"],  # 모든 HTTP 메서드 허용
    allow_headers=["*"],  # 모든 헤더 허용
    expose_headers=["*"],  # 모든 헤더 노출
)

# Health check endpoint for Railway
@app.get("/health")
async def health_check():
    return {"status": "healthy", "service": "holoduel-server"}

@app.get("/")
async def root():
    return RedirectResponse(url="/game/game.html")

# HTML5 WebSocket 연결을 위한 추가 엔드포인트
@app.get("/ws")
async def websocket_info():
    """WebSocket 연결 정보를 제공하는 엔드포인트"""
    return {
        "websocket_url": "wss://holoduel-production.up.railway.app/ws",
        "protocol": "websocket",
        "cors_enabled": True
    }

# Store connected clients
class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        # accept는 이미 websocket_endpoint에서 호출됨
        if websocket not in self.active_connections:
            self.active_connections.append(websocket)

    async def disconnect(self, websocket: WebSocket, send_disconnection = False):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
            if send_disconnection:
                try:
                    await websocket.close()
                except:
                    pass

    async def broadcast(self, message : message_types.Message):
        dict_message = message.as_dict()
        for connection in self.active_connections:
            try:
                await connection.send_json(dict_message)
            except:
                pass

manager = ConnectionManager()

player_manager : PlayerManager = PlayerManager()
game_rooms : List[GameRoom] = []
matchmaking : Matchmaking = Matchmaking()
card_db : CardDatabase = CardDatabase()
last_idle_check = time.time()

async def broadcast_server_info():
    await player_manager.broadcast_server_info(matchmaking.get_queue_info(), game_rooms)

async def send_error_message(websocket: WebSocket, error_id, error_str : str):
    message = message_types.ErrorMessage(
        message_type="error",
        error_id = error_id,
        error_message=error_str,
    )
    await websocket.send_json(message.as_dict())


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    # HTML5 CORS를 위한 추가 헤더 설정
    try:
        # WebSocket 연결 수락 (CORS 헤더 포함)
        await websocket.accept()
        
        player_id = str(uuid.uuid4())
        player = player_manager.get_player(player_id)
        if player:
            player.websocket = websocket
        else:
            player = player_manager.add_player(player_id, websocket)

        # ConnectionManager에 추가 (이미 accept됨)
        manager.active_connections.append(websocket)
        
    except Exception as e:
        logger.error(f"WebSocket connection error: {e}")
        return
    try:
        while True:
            data = await websocket.receive_text()
            try:
                message = message_types.parse_message(data)
            except Exception as e:
                logger.error("Error in message parsing: {e}\nMessage: {data}")
                await send_error_message(websocket, "invalid_message", f"ERROR: Invalid JSON: {data}")
                continue

            player.last_seen = time.time()

            if isinstance(message, message_types.JoinServerMessage):
                await broadcast_server_info()

            elif isinstance(message, message_types.ObserveRoomMessage):
                room_id = message.room_id
                for room in game_rooms:
                    if room.room_id == room_id:
                        player.current_game_room = room
                        await room.join_as_observer(player)
                        await broadcast_server_info()
                        break
                else:
                    await send_error_message(websocket, "invalid_room", f"ERROR: Match not found.")
            elif isinstance(message, message_types.ObserverGetEventsMessage):
                if not player.current_game_room:
                    await send_error_message(websocket, "not_in_room", f"ERROR: Not in a game room.")
                    break
                await player.current_game_room.observer_request_next_events(player, message.next_event_index)
            elif isinstance(message, message_types.JoinMatchmakingQueueMessage):
                # Ensure player is in a joinable state.
                if not can_player_join_queue(player):
                    await send_error_message(websocket, "joinmatch_invalid_alreadyinmatch", "Already in a match.")
                elif not matchmaking.is_game_type_valid(message.game_type):
                    await send_error_message(websocket, "joinmatch_invalid_gametype", "Invalid game type.")
                else:
                    queue_name = message.queue_name.strip()
                    if not matchmaking.is_valid_queue_name(queue_name):
                        await send_error_message(websocket, "joinmatch_invalid_queuename", "Invalid queue name.")
                    else:
                        is_valid = card_db.validate_deck(
                            oshi_id=message.oshi_id,
                            deck=message.deck,
                            cheer_deck=message.cheer_deck
                        )

                        if is_valid:
                            player.save_deck_info(
                                oshi_id=message.oshi_id,
                                deck=message.deck,
                                cheer_deck=message.cheer_deck
                            )
                            player.ai_deck_name = getattr(message, "ai_deck_name", "random")
                            player.ai_custom_deck = None
                            ai_oshi_id = getattr(message, "ai_oshi_id", "")
                            ai_deck_data = getattr(message, "ai_deck", None)
                            ai_cheer_data = getattr(message, "ai_cheer_deck", None)
                            if ai_oshi_id and ai_deck_data and ai_cheer_data:
                                if card_db.validate_deck(ai_oshi_id, ai_deck_data, ai_cheer_data):
                                    player.ai_custom_deck = {
                                        "deck_id": "custom",
                                        "oshi_id": ai_oshi_id,
                                        "deck": ai_deck_data,
                                        "cheer_deck": ai_cheer_data
                                    }
                                    logger.info(f"Player {player.get_username()} using custom AI deck (oshi: {ai_oshi_id})")
                                else:
                                    logger.warning(f"Player {player.get_username()} sent invalid custom AI deck, falling back to server deck")
                            match = matchmaking.add_player_to_queue(
                                player=player,
                                queue_name=message.queue_name,
                                custom_game=message.custom_game,
                                game_type=message.game_type,
                            )
                            if match:
                                game_rooms.append(match)
                                await match.start(card_db)

                            await broadcast_server_info()
                        else:
                            await send_error_message(websocket, "joinmatch_invaliddeck", "Invalid deck list.")

            elif isinstance(message, message_types.LeaveMatchmakingQueueMessage):
                matchmaking.remove_player_from_queue(player)
                await broadcast_server_info()

            elif isinstance(message, message_types.LeaveGameMessage):
                player_room : GameRoom = player.current_game_room
                if player_room is not None:
                    await player_room.handle_player_quit(player)
                    check_cleanup_room(player_room)
                    await broadcast_server_info()
                else:
                    await send_error_message(websocket, "not_in_room", f"ERROR: Not in a game room to leave.")

            elif isinstance(message, message_types.GameActionMessage):
                #logger.info(f"GAMEACTION: {message.action_type}")
                player_room : GameRoom = player.current_game_room
                if player_room and not player_room.is_ready_for_cleanup():
                    await player_room.handle_game_message(player.player_id, message.action_type, message.action_data)
                    check_cleanup_room(player_room)
                else:
                    await send_error_message(websocket, "not_in_room", f"ERROR: Not in a game room to send a game message.")
            
            elif isinstance(message, message_types.EmoteMessage):
                logger.info(f"Received emote message from player {player.get_username()} - {player.player_id}: emote_id = {message.emote_id}")
                player_room : GameRoom = player.current_game_room
                if player_room and not player_room.is_ready_for_cleanup():
                    await player_room.handle_emote_message(player.player_id, message.emote_id)
                else:
                    logger.warning(f"Player {player.get_username()} - {player.player_id} tried to send emote but not in a game room")
                    await send_error_message(websocket, "not_in_room", f"ERROR: Not in a game room to send emote.")

            elif isinstance(message, message_types.RequestAIDeckListMessage):
                deck_names = get_ai_deck_names()
                response = {
                    "message_type": "ai_deck_list",
                    "deck_list": deck_names,
                }
                await websocket.send_json(response)

            else:
                await send_error_message(websocket, "invalid_game_message", f"ERROR: Invalid message: {data}")

            await check_idle_users_task()

    except WebSocketDisconnect:
        logger.info(f"Client disconnected: {player.get_username()} - {player.player_id}")
        player.connected = False
        matchmaking.remove_player_from_queue(player)
        for room in game_rooms:
            if player in room.players or player in room.observers:
                await room.handle_player_disconnect(player)
                check_cleanup_room(room)
                break

        player_manager.remove_player(player_id)
        await manager.disconnect(websocket)
        await broadcast_server_info()
    except Exception as e:
        error_details = traceback.format_exc()
        logger.error(f"Error websocket loop from player {player.get_username()} - {player.player_id}: {e} Callstack: {error_details}")

def cleanup_room(room: GameRoom):
    logger.info("Cleanup game room ID: %s" % room.room_id)
    game_rooms.remove(room)
    for player in room.players:
        player.current_game_room = None
    for observer in room.observers:
        observer.current_game_room = None

def check_cleanup_room(room: GameRoom):
    if room.is_ready_for_cleanup():
        cleanup_room(room)
    else:
        state = "NO_ENGINE"
        if room.engine:
            state = room.engine.phase
        if state == GamePhase.GameOver:
            last_event = room.engine.all_events[-1]
            last_message = room.engine.all_game_messages[-1]
            logger.error(f"Room {room.room_id} open after game over.  Event: {last_event}  Message: {last_message}  PlayerCount: {len(room.players)}\n")
            cleanup_room(room)

def can_player_join_queue(player: Player):
    # If the player is in a queue or in a game room, then they can't join another queue.
    if player.current_game_room or matchmaking.get_player_queue(player):
        return False
    return True

async def check_idle_users_task():
    global last_idle_check
    if last_idle_check + IDLE_TASK_TIMER > time.time():
        return
    last_idle_check = time.time()

    # Check for idle players.
    removed_players = False
    player_keys = list(player_manager.active_players.keys())
    for player_id in player_keys:
        player = player_manager.get_player(player_id)
        if player:
            if time.time() - player.last_seen > PLAYER_TIMEOUT_THRESHOLD:
                logger.info(f"Player timed out: {player.get_username()} - {player.player_id}")
                matchmaking.remove_player_from_queue(player)
                for room in game_rooms:
                    if player in room.players or player in room.observers:
                        await room.handle_player_quit(player)
                        check_cleanup_room(room)
                        break
                player.connected = False
                player_manager.remove_player(player_id)
                await manager.disconnect(player.websocket, True)
                removed_players = True
        else:
            # Don't know exactly how this could happen but it did?
            # Probably during an await something else removed the player.
            player_manager.remove_player(player_id)
            removed_players = True
    if removed_players:
        await broadcast_server_info()


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

