extends Node

# HTML5 환경에서 서버 연결 테스트 스크립트
# 이 스크립트를 HTML5 export에서 실행하여 연결을 테스트할 수 있습니다.

func _ready():
	print("=== HTML5 서버 연결 테스트 ===")
	print()
	
	# 1. 플랫폼 정보 확인
	print("1. 플랫폼 정보:")
	print("   플랫폼: ", OS.get_name())
	print("   HTML5 환경: ", GlobalSettings.is_html5_export())
	print("   빌드 타입: ", "Release" if not OS.is_debug_build() else "Debug")
	
	print()
	
	# 2. 서버 URL 확인
	print("2. 서버 URL 설정:")
	print("   현재 서버 URL: ", GlobalSettings.get_server_url())
	print("   서버 이름: ", GlobalSettings.get_current_server_name())
	print("   폴백 가능: ", GlobalSettings.has_more_servers())
	
	print()
	
	# 3. WebSocket 연결 테스트
	print("3. WebSocket 연결 테스트:")
	print("   연결을 시도합니다...")
	
	var socket = WebSocketPeer.new()
	var server_url = GlobalSettings.get_server_url()
	
	print("   서버 URL: ", server_url)
	socket.connect_to_url(server_url)
	
	# 10초 대기
	await get_tree().create_timer(10.0).timeout
	
	var state = socket.get_ready_state()
	match state:
		WebSocketPeer.STATE_OPEN:
			print("   ✅ WebSocket 연결 성공!")
			print("   연결된 서버: ", GlobalSettings.get_current_server_name())
		WebSocketPeer.STATE_CONNECTING:
			print("   ⏳ WebSocket 연결 중... (시간 초과)")
		WebSocketPeer.STATE_CLOSED:
			print("   ❌ WebSocket 연결 실패")
			var code = socket.get_close_code()
			var reason = socket.get_close_reason()
			print("   오류 코드: ", code)
			print("   오류 이유: ", reason)
		_:
			print("   ❓ 알 수 없는 연결 상태: ", state)
	
	socket.close()
	
	print()
	print("=== 테스트 완료 ===")
	print()
	print("HTML5 환경에서는 Railway 서버만 사용됩니다.")
	print("로컬 서버 폴백은 비활성화되어 있습니다.")
	
	# 5초 후 종료
	await get_tree().create_timer(5.0).timeout
	get_tree().quit() 