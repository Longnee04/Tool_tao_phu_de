@echo off
chcp 65001 >nul 2>&1
title 🎬 Auto Subtitle Generator - Đang khởi động...
color 0B

:: ============================================================
:: Run_Tool.bat - Script khởi động 1-Click cho Auto Subtitle Generator
::
:: Người dùng chỉ cần nhấp đúp file này để chạy ứng dụng.
:: Script sẽ tự động:
::   1. Kiểm tra Python đã cài đặt chưa
::   2. Tạo môi trường ảo (venv) nếu chưa có
::   3. Cài đặt thư viện nếu là lần đầu
::   4. Khởi chạy Streamlit và mở trình duyệt
:: ============================================================

echo.
echo  ╔══════════════════════════════════════════════════════╗
echo  ║                                                      ║
echo  ║      🎬  AUTO SUBTITLE GENERATOR  v1.0               ║
echo  ║      Công cụ tạo phụ đề tự động                      ║
echo  ║                                                      ║
echo  ╚══════════════════════════════════════════════════════╝
echo.

:: --- Xác định thư mục gốc của dự án (nơi chứa file .bat này) ---
cd /d "%~dp0"
set "PROJECT_DIR=%~dp0"
set "VENV_DIR=%PROJECT_DIR%venv"
set "REQUIREMENTS=%PROJECT_DIR%requirements.txt"
set "INSTALLED_FLAG=%VENV_DIR%\.installed"

:: --- Tự động thêm đường dẫn Python 3.12 mặc định trên Windows vào PATH ---
set "PATH=%LOCALAPPDATA%\Programs\Python\Python312;%LOCALAPPDATA%\Programs\Python\Python312\Scripts;%PATH%"


:: ============================================================
:: BƯỚC 1: KIỂM TRA PYTHON
:: ============================================================
echo  [1/4] Đang kiểm tra Python...

:: Thử tìm Python trong PATH
where python >nul 2>&1
if %ERRORLEVEL% EQU 0 (
    :: Kiểm tra phiên bản Python
    for /f "tokens=*" %%i in ('python --version 2^>^&1') do set PYTHON_VER=%%i
    echo        ✅ Đã tìm thấy: %PYTHON_VER%
    set "PYTHON_CMD=python"
    goto :check_python_ok
)

:: Thử tìm python3
where python3 >nul 2>&1
if %ERRORLEVEL% EQU 0 (
    for /f "tokens=*" %%i in ('python3 --version 2^>^&1') do set PYTHON_VER=%%i
    echo        ✅ Đã tìm thấy: %PYTHON_VER%
    set "PYTHON_CMD=python3"
    goto :check_python_ok
)

:: Thử tìm Python ở đường dẫn mặc định trên Windows
set "PY_PATHS=%LOCALAPPDATA%\Programs\Python\Python312\python.exe;%LOCALAPPDATA%\Programs\Python\Python311\python.exe;%LOCALAPPDATA%\Programs\Python\Python310\python.exe;%LOCALAPPDATA%\Programs\Python\Python39\python.exe"

for %%p in (%PY_PATHS%) do (
    if exist "%%p" (
        for /f "tokens=*" %%i in ('"%%p" --version 2^>^&1') do set PYTHON_VER=%%i
        echo        ✅ Đã tìm thấy: %PYTHON_VER% tại %%p
        set "PYTHON_CMD=%%p"
        goto :check_python_ok
    )
)

:: Không tìm thấy Python
echo.
echo  ╔══════════════════════════════════════════════════════╗
echo  ║  ❌ KHÔNG TÌM THẤY PYTHON TRÊN MÁY TÍNH!           ║
echo  ║                                                      ║
echo  ║  Bạn cần cài đặt Python trước khi sử dụng tool.     ║
echo  ║                                                      ║
echo  ║  📥 Cách cài đặt:                                    ║
echo  ║   1. Truy cập: https://www.python.org/downloads/     ║
echo  ║   2. Tải bản Python 3.10 trở lên                     ║
echo  ║   3. Khi cài đặt, NHẤT ĐỊNH phải tích chọn           ║
echo  ║      ☑ "Add Python to PATH"                          ║
echo  ║   4. Cài xong, khởi động lại máy rồi chạy lại       ║
echo  ║      file này.                                       ║
echo  ║                                                      ║
echo  ╚══════════════════════════════════════════════════════╝
echo.
echo  Đang mở trang tải Python cho bạn...
start https://www.python.org/downloads/
echo.
pause
exit /b 1

:check_python_ok

:: ============================================================
:: BƯỚC 2: TẠO MÔI TRƯỜNG ẢO (VENV)
:: ============================================================
echo  [2/4] Đang kiểm tra môi trường ảo (Virtual Environment)...

if exist "%VENV_DIR%\Scripts\activate.bat" (
    echo        ✅ Môi trường ảo đã tồn tại.
) else (
    echo        📦 Đang tạo môi trường ảo lần đầu...
    echo        (Quá trình này có thể mất 30 giây - 1 phút)
    %PYTHON_CMD% -m venv "%VENV_DIR%"
    if %ERRORLEVEL% NEQ 0 (
        echo.
        echo  ❌ Không thể tạo môi trường ảo.
        echo     Hãy thử chạy lại với quyền Administrator.
        pause
        exit /b 1
    )
    echo        ✅ Tạo môi trường ảo thành công!
    :: Xóa flag cài đặt cũ (nếu có) để buộc cài lại thư viện
    if exist "%INSTALLED_FLAG%" del "%INSTALLED_FLAG%"
)

:: Kích hoạt môi trường ảo
call "%VENV_DIR%\Scripts\activate.bat"
echo        ✅ Đã kích hoạt môi trường ảo.

:: ============================================================
:: BƯỚC 3: CÀI ĐẶT THƯ VIỆN (CHỈ LẦN ĐẦU)
:: ============================================================
echo  [3/4] Đang kiểm tra thư viện...

if exist "%INSTALLED_FLAG%" (
    echo        ✅ Thư viện đã được cài đặt từ trước.
) else (
    echo.
    echo  ╔══════════════════════════════════════════════════════╗
    echo  ║  📦 ĐANG CÀI ĐẶT THƯ VIỆN LẦN ĐẦU...             ║
    echo  ║                                                      ║
    echo  ║  Quá trình này cần kết nối Internet và có thể        ║
    echo  ║  mất từ 3-10 phút tùy tốc độ mạng.                  ║
    echo  ║                                                      ║
    echo  ║  ⚠️  VUI LÒNG KHÔNG TẮT CỬA SỔ NÀY!                ║
    echo  ╚══════════════════════════════════════════════════════╝
    echo.

    :: Nâng cấp pip trước
    echo  → Đang cập nhật pip...
    python -m pip install --upgrade pip --quiet
    
    :: Cài đặt thư viện từ requirements.txt
    echo  → Đang cài đặt thư viện từ requirements.txt...
    pip install -r "%REQUIREMENTS%"
    
    if %ERRORLEVEL% NEQ 0 (
        echo.
        echo  ❌ Cài đặt thư viện thất bại!
        echo     Nguyên nhân có thể:
        echo       - Không có kết nối Internet
        echo       - Đĩa cứng hết dung lượng
        echo       - Xung đột quyền truy cập
        echo.
        echo     Hãy kiểm tra và thử chạy lại.
        pause
        exit /b 1
    )

    :: Tạo file đánh dấu đã cài thành công
    echo installed> "%INSTALLED_FLAG%"
    echo.
    echo  ╔══════════════════════════════════════════════════════╗
    echo  ║  ✅ CÀI ĐẶT THƯ VIỆN HOÀN TẤT!                    ║
    echo  ║  Từ lần sau, tool sẽ khởi động nhanh hơn.           ║
    echo  ╚══════════════════════════════════════════════════════╝
    echo.
)

:: ============================================================
:: BƯỚC 4: KHỞI CHẠY ỨNG DỤNG
:: ============================================================
echo  [4/4] Đang khởi chạy ứng dụng...
echo.
echo  ╔══════════════════════════════════════════════════════╗
echo  ║                                                      ║
echo  ║  🚀 ỨNG DỤNG ĐANG CHẠY!                             ║
echo  ║                                                      ║
echo  ║  Trình duyệt sẽ tự động mở tại:                     ║
echo  ║  👉  http://localhost:8501                            ║
echo  ║                                                      ║
echo  ║  Nếu trình duyệt không tự mở, hãy copy đường dẫn    ║
echo  ║  trên và dán vào trình duyệt.                        ║
echo  ║                                                      ║
echo  ║  ⚠️  KHÔNG TẮT CỬA SỔ NÀY khi đang sử dụng tool!   ║
echo  ║  Để dừng: nhấn Ctrl+C hoặc đóng cửa sổ này.         ║
echo  ║                                                      ║
echo  ╚══════════════════════════════════════════════════════╝
echo.

:: Khởi chạy Streamlit
:: --server.headless=false: tự động mở trình duyệt
:: --server.port=8501: cổng mặc định
:: --browser.gatherUsageStats=false: không gửi dữ liệu tracking
streamlit run "%PROJECT_DIR%app.py" --server.headless=false --server.port=8501 --browser.gatherUsageStats=false

:: Nếu Streamlit bị tắt (Ctrl+C hoặc lỗi)
echo.
echo  ═══════════════════════════════════════════════════════
echo  🛑 Ứng dụng đã dừng.
echo  Nhấn phím bất kỳ để đóng cửa sổ này...
echo  ═══════════════════════════════════════════════════════
pause >nul
