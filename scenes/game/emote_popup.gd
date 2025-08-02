extends Control

signal emote_selected(emote_id: int)

func _ready():
	# 버튼 연결
	$PopupContainer/EmoteGrid/HelloButton.pressed.connect(_on_hello_pressed)
	$PopupContainer/EmoteGrid/ThanksButton.pressed.connect(_on_thanks_pressed)
	$PopupContainer/EmoteGrid/SorryButton.pressed.connect(_on_sorry_pressed)
	$PopupContainer/EmoteGrid/WowButton.pressed.connect(_on_wow_pressed)
	$PopupContainer/EmoteGrid/WinButton.pressed.connect(_on_win_pressed)
	$PopupContainer/EmoteGrid/CancelButton.pressed.connect(_on_cancel_pressed)
	
	# 배경 클릭으로 닫기
	$Background.gui_input.connect(_on_background_input)

func show_popup():
	visible = true
	# 자동으로 2초 후 닫기
	var timer = get_tree().create_timer(2.0)
	timer.timeout.connect(_on_cancel_pressed)

func hide_popup():
	visible = false

func _on_hello_pressed():
	emote_selected.emit(0)  # EmoteId.HELLO
	hide_popup()

func _on_thanks_pressed():
	emote_selected.emit(1)  # EmoteId.THANKS
	hide_popup()

func _on_sorry_pressed():
	emote_selected.emit(2)  # EmoteId.SORRY
	hide_popup()

func _on_wow_pressed():
	emote_selected.emit(3)  # EmoteId.WOW
	hide_popup()

func _on_win_pressed():
	emote_selected.emit(4)  # EmoteId.I_WIN
	hide_popup()

func _on_cancel_pressed():
	hide_popup()

func _on_background_input(event):
	if event is InputEventMouseButton and event.pressed and event.button_index == MOUSE_BUTTON_LEFT:
		hide_popup() 