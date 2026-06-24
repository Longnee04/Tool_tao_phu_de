"""
app.py - Giao diện người dùng Streamlit cho công cụ tạo phụ đề tự động.

Chạy ứng dụng:
    streamlit run app.py

Giao diện bao gồm:
    - Kéo thả file video/audio
    - Chọn ngôn ngữ & model
    - Thanh tiến trình + ETA theo thời gian thực
    - Xem trước & tải về phụ đề
    - Mở thư mục chứa kết quả
"""

import os
import sys
import time
import platform
import subprocess
import tempfile
import threading
from pathlib import Path
from datetime import datetime

import streamlit as st

import config
from core_processor import (
    process_file,
    check_system_requirements,
)

# ============================================================
# CẤU HÌNH TRANG STREAMLIT
# ============================================================
st.set_page_config(
    page_title="🎬 Auto Subtitle Generator",
    page_icon="🎬",
    layout="wide",
    initial_sidebar_state="expanded",
)


# ============================================================
# CSS TÙY CHỈNH - GIAO DIỆN HIỆN ĐẠI
# ============================================================
def inject_custom_css():
    """Thêm CSS tùy chỉnh để giao diện đẹp và chuyên nghiệp hơn."""
    st.markdown("""
    <style>
        /* === FONT & NỀN CHUNG === */
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');

        .stApp {
            font-family: 'Inter', sans-serif;
        }

        /* === HEADER GRADIENT === */
        .main-header {
            background: linear-gradient(135deg, #0f0c29, #302b63, #24243e);
            padding: 2rem 2.5rem;
            border-radius: 16px;
            margin-bottom: 2rem;
            text-align: center;
            box-shadow: 0 8px 32px rgba(48, 43, 99, 0.3);
        }
        .main-header h1 {
            color: #ffffff;
            font-size: 2.2rem;
            font-weight: 700;
            margin: 0;
            letter-spacing: -0.5px;
        }
        .main-header p {
            color: rgba(255, 255, 255, 0.75);
            font-size: 1rem;
            margin-top: 0.5rem;
            font-weight: 300;
        }

        /* === CARD CONTAINER === */
        .custom-card {
            background: linear-gradient(145deg, #1a1a2e, #16213e);
            border: 1px solid rgba(255, 255, 255, 0.08);
            border-radius: 14px;
            padding: 1.8rem;
            margin-bottom: 1.2rem;
            box-shadow: 0 4px 20px rgba(0, 0, 0, 0.2);
            transition: transform 0.2s ease, box-shadow 0.2s ease;
        }
        .custom-card:hover {
            transform: translateY(-2px);
            box-shadow: 0 6px 28px rgba(0, 0, 0, 0.3);
        }
        .custom-card h3 {
            color: #e0e0ff;
            font-size: 1.1rem;
            margin-bottom: 1rem;
            font-weight: 600;
        }

        /* === TRẠNG THÁI HỆ THỐNG === */
        .status-badge {
            display: inline-block;
            padding: 4px 14px;
            border-radius: 20px;
            font-size: 0.82rem;
            font-weight: 500;
            margin: 3px 4px;
        }
        .status-ok {
            background: rgba(46, 213, 115, 0.15);
            color: #2ed573;
            border: 1px solid rgba(46, 213, 115, 0.3);
        }
        .status-error {
            background: rgba(255, 71, 87, 0.15);
            color: #ff4757;
            border: 1px solid rgba(255, 71, 87, 0.3);
        }

        /* === KẾT QUẢ === */
        .result-box {
            background: linear-gradient(145deg, #0a3d0a, #1a4a1a);
            border: 1px solid rgba(46, 213, 115, 0.25);
            border-radius: 14px;
            padding: 1.8rem;
            margin-top: 1rem;
        }
        .result-box h3 {
            color: #2ed573;
            font-weight: 600;
        }

        .error-box {
            background: linear-gradient(145deg, #3d0a0a, #4a1a1a);
            border: 1px solid rgba(255, 71, 87, 0.25);
            border-radius: 14px;
            padding: 1.8rem;
            margin-top: 1rem;
        }
        .error-box h3 {
            color: #ff4757;
            font-weight: 600;
        }

        /* === METRIC CARD === */
        .metric-row {
            display: flex;
            gap: 1rem;
            margin-top: 1rem;
        }
        .metric-item {
            flex: 1;
            background: rgba(255, 255, 255, 0.05);
            border-radius: 10px;
            padding: 1rem;
            text-align: center;
        }
        .metric-value {
            font-size: 1.6rem;
            font-weight: 700;
            color: #7c83ff;
        }
        .metric-label {
            font-size: 0.8rem;
            color: rgba(255, 255, 255, 0.5);
            margin-top: 4px;
        }

        /* === SUBTITLE PREVIEW === */
        .subtitle-preview {
            background: rgba(0, 0, 0, 0.3);
            border: 1px solid rgba(255, 255, 255, 0.1);
            border-radius: 10px;
            padding: 1.2rem;
            max-height: 400px;
            overflow-y: auto;
            font-family: 'Consolas', 'Courier New', monospace;
            font-size: 0.85rem;
            line-height: 1.6;
            color: #e0e0e0;
        }

        /* === NÚT BẤM === */
        .stButton > button {
            border-radius: 10px;
            font-weight: 600;
            letter-spacing: 0.3px;
            transition: all 0.2s ease;
        }

        /* === PROGRESS BAR STYLE === */
        .stProgress > div > div {
            background: linear-gradient(90deg, #7c83ff, #6c5ce7);
            border-radius: 10px;
        }

        /* === PROGRESS INFO CARD === */
        .progress-card {
            background: linear-gradient(145deg, #1a1a3e, #16214e);
            border: 1px solid rgba(124, 131, 255, 0.2);
            border-radius: 14px;
            padding: 1.5rem 2rem;
            margin: 1rem 0;
        }
        .progress-card h3 {
            color: #7c83ff;
            margin: 0 0 1rem 0;
            font-weight: 600;
        }
        .progress-stats {
            display: flex;
            gap: 2rem;
            margin-top: 0.8rem;
            flex-wrap: wrap;
        }
        .progress-stat {
            display: flex;
            align-items: center;
            gap: 0.5rem;
            color: rgba(255, 255, 255, 0.7);
            font-size: 0.9rem;
        }
        .progress-stat .stat-icon {
            font-size: 1.1rem;
        }
        .progress-stat .stat-value {
            color: #e0e0ff;
            font-weight: 600;
        }

        /* === SIDEBAR === */
        [data-testid="stSidebar"] {
            background: linear-gradient(180deg, #0f0c29 0%, #1a1a2e 100%);
        }
        [data-testid="stSidebar"] .stMarkdown h2 {
            color: #e0e0ff;
        }

        /* === FILE UPLOADER === */
        [data-testid="stFileUploader"] {
            border: 2px dashed rgba(124, 131, 255, 0.3);
            border-radius: 14px;
            padding: 1rem;
            transition: border-color 0.3s ease;
        }
        [data-testid="stFileUploader"]:hover {
            border-color: rgba(124, 131, 255, 0.6);
        }

        /* === OPEN FOLDER BUTTON === */
        .open-folder-btn {
            background: linear-gradient(135deg, #6c5ce7, #7c83ff);
            color: white;
            border: none;
            border-radius: 10px;
            padding: 0.7rem 1.5rem;
            font-weight: 600;
            font-size: 0.95rem;
            cursor: pointer;
            transition: all 0.2s ease;
            display: inline-flex;
            align-items: center;
            gap: 0.5rem;
            text-decoration: none;
        }
        .open-folder-btn:hover {
            transform: translateY(-1px);
            box-shadow: 0 4px 15px rgba(108, 92, 231, 0.4);
        }

        /* === FOOTER === */
        .footer {
            text-align: center;
            color: rgba(255, 255, 255, 0.3);
            font-size: 0.78rem;
            margin-top: 3rem;
            padding: 1.5rem 0;
            border-top: 1px solid rgba(255, 255, 255, 0.05);
        }
    </style>
    """, unsafe_allow_html=True)


