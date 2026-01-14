@echo off
chcp 65001 > nul
title 谷歌账号管理系统 - 打包工具
color 0B

:: 保存package目录的绝对路径
set PACKAGE_DIR=%~dp0
:: 去掉末尾的反斜杠
if "%PACKAGE_DIR:~-1%"=="\" set PACKAGE_DIR=%PACKAGE_DIR:~0,-1%
:: 项目根目录
for %%I in ("%PACKAGE_DIR%\..") do set ROOT_DIR=%%~fI

:: 切换到项目根目录
cd /d "%ROOT_DIR%"

:menu
cls
echo ========================================
echo   谷歌账号管理系统 - 打包工具
echo ========================================
echo.
echo 项目根目录: %ROOT_DIR%
echo 打包配置目录: %PACKAGE_DIR%
echo.
if not exist "requirements.txt" (
    echo [警告] 未找到 requirements.txt
    echo.
)
echo [1] 安装依赖
echo [2] 启动程序（开发测试）
echo [3] 打包成 EXE
echo [4] 制作用户部署包
echo [0] 退出
echo.
set /p choice=请选择 (0-4): 

if "%choice%"=="1" goto install
if "%choice%"=="2" goto run
if "%choice%"=="3" goto build
if "%choice%"=="4" goto package_app
if "%choice%"=="0" exit
goto menu

:install
cls
echo ========================================
echo   安装依赖
echo ========================================
echo.
if not exist "requirements.txt" (
    echo [错误] 找不到 requirements.txt 文件！
    echo 当前目录: %cd%
    echo.
    pause
    goto menu
)
echo 正在升级 pip...
python -m pip install --upgrade pip
echo.
echo 正在安装依赖包...
pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
if %errorlevel% equ 0 (
    echo.
    echo ✓ 依赖安装完成
) else (
    echo.
    echo × 依赖安装失败
)
pause
goto menu

:run
cls
echo ========================================
echo   启动程序
echo ========================================
echo.
echo 访问地址: http://localhost:5000
echo 按 Ctrl+C 停止
echo.
if not exist "main.py" (
    echo [错误] 找不到 main.py 文件！
    pause
    goto menu
)
python main.py
pause
goto menu

:build
cls
echo ========================================
echo   打包成 EXE
echo ========================================
echo.
echo 正在安装 PyInstaller...
pip install pyinstaller -i https://pypi.tuna.tsinghua.edu.cn/simple >nul 2>&1

echo 清理旧文件...
if exist build rmdir /s /q build
if exist dist rmdir /s /q dist

echo 开始打包（这可能需要几分钟）...
echo.
echo 使用配置文件: %PACKAGE_DIR%\build.spec
echo.

:: 直接使用完整路径执行 pyinstaller
pyinstaller "%PACKAGE_DIR%\build.spec" --clean

if %errorlevel% equ 0 (
    echo.
    echo ========================================
    echo ✓ 打包成功！
    echo ========================================
    echo 位置: %ROOT_DIR%\dist\谷歌账号管理系统\
    echo.
) else (
    echo.
    echo × 打包失败，请检查错误信息
)
pause
goto menu

:package_app
cls
echo ========================================
echo   制作用户部署包
echo ========================================
echo.

if not exist "dist\谷歌账号管理系统\谷歌账号管理系统.exe" (
    echo × 找不到打包后的程序
    echo 请先执行 [3] 打包成 EXE
    pause
    goto menu
)

set PKG_DIR=谷歌账号管理系统_部署包
echo 清理旧文件...
if exist "%PKG_DIR%" rmdir /s /q "%PKG_DIR%"
mkdir "%PKG_DIR%"

echo 复制程序文件...
xcopy "dist\谷歌账号管理系统\*" "%PKG_DIR%\" /E /I /Y >nul

echo 创建启动脚本...
(
echo @echo off
echo chcp 65001 ^> nul
echo title 谷歌账号管理系统
echo color 0B
echo.
echo ========================================
echo   谷歌账号管理系统
echo ========================================
echo.
echo 正在启动...
echo 启动后请访问: http://localhost:5000
echo.
echo 按 Ctrl+C 可停止程序
echo ========================================
echo.
echo :: 检查配置文件
echo if not exist config.json ^(
echo     if exist config.json.example ^(
echo         echo [提示] 首次运行，正在创建配置文件...
echo         copy config.json.example config.json ^>nul
echo         echo.
echo         echo 请编辑 config.json 文件配置您的数据库信息
echo         echo 配置完成后重新运行本脚本
echo         echo.
echo         pause
echo         exit /b
echo     ^) else ^(
echo         echo [错误] 找不到配置文件模板 config.json.example
echo         pause
echo         exit /b 1
echo     ^)
echo ^)
echo.
echo "谷歌账号管理系统.exe"
echo.
echo if %%errorlevel%% neq 0 ^(
echo     echo.
echo     echo ========================================
echo     echo [错误] 程序异常退出！
echo     echo ========================================
echo     echo.
echo     echo 可能的原因：
echo     echo 1. MySQL 服务未启动 ^(执行: net start MySQL^)
echo     echo 2. config.json 配置错误
echo     echo 3. 数据库未创建
echo     echo.
echo     pause
echo ^)
) > "%PKG_DIR%\启动.bat"

echo 复制说明文档...
if exist "%PACKAGE_DIR%\使用说明.txt" (
    copy "%PACKAGE_DIR%\使用说明.txt" "%PKG_DIR%\" >nul
)

echo.
echo ========================================
echo ✓ 部署包制作完成
echo ========================================
echo 位置: %ROOT_DIR%\%PKG_DIR%\
echo.
echo 是否创建 ZIP 压缩包？(Y/N)
set /p zip_choice=
if /i "%zip_choice%"=="Y" (
    echo 正在创建压缩包...
    powershell -Command "Compress-Archive -Path '%PKG_DIR%' -DestinationPath '%PKG_DIR%.zip' -Force"
    if exist "%PKG_DIR%.zip" (
        echo ✓ 已创建 %PKG_DIR%.zip
    ) else (
        echo × 压缩包创建失败
    )
)
echo.
pause
goto menu
