extends Node

# Android 환경에서 서버 연결 테스트 스크립트
# 이 스크립트를 Android에서 실행하여 연결을 테스트할 수 있습니다.

func _ready():
	print("=== Android 서버 연결 테스트 ===")
	print()
	
	# 1. 플랫폼 정보 확인
	print("1. 플랫폼 정보:")
	print("   플랫폼: ", OS.get_name())
	print("   Android 환경: ", GlobalSettings.is_android_export())
	print("   빌드 타입: ", "Release" if not OS.is_debug_build() else "Debug")
	
	# Android 특정 정보
	if GlobalSettings.is_android_export():
		print("   Android API Level: ", OS.get_environment("ANDROID_API_LEVEL"))
		print("   Android Version: ", OS.get_environment("ANDROID_VERSION"))
		print("   Android Model: ", OS.get_environment("ANDROID_MODEL"))
	
	print()
	
	# 2. 네트워크 권한 확인
	print("2. 네트워크 권한 확인:")
	print("   인터넷 권한 필요: true")
	print("   네트워크 상태: ", "연결됨" if OS.has_feature("network") else "연결 안됨")
	
	print()
	
	# 3. 서버 URL 확인
	print("3. 서버 URL 설정:")
	print("   현재 서버 URL: ", GlobalSettings.get_server_url())
	print("   서버 이름: ", GlobalSettings.get_current_server_name())
	print("   폴백 가능: ", GlobalSettings.has_more_servers())
	
	print()
	
	# 4. WebSocket 연결 테스트
	print("4. WebSocket 연결 테스트:")
	print("   연결을 시도합니다...")
	
	var socket = WebSocketPeer.new()
	var server_url = GlobalSettings.get_server_url()
	
	print("   서버 URL: ", server_url)
	socket.connect_to_url(server_url)
	
	# 15초 대기 (모바일 네트워크는 느릴 수 있음)
	await get_tree().create_timer(15.0).timeout
	
	var state = socket.get_ready_state()
	match state:
		WebSocketPeer.STATE_OPEN:
			print("   ✅ WebSocket 연결 성공!")
			print("   연결된 서버: ", GlobalSettings.get_current_server_name())
			
			# 간단한 메시지 전송 테스트
			var test_message = {"message_type": "join_server"}
			socket.send_text(JSON.stringify(test_message))
			print("   테스트 메시지 전송됨")
			
		WebSocketPeer.STATE_CONNECTING:
			print("   ⏳ WebSocket 연결 중... (시간 초과)")
			print("   모바일 네트워크 환경에서 연결이 느릴 수 있습니다.")
		WebSocketPeer.STATE_CLOSED:
			print("   ❌ WebSocket 연결 실패")
			var code = socket.get_close_code()
			var reason = socket.get_close_reason()
			print("   오류 코드: ", code)
			print("   오류 이유: ", reason)
			
			# 일반적인 Android 연결 문제 해결 방법 제시
			print("   가능한 원인:")
			print("   - 인터넷 연결 확인")
			print("   - 앱 권한 확인 (인터넷 접근)")
			print("   - 방화벽/보안 앱 설정")
			print("   - 모바일 데이터 사용량 확인")
		_:
			print("   ❓ 알 수 없는 연결 상태: ", state)
	
	socket.close()
	
	print()
	print("=== 테스트 완료 ===")
	print()
	print("Android 환경에서는 Railway 서버만 사용됩니다.")
	print("로컬 서버 폴백은 비활성화되어 있습니다.")
	
	# 5초 후 종료
	await get_tree().create_timer(5.0).timeout
	get_tree().quit() 