# ============================================================
# KHỞI TẠO SESSION STATE
# ============================================================
def init_session_state():
    """Khởi tạo các biến trạng thái trong Streamlit session."""
    if "status_dict" not in st.session_state:
        st.session_state.status_dict = {
            "processing": False,          # Đang xử lý hay không
            "progress_percent": 0.0,      # Tiến trình (0.0 - 1.0)
            "progress_message": "",       # Thông báo tiến trình
            "result": None,               # Kết quả xử lý
            "error_message": None,        # Thông báo lỗi
            "processing_start_time": 0,   # Thời điểm bắt đầu xử lý
        }
    
    defaults = {
        "system_checked": False,      # Đã kiểm tra hệ thống chưa
        "system_status": None,        # Trạng thái hệ thống
    }
    for key, default_value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = default_value


# ============================================================
# CALLBACK CẬP NHẬT TIẾN TRÌNH
# ============================================================
def make_update_progress(status_dict: dict):
    """
    Tạo hàm callback cập nhật tiến độ trích xuất bằng closure.
    Tránh truy cập trực tiếp st.session_state từ luồng xử lý nền (Background Thread).
    """
    def update_progress(percentage: float, message: str):
        status_dict["progress_percent"] = percentage
        status_dict["progress_message"] = message
    return update_progress


