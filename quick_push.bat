@echo off
echo HoloDuel Server - Quick Push
echo ============================

REM 모든 변경사항 추가 및 커밋
git add .
git commit -m "Update server files - %date% %time%"

REM GitHub에 push
git push origin main

echo.
echo Push 완료!
pause 