extends Node

signal disconnected_from_server
signal connected_to_server
signal server_info(queue_info)
signal join_operation_failed()
signal game_event(event_type, event_data)

enum NetworkState {
	NetworkState_NotConnected,
	NetworkState_Connecting,
	NetworkState_Connected,
}

var _socket : WebSocketPeer = null
var network_state : NetworkState = NetworkState.NetworkState_NotConnected
var cached_server_info = {}

var connection_start_time = 0
var first_connection = false

const ServerMessageType_GameEvent = "game_event"
const ServerMessageType_Error = "error"
const ServerMessageType_ServerInfo = "server_info"

const ServerError_JoinInvalidDeck = "joinmatch_invaliddeck"
const ServerError_InvalidRoom = "invalid_room"

const ClientMessage_GameAction = "game_action"
const ClientMessage_LeaveGame = "leave_game"
const ClientMessage_LeaveMatchmakingQueue = "leave_matchmaking_queue"
const ClientMessage_JoinMatchmakingQueue = "join_matchmaking_queue"
const ClientMessage_JoinServer = "join_server"
const ClientMessage_ObserveRoom = "observe_room"
const ClientMessage_ObserverGetEvents = "observer_get_events"

func is_server_connected() -> bool:
	return _socket != null

func connect_to_server():
	if _socket != null: return
	print("DEBUG: 서버 연결을 시도합니다...")
	first_connection = true
	_attempt_connection()

func disconnect_from_server():
	if _socket != null:
		print("DEBUG: 서버 연결을 해제합니다...")
		_socket.close()
		_socket = null
		network_state = NetworkState.NetworkState_NotConnected
		disconnected_from_server.emit()

func _attempt_connection():
	# 현재 서버에 연결 시도
	_socket = WebSocketPeer.new()
	var server_url = GlobalSettings.get_server_url()
	var server_name = GlobalSettings.get_current_server_name()
	var platform = OS.get_name()
	
	print("DEBUG: 서버 연결 시도 중... (", server_name, ")")
	print("DEBUG: 서버 URL: ", server_url)
	print("DEBUG: 플랫폼: ", platform)
	print("DEBUG: 빌드 타입: ", "Release" if not OS.is_debug_build() else "Debug")
	print("DEBUG: UseAzureServerAlways: ", GlobalSettings.UseAzureServerAlways)
	
	# HTML5/Android 환경에서 추가 디버그 정보
	if GlobalSettings.is_html5_export():
		print("DEBUG: HTML5 환경 감지됨 - Railway 서버만 사용")
	if GlobalSettings.is_android_export():
		print("DEBUG: Android 환경 감지됨 - Railway 서버만 사용")
		print("DEBUG: Android API Level: ", OS.get_environment("ANDROID_API_LEVEL"))
		print("DEBUG: Android Version: ", OS.get_environment("ANDROID_VERSION"))
	
	_socket.connect_to_url(server_url)
	Logger.log(Logger.LogArea_Network, "Connecting to server: %s" % server_url)
	network_state = NetworkState.NetworkState_Connecting
	connection_start_time = Time.get_unix_time_from_system()

func _handle_connection_failure():
	"""연결 실패 시 다음 서버로 폴백"""
	var current_server = GlobalSettings.get_current_server_name()
	print("DEBUG: ", current_server, " 서버 연결 실패")
	
	# 현재 소켓 정리
	_socket = null
	
	# 다음 서버가 있는지 확인
	if GlobalSettings.has_more_servers():
		var next_server = GlobalSettings.get_next_server_url()
		var next_server_name = GlobalSettings.get_current_server_name()
		print("DEBUG: 다음 서버로 폴백 시도: ", next_server_name)
		print("DEBUG: 다음 서버 URL: ", next_server)
		
		# 잠시 대기 후 다음 서버 시도
		await get_tree().create_timer(1.0).timeout
		_attempt_connection()
	else:
		# 모든 서버 시도 실패
		print("DEBUG: 모든 서버 연결 시도 실패")
		disconnected_from_server.emit()
		network_state = NetworkState.NetworkState_NotConnected
		# 서버 인덱스 리셋
		GlobalSettings.reset_server_index()

func _process(_delta):
	_handle_sockets()

