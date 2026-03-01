#!/usr/bin/env python3
"""
새로운 카드 hBP06-094 기능 테스트
"""

import json
import sys
import os

# app 디렉토리를 Python 경로에 추가
sys.path.append(os.path.join(os.path.dirname(__file__), 'app'))

from app.card_database import CardDatabase
from app.gameengine import GameEngine, Condition


def test_new_card():
    """hBP06-094 카드가 정상적으로 로드되는지 테스트"""
    print("=== hBP06-094 카드 로드 테스트 ===")

    card_db = CardDatabase()
    card = card_db.get_card_by_id("hBP06-094")
    if not card:
        print("❌ 카드 hBP06-094를 찾을 수 없습니다.")
        return False

    print("✅ 카드 hBP06-094가 성공적으로 로드되었습니다.")
    print(f"   이름: {card['card_names']}")
    print(f"   타입: {card['card_type']}")
    print(f"   서브타입: {card['sub_type']}")
    print(f"   LIMITED: {card.get('limited', False)}")

    # play_conditions 확인
    play_conditions = card.get("play_conditions", [])
    if len(play_conditions) != 1:
        print(f"❌ play_conditions 개수가 1이 아닙니다: {len(play_conditions)}")
        return False
    or_cond = play_conditions[0]
    if or_cond["condition"] != "or":
        print(f"❌ play_conditions[0]이 'or' 조건이 아닙니다: {or_cond['condition']}")
        return False
    or_conditions = or_cond["or_conditions"]
    if len(or_conditions) != 2:
        print(f"❌ or_conditions 개수가 2가 아닙니다: {len(or_conditions)}")
        return False
    if or_conditions[0]["condition"] != "self_zone_has_holomem":
        print(f"❌ or_conditions[0]이 self_zone_has_holomem이 아닙니다: {or_conditions[0]['condition']}")
        return False
    if or_conditions[0]["condition_zone"] != "collab":
        print(f"❌ condition_zone이 collab이 아닙니다: {or_conditions[0]['condition_zone']}")
        return False
    if or_conditions[1]["condition"] != "opponent_has_no_collab":
        print(f"❌ or_conditions[1]이 opponent_has_no_collab이 아닙니다: {or_conditions[1]['condition']}")
        return False
    print("   ✅ play_conditions 구조 정상 (or: self_zone_has_holomem(collab) | opponent_has_no_collab)")

    # effects 확인
    effects = card.get("effects", [])
    if len(effects) != 1:
        print(f"❌ effects 개수가 1이 아닙니다: {len(effects)}")
        return False
    effect = effects[0]
    if effect["effect_type"] != "add_turn_effect_for_holomem":
        print(f"❌ effect_type이 add_turn_effect_for_holomem이 아닙니다: {effect['effect_type']}")
        return False
    if not effect.get("source_from_chosen", False):
        print("❌ source_from_chosen이 true가 아닙니다")
        return False

    turn_effect = effect["turn_effect"]
    if turn_effect["timing"] != "before_art":
        print(f"❌ turn_effect timing이 before_art가 아닙니다: {turn_effect['timing']}")
        return False
    if turn_effect["effect_type"] != "power_boost":
        print(f"❌ turn_effect effect_type이 power_boost가 아닙니다: {turn_effect['effect_type']}")
        return False
    if turn_effect["amount"] != 20:
        print(f"❌ 기본 power_boost amount가 20이 아닙니다: {turn_effect['amount']}")
        return False

    # and 효과 (Buzz/2nd 추가 부스트) 확인
    and_effects = turn_effect.get("and", [])
    if len(and_effects) != 1:
        print(f"❌ and 효과 개수가 1이 아닙니다: {len(and_effects)}")
        return False
    bonus_effect = and_effects[0]
    if bonus_effect["effect_type"] != "power_boost" or bonus_effect["amount"] != 30:
        print(f"❌ Buzz/2nd 추가 부스트가 power_boost +30이 아닙니다")
        return False

    bonus_conditions = bonus_effect.get("conditions", [])
    if len(bonus_conditions) != 1 or bonus_conditions[0]["condition"] != "or":
        print("❌ Buzz/2nd 조건이 or 조건이 아닙니다")
        return False
    bonus_or = bonus_conditions[0]["or_conditions"]
    cond_names = {c["condition"] for c in bonus_or}
    if cond_names != {"performer_is_buzz", "performer_bloom_level"}:
        print(f"❌ Buzz/2nd or 조건이 올바르지 않습니다: {cond_names}")
        return False
    print("   ✅ effects 구조 정상 (add_turn_effect_for_holomem: +20, Buzz/2nd시 +30 추가 = 총 +50)")

    return True


def test_conditions():
    """새로운 조건들이 정상적으로 정의되어 있는지 테스트"""
    print("\n=== 신규 Condition 정의 테스트 ===")

    all_ok = True

    if hasattr(Condition, 'Condition_SelfZoneHasHolomem'):
        print(f"   ✅ Condition_SelfZoneHasHolomem = \"{Condition.Condition_SelfZoneHasHolomem}\"")
    else:
        print("   ❌ Condition_SelfZoneHasHolomem이 정의되지 않았습니다.")
        all_ok = False

    if hasattr(Condition, 'Condition_PerformerIsBuzz'):
        print(f"   ✅ Condition_PerformerIsBuzz = \"{Condition.Condition_PerformerIsBuzz}\"")
    else:
        print("   ❌ Condition_PerformerIsBuzz이 정의되지 않았습니다.")
        all_ok = False

    if all_ok:
        print("✅ 모든 신규 Condition이 정상 정의되었습니다.")
    return all_ok


def main():
    """메인 테스트 함수"""
    print("hBP06-094 (워크아웃) 카드 구현 테스트를 시작합니다...\n")

    results = []
    results.append(test_new_card())
    results.append(test_conditions())

    print("\n=== 테스트 결과 요약 ===")
    passed = sum(results)
    total = len(results)

    if passed == total:
        print(f"✅ 모든 테스트가 통과했습니다! ({passed}/{total})")
    else:
        print(f"❌ 일부 테스트가 실패했습니다. ({passed}/{total})")

    return passed == total


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