# ============================================================
# HÀM MỞ THƯ MỤC TRONG FILE EXPLORER
# ============================================================
def open_folder_in_explorer(folder_path: str):
    """
    Mở thư mục trong Windows Explorer (hoặc file manager tương ứng).

    Args:
        folder_path: Đường dẫn thư mục cần mở.
    """
    try:
        folder_path = os.path.normpath(folder_path)
        if not os.path.isdir(folder_path):
            # Nếu là file, lấy thư mục chứa file đó
            folder_path = os.path.dirname(folder_path)

        system = platform.system()
        if system == "Windows":
            # Mở Windows Explorer tại thư mục
            os.startfile(folder_path)
        elif system == "Darwin":
            # macOS
            subprocess.Popen(["open", folder_path])
        else:
            # Linux
            subprocess.Popen(["xdg-open", folder_path])
    except Exception as e:
        st.error(f"Không thể mở thư mục: {e}")


# ============================================================
# HÀM XỬ LÝ TRONG BACKGROUND THREAD
# ============================================================
def run_processing_in_background(
    status_dict: dict,
    file_path: str,
    language: str,
    model_size: str,
    output_dir: str,
    export_formats: list[str],
    gemini_enabled: bool = False,
    gemini_api_key: str = "",
):
    """
    Chạy pipeline xử lý trong thread riêng để không block giao diện.

    Args:
        status_dict:    Từ điển chia sẻ để cập nhật tiến độ (tránh lỗi st.session_state).
        file_path:      Đường dẫn file đã lưu tạm.
        language:       Mã ngôn ngữ.
        model_size:     Kích thước model Whisper.
        output_dir:     Thư mục lưu file phụ đề đầu ra.
        export_formats: Danh sách định dạng xuất.
        gemini_enabled: Bật/tắt AI biên tập.
        gemini_api_key: API Key Gemini.
    """
    try:
        # Tạo hàm callback cập nhật trực tiếp vào status_dict
        progress_cb = make_update_progress(status_dict)

        result = process_file(
            input_path=file_path,
            language=language,
            model_size=model_size,
            output_dir=output_dir,
            export_formats=export_formats,
            progress_callback=progress_cb,
            gemini_enabled=gemini_enabled,
            gemini_api_key=gemini_api_key,
        )
        status_dict["result"] = result
        status_dict["error_message"] = result.get("error")
    except Exception as e:
        status_dict["error_message"] = f"Lỗi nghiêm trọng: {str(e)}"
    finally:
        status_dict["processing"] = False
        # DỌN DẸP TRIỆT ĐỂ FILE VIDEO TẠM VÀ THƯ MỤC TẠM TRỐNG
        if file_path and os.path.exists(file_path):
            try:
                os.remove(file_path)
                # Lấy thư mục chứa file và thử xóa thư mục tạm nếu trống
                temp_dir = os.path.dirname(file_path)
                if os.path.isdir(temp_dir) and temp_dir != config.PROJECT_DIR:
                    # Nếu thư mục rỗng (không chứa file phụ đề do đã lưu sang outputs/) thì xóa đi
                    if not os.listdir(temp_dir):
                        os.rmdir(temp_dir)
            except Exception:
                pass


