#!/usr/bin/env python3
"""
로컬 저장소 기능 테스트 스크립트
"""

import os
import json
from app.dbaccess import (
    ensure_directories,
    upload_match_to_local_storage,
    download_match_logs_between_dates
)
from datetime import datetime, timezone, timedelta

def test_local_storage():
    """로컬 저장소 기능을 테스트합니다."""
    print("=== 로컬 저장소 기능 테스트 ===")
    
    # 1. 디렉토리 생성 테스트
    print("1. 디렉토리 생성 테스트...")
    ensure_directories()
    print("✓ 디렉토리 생성 완료")
    
    # 2. 매치 데이터 저장 테스트
    print("2. 매치 데이터 저장 테스트...")
    test_match_data = {
        "player_info": [
            {"username": "test_player1", "oshi_id": "test_oshi1"},
            {"username": "test_player2", "oshi_id": "test_oshi2"}
        ],
        "player_clocks": [300, 300],
        "player_final_life": [20, 0],
        "game_over_reason": "test_reason",
        "queue_name": "test_queue",
        "starting_player": 0,
        "turn_number": 5,
        "winner": "test_player1"
    }
    
    upload_match_to_local_storage(test_match_data)
    print("✓ 매치 데이터 저장 완료")
    
    # 3. 매치 로그 다운로드 테스트
    print("3. 매치 로그 다운로드 테스트...")
    end_date = datetime.now(timezone.utc)
    start_date = end_date - timedelta(days=1)
    download_path = "test_download"
    
    download_match_logs_between_dates(start_date, end_date, download_path)
    print("✓ 매치 로그 다운로드 완료")
    
    # 4. 저장된 파일 확인
    print("4. 저장된 파일 확인...")
    if os.path.exists("data/match_logs"):
        files = os.listdir("data/match_logs")
        print(f"✓ 매치 로그 파일 수: {len(files)}")
        for file in files[:3]:  # 처음 3개 파일만 표시
            print(f"  - {file}")
    
    if os.path.exists(download_path):
        files = os.listdir(download_path)
        print(f"✓ 다운로드된 파일 수: {len(files)}")
    
    print("\n=== 테스트 완료 ===")

if __name__ == "__main__":
    test_local_storage() 