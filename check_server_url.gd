extends Node

# 서버 URL 확인 스크립트
# 이 스크립트를 실행하여 현재 설정된 서버 URL을 확인할 수 있습니다.

func _ready():
	print("=== HoloDuel 서버 URL 확인 ===")
	print()
	
	# 빌드 타입 확인
	var build_type = "Release" if not OS.is_debug_build() else "Debug"
	print("빌드 타입: ", build_type)
	
	# UseAzureServerAlways 설정 확인
	print("UseAzureServerAlways: ", GlobalSettings.UseAzureServerAlways)
	
	# 서버 URL 확인
	var server_url = GlobalSettings.get_server_url()
	print("서버 URL: ", server_url)
	
	# URL 분석
	if server_url.begins_with("ws://127.0.0.1"):
		print("✅ 로컬 서버 (개발용)")
		print("   - 로컬 서버가 실행 중인지 확인하세요")
		print("   - http://127.0.0.1:8000 으로 접속 가능한지 확인")
	elif server_url.begins_with("wss://"):
		print("✅ Railway 서버 (프로덕션용)")
		print("   - Railway에서 서버가 배포되었는지 확인하세요")
		print("   - URL이 올바른지 확인하세요")
	else:
		print("⚠️  알 수 없는 서버 URL")
	
	print()
	print("=== 연결 테스트 ===")
	print("서버 연결을 시도합니다...")
	
	# 간단한 연결 테스트
	var socket = WebSocketPeer.new()
	socket.connect_to_url(server_url)
	
	# 5초 대기
	await get_tree().create_timer(5.0).timeout
	
	var state = socket.get_ready_state()
	match state:
		WebSocketPeer.STATE_OPEN:
			print("✅ 서버 연결 성공!")
		WebSocketPeer.STATE_CONNECTING:
			print("⏳ 서버 연결 중... (시간 초과)")
		WebSocketPeer.STATE_CLOSED:
			print("❌ 서버 연결 실패")
			var code = socket.get_close_code()
			var reason = socket.get_close_reason()
			print("   오류 코드: ", code)
			print("   오류 이유: ", reason)
		_:
			print("❓ 알 수 없는 연결 상태: ", state)
	
	socket.close()
	
	print()
	print("=== 확인 완료 ===")
	
	# 3초 후 종료
	await get_tree().create_timer(3.0).timeout
	get_tree().quit() 