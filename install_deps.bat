@echo off
chcp 65001 >nul
echo.
echo ========================================
echo   salsaAuto 依赖安装脚本
echo ========================================
echo.

python --version >nul 2>&1
if errorlevel 1 (
    echo [错误] 未检测到 Python，请先安装 Python 3.8+
    pause
    exit /b 1
)

echo [信息] Python 版本:
python --version
echo.

echo [步骤 1/2] 升级 pip...
python -m pip install --upgrade pip -q
echo.

echo [步骤 2/2] 安装项目依赖...
python -m pip install -r requirements.txt
if errorlevel 1 (
    echo.
    echo [错误] 依赖安装失败
    pause
    exit /b 1
)

echo.
echo ========================================
echo   安装完成！
echo ========================================
echo.
echo 运行 start_web.bat 启动服务
echo.
pause