# ============================================================
# KIỂM TRA HỆ THỐNG
# ============================================================
def render_system_check():
    """Hiển thị trạng thái kiểm tra yêu cầu hệ thống trong sidebar."""
    with st.sidebar:
        st.markdown("## ⚙️ Trạng thái hệ thống")

        if not st.session_state.system_checked:
            with st.spinner("Đang kiểm tra..."):
                st.session_state.system_status = check_system_requirements()
                st.session_state.system_checked = True

        status = st.session_state.system_status
        if status:
            for key, info in status.items():
                css_class = "status-ok" if info["ok"] else "status-error"
                st.markdown(
                    f'<span class="status-badge {css_class}">{info["message"]}</span>',
                    unsafe_allow_html=True,
                )

        st.markdown("---")


# ============================================================
# SIDEBAR - CÀI ĐẶT
# ============================================================
def render_sidebar() -> dict:
    """
    Hiển thị các tùy chọn cài đặt trong sidebar.

    Returns:
        Dict chứa các tham số cấu hình người dùng đã chọn.
    """
    with st.sidebar:
        st.markdown("## 🎛️ Cài đặt")

        # --- Chọn ngôn ngữ ---
        st.markdown("#### 🌐 Ngôn ngữ")
        lang_options = list(config.SUPPORTED_LANGUAGES.keys())
        lang_labels = list(config.SUPPORTED_LANGUAGES.values())
        selected_lang_idx = st.selectbox(
            "Chọn ngôn ngữ nhận diện",
            range(len(lang_options)),
            format_func=lambda i: lang_labels[i],
            index=0,
            help="Chọn 'Tự động phát hiện' nếu không chắc chắn ngôn ngữ của file.",
        )
        selected_language = lang_options[selected_lang_idx]

        st.markdown("---")

        # --- Chọn model ---
        st.markdown("#### 🤖 Model nhận diện")
        model_options = {
            "tiny": "⚡ Tiny — Siêu nhanh, độ chính xác thấp (~40MB)",
            "base": "🔹 Base — Nhanh, độ chính xác vừa (~150MB)",
            "small": "🔸 Small — Cân bằng tốt (~500MB)",
            "medium": "🔶 Medium — Chậm, chính xác cao (~1.5GB)",
        }
        selected_model = st.selectbox(
            "Chọn kích thước model",
            list(model_options.keys()),
            format_func=lambda k: model_options[k],
            index=1,  # Mặc định: base
            help="Model lớn hơn cho kết quả tốt hơn nhưng chậm hơn và tốn RAM hơn.",
        )

        st.markdown("---")

        # --- Chọn định dạng xuất ---
        st.markdown("#### 📄 Định dạng xuất")
        export_srt = st.checkbox("SRT (SubRip)", value=True, help="Phổ biến nhất, tương thích hầu hết trình phát video.")
        export_vtt = st.checkbox("VTT (WebVTT)", value=True, help="Chuẩn web, dùng cho HTML5 video player.")

        export_formats = []
        if export_srt:
            export_formats.append("srt")
        if export_vtt:
            export_formats.append("vtt")

        st.markdown("---")

        # --- Thư mục đầu ra ---
        st.markdown("#### 📁 Thư mục đầu ra")
        output_mode = st.radio(
            "Lưu phụ đề vào đâu?",
            ["Thư mục mặc định (outputs/)", "Thư mục tùy chọn"],
            index=0,
            help="Vì bảo mật của trình duyệt, ứng dụng không thể tự động phát hiện thư mục chứa file gốc trên máy bạn. Mặc định phụ đề sẽ được lưu gọn gàng vào thư mục 'outputs' trong thư mục của tool.",
        )

        custom_output_dir = None
        if output_mode == "Thư mục tùy chọn":
            custom_output_dir = st.text_input(
                "Nhập đường dẫn thư mục",
                value=os.path.expanduser("~\\Desktop"),
                help="Nhập đường dẫn tuyệt đối đến thư mục bạn muốn lưu.",
            )

        st.markdown("---")

        # --- AI Biên tập phụ đề (Gemini) ---
        st.markdown("#### ✨ AI Biên tập phụ đề")
        gemini_enabled = st.toggle(
            "Sử dụng AI sửa lỗi ngữ cảnh & chính tả",
            value=config.GEMINI_ENABLED_DEFAULT,
            help="Bật để Gemini AI tự động sửa lỗi chính tả, nghe nhầm, thêm dấu câu cho phụ đề. Cần API Key miễn phí từ Google AI Studio.",
        )

        gemini_api_key = config.GEMINI_API_KEY  # Mặc định từ config
        if gemini_enabled:
            st.caption("🔑 Lấy API Key miễn phí tại [Google AI Studio](https://aistudio.google.com/apikey)")
            api_key_input = st.text_input(
                "Nhập Gemini API Key",
                value=gemini_api_key,
                type="password",
                help="Dán API Key từ Google AI Studio vào đây. Key sẽ không được lưu lại sau khi đóng app.",
                placeholder="AIzaSy...",
            )
            if api_key_input:
                gemini_api_key = api_key_input

            if not gemini_api_key:
                st.warning("⚠️ Cần nhập API Key để sử dụng AI biên tập.")
            else:
                st.success("🔑 API Key đã sẵn sàng")

            st.caption(f"Model: `{config.GEMINI_MODEL}` | Batch: {config.GEMINI_BATCH_SIZE} dòng/cụm")

        st.markdown("---")

        # --- Hướng dẫn ---
        st.markdown("## 📖 Hướng dẫn")
        st.markdown("""
        1. **Kéo thả** file video hoặc audio vào ô upload
        2. **Chọn ngôn ngữ** hoặc để Tự động
        3. **Bật AI** biên tập nếu muốn (cần API Key)
        4. **Bấm** "🚀 Tạo Phụ Đề"
        5. **Đợi** xử lý hoàn tất
        6. **Tải về** file phụ đề
        """)

        return {
            "language": selected_language,
            "model_size": selected_model,
            "export_formats": export_formats,
            "custom_output_dir": custom_output_dir,
            "gemini_enabled": gemini_enabled,
            "gemini_api_key": gemini_api_key if gemini_enabled else "",
        }


