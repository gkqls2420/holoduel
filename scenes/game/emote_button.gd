extends Button

func _ready():
	pressed.connect(_on_pressed)

func _on_pressed():
	# 감정표현 팝업을 표시
	var main_scene = get_tree().get_current_scene()
	
	# Main 씬에서 Game 노드 찾기
	var game = null
	if main_scene.has_method("get_node") and main_scene.has_node("Game"):
		game = main_scene.get_node("Game")
	elif main_scene.has("game") and main_scene.game != null:
		game = main_scene.game
	
	if game and game.has_method("show_emote_popup"):
		game.show_emote_popup()

func _input(event):
	if event is InputEventKey and event.pressed:
		# ESC 키로 팝업 닫기
		if event.keycode == KEY_ESCAPE:
			var main_scene = get_tree().get_current_scene()
			var game = null
			if main_scene.has_method("get_node") and main_scene.has_node("Game"):
				game = main_scene.get_node("Game")
			elif main_scene.has("game") and main_scene.game != null:
				game = main_scene.game
			
			if game and game.has_method("hide_emote_popup"):
				game.hide_emote_popup() 
