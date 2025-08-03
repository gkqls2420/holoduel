extends Control

func _ready():
	# 초기에는 숨김
	visible = false

func show_emote(emote_id: int, player_id: String):
	# 감정표현 데이터 가져오기
	var game = get_parent()
	var emote_text = game.EMOTE_TEXT.get(emote_id, "")
	var emote_icon = game.EMOTE_ICON.get(emote_id, "")
	
	# UI 업데이트
	$EmoteBubble/VBoxContainer/IconLabel.text = emote_icon
	$EmoteBubble/VBoxContainer/TextLabel.text = emote_text
	
	# 플레이어에 따라 위치 조정
	var target_position = Vector2.ZERO
	
	if game.has_method("get_player"):
		var player = game.get_player(player_id)
		if player and player.has_method("get_oshi_zone_position"):
			target_position = player.get_oshi_zone_position()
			
			# 자신과 상대방의 감정표현을 다른 위치에 표시
			if player.is_me():
				# 자신의 감정표현: oshi 카드 우측 위에 표시
				target_position.x += 160  # 버튼 위치에 맞춤
				target_position.y -= 30   # 위쪽 여백
			else:
				# 상대방의 감정표현: oshi 카드 좌측 위에 표시
				target_position.x -= 160  # 좌측으로 이동
				target_position.y -= 30   # 위쪽 여백
		else:
			# 기본 위치 (화면 중앙)
			target_position = Vector2(640, 360)
	else:
		# 기본 위치 (화면 중앙)
		target_position = Vector2(640, 360)
	
	# 위치 설정
	$EmoteBubble.position = target_position
	
	# 표시
	visible = true
	
	# 3초 후 자동 숨김
	var timer = get_tree().create_timer(3.0)
	timer.timeout.connect(_on_timeout)

func _on_timeout():
	visible = false 