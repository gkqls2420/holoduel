# HoloDuel 서버 폴백 기능 가이드

## 🚀 **서버 폴백 기능 개요**

HoloDuel 클라이언트는 이제 **자동 서버 폴백** 기능을 지원합니다. Railway 서버에 연결이 실패하면 자동으로 로컬 서버로 전환됩니다.

## 📋 **서버 우선순위**

1. **Railway 서버** (1순위)
   - URL: `wss://web-production-db70.up.railway.app/ws`
   - 프로덕션 환경용
   - 인터넷 연결 필요

2. **로컬 서버** (2순위)
   - URL: `ws://127.0.0.1:8000/ws`
   - 개발 환경용
   - 로컬 서버 실행 필요

## 🔧 **동작 방식**

### 연결 시도 순서
1. Railway 서버에 연결 시도
2. Railway 서버 실패 시 → 로컬 서버로 자동 전환
3. 로컬 서버도 실패 시 → 연결 실패

### 연결 성공 시
- 성공한 서버와 연결 유지
- 다음 연결 시도 시 다시 Railway 서버부터 시작

## 🎮 **사용자 경험**

### 연결 중 표시
```
Connecting to server...
Railway (wss://web-production-db70.up.railway.app/ws)
```

### 연결 성공 표시
```
Connected to Railway
wss://web-production-db70.up.railway.app/ws
```

### 폴백 시 표시
```
Connecting to server...
Local (ws://127.0.0.1:8000/ws)
```

### 연결 실패 표시
```
Disconnected from server
Click 'Connect' to retry
```

## 🛠️ **개발자 정보**

### 주요 변경사항

#### `global_settings.gd`
- `SERVER_URLS` 배열로 서버 목록 관리
- `current_server_index`로 현재 서버 추적
- `get_next_server_url()` 폴백 함수
- `reset_server_index()` 리셋 함수

#### `network_manager.gd`
- `_attempt_connection()` 연결 시도 함수
- `_handle_connection_failure()` 실패 처리 함수
- 자동 폴백 로직 구현

#### `main_menu.gd`
- 서버 이름 표시 개선
- 연결 재시도 시 인덱스 리셋

### 디버그 정보

콘솔에서 다음과 같은 로그를 확인할 수 있습니다:

```
DEBUG: 서버 연결 시도 중... (Railway)
DEBUG: 서버 URL: wss://web-production-db70.up.railway.app/ws
DEBUG: Railway 서버 연결 실패
DEBUG: 다음 서버로 폴백 시도: Local
DEBUG: 다음 서버 URL: ws://127.0.0.1:8000/ws
DEBUG: Local 서버에 성공적으로 연결되었습니다! (소요시간: 0.5초)
```

## 🧪 **테스트 방법**

### 1. 테스트 스크립트 실행
```bash
# Godot에서 test_server_fallback.gd 실행
```

### 2. 실제 연결 테스트
1. Railway 서버 중단 시뮬레이션
2. 클라이언트 실행
3. 자동 폴백 확인

### 3. 로컬 서버 테스트
1. 로컬 서버 실행: `runserver.cmd`
2. 클라이언트에서 "Connect" 버튼 클릭
3. 로컬 서버 연결 확인

## 🔍 **문제 해결**

### Railway 서버 연결 실패
- Railway 서비스 상태 확인
- 네트워크 연결 확인
- 자동으로 로컬 서버로 폴백됨

### 로컬 서버 연결 실패
- 로컬 서버 실행 여부 확인
- 포트 8000 사용 가능 여부 확인
- 방화벽 설정 확인

### 모든 서버 연결 실패
- 네트워크 연결 상태 확인
- 서버 상태 확인
- "Connect" 버튼으로 재시도

## 📝 **환경별 설정**

### 개발 환경
- Railway 서버 우선 시도
- 실패 시 로컬 서버로 폴백
- 디버그 로그 활성화

### 프로덕션 환경
- Railway 서버만 사용
- 로컬 서버 폴백 비활성화 가능
- 최적화된 연결 설정

## 🎯 **장점**

1. **높은 가용성**: 서버 장애 시 자동 복구
2. **개발 편의성**: 로컬 개발 시 자동 전환
3. **사용자 경험**: 연결 실패 시 투명한 폴백
4. **유지보수성**: 서버 추가/제거 용이

---

**참고**: 이 기능은 네트워크 연결의 안정성을 크게 향상시킵니다. Railway 서버가 일시적으로 사용할 수 없어도 로컬 서버를 통해 게임을 계속할 수 있습니다. 