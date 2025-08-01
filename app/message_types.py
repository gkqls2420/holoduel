from dataclasses import dataclass, asdict
from typing import Any, Dict, List
import json

@dataclass
class Message:
    message_type: str

    def as_dict(self) -> str:
        return asdict(self)

# Server Outbound Messages
@dataclass
class ServerInfoMessage(Message):
    queue_info: Dict[str, Any]
    room_info: List[Dict]
    players_info: List[Dict]
    your_id : str
    your_username : str

@dataclass
class ErrorMessage(Message):
    error_id: str
    error_message: str

# Server Inbound Messages
@dataclass
class JoinServerMessage(Message):
    pass

@dataclass
class ObserveRoomMessage(Message):
    room_id: str

@dataclass
class ObserverGetEventsMessage(Message):
    next_event_index : int

@dataclass
class JoinMatchmakingQueueMessage(Message):
    custom_game: bool
    queue_name: str
    game_type: str
    oshi_id: str
    deck: Dict[str, int]
    cheer_deck: Dict[str, int]

@dataclass
class LeaveMatchmakingQueueMessage(Message):
    pass

@dataclass
class LeaveGameMessage(Message):
    pass

@dataclass
class GameActionMessage(Message):
    action_type: str
    action_data: Dict[str, Any]

@dataclass
class EmoteMessage(Message):
    emote_id: int

def parse_message(json_data: str) -> Message:
    data = json.loads(json_data)
    message_type = data.get("message_type")

    match message_type:
        case "join_server":
            return JoinServerMessage(**data)
        case "join_matchmaking_queue":
            return JoinMatchmakingQueueMessage(**data)
        case "leave_matchmaking_queue":
            return LeaveMatchmakingQueueMessage(**data)
        case "leave_game":
            return LeaveGameMessage(**data)
        case "game_action":
            return GameActionMessage(**data)
        case "observe_room":
            return ObserveRoomMessage(**data)
        case "observer_get_events":
            return ObserverGetEventsMessage(**data)
        case "emote":
            return EmoteMessage(**data)
        case _:
            raise ValueError(f"Unknown message type: {json_data}")
