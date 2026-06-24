"""
config.py - Tập trung toàn bộ cấu hình của ứng dụng.
Người dùng có thể chỉnh sửa file này để thay đổi hành vi mà không cần sửa code chính.
"""

import os
import sys

# ============================================================
# ĐƯỜNG DẪN GỐC CỦA DỰ ÁN
# ============================================================
PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))

# ============================================================
# CẤU HÌNH FFMPEG PORTABLE
# ============================================================
# Thư mục chứa ffmpeg.exe và ffprobe.exe portable
# Người dùng chỉ cần bỏ 2 file vào thư mục bin/ là xong
FFMPEG_BIN_DIR = os.path.join(PROJECT_DIR, "bin")

# Đường dẫn cụ thể đến file thực thi FFmpeg portable
FFMPEG_EXE = os.path.join(FFMPEG_BIN_DIR, "ffmpeg.exe")
FFPROBE_EXE = os.path.join(FFMPEG_BIN_DIR, "ffprobe.exe")


def get_ffmpeg_path() -> str:
    """
    Trả về đường dẫn đến ffmpeg.exe.
    Ưu tiên bản portable trong thư mục bin/, nếu không có thì dùng bản hệ thống.
    """
    if os.path.isfile(FFMPEG_EXE):
        return FFMPEG_EXE
    # Fallback: tìm trong PATH hệ thống
    return "ffmpeg"


def get_ffprobe_path() -> str:
    """
    Trả về đường dẫn đến ffprobe.exe.
    Ưu tiên bản portable trong thư mục bin/, nếu không có thì dùng bản hệ thống.
    """
    if os.path.isfile(FFPROBE_EXE):
        return FFPROBE_EXE
    # Fallback: tìm trong PATH hệ thống
    return "ffprobe"


def is_ffmpeg_portable() -> bool:
    """Kiểm tra xem đang dùng FFmpeg portable hay hệ thống."""
    return os.path.isfile(FFMPEG_EXE) and os.path.isfile(FFPROBE_EXE)


def setup_ffmpeg_env():
    """
    Thiết lập biến môi trường để thư viện ffmpeg-python sử dụng bản portable.
    Hàm này PHẢI được gọi trước khi import ffmpeg trong core_processor.

    Cơ chế: thêm thư mục bin/ vào đầu PATH để subprocess tìm thấy
    ffmpeg.exe/ffprobe.exe mà không cần cài vào hệ thống.
    """
    if os.path.isdir(FFMPEG_BIN_DIR):
        # Thêm thư mục bin vào ĐẦU PATH (ưu tiên cao nhất)
        current_path = os.environ.get("PATH", "")
        if FFMPEG_BIN_DIR not in current_path:
            os.environ["PATH"] = FFMPEG_BIN_DIR + os.pathsep + current_path


# Tự động thiết lập khi import config
setup_ffmpeg_env()


# ============================================================
# CẤU HÌNH MODEL NHẬN DIỆN GIỌNG NÓI (Faster-Whisper)
# ============================================================

# Kích thước model: "tiny", "base", "small", "medium", "large-v2", "large-v3"
# - "base"  : nhanh, nhẹ (~150MB RAM), độ chính xác vừa phải
# - "small" : cân bằng (~500MB RAM), độ chính xác tốt
# - "medium": chậm hơn (~1.5GB RAM), độ chính xác cao
WHISPER_MODEL_SIZE = "base"

# Thiết bị chạy: "cpu" hoặc "cuda" (nếu có GPU NVIDIA)
WHISPER_DEVICE = "cpu"

# Kiểu tính toán: "int8" tối ưu RAM cho CPU, "float16" cho GPU
WHISPER_COMPUTE_TYPE = "int8"

# Số luồng CPU sử dụng (0 = tự động chọn theo số core)
WHISPER_CPU_THREADS = 0

# Số worker xử lý song song khi decode
WHISPER_NUM_WORKERS = 1

# ============================================================
# CẤU HÌNH TRÍCH XUẤT ÂM THANH (FFmpeg)
# ============================================================

# Tần số lấy mẫu khi trích xuất audio (Hz)
AUDIO_SAMPLE_RATE = 16000

# Số kênh audio (1 = mono, 2 = stereo)
AUDIO_CHANNELS = 1