# ============================================================
# KHU VỰC CHÍNH - UPLOAD & XỬ LÝ
# ============================================================
def render_main_area(settings: dict):
    """
    Hiển thị khu vực chính: Upload file, nút xử lý, thanh tiến trình, kết quả.

    Args:
        settings: Dict cài đặt từ sidebar.
    """
    # --- HEADER ---
    st.markdown("""
    <div class="main-header">
        <h1>🎬 Auto Subtitle Generator</h1>
        <p>Công cụ tạo phụ đề tự động — Chạy 100% trên máy tính của bạn, không cần Internet</p>
    </div>
    """, unsafe_allow_html=True)

    # --- KHU VỰC UPLOAD FILE ---
    st.markdown('<div class="custom-card"><h3>📤 Tải lên file Video hoặc Audio</h3>', unsafe_allow_html=True)

    # Tạo danh sách đuôi file được hỗ trợ
    all_formats = config.SUPPORTED_VIDEO_FORMATS + config.SUPPORTED_AUDIO_FORMATS

    uploaded_file = st.file_uploader(
        "Kéo thả hoặc bấm để chọn file",
        type=[fmt.lstrip(".") for fmt in all_formats],
        help=f"Hỗ trợ: {', '.join(all_formats)}",
        key="file_uploader",
    )

    st.markdown('</div>', unsafe_allow_html=True)

    # --- HIỂN THỊ THÔNG TIN FILE ĐÃ UPLOAD ---
    if uploaded_file is not None:
        file_size_mb = uploaded_file.size / (1024 * 1024)
        file_ext = Path(uploaded_file.name).suffix.lower()

        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("📁 Tên file", uploaded_file.name)
        with col2:
            st.metric("📏 Kích thước", f"{file_size_mb:.1f} MB")
        with col3:
            file_type = "🎬 Video" if file_ext in config.SUPPORTED_VIDEO_FORMATS else "🎵 Audio"
            st.metric("📋 Loại file", file_type)

    # --- NÚT BẤM XỬ LÝ ---
    status_dict = st.session_state.status_dict
    col_left, col_center, col_right = st.columns([1, 2, 1])
    with col_center:
        # Kiểm tra điều kiện
        can_process = (
            uploaded_file is not None
            and not status_dict["processing"]
            and len(settings.get("export_formats", [])) > 0
        )

        if not settings.get("export_formats"):
            st.warning("⚠️ Vui lòng chọn ít nhất 1 định dạng xuất (SRT hoặc VTT).")

        process_button = st.button(
            "🚀 Tạo Phụ Đề" if not status_dict["processing"] else "⏳ Đang xử lý...",
            type="primary",
            disabled=not can_process,
            use_container_width=True,
        )

    # --- XỬ LÝ KHI BẤM NÚT ---
    if process_button and uploaded_file is not None:
        # Reset trạng thái
        status_dict["processing"] = True
        status_dict["progress_percent"] = 0.0
        status_dict["progress_message"] = "Đang chuẩn bị..."
        status_dict["result"] = None
        status_dict["error_message"] = None
        status_dict["processing_start_time"] = time.time()

        # Lưu file upload vào đĩa tạm
        temp_dir = tempfile.mkdtemp(prefix="subtitle_")
        temp_file_path = os.path.join(temp_dir, uploaded_file.name)

        with open(temp_file_path, "wb") as f:
            f.write(uploaded_file.getbuffer())

        # Xác định thư mục đầu ra
        # Nếu dùng Thư mục mặc định, lưu vào thư mục 'outputs' của dự án để tránh rác Temp và dễ tìm kiếm
        output_dir = settings.get("custom_output_dir") or os.path.join(config.PROJECT_DIR, "outputs")
        os.makedirs(output_dir, exist_ok=True)

        # Khởi chạy xử lý trong thread nền
        thread = threading.Thread(
            target=run_processing_in_background,
            args=(
                status_dict,
                temp_file_path,
                settings["language"],
                settings["model_size"],
                output_dir,
                settings["export_formats"],
                settings.get("gemini_enabled", False),
                settings.get("gemini_api_key", ""),
            ),
            daemon=True,
        )
        thread.start()
        st.rerun()

    # --- THANH TIẾN TRÌNH NÂNG CAO ---
    if status_dict["processing"]:
        st.markdown("---")

        percent = status_dict["progress_percent"]
        message = status_dict["progress_message"]
        elapsed = time.time() - status_dict["processing_start_time"]
        elapsed_str = _format_elapsed_time(elapsed)

        # Ước tính ETA từ phần trăm tổng
        if percent > 0.05:
            estimated_total = elapsed / percent
            eta = max(estimated_total - elapsed, 0)
            eta_str = _format_elapsed_time(eta)
        else:
            eta_str = "đang ước tính..."

        percent_display = int(percent * 100)

        # Card tiến trình trực quan
        st.markdown(f"""
        <div class="progress-card">
            <h3>⏳ Đang xử lý... {percent_display}%</h3>
            <div class="progress-stats">
                <div class="progress-stat">
                    <span class="stat-icon">⏱️</span>
                    <span>Đã chạy: <span class="stat-value">{elapsed_str}</span></span>
                </div>
                <div class="progress-stat">
                    <span class="stat-icon">🕐</span>
                    <span>Còn khoảng: <span class="stat-value">{eta_str}</span></span>
                </div>
                <div class="progress-stat">
                    <span class="stat-icon">📊</span>
                    <span>Tiến độ: <span class="stat-value">{percent_display}%</span></span>
                </div>
            </div>
        </div>
        """, unsafe_allow_html=True)

        # Thanh progress bar thực tế
        st.progress(percent)

        # Thông báo chi tiết bước đang thực hiện
        st.info(f"**{message}**")

        # Auto-refresh
        time.sleep(1.5)
        st.rerun()

    # --- HIỂN THỊ KẾT QUẢ ---
    if status_dict["result"] is not None and not status_dict["processing"]:
        render_results(status_dict["result"])

    # --- HIỂN THỊ LỖI ---
    if status_dict["error_message"] and not status_dict["processing"] and status_dict["result"] is None:
        st.markdown(f"""
        <div class="error-box">
            <h3>❌ Đã xảy ra lỗi</h3>
            <p>{status_dict['error_message']}</p>
        </div>
        """, unsafe_allow_html=True)


