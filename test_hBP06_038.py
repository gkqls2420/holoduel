#!/usr/bin/env python3
"""
hBP06-038 카드 검증 및 크래시 원인 수정 테스트
- 카드 정의 검증
- condition_mixin.py의 null 참조 안전성 검증
- turn_mixin.py의 performance 상태 초기화 검증
"""

import sys
import os

sys.path.append(os.path.join(os.path.dirname(__file__), 'app'))

from app.card_database import CardDatabase
from app.engine.constants import *
from app.engine.models import ArtStatBoosts


def test_card_definition():
    """hBP06-038 카드가 올바르게 정의되어 있는지 테스트"""
    print("=== hBP06-038 카드 정의 테스트 ===")

    card_db = CardDatabase()
    card = card_db.get_card_by_id("hBP06-038")
    if not card:
        print("FAIL: 카드 hBP06-038을 찾을 수 없습니다.")
        return False

    print(f"  card_names: {card['card_names']}")
    print(f"  card_type: {card['card_type']}")
    print(f"  bloom_level: {card['bloom_level']}")
    print(f"  hp: {card['hp']}")

    if card["card_type"] != "holomem_bloom":
        print(f"FAIL: card_type이 holomem_bloom이 아닙니다: {card['card_type']}")
        return False

    if card["bloom_level"] != 1:
        print(f"FAIL: bloom_level이 1이 아닙니다: {card['bloom_level']}")
        return False

    arts = card.get("arts", [])
    if len(arts) != 1:
        print(f"FAIL: arts 개수가 1이 아닙니다: {len(arts)}")
        return False

    art = arts[0]
    if art["art_id"] != "here_we_go":
        print(f"FAIL: art_id가 here_we_go가 아닙니다: {art['art_id']}")
        return False

    if art["power"] != 30:
        print(f"FAIL: power가 30이 아닙니다: {art['power']}")
        return False

    art_effects = art.get("art_effects", [])
    if len(art_effects) != 1:
        print(f"FAIL: art_effects 개수가 1이 아닙니다: {len(art_effects)}")
        return False

    effect = art_effects[0]
    if effect["timing"] != "before_art":
        print(f"FAIL: timing이 before_art가 아닙니다: {effect['timing']}")
        return False

    if effect["effect_type"] != "choice":
        print(f"FAIL: effect_type이 choice가 아닙니다: {effect['effect_type']}")
        return False

    choice = effect["choice"]
    if len(choice) != 2:
        print(f"FAIL: choice 옵션이 2개가 아닙니다: {len(choice)}")
        return False

    choose_cards = choice[0]
    if choose_cards["effect_type"] != "choose_cards":
        print(f"FAIL: 첫 번째 선택지가 choose_cards가 아닙니다: {choose_cards['effect_type']}")
        return False
    if choose_cards["from"] != "cheer_deck":
        print(f"FAIL: from이 cheer_deck이 아닙니다: {choose_cards['from']}")
        return False

    and_effects = choose_cards.get("and", [])
    if len(and_effects) != 1 or and_effects[0]["effect_type"] != "deal_damage":
        print("FAIL: and 효과가 deal_damage가 아닙니다")
        return False

    if choice[1]["effect_type"] != "pass":
        print(f"FAIL: 두 번째 선택지가 pass가 아닙니다: {choice[1]['effect_type']}")
        return False

    print("PASS: hBP06-038 카드 정의가 올바릅니다.")
    return True