# Codec audio đầu ra
AUDIO_CODEC = "pcm_s16le"

# ============================================================
# CẤU HÌNH GIAO DIỆN & ỨNG DỤNG
# ============================================================

# Thư mục tạm chứa file audio trích xuất
TEMP_DIR = os.path.join(PROJECT_DIR, "temp")

# Các định dạng file được hỗ trợ
SUPPORTED_VIDEO_FORMATS = [".mp4", ".mkv", ".avi", ".mov", ".webm", ".flv"]
SUPPORTED_AUDIO_FORMATS = [".mp3", ".wav", ".flac", ".aac", ".ogg", ".m4a"]

# Kích thước file tối đa cho upload (MB)
MAX_FILE_SIZE_MB = 2048  # 2GB

# ============================================================
# CẤU HÌNH NGÔN NGỮ
# ============================================================

# Danh sách ngôn ngữ hỗ trợ (mã ISO 639-1)
SUPPORTED_LANGUAGES = {
    "auto": "🌐 Tự động phát hiện",
    "vi": "🇻🇳 Tiếng Việt",
    "en": "🇺🇸 Tiếng Anh",
    "ja": "🇯🇵 Tiếng Nhật",
    "ko": "🇰🇷 Tiếng Hàn",
    "zh": "🇨🇳 Tiếng Trung",
    "fr": "🇫🇷 Tiếng Pháp",
}

# ============================================================
# CẤU HÌNH AI BIÊN TẬP PHỤ ĐỀ (Google Gemini)
# ============================================================

# API Key của Google AI Studio (lấy miễn phí tại https://aistudio.google.com/apikey)
# Có thể nhập trực tiếp ở đây hoặc nhập qua giao diện Streamlit
GEMINI_API_KEY = ""

# Model Gemini sử dụng (gemini-2.5-flash miễn phí, nhanh, đủ tốt)
GEMINI_MODEL = "gemini-2.5-flash"

# Bật/tắt tính năng AI biên tập mặc định
GEMINI_ENABLED_DEFAULT = False

# Số dòng phụ đề gom thành 1 cụm gửi cho Gemini (tránh quá tải token)
GEMINI_BATCH_SIZE = 35

# Thời gian chờ tối đa cho mỗi request API (giây)
GEMINI_TIMEOUT = 120

# Số lần thử lại khi API lỗi
GEMINI_MAX_RETRIES = 2

# Prompt hệ thống cho Gemini — ép biên tập nghiêm ngặt
GEMINI_SYSTEM_PROMPT = """Bạn là một biên tập viên phụ đề chuyên nghiệp. Nhiệm vụ của bạn là sửa lỗi chính tả, nghe nhầm, và thêm dấu câu cho phụ đề được tạo từ nhận diện giọng nói tự động.

QUY TẮC BẮT BUỘC:
1. SỬA LỖI CHÍNH TẢ: Sửa từ bị nhận diện sai, lỗi chính tả, từ lóng bị nghe nhầm thành từ đúng nghĩa trong ngữ cảnh.
2. DẤU CÂU: Thêm dấu chấm, dấu phẩy, dấu hỏi, dấu chấm than hợp lý dựa trên ngữ cảnh câu nói.
3. VIẾT HOA: Viết hoa đầu câu và tên riêng.
4. GIỮ NGUYÊN Ý NGHĨA: Không thêm bớt nội dung, không diễn giải lại, không dịch sang ngôn ngữ khác.
5. GIỮ NGUYÊN SỐ LƯỢNG DÒNG: Số dòng đầu ra PHẢI BẰNG CHÍNH XÁC số dòng đầu vào.
6. GIỮ NGUYÊN ĐỊNH DẠNG: Mỗi dòng bắt đầu bằng [số] và giữ nguyên phần [số] đó.

ĐỊNH DẠNG ĐẦU VÀO (mỗi dòng):
[số_thứ_tự] nội dung phụ đề thô

ĐỊNH DẠNG ĐẦU RA (mỗi dòng, ĐÚNG SỐ LƯỢNG):
[số_thứ_tự] nội dung phụ đề đã sửa

CHỈ trả về các dòng đã sửa, KHÔNG kèm giải thích, KHÔNG thêm bất kỳ text nào khác."""