# ============================================================
# HÀM PHỤ: ĐỊNH DẠNG THỜI GIAN ĐÃ TRÔI
# ============================================================
def _format_elapsed_time(seconds: float) -> str:
    """Định dạng số giây thành chuỗi dễ đọc."""
    if seconds < 0:
        return "N/A"
    if seconds < 60:
        return f"{int(seconds)} giây"
    minutes = int(seconds // 60)
    secs = int(seconds % 60)
    if minutes < 60:
        return f"{minutes} phút {secs:02d} giây"
    hours = int(minutes // 60)
    mins = int(minutes % 60)
    return f"{hours} giờ {mins:02d} phút"


# ============================================================
# HIỂN THỊ KẾT QUẢ
# ============================================================
def render_results(result: dict):
    """
    Hiển thị kết quả xử lý: thống kê, xem trước, nút tải về, nút mở thư mục.

    Args:
        result: Dict kết quả từ process_file().
    """
    st.markdown("---")

    if result.get("success"):
        # --- THÔNG BÁO THÀNH CÔNG ---
        processing_time = result.get("processing_time", 0)
        time_str = time.strftime("%M:%S", time.gmtime(processing_time))

        st.markdown(f"""
        <div class="result-box">
            <h3>🎉 Tạo phụ đề thành công!</h3>
            <div class="metric-row">
                <div class="metric-item">
                    <div class="metric-value">{result.get('total_segments', 0)}</div>
                    <div class="metric-label">Đoạn phụ đề</div>
                </div>
                <div class="metric-item">
                    <div class="metric-value">{time_str}</div>
                    <div class="metric-label">Thời gian xử lý</div>
                </div>
                <div class="metric-item">
                    <div class="metric-value">{len(result.get('output_files', {}))}</div>
                    <div class="metric-label">File đã tạo</div>
                </div>
                <div class="metric-item">
                    <div class="metric-value">{'✅' if result.get('ai_refined') else '➖'}</div>
                    <div class="metric-label">AI Biên tập</div>
                </div>
            </div>
        </div>
        """, unsafe_allow_html=True)

        st.markdown("")

        # --- NÚT TẢI VỀ + MỞ THƯ MỤC ---
        st.markdown("### 📥 Tải về file phụ đề")
        output_files = result.get("output_files", {})

        # Tạo cột: các nút tải + nút mở thư mục
        num_cols = len(output_files) + 1  # +1 cho nút mở thư mục
        download_cols = st.columns(num_cols)

        for idx, (fmt, file_path) in enumerate(output_files.items()):
            with download_cols[idx]:
                if os.path.exists(file_path):
                    with open(file_path, "r", encoding="utf-8") as f:
                        file_content = f.read()

                    file_name = Path(file_path).name
                    mime_type = "text/srt" if fmt == "srt" else "text/vtt"

                    st.download_button(
                        label=f"⬇️ Tải {fmt.upper()} ({file_name})",
                        data=file_content,
                        file_name=file_name,
                        mime=mime_type,
                        use_container_width=True,
                    )
                    st.caption(f"📂 `{file_path}`")
                else:
                    st.warning(f"Không tìm thấy file: {file_path}")

        # --- NÚT MỞ THƯ MỤC CHỨA KẾT QUẢ ---
        with download_cols[-1]:
            output_dir = result.get("output_dir", "")
            # Nếu output_dir trống, lấy thư mục từ file đầu ra đầu tiên
            if not output_dir and output_files:
                first_file = list(output_files.values())[0]
                output_dir = os.path.dirname(first_file)

            if output_dir and os.path.isdir(output_dir):
                if st.button(
                    "📂 Mở thư mục kết quả",
                    use_container_width=True,
                    key="open_output_folder",
                ):
                    open_folder_in_explorer(output_dir)
                st.caption(f"📁 `{output_dir}`")

        # --- XEM TRƯỚC PHỤ ĐỀ ---
        st.markdown("### 👁️ Xem trước phụ đề")

        segments = result.get("segments", [])
        if segments:
            # Hiển thị 20 đoạn đầu tiên
            preview_count = min(20, len(segments))
            preview_lines = []
            for seg in segments[:preview_count]:
                start_min = int(seg["start"] // 60)
                start_sec = seg["start"] % 60
                end_min = int(seg["end"] // 60)
                end_sec = seg["end"] % 60
                preview_lines.append(
                    f"[{start_min:02d}:{start_sec:05.2f} → {end_min:02d}:{end_sec:05.2f}]  {seg['text']}"
                )

            preview_text = "\n".join(preview_lines)
            if len(segments) > preview_count:
                preview_text += f"\n\n... và {len(segments) - preview_count} đoạn nữa"

            st.markdown(
                f'<div class="subtitle-preview">{preview_text}</div>',
                unsafe_allow_html=True,
            )

            # Bảng chi tiết (có thể mở rộng)
            with st.expander(f"📊 Xem toàn bộ {len(segments)} đoạn (dạng bảng)"):
                import pandas as pd

                df = pd.DataFrame(segments)
                df["start"] = df["start"].apply(lambda x: f"{int(x//60):02d}:{x%60:05.2f}")
                df["end"] = df["end"].apply(lambda x: f"{int(x//60):02d}:{x%60:05.2f}")
                df.columns = ["#", "Bắt đầu", "Kết thúc", "Nội dung"]
                st.dataframe(df, use_container_width=True, height=400)

    else:
        # --- THÔNG BÁO LỖI ---
        error_msg = result.get("error", "Lỗi không xác định")
        st.markdown(f"""
        <div class="error-box">
            <h3>❌ Xử lý không thành công</h3>
            <p style="color: #ffaaaa;">{error_msg}</p>
        </div>
        """, unsafe_allow_html=True)

        # Gợi ý khắc phục
        st.markdown("#### 💡 Gợi ý khắc phục:")
        st.markdown("""
        - Kiểm tra file video/audio có bị hỏng không
        - Đảm bảo FFmpeg đã có (bỏ vào thư mục `bin/` hoặc cài vào hệ thống)
        - Thử với model nhỏ hơn (Tiny hoặc Base)
        - Kiểm tra dung lượng ổ đĩa còn đủ không
        """)


# ============================================================
# FOOTER
# ============================================================
def render_footer():
    """Hiển thị footer với thông tin ứng dụng."""
    st.markdown("""
    <div class="footer">
        <p>🎬 Auto Subtitle Generator v1.0 — Chạy 100% local trên máy tính của bạn</p>
        <p>Powered by Faster-Whisper & FFmpeg | Không cần API, không phát sinh chi phí</p>
    </div>
    """, unsafe_allow_html=True)


# ============================================================
# HÀM CHÍNH - CHẠY ỨNG DỤNG
# ============================================================
def main():
    """Điểm khởi chạy chính của ứng dụng Streamlit."""

    # Thêm CSS tùy chỉnh
    inject_custom_css()

    # Khởi tạo trạng thái session
    init_session_state()

    # Kiểm tra hệ thống & hiển thị sidebar
    render_system_check()
    settings = render_sidebar()

    # Hiển thị khu vực chính
    render_main_area(settings)

    # Footer
    render_footer()


# ============================================================
# ENTRY POINT
# ============================================================
if __name__ == "__main__":
    main()