def test_condition_null_safety():
    """performance_performer_card/performance_target_card가 None일 때 조건 체크가 크래시하지 않는지 테스트"""
    print("\n=== condition_mixin.py null 참조 안전성 테스트 ===")

    from app.engine.condition_mixin import ConditionMixin

    class MockEngine(ConditionMixin):
        def __init__(self):
            self.performance_performer_card = None
            self.performance_performing_player = None
            self.performance_target_card = None
            self.performance_target_player = None
            self.performance_artstatboosts = ArtStatBoosts()
            self.take_damage_state = None
            self.after_damage_state = None
            self.down_holomem_state = None
            self.player_states = []

    engine = MockEngine()
    all_ok = True

    test_cases = [
        (
            "Condition_PerformerIsColor",
            {"condition": Condition.Condition_PerformerIsColor, "condition_colors": ["red"]},
        ),
        (
            "Condition_PerformerIsSpecificId",
            {"condition": Condition.Condition_PerformerIsSpecificId, "required_id": "test_id"},
        ),
        (
            "Condition_PerformerHasAnyTag",
            {"condition": Condition.Condition_PerformerHasAnyTag, "condition_tags": ["#JP"]},
        ),
        (
            "Condition_PerformanceTargetHasDamageOverHp",
            {"condition": Condition.Condition_PerformanceTargetHasDamageOverHp, "amount": 0},
        ),
        (
            "Condition_TargetColor",
            {"condition": Condition.Condition_TargetColor, "color_requirement": "red"},
        ),
        (
            "Condition_TargetIsBackstage",
            {"condition": Condition.Condition_TargetIsBackstage},
        ),
        (
            "Condition_TargetIsNotBackstage",
            {"condition": Condition.Condition_TargetIsNotBackstage},
        ),
    ]

    for name, condition in test_cases:
        try:
            result = engine.is_condition_met(None, "", condition)
            if result:
                print(f"  FAIL: {name} - None일 때 True를 반환 (False여야 함)")
                all_ok = False
            else:
                print(f"  PASS: {name} - None일 때 False 반환")
        except (TypeError, AttributeError) as e:
            print(f"  FAIL: {name} - 크래시 발생: {e}")
            all_ok = False

    if all_ok:
        print("PASS: 모든 조건이 null 안전합니다.")
    else:
        print("FAIL: 일부 조건에서 null 안전성 문제가 있습니다.")
    return all_ok


def test_performance_state_cleanup():
    """continue_performance_step()에서 performance 상태가 올바르게 초기화되는지 테스트"""
    print("\n=== turn_mixin.py performance 상태 초기화 테스트 ===")

    from app.engine.turn_mixin import TurnMixin

    class MockEngine(TurnMixin):
        def __init__(self):
            self.performance_artstatboosts = ArtStatBoosts()
            self.performance_performing_player = "mock_player"
            self.performance_performer_card = {"game_card_id": "test"}
            self.performance_target_player = "mock_target_player"
            self.performance_target_card = {"game_card_id": "test_target", "damage": 0}
            self.performance_art = "mock_art"
            self.send_actions_called = False

        def send_performance_step_actions(self):
            self.send_actions_called = True

        def get_player(self, player_id):
            return None

    engine = MockEngine()
    engine.performance_artstatboosts.repeat_art = False
    engine.continue_performance_step()

    all_ok = True

    if engine.performance_performing_player is not None:
        print("  FAIL: performance_performing_player가 None이 아닙니다")
        all_ok = False

    if engine.performance_performer_card is not None:
        print("  FAIL: performance_performer_card가 None이 아닙니다")
        all_ok = False

    if engine.performance_target_player is not None:
        print("  FAIL: performance_target_player가 None이 아닙니다")
        all_ok = False

    if engine.performance_target_card is not None:
        print("  FAIL: performance_target_card가 None이 아닙니다")
        all_ok = False

    if not engine.send_actions_called:
        print("  FAIL: send_performance_step_actions가 호출되지 않았습니다")
        all_ok = False

    if all_ok:
        print("PASS: performance 상태가 올바르게 초기화됩니다.")
    else:
        print("FAIL: performance 상태 초기화에 문제가 있습니다.")
    return all_ok


def main():
    print("hBP06-038 크래시 원인 수정 검증 테스트\n")

    results = []
    results.append(test_card_definition())
    results.append(test_condition_null_safety())
    results.append(test_performance_state_cleanup())

    print("\n=== 테스트 결과 요약 ===")
    passed = sum(results)
    total = len(results)

    if passed == total:
        print(f"모든 테스트 통과 ({passed}/{total})")
    else:
        print(f"일부 테스트 실패 ({passed}/{total})")

    return passed == total


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
