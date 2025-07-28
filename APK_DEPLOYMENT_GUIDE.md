# HoloDuel APK 배포 가이드

## 🚀 APK 배포 전 확인사항

### 1. 서버 URL 설정 확인

**현재 설정된 서버 URL:**
```gdscript
// global_settings.gd에서 확인
const railway_url = "wss://your-railway-url.railway.app/ws"
```

**Railway 서버 URL로 변경해야 할 경우:**
1. Railway에서 배포된 서버 URL 확인
2. `holocardclient-main/globals/global_settings.gd` 파일 수정
3. `railway_url` 상수를 실제 URL로 변경

### 2. 서버 연결 테스트

**로컬에서 테스트:**
```bash
# 로컬 서버 실행
cd holocardserver-main
python runserver.cmd
```

**Railway 서버 테스트:**
```bash
# 헬스체크 확인
curl https://your-railway-url.railway.app/health

# WebSocket 연결 테스트
wscat -c wss://your-railway-url.railway.app/ws
```

## 📱 APK 빌드 및 배포

### 1. Godot에서 APK 빌드

1. **Godot 4.3+ 실행**
2. **프로젝트 열기**: `holocardclient-main/project.godot`
3. **빌드 설정 확인**:
   - Project → Project Settings → Export
   - Android 설정 확인
   - Keystore 설정 (필요시)

4. **APK 빌드**:
   - Project → Export
   - Android 선택
   - "Export Project" 클릭
   - APK 파일 저장

### 2. 빌드 타입별 서버 설정

#### Debug 빌드 (개발용)
- **서버 URL**: `ws://127.0.0.1:8000/ws` (로컬 서버)
- **용도**: 개발 및 테스트

#### Release 빌드 (배포용)
- **서버 URL**: `wss://your-railway-url.railway.app/ws` (Railway 서버)
- **용도**: 실제 배포

### 3. 서버 URL 변경 방법

#### 방법 1: 코드 수정
```gdscript
// global_settings.gd 수정
const railway_url = "wss://실제-railway-url.railway.app/ws"
```

#### 방법 2: 빌드 시점에 결정
```gdscript
// 빌드 타입에 따라 자동 선택
if OS.is_debug_build():
    return local_url  // 로컬 서버
else:
    return railway_url  // Railway 서버
```

## 🔧 서버 연결 확인 방법

### 1. 앱 내에서 확인
- 메인 메뉴 하단에 서버 상태 표시
- 연결 중: "Connecting to server... [URL]"
- 연결됨: "Connected [URL]"
- 연결 끊김: "Disconnected from server"

### 2. 콘솔 로그 확인
```
DEBUG: 서버 연결을 시도합니다...
DEBUG: 서버 URL: wss://your-railway-url.railway.app/ws
DEBUG: 빌드 타입: Release
DEBUG: UseAzureServerAlways: false
DEBUG: 서버에 성공적으로 연결되었습니다! (소요시간: 1.2초)
```

### 3. 서버 URL 확인 스크립트
```bash
# check_server_url.gd 스크립트 실행
# Godot에서 스크립트를 실행하여 서버 URL 확인
```

## 📋 배포 체크리스트

### Railway 서버 배포 확인
- [ ] Railway에서 서버 배포 완료
- [ ] 헬스체크 엔드포인트 정상 작동
- [ ] WebSocket 연결 정상 작동
- [ ] 서버 URL 확인 및 복사

### 클라이언트 설정 확인
- [ ] `global_settings.gd`에서 Railway URL 설정
- [ ] `UseAzureServerAlways` 설정 확인
- [ ] 빌드 타입별 서버 URL 동작 확인

### APK 빌드 및 테스트
- [ ] Debug 빌드로 로컬 서버 연결 테스트
- [ ] Release 빌드로 Railway 서버 연결 테스트
- [ ] APK 파일 생성 및 저장
- [ ] 실제 기기에서 테스트

## 🚨 문제 해결

### 일반적인 문제들

#### 1. 서버 연결 실패
**증상**: "Disconnected from server" 메시지
**해결방법**:
- Railway 서버가 실행 중인지 확인
- 서버 URL이 올바른지 확인
- 네트워크 연결 상태 확인

#### 2. WebSocket 연결 오류
**증상**: 연결 시간 초과
**해결방법**:
- Railway 서버 로그 확인
- 방화벽 설정 확인
- SSL 인증서 문제 확인

#### 3. 빌드 타입별 URL 문제
**증상**: Debug/Release에서 다른 서버에 연결
**해결방법**:
- `global_settings.gd`의 URL 설정 확인
- `UseAzureServerAlways` 설정 확인

### 로그 확인 방법

#### Godot 콘솔 로그
```
# 연결 시도
DEBUG: 서버 연결을 시도합니다...
DEBUG: 서버 URL: wss://your-railway-url.railway.app/ws

# 연결 성공
DEBUG: 서버에 성공적으로 연결되었습니다! (소요시간: 1.2초)

# 연결 실패
DEBUG: WebSocket 연결이 종료되었습니다!
```

#### Railway 서버 로그
```bash
# Railway CLI로 로그 확인
railway logs --follow
```

## 📞 지원

### 문제 발생 시
1. Godot 콘솔 로그 확인
2. Railway 서버 로그 확인
3. 네트워크 연결 상태 확인
4. 서버 URL 설정 확인

### 유용한 링크
- [Railway Documentation](https://docs.railway.app/)
- [Godot Android Export](https://docs.godotengine.org/en/stable/tutorials/export/exporting_for_android.html)
- [WebSocket Testing](https://websocket.org/echo.html) 