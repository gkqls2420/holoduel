import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.gameengine import GameEngine, Condition
from app.card_database import CardDatabase

def test_monocolor_different_colors_on_stage_condition():
    """monocolor_different_colors_on_stage 조건이 올바르게 작동하는지 테스트
    
    hBP04-089 (투톤 컬러 컴퓨터) 사용 조건:
    - 자신의 스테이지에 색이 1색이고 서로 다른 색의 홀로멤이 2명 이상
    """
    
    print("테스트 시작: monocolor_different_colors_on_stage 조건 테스트")
    
    # 카드 데이터베이스 초기화
    card_db = CardDatabase()
    
    # 플레이어 정보 설정
    player_infos = [
        {
            "player_id": "player1",
            "username": "test_player1",
            "oshi_id": "hSD01-001",
            "deck": {"hSD01-003": 1},
            "cheer_deck": {}
        },
        {
            "player_id": "player2",
            "username": "test_player2",
            "oshi_id": "hSD01-001",
            "deck": {"hSD01-003": 1},
            "cheer_deck": {}
        }
    ]
    
    # 게임 엔진 초기화
    engine = GameEngine(card_db, "test", player_infos)
    engine.begin_game()
    
    player1 = engine.get_player("player1")
    
    print("✅ 게임 엔진 초기화 성공")
    
    # 조건 정의
    condition = {
        "condition": "monocolor_different_colors_on_stage"
    }
    
    all_passed = True
    
    # 테스트 케이스 1: 모노컬러 홀로멤 2명, 서로 다른 색 (빨강 + 파랑)
    print("\n--- 테스트 케이스 1: 모노컬러 홀로멤 2명 (빨강 + 파랑) ---")
    player1.center = [{
        "game_card_id": "test1",
        "card_id": "mono_red",
        "card_type": "holomem_debut",
        "colors": ["red"],
        "hp": 100,
        "damage": 0
    }]
    player1.backstage = [{
        "game_card_id": "test2",
        "card_id": "mono_blue",
        "card_type": "holomem_debut",
        "colors": ["blue"],
        "hp": 100,
        "damage": 0
    }]
    player1.collab = []
    
    result = engine.is_condition_met(player1, "test_card", condition)
    print(f"결과: {result} (기대값: True)")
    if result != True:
        print("❌ 테스트 케이스 1 실패!")
        all_passed = False
    else:
        print("✅ 테스트 케이스 1 통과!")
    
    # 테스트 케이스 2: 모노컬러 홀로멤 2명, 같은 색 (빨강 + 빨강)
    print("\n--- 테스트 케이스 2: 모노컬러 홀로멤 2명 같은 색 (빨강 + 빨강) ---")
    player1.center = [{
        "game_card_id": "test1",
        "card_id": "mono_red1",
        "card_type": "holomem_debut",
        "colors": ["red"],
        "hp": 100,
        "damage": 0
    }]
    player1.backstage = [{
        "game_card_id": "test2",
        "card_id": "mono_red2",
        "card_type": "holomem_debut",
        "colors": ["red"],
        "hp": 100,
        "damage": 0
    }]
    player1.collab = []
    
    result = engine.is_condition_met(player1, "test_card", condition)
    print(f"결과: {result} (기대값: False)")
    if result != False:
        print("❌ 테스트 케이스 2 실패!")
        all_passed = False
    else:
        print("✅ 테스트 케이스 2 통과!")
    
    # 테스트 케이스 3: 모노컬러 1명 + 듀얼컬러 1명 (버그 수정 전에는 통과했던 케이스)
    print("\n--- 테스트 케이스 3: 모노컬러 1명 + 듀얼컬러 1명 ---")
    player1.center = [{
        "game_card_id": "test1",
        "card_id": "mono_red",
        "card_type": "holomem_debut",
        "colors": ["red"],
        "hp": 100,
        "damage": 0
    }]
    player1.backstage = [{
        "game_card_id": "test2",
        "card_id": "dual_red_blue",
        "card_type": "holomem_debut",
        "colors": ["red", "blue"],  # 듀얼컬러
        "hp": 100,
        "damage": 0
    }]
    player1.collab = []
    
    result = engine.is_condition_met(player1, "test_card", condition)
    print(f"결과: {result} (기대값: False - 모노컬러가 2명 이상이어야 함)")
    if result != False:
        print("❌ 테스트 케이스 3 실패! (버그: 모노컬러 1명 + 듀얼컬러 1명도 통과함)")
        all_passed = False
    else:
        print("✅ 테스트 케이스 3 통과!")
    
    # 테스트 케이스 4: 듀얼컬러 홀로멤만 2명 (다른 색)
    print("\n--- 테스트 케이스 4: 듀얼컬러 홀로멤만 2명 ---")
    player1.center = [{
        "game_card_id": "test1",
        "card_id": "dual_red_blue",
        "card_type": "holomem_debut",
        "colors": ["red", "blue"],
        "hp": 100,
        "damage": 0
    }]
    player1.backstage = [{
        "game_card_id": "test2",
        "card_id": "dual_green_yellow",
        "card_type": "holomem_debut",
        "colors": ["green", "yellow"],
        "hp": 100,
        "damage": 0
    }]
    player1.collab = []
    
    result = engine.is_condition_met(player1, "test_card", condition)
    print(f"결과: {result} (기대값: False)")
    if result != False:
        print("❌ 테스트 케이스 4 실패!")
        all_passed = False
    else:
        print("✅ 테스트 케이스 4 통과!")
    
    # 테스트 케이스 5: 홀로멤 1명만
    print("\n--- 테스트 케이스 5: 홀로멤 1명만 ---")
    player1.center = [{
        "game_card_id": "test1",
        "card_id": "mono_red",
        "card_type": "holomem_debut",
        "colors": ["red"],
        "hp": 100,
        "damage": 0
    }]
    player1.backstage = []
    player1.collab = []
    
    result = engine.is_condition_met(player1, "test_card", condition)
    print(f"결과: {result} (기대값: False)")
    if result != False:
        print("❌ 테스트 케이스 5 실패!")
        all_passed = False
    else:
        print("✅ 테스트 케이스 5 통과!")
    
    # 테스트 케이스 6: 모노컬러 3명, 2가지 색 (빨강 2명 + 파랑 1명)
    print("\n--- 테스트 케이스 6: 모노컬러 3명 (빨강 2명 + 파랑 1명) ---")
    player1.center = [{
        "game_card_id": "test1",
        "card_id": "mono_red1",
        "card_type": "holomem_debut",
        "colors": ["red"],
        "hp": 100,
        "damage": 0
    }]
    player1.backstage = [
        {
            "game_card_id": "test2",
            "card_id": "mono_red2",
            "card_type": "holomem_debut",
            "colors": ["red"],
            "hp": 100,
            "damage": 0
        },
        {
            "game_card_id": "test3",
            "card_id": "mono_blue",
            "card_type": "holomem_debut",
            "colors": ["blue"],
            "hp": 100,
            "damage": 0
        }
    ]
    player1.collab = []
    
    result = engine.is_condition_met(player1, "test_card", condition)
    print(f"결과: {result} (기대값: True)")
    if result != True:
        print("❌ 테스트 케이스 6 실패!")
        all_passed = False
    else:
        print("✅ 테스트 케이스 6 통과!")
    
    # 테스트 케이스 7: 모노컬러 2명 + 듀얼컬러 1명 (모노컬러들이 서로 다른 색)
    print("\n--- 테스트 케이스 7: 모노컬러 2명 (서로 다른 색) + 듀얼컬러 1명 ---")
    player1.center = [{
        "game_card_id": "test1",
        "card_id": "mono_red",
        "card_type": "holomem_debut",
        "colors": ["red"],
        "hp": 100,
        "damage": 0
    }]
    player1.backstage = [{
        "game_card_id": "test2",
        "card_id": "mono_blue",
        "card_type": "holomem_debut",
        "colors": ["blue"],
        "hp": 100,
        "damage": 0
    }]
    player1.collab = [{
        "game_card_id": "test3",
        "card_id": "dual_green_yellow",
        "card_type": "holomem_debut",
        "colors": ["green", "yellow"],
        "hp": 100,
        "damage": 0
    }]
    
    result = engine.is_condition_met(player1, "test_card", condition)
    print(f"결과: {result} (기대값: True)")
    if result != True:
        print("❌ 테스트 케이스 7 실패!")
        all_passed = False
    else:
        print("✅ 테스트 케이스 7 통과!")
    
    return all_passed


if __name__ == "__main__":
    print("hBP04-089 (투톤 컬러 컴퓨터) 카드 테스트 시작")
    print("=" * 60)
    
    success = test_monocolor_different_colors_on_stage_condition()
    
    print("\n" + "=" * 60)
    if success:
        print("🎉 모든 테스트가 성공했습니다!")
        print("✅ 검증된 기능:")
        print("  - monocolor_different_colors_on_stage 조건")
        print("  - 모노컬러 홀로멤 2명 이상 필요")
        print("  - 그 모노컬러 홀로멤들의 색이 서로 달라야 함")
        sys.exit(0)
    else:
        print("❌ 일부 테스트가 실패했습니다.")
        sys.exit(1)

