# HTML5 Export 문제 해결 가이드

## 🚨 **"Failed to fetch" 오류 해결**

HTML5 export에서 "Failed to fetch" 오류가 발생하는 경우, 다음과 같은 단계로 문제를 해결할 수 있습니다.

## 🔍 **문제 진단**

### 1. 브라우저 개발자 도구 확인
1. F12 키를 눌러 개발자 도구 열기
2. **Console** 탭에서 오류 메시지 확인
3. **Network** 탭에서 WebSocket 연결 상태 확인

### 2. 일반적인 오류 메시지
```
Failed to fetch
WebSocket connection failed
CORS error
```

## 🛠️ **해결 방법**

### 1. CORS 설정 확인
서버의 CORS 설정이 올바른지 확인:

```python
# server.py에서 확인
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"],
)
```

### 2. WebSocket 연결 확인
브라우저에서 직접 WebSocket 연결 테스트:

```javascript
// 브라우저 콘솔에서 실행
const ws = new WebSocket('wss://web-production-db70.up.railway.app/ws');
ws.onopen = () => console.log('Connected!');
ws.onerror = (error) => console.log('Error:', error);
ws.onclose = () => console.log('Disconnected');
```

### 3. 서버 상태 확인
```bash
# 서버 헬스체크
curl https://web-production-db70.up.railway.app/health
```

## 🎯 **HTML5 전용 설정**

### 서버 URL 설정
HTML5 환경에서는 Railway 서버만 사용됩니다:

```gdscript
# global_settings.gd
func get_server_url() -> String:
    if is_html5_export():
        return SERVER_URLS[0]  # Railway 서버만 사용
    # ...
```

### 폴백 비활성화
HTML5에서는 로컬 서버 폴백이 비활성화됩니다:

```gdscript
func has_more_servers() -> bool:
    if is_html5_export():
        return false  # 폴백 비활성화
    # ...
```

## 🧪 **테스트 방법**

### 1. HTML5 연결 테스트
```bash
# Godot에서 test_html5_connection.gd 실행
# HTML5 export 후 브라우저에서 확인
```

### 2. 브라우저별 테스트
- **Chrome**: 가장 안정적
- **Firefox**: WebSocket 지원 확인
- **Safari**: CORS 정책 확인
- **Edge**: 최신 버전 사용 권장

### 3. 로컬 테스트
```bash
# 로컬 서버 실행
cd holocardserver-main
python -m uvicorn server:app --host 0.0.0.0 --port 8000

# 브라우저에서 접속
http://localhost:8000/game/index.html
```

## 🔧 **고급 문제 해결**

### 1. HTTPS/WSS 요구사항
일부 브라우저는 보안 연결을 요구합니다:
- Railway 서버는 HTTPS/WSS 사용
- 로컬 테스트 시 HTTP/WS 사용 가능

### 2. 방화벽/프록시 설정
- 회사 네트워크에서 WebSocket 차단 가능
- 프록시 설정 확인
- 방화벽에서 포트 443 허용

### 3. 브라우저 캐시 문제
- 브라우저 캐시 삭제
- 하드 새로고침 (Ctrl+F5)
- 시크릿 모드에서 테스트

## 📋 **체크리스트**

### 서버 측 확인사항
- [ ] Railway 서버가 실행 중인지 확인
- [ ] CORS 설정이 올바른지 확인
- [ ] WebSocket 엔드포인트가 정상인지 확인
- [ ] 헬스체크 엔드포인트 응답 확인

### 클라이언트 측 확인사항
- [ ] HTML5 환경 감지가 정상인지 확인
- [ ] Railway 서버 URL이 올바른지 확인
- [ ] WebSocket 연결 시도가 정상인지 확인
- [ ] 브라우저 콘솔에서 오류 메시지 확인

### 네트워크 확인사항
- [ ] 인터넷 연결 상태 확인
- [ ] Railway 서비스 상태 확인
- [ ] DNS 해석이 정상인지 확인
- [ ] 방화벽/프록시 설정 확인

## 🚀 **성공적인 HTML5 Export**

### 정상 작동 시나리오
1. **서버 연결**: Railway 서버에 성공적으로 연결
2. **게임 로드**: 모든 게임 리소스가 정상 로드
3. **WebSocket 통신**: 실시간 게임 통신 정상 작동
4. **멀티플레이어**: 다른 플레이어와 매치 가능

### 예상되는 로그
```
DEBUG: HTML5 환경 감지됨 - Railway 서버만 사용
DEBUG: 서버 연결 시도 중... (Railway)
DEBUG: Railway 서버에 성공적으로 연결되었습니다! (소요시간: 1.2초)
```

## 📞 **추가 지원**

문제가 지속되는 경우:
1. 브라우저 개발자 도구의 오류 메시지 캡처
2. 서버 로그 확인 (Railway 대시보드)
3. 네트워크 연결 상태 확인
4. 다른 브라우저에서 테스트

---

**참고**: HTML5 export는 웹 브라우저의 보안 정책과 CORS 정책을 따라야 합니다. Railway 서버는 이러한 정책을 준수하도록 설정되어 있습니다. 