# HTML5 Export 가이드

## 🚨 "Failed to fetch" 오류 해결

HTML5 export에서 발생하는 "Failed to fetch" 오류는 CORS (Cross-Origin Resource Sharing) 문제입니다.

### ✅ 해결 완료된 사항

1. **Railway 서버에 CORS 설정 추가됨**
   - 모든 origin 허용 (`allow_origins=["*"]`)
   - WebSocket CORS 헤더 설정
   - 자동 배포 완료

2. **서버 재배포 완료**
   - GitHub에 CORS 설정 푸시됨
   - Railway에서 자동 배포 진행 중

### 🔧 HTML5 Export 설정

#### 1. Godot에서 HTML5 Export 설정

1. **Project → Project Settings → Export**
2. **HTML5 / WebGL** 선택
3. **Export Path** 설정
4. **Export Project** 클릭

#### 2. HTML5 Export 옵션

**권장 설정:**
- **HTML → Head Include**: 비워두기
- **HTML → Custom HTML Shell**: 기본값 사용
- **Progressive Web App**: 필요시 활성화

#### 3. 서버 URL 확인

HTML5 export에서도 동일한 서버 URL을 사용합니다:
```
wss://web-production-db70.up.railway.app/ws
```

### 🌐 HTML5 배포 방법

#### 방법 1: 로컬 서버로 테스트
```bash
# Python HTTP 서버 실행
cd export_directory
python -m http.server 8000

# 브라우저에서 접속
http://localhost:8000
```

#### 방법 2: GitHub Pages 배포
1. GitHub 저장소에 HTML5 파일 업로드
2. Settings → Pages → Source 설정
3. 자동 배포 완료

#### 방법 3: Netlify/Vercel 배포
1. HTML5 파일을 Netlify/Vercel에 업로드
2. 자동 배포 완료

### 🔍 문제 해결

#### 1. CORS 오류 확인
**브라우저 개발자 도구 (F12) → Console**에서 확인:
```
Access to fetch at 'wss://web-production-db70.up.railway.app/ws' 
from origin 'http://localhost:8000' has been blocked by CORS policy
```

#### 2. WebSocket 연결 확인
**브라우저 개발자 도구 → Network**에서 확인:
- WebSocket 연결 상태
- 연결 실패 시 오류 메시지

#### 3. 서버 상태 확인
```bash
# 헬스체크
curl https://web-production-db70.up.railway.app/health

# WebSocket 테스트
wscat -c wss://web-production-db70.up.railway.app/ws
```

### 📱 HTML5 vs APK 비교

| 기능 | HTML5 | APK |
|------|-------|-----|
| 배포 | 웹 서버 | Google Play |
| 접근성 | 브라우저 | 앱 설치 |
| 성능 | 브라우저 의존 | 네이티브 |
| 업데이트 | 즉시 반영 | 앱 업데이트 필요 |
| CORS | 필요 | 불필요 |

### 🚀 권장 워크플로우

#### 개발 단계
1. **로컬 테스트**: HTML5 export + 로컬 서버
2. **서버 테스트**: HTML5 export + Railway 서버
3. **배포**: GitHub Pages 또는 Netlify

#### 프로덕션 단계
1. **APK 배포**: Google Play Store
2. **HTML5 배포**: 웹 버전 제공

### 📞 추가 지원

#### 문제 발생 시
1. 브라우저 개발자 도구 확인
2. Railway 서버 로그 확인
3. CORS 설정 재확인

#### 유용한 도구
- [WebSocket Tester](https://websocket.org/echo.html)
- [CORS Tester](https://cors-anywhere.herokuapp.com/)
- [Browser DevTools](https://developer.chrome.com/docs/devtools/)

### ✅ 확인 체크리스트

- [ ] Railway 서버 CORS 설정 완료
- [ ] HTML5 export 성공
- [ ] 로컬에서 테스트 완료
- [ ] Railway 서버 연결 확인
- [ ] 웹 배포 완료 