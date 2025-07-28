# Android APK Railway 서버 연결 문제 해결 가이드

## 🚨 **Android APK에서 Railway 서버 접속 안됨**

Android APK에서 Railway 서버에 연결되지 않는 문제를 해결하는 방법을 안내합니다.

## 🔍 **문제 진단**

### 1. Android 환경 확인
```gdscript
# Godot에서 확인
print("플랫폼: ", OS.get_name())  # "Android" 출력
print("Android 환경: ", GlobalSettings.is_android_export())  # true 출력
```

### 2. 서버 URL 설정 확인
```gdscript
# 현재 설정된 서버 URL
const SERVER_URLS = [
    "wss://web-production-db70.up.railway.app/ws",  # Railway 서버
    "ws://127.0.0.1:8000/ws"  # 로컬 서버 (Android에서는 사용 안함)
]
```

## 🛠️ **해결 방법**

### 1. Android 권한 설정 확인

#### **AndroidManifest.xml 확인**
```xml
<uses-permission android:name="android.permission.INTERNET" />
<uses-permission android:name="android.permission.ACCESS_NETWORK_STATE" />
```

#### **Godot 프로젝트 설정**
1. Project → Project Settings → Android
2. Permissions 탭에서 확인:
   - `INTERNET` 권한 활성화
   - `ACCESS_NETWORK_STATE` 권한 활성화

### 2. 네트워크 보안 설정

#### **network_security_config.xml 생성**
```xml
<?xml version="1.0" encoding="utf-8"?>
<network-security-config>
    <domain-config cleartextTrafficPermitted="true">
        <domain includeSubdomains="true">web-production-db70.up.railway.app</domain>
    </domain-config>
</network-security-config>
```

#### **AndroidManifest.xml에 추가**
```xml
<application
    android:networkSecurityConfig="@xml/network_security_config"
    ...>
```

### 3. WebSocket 연결 타임아웃 설정

#### **연결 타임아웃 증가**
```gdscript
# network_manager.gd에서
var connection_timeout = 30.0  # 30초로 증가
```

### 4. 모바일 네트워크 환경 고려

#### **연결 재시도 로직**
```gdscript
# 연결 실패 시 재시도
var max_retry_count = 3
var retry_delay = 2.0  # 2초 대기
```

## 🧪 **테스트 방법**

### 1. Android 연결 테스트 스크립트
```bash
# Godot에서 test_android_connection.gd 실행
# Android 디바이스에서 로그 확인
```

### 2. ADB 로그 확인
```bash
# Android 디바이스 연결 후
adb logcat | grep -i godot
adb logcat | grep -i websocket
```

### 3. 네트워크 연결 테스트
```bash
# Android 디바이스에서
ping web-production-db70.up.railway.app
```

## 🔧 **일반적인 Android 연결 문제**

### 1. 인터넷 권한 문제
**증상**: 연결 시도 자체가 안됨
**해결**: AndroidManifest.xml에서 INTERNET 권한 확인

### 2. 방화벽/보안 앱 차단
**증상**: 연결 시도는 되지만 실패
**해결**: 
- 방화벽 앱에서 Godot 앱 허용
- 보안 앱 설정 확인
- 기업 보안 정책 확인

### 3. 모바일 데이터 제한
**증상**: Wi-Fi에서는 작동하지만 모바일 데이터에서 안됨
**해결**:
- 모바일 데이터 사용량 확인
- 데이터 절약 모드 비활성화
- 앱별 데이터 사용량 설정 확인

### 4. 네트워크 타임아웃
**증상**: 연결 시도 중 타임아웃
**해결**:
- 연결 타임아웃 시간 증가
- 재시도 로직 구현
- 네트워크 상태 확인

## 📋 **체크리스트**

### Android 권한 확인
- [ ] INTERNET 권한 활성화
- [ ] ACCESS_NETWORK_STATE 권한 활성화
- [ ] 네트워크 보안 설정 확인

### 네트워크 환경 확인
- [ ] 인터넷 연결 상태 확인
- [ ] Wi-Fi/모바일 데이터 모두 테스트
- [ ] 방화벽/보안 앱 설정 확인

### 앱 설정 확인
- [ ] Godot Android 설정 확인
- [ ] WebSocket 연결 타임아웃 설정
- [ ] 재시도 로직 구현

### 서버 연결 확인
- [ ] Railway 서버 상태 확인
- [ ] WebSocket 엔드포인트 테스트
- [ ] CORS 설정 확인

## 🚀 **디버깅 정보**

### Android 로그 확인
```bash
# 개발자 옵션에서 USB 디버깅 활성화
adb logcat -s Godot
```

### 네트워크 상태 확인
```gdscript
# Godot에서 실행
print("네트워크 기능: ", OS.has_feature("network"))
print("Android API Level: ", OS.get_environment("ANDROID_API_LEVEL"))
```

### WebSocket 상태 확인
```gdscript
# 연결 상태 로깅
print("WebSocket 상태: ", socket.get_ready_state())
print("연결 코드: ", socket.get_close_code())
print("연결 이유: ", socket.get_close_reason())
```

## 📞 **추가 지원**

### 문제가 지속되는 경우
1. **로그 수집**: ADB 로그캣으로 상세 로그 수집
2. **네트워크 테스트**: 다른 앱에서 동일 서버 연결 테스트
3. **디바이스 변경**: 다른 Android 디바이스에서 테스트
4. **네트워크 변경**: 다른 네트워크 환경에서 테스트

### 개발자 도구
- **Android Studio**: 네트워크 모니터링
- **Charles Proxy**: 네트워크 트래픽 분석
- **Wireshark**: 패킷 분석

---

**참고**: Android 환경에서는 네트워크 연결이 데스크톱보다 복잡할 수 있습니다. 권한, 보안 설정, 네트워크 환경을 종합적으로 확인해야 합니다. 