func _handle_sockets():
	if _socket:
		_socket.poll()
		var state = _socket.get_ready_state()
		match state:
			WebSocketPeer.STATE_OPEN:
				if network_state == NetworkState.NetworkState_Connecting:
					var end_time = Time.get_unix_time_from_system()
					var elapsed_time = end_time - connection_start_time
					var server_name = GlobalSettings.get_current_server_name()
					print("DEBUG: ", server_name, " 서버에 성공적으로 연결되었습니다! (소요시간: ", elapsed_time, "초)")
					Logger.log(Logger.LogArea_Network, "Connected to server: %s" % elapsed_time)
					# 연결 성공 시 서버 인덱스 리셋 (다음 연결 시 첫 번째 서버부터 시도)
					GlobalSettings.reset_server_index()
					# Send the join_server message.
					_send_join_server()
				network_state = NetworkState.NetworkState_Connected
				while _socket.get_available_packet_count():
					var packet = _socket.get_packet()
					if _socket.was_string_packet():
						var strpacket = packet.get_string_from_utf8()
						_handle_server_response(strpacket)
			WebSocketPeer.STATE_CLOSING:
				print("DEBUG: WebSocket 연결이 종료 중입니다...")
				pass
			WebSocketPeer.STATE_CLOSED:
				print("DEBUG: WebSocket 연결이 종료되었습니다!")
				var code = _socket.get_close_code()
				var reason = _socket.get_close_reason()
				Logger.log(Logger.LogArea_Network, "WebSocket closed with code: %d, reason %s. Clean: %s" % [code, reason, code != -1])
				
				# 연결 실패 시 다음 서버로 폴백 시도
				if network_state == NetworkState.NetworkState_Connecting:
					_handle_connection_failure()
				else:
					# 이미 연결된 상태에서 끊어진 경우
					disconnected_from_server.emit()
					network_state = NetworkState.NetworkState_NotConnected
					_socket = null

func _handle_server_response(data):
	var parser = JSON.new()
	var result = parser.parse(data)
	if result != OK:
		Logger.log(Logger.LogArea_Network, "Error parsing JSON from server: %s" % data)
		return

	var data_obj = parser.get_data()
	var message_type = data_obj["message_type"]
	match message_type:
		ServerMessageType_ServerInfo:
			_handle_server_info(data_obj)
		ServerMessageType_Error:
			_handle_server_error(data_obj)
		ServerMessageType_GameEvent:
			_handle_game_event(data_obj)
		_:
			Logger.log(Logger.LogArea_Network, "Unhandled message type: %s" % message_type)

func _handle_server_info(message):
	cached_server_info = message
	if first_connection:
		Logger.log(Logger.LogArea_Network, "Connected to server!")
		connected_to_server.emit()
		first_connection = false
	server_info.emit()

func get_players_info():
	return cached_server_info["players_info"]

func get_queue_info():
	return cached_server_info["queue_info"]

func get_room_info():
	return cached_server_info["room_info"]

func get_my_player_id():
	return cached_server_info["your_id"]

func get_my_player_name():
	return cached_server_info["your_username"]

func _handle_server_error(message):
	Logger.log(Logger.LogArea_Network, "ERROR: %s - %s" % [message["error_id"], message["error_message"]])

	match message["error_id"]:
		ServerError_JoinInvalidDeck:
			join_operation_failed.emit(ServerError_JoinInvalidDeck)
		ServerError_InvalidRoom:
			join_operation_failed.emit(ServerError_InvalidRoom)
		_:
			# No special error handling.
			pass

func _handle_game_event(message):
	_handle_game_event_internal(message["event_data"])

func _handle_game_event_internal(event):
	var event_type = event["event_type"]
	#Logger.log(Logger.LogArea_Network, "Game event (%s): %s" % [event_type, message["event_data"]])
	game_event.emit(event_type, event)

func _send_join_server():
	var message = {
		"message_type": ClientMessage_JoinServer,
	}
	_send_message(message)

func _send_message(message):
	var json = JSON.stringify(message)
	if _socket:
		_socket.send_text(json)

### Commands ###

func join_match_queue(queue_name, oshi_id, deck, cheer_deck):
	print("DEBUG: NetworkManager.join_match_queue 호출됨")
	print("DEBUG: queue_name:", queue_name)
	print("DEBUG: oshi_id:", oshi_id)
	print("DEBUG: deck:", deck)
	print("DEBUG: cheer_deck:", cheer_deck)
	
	var game_type = "versus"
	var custom_game = true
	for queue in get_queue_info():
		if queue["queue_name"] == queue_name:
			game_type = queue["game_type"]
			custom_game = queue["custom_game"]
	var message = {
		"message_type": ClientMessage_JoinMatchmakingQueue,
		"custom_game": custom_game,
		"queue_name": queue_name,
		"game_type": game_type,
		"oshi_id": oshi_id,
		"deck": deck,
		"cheer_deck": cheer_deck,
	}
	print("DEBUG: 서버로 전송할 메시지:", message)
	_send_message(message)


func leave_match_queue():
	var message = {
		"message_type": ClientMessage_LeaveMatchmakingQueue,
	}
	_send_message(message)

func leave_game():
	var message = {
		"message_type": ClientMessage_LeaveGame,
	}
	_send_message(message)

func send_game_message(action_type:String, action_data :Dictionary):
	var message = {
		"message_type": ClientMessage_GameAction,
		"action_type": action_type,
		"action_data": action_data,
	}
	Logger.log_net("Sending game message - %s: %s" % [action_type, message])
	_send_message(message)

func observe_room(room_index):
	var room_id = cached_server_info["room_info"][room_index]["room_id"]
	var message = {
		"message_type": ClientMessage_ObserveRoom,
		"room_id": room_id,
	}
	_send_message(message)

func observer_get_events(event_index):
	var message = {
		"message_type": ClientMessage_ObserverGetEvents,
		"next_event_index": event_index,
	}
	_send_message(message)
