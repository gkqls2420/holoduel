@echo off
echo ========================================
echo HoloDuel Server - GitHub Push Script
echo ========================================
echo.

REM 현재 디렉토리 확인
echo 현재 디렉토리: %CD%
echo.

REM Git 상태 확인
echo 1. Git 상태 확인 중...
git status
echo.

REM 변경사항이 있는지 확인
git diff --quiet
if %errorlevel% equ 0 (
    echo 변경사항이 없습니다.
    echo.
    set /p continue="계속 진행하시겠습니까? (y/n): "
    if /i not "%continue%"=="y" goto :end
) else (
    echo 변경사항이 발견되었습니다.
)

REM 모든 변경사항 추가
echo 2. 변경사항을 스테이징 영역에 추가 중...
git add .
if %errorlevel% neq 0 (
    echo ❌ Git add 실패
    pause
    exit /b 1
)
echo ✅ 변경사항 추가 완료
echo.

REM 커밋 메시지 입력
echo 3. 커밋 메시지를 입력하세요:
set /p commit_message="커밋 메시지: "
if "%commit_message%"=="" (
    echo 기본 커밋 메시지를 사용합니다: "Update server files"
    set commit_message=Update server files
)

REM 커밋 생성
echo 4. 커밋 생성 중...
git commit -m "%commit_message%"
if %errorlevel% neq 0 (
    echo ❌ 커밋 실패
    pause
    exit /b 1
)
echo ✅ 커밋 완료
echo.

REM 원격 저장소 확인
echo 5. 원격 저장소 확인 중...
git remote -v
echo.

REM Push 실행
echo 6. GitHub에 push 중...
git push origin main
if %errorlevel% neq 0 (
    echo ❌ Push 실패
    echo.
    echo 가능한 해결 방법:
    echo 1. GitHub 인증 정보 확인
    echo 2. 원격 저장소 URL 확인
    echo 3. 브랜치 이름 확인
    echo.
    pause
    exit /b 1
)

echo.
echo ========================================
echo ✅ GitHub Push 완료!
echo ========================================
echo.
echo 저장소: https://github.com/gkqls2420/holoduel
echo 커밋 메시지: %commit_message%
echo.

:end
pause 