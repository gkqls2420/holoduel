import unittest
from app.gameengine import GameEngine, GameAction
from app.gameengine import PlayerState
from app.gameengine import EventType
from tests.helpers import *


class Test_hBP04_006(unittest.TestCase):
    """
    hBP04-006 오오조라 스바루 오시 카드 테스트
    
    일반 오시 스킬 (턴에 1번, 홀로파워 -2):
    - 상대 턴에 자신의 <오오조라 스바루>가 대미지를 받을 때 사용
    - 자신의 <오오조라 스바루> 전원이 받는 대미지 -30
    
    SP 오시 스킬 (게임에 1번, 홀로파워 -2):
    - 자신의 라이프가 3 이하일 때 사용
    - 이 턴 동안 센터 <오오조라 스바루> 아츠 +100
    """
    engine: GameEngine
    player1: str
    player2: str

    def setUp(self):
        # p1: 오오조라 스바루 오시, 백스테이지에 스바루 배치
        # p2: 코보 카나에루 (hBP05-048) - 여러 타겟에게 스페셜 대미지
        p1_deck = generate_deck_with("hBP04-006", {
            "hBP04-067": 6,  # 오오조라 스바루 데뷔
            "hSD01-006": 2,  # 토키노 소라 블룸 (더미)
        })
        p2_deck = generate_deck_with("", {
            "hBP05-048": 4,  # 코보 카나에루 1st 블룸
        })
        initialize_game_to_third_turn(self, p1_deck, p2_deck)

    def test_passive_skill_reduces_damage_on_opponent_turn(self):
        """일반 오시 스킬: 상대 턴에 오오조라 스바루가 대미지를 받을 때 스킬 사용 가능"""
        engine = self.engine
        p1: PlayerState = engine.get_player(self.player1)
        p2: PlayerState = engine.get_player(self.player2)

        # Setup: p1 센터에 오오조라 스바루 배치
        p1.center = []
        center_card, center_card_id = unpack_game_id(put_card_in_play(self, p1, "hBP04-067", p1.center))
        
        # p1에게 홀로파워 2 부여
        p1.holopower = p1.deck[:2]
        p1.deck = p1.deck[2:]
        
        # p2 센터에 카드 배치 및 응원 부착 (기존 센터 카드 사용)
        p2_center = p2.center[0]
        p2_center_id = p2_center["game_card_id"]
        spawn_cheer_on_card(self, p2, p2_center_id, "white", "cheer1")

        # p1 턴 종료 -> p2 턴으로 전환
        end_turn(self)
        do_cheer_step_on_card(self, p2.center[0])
        
        self.assertEqual(engine.active_player_id, self.player2)
        
        # p2가 퍼포먼스 시작
        begin_performance(self)
        
        # p2가 p1 센터(오오조라 스바루)를 공격
        engine.handle_game_message(self.player2, GameAction.PerformanceStepUseArt, {
            "performer_id": p2_center_id,
            "art_id": "nunnun",
            "target_id": center_card_id,
        })
        events = engine.grab_events()
        
        # 오시 스킬 사용 선택지가 나와야 함
        choice_event = None
        for event in events:
            if event["event_type"] == EventType.EventType_Decision_Choice:
                choice_event = event
                break
        
        self.assertIsNotNone(choice_event, "오시 스킬 사용 선택지가 나와야 합니다")
        
        # 스킬 사용 (choice index 0)
        pick_choice(self, self.player1, 0)
        events = engine.grab_events()
        
        # 대미지가 30 감소되어야 함 (20 - 30 = 0, 최소 0)
        damage_event = None
        for event in events:
            if event["event_type"] == EventType.EventType_DamageDealt:
                damage_event = event
                break
        
        # 20 - 30 = -10 -> 0 (최소)
        # center_card의 damage 확인
        self.assertEqual(center_card["damage"], 0)

    def test_passive_skill_not_triggered_on_own_turn(self):
        """일반 오시 스킬: 자신의 턴에는 스킬이 트리거되지 않음"""
        engine = self.engine
        p1: PlayerState = engine.get_player(self.player1)
        p2: PlayerState = engine.get_player(self.player2)

        # Setup: p1 센터에 오오조라 스바루 배치
        p1.center = []
        center_card, center_card_id = unpack_game_id(put_card_in_play(self, p1, "hBP04-067", p1.center))
        spawn_cheer_on_card(self, p1, center_card_id, "yellow", "cheer1")
        
        # p1에게 홀로파워 2 부여
        p1.holopower = p1.deck[:2]
        p1.deck = p1.deck[2:]
        
        # p2 센터에 카드 배치
        p2_center = p2.center[0]
        p2_center_id = p2_center["game_card_id"]
        
        # 자신의 턴(p1)에서는 오시 스킬이 트리거되지 않아야 함
        self.assertEqual(engine.active_player_id, self.player1)
        
        # 퍼포먼스 시작
        begin_performance(self)
        
        # p1이 p2를 공격
        engine.handle_game_message(self.player1, GameAction.PerformanceStepUseArt, {
            "performer_id": center_card_id,
            "art_id": "ajimaru",
            "target_id": p2_center_id,
        })
        events = engine.grab_events()
        
        # 오시 스킬 선택지가 나오지 않아야 함 (자신의 턴이므로)
        choice_event = None
        for event in events:
            if event["event_type"] == EventType.EventType_Decision_Choice:
                # 이것은 p1의 오시 스킬이 아니라 다른 선택지일 수 있음
                if "mentalphysicalfashion_passive" in str(event.get("choice", [])):
                    choice_event = event
                    break
        
        # 자신의 턴에는 트리거되지 않으므로 선택지가 없어야 함
        self.assertIsNone(choice_event, "자신의 턴에는 오시 스킬이 트리거되지 않아야 합니다")

    def test_sp_skill_available_when_life_3_or_less(self):
        """SP 오시 스킬: 라이프 3 이하일 때 사용 가능"""
        engine = self.engine
        p1: PlayerState = engine.get_player(self.player1)

        # Setup: p1 센터에 오오조라 스바루 배치
        p1.center = []
        center_card, center_card_id = unpack_game_id(put_card_in_play(self, p1, "hBP04-067", p1.center))
        spawn_cheer_on_card(self, p1, center_card_id, "yellow", "cheer1")
        spawn_cheer_on_card(self, p1, center_card_id, "yellow", "cheer2")
        spawn_cheer_on_card(self, p1, center_card_id, "yellow", "cheer3")
        
        # p1에게 홀로파워 2 부여
        p1.holopower = p1.deck[:2]
        p1.deck = p1.deck[2:]
        
        # 라이프가 5일 때는 SP 스킬 사용 불가
        self.assertEqual(len(p1.life), 5)
        actions = reset_mainstep(self)
        
        sp_skill_available = any(
            action.get("action_type") == GameAction.MainStepOshiSkill and 
            action.get("skill_id") == "mentalphysicalfashion"
            for action in actions
        )
        self.assertFalse(sp_skill_available, "라이프 5일 때 SP 스킬 사용 불가")
        
        # 라이프를 3으로 줄임
        p1.life = p1.life[:3]
        actions = reset_mainstep(self)
        
        sp_skill_available = any(
            action.get("action_type") == GameAction.MainStepOshiSkill and 
            action.get("skill_id") == "mentalphysicalfashion"
            for action in actions
        )
        self.assertTrue(sp_skill_available, "라이프 3 이하일 때 SP 스킬 사용 가능")

    def test_sp_skill_gives_center_subaru_100_power(self):
        """SP 오시 스킬: 센터 오오조라 스바루 아츠 +100"""
        engine = self.engine
        p1: PlayerState = engine.get_player(self.player1)
        p2: PlayerState = engine.get_player(self.player2)

        # Setup: p1 센터에 오오조라 스바루 배치
        p1.center = []
        center_card, center_card_id = unpack_game_id(put_card_in_play(self, p1, "hBP04-067", p1.center))
        spawn_cheer_on_card(self, p1, center_card_id, "yellow", "cheer1")
        
        # p1에게 홀로파워 2 부여
        p1.holopower = p1.deck[:2]
        p1.deck = p1.deck[2:]
        
        # 라이프를 3으로 줄임
        p1.life = p1.life[:3]
        
        # p2 센터 (기존 센터 카드 사용)
        p2_center = p2.center[0]
        p2_center_id = p2_center["game_card_id"]
        
        actions = reset_mainstep(self)
        
        # SP 스킬 사용
        use_oshi_action(self, "mentalphysicalfashion")
        
        # 퍼포먼스로 아트 파워 확인
        begin_performance(self)
        
        # 아트 사용 (기본 파워 20 + 100 = 120)
        engine.handle_game_message(self.player1, GameAction.PerformanceStepUseArt, {
            "performer_id": center_card_id,
            "art_id": "ajimaru",
            "target_id": p2_center_id,
        })
        events = engine.grab_events()
        
        # 대미지 이벤트에서 120 대미지 확인
        damage_event = None
        for event in events:
            if event["event_type"] == EventType.EventType_DamageDealt:
                damage_event = event
                break
        
        self.assertIsNotNone(damage_event)
        self.assertEqual(damage_event["damage"], 120, "아트 파워 20 + 100 = 120")


if __name__ == '__main__':
    unittest.main()

