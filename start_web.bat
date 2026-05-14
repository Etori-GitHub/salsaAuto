@echo off
chcp 65001 >nul
echo 启动 salsaAuto Web 服务...
echo.
python -m src web --host 127.0.0.1 --port 8080
pause