extends Node

# 서버 폴백 기능 테스트 스크립트
# 이 스크립트를 실행하여 서버 연결 폴백 기능을 테스트할 수 있습니다.

func _ready():
	print("=== HoloDuel 서버 폴백 기능 테스트 ===")
	print()
	
	# 1. 서버 URL 목록 확인
	print("1. 서버 URL 목록:")
	for i in range(GlobalSettings.SERVER_URLS.size()):
		var url = GlobalSettings.SERVER_URLS[i]
		var name = "Railway" if i == 0 else "Local"
		print("   ", i + 1, ". ", name, ": ", url)
	
	print()
	
	# 2. 현재 서버 인덱스 확인
	print("2. 현재 서버 인덱스: ", GlobalSettings.current_server_index)
	print("   현재 서버: ", GlobalSettings.get_current_server_name())
	print("   현재 URL: ", GlobalSettings.get_server_url())
	
	print()
	
	# 3. 폴백 테스트
	print("3. 폴백 테스트:")
	for i in range(GlobalSettings.SERVER_URLS.size() + 1):
		print("   시도 ", i + 1, ": ", GlobalSettings.get_current_server_name())
		if GlobalSettings.has_more_servers():
			GlobalSettings.get_next_server_url()
		else:
			print("   더 이상 시도할 서버가 없습니다.")
			break
	
	print()
	
	# 4. 서버 인덱스 리셋
	print("4. 서버 인덱스 리셋:")
	GlobalSettings.reset_server_index()
	print("   리셋 후 인덱스: ", GlobalSettings.current_server_index)
	print("   리셋 후 서버: ", GlobalSettings.get_current_server_name())
	
	print()
	print("=== 테스트 완료 ===")
	print()
	print("실제 연결 테스트를 위해 게임을 실행하세요.")
	print("Railway 서버가 실패하면 자동으로 로컬 서버로 폴백됩니다.")
	
	# 3초 후 종료
	await get_tree().create_timer(3.0).timeout
	get_tree().quit() 