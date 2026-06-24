"""
core_processor.py - Module xử lý cốt lõi của ứng dụng tạo phụ đề.

Module này chứa 4 chức năng chính:
    1. Trích xuất audio từ video bằng FFmpeg (hỗ trợ portable)
    2. Nhận diện giọng nói bằng Faster-Whisper (chạy 100% local)
    3. AI biên tập phụ đề bằng Google Gemini (sửa chính tả, ngữ cảnh, dấu câu)
    4. Xuất file phụ đề .srt và .vtt

Tác giả: Auto Subtitle Tool
"""

import os
import re
import sys
import time
import logging
import subprocess
import tempfile
from pathlib import Path
from typing import Optional, Callable

# QUAN TRỌNG: import config TRƯỚC ffmpeg để setup_ffmpeg_env() chạy trước
import config

import ffmpeg
from faster_whisper import WhisperModel

# ============================================================
# THIẾT LẬP LOGGING
# ============================================================
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("CoreProcessor")


# ============================================================
# LỚP QUẢN LÝ TIẾN TRÌNH (Progress Callback) + ETA
# ============================================================
class ProgressTracker:
    """
    Theo dõi và báo cáo tiến trình xử lý, bao gồm ước tính thời gian còn lại (ETA).
    Dùng callback để cập nhật giao diện Streamlit theo thời gian thực.
    """

    def __init__(self, callback: Optional[Callable] = None):
        """
        Args:
            callback: Hàm callback nhận (phần_trăm, thông_báo, eta_giây, bước_hiện_tại, tổng_bước)
                      để cập nhật giao diện.
        """
        self._callback = callback
        self.current_step = ""
        self.percentage = 0.0
        self._start_time = time.time()
        # Thông tin ETA chi tiết
        self.audio_duration = 0.0       # Tổng thời lượng audio (giây)
        self.processed_seconds = 0.0    # Số giây audio đã xử lý
        self.total_segments = 0         # Tổng số đoạn đã nhận diện
        self.eta_seconds = -1.0         # Ước tính thời gian còn lại (-1 = chưa biết)
        self.current_phase = ""         # Giai đoạn hiện tại

    def set_audio_duration(self, duration: float):
        """Ghi nhận tổng thời lượng audio để tính ETA chính xác."""
        self.audio_duration = duration

    def update_transcription_progress(self, segment_end_time: float, segment_count: int):
        """
        Cập nhật tiến trình nhận diện dựa trên vị trí thời gian thực tế của audio.

        Args:
            segment_end_time: Thời điểm kết thúc của đoạn vừa xử lý (giây).
            segment_count:    Tổng số đoạn đã nhận diện đến giờ.
        """
        self.processed_seconds = segment_end_time
        self.total_segments = segment_count

        if self.audio_duration > 0:
            # Tính phần trăm dựa trên audio thực tế (giai đoạn transcribe chiếm 40%-85%)
            audio_progress = min(segment_end_time / self.audio_duration, 1.0)
            self.percentage = 0.40 + (audio_progress * 0.45)  # Map vào khoảng 40%–85%

            # Tính ETA dựa trên tốc độ xử lý thực tế
            elapsed = time.time() - self._start_time
            if audio_progress > 0.01:
                total_estimated = elapsed / audio_progress
                self.eta_seconds = max(total_estimated - elapsed, 0)

            # Tạo thông báo chi tiết
            processed_str = self._format_time(segment_end_time)
            total_str = self._format_time(self.audio_duration)
            eta_str = self._format_time(self.eta_seconds) if self.eta_seconds >= 0 else "đang ước tính..."

            message = (
                f"🎙️ Đang nhận diện: {processed_str} / {total_str} "
                f"| {segment_count} đoạn | ⏱️ Còn ~{eta_str}"
            )
            self.current_step = message
            self._send_callback(message)

    def update(self, percentage: float, message: str):
        """Cập nhật tiến trình và gửi về giao diện."""
        self.percentage = min(percentage, 1.0)
        self.current_step = message
        logger.info(f"[{self.percentage:.0%}] {message}")
        self._send_callback(message)

    def _send_callback(self, message: str):
        """Gửi callback an toàn (không để lỗi callback gián đoạn xử lý)."""
        if self._callback:
            try:
                self._callback(self.percentage, message)
            except Exception:
                pass

    @staticmethod
    def _format_time(seconds: float) -> str:
        """Định dạng giây thành chuỗi dễ đọc (VD: '2 phút 30 giây')."""
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
# 1. TRÍCH XUẤT AUDIO TỪ VIDEO BẰNG FFMPEG (HỖ TRỢ PORTABLE)
# ============================================================
def extract_audio(
    input_path: str,
    output_path: Optional[str] = None,
    progress: Optional[ProgressTracker] = None,
) -> str:
    """
    Trích xuất luồng âm thanh từ file video/audio sang định dạng WAV chuẩn.

    Tự động sử dụng FFmpeg portable trong thư mục bin/ nếu có,
    hoặc fallback về FFmpeg trong PATH hệ thống.

    Args:
        input_path:  Đường dẫn tuyệt đối đến file video hoặc audio gốc.
        output_path: (Tùy chọn) Đường dẫn lưu file WAV đầu ra.
        progress:    (Tùy chọn) Đối tượng ProgressTracker để báo cáo tiến trình.

    Returns:
        Đường dẫn tuyệt đối đến file WAV đã trích xuất.

    Raises:
        FileNotFoundError: Nếu file đầu vào không tồn tại.
        RuntimeError:      Nếu FFmpeg gặp lỗi khi xử lý.
    """
    # --- Kiểm tra file đầu vào ---
    if not os.path.exists(input_path):
        raise FileNotFoundError(f"Không tìm thấy file: {input_path}")

    if progress:
        progress.update(0.05, "🔍 Đang kiểm tra file đầu vào...")

    # --- Xác định đường dẫn đầu ra ---
    if output_path is None:
        os.makedirs(config.TEMP_DIR, exist_ok=True)
        base_name = Path(input_path).stem
        output_path = os.path.join(config.TEMP_DIR, f"{base_name}_audio.wav")

    if progress:
        progress.update(0.10, "🎵 Đang trích xuất âm thanh bằng FFmpeg...")

    # --- Lấy đường dẫn FFmpeg (portable hoặc hệ thống) ---
    ffmpeg_exe = config.get_ffmpeg_path()
    ffprobe_exe = config.get_ffprobe_path()

    if config.is_ffmpeg_portable():
        logger.info(f"Sử dụng FFmpeg portable: {ffmpeg_exe}")
    else:
        logger.info("Sử dụng FFmpeg từ PATH hệ thống")

    try:
        # --- Lấy thông tin file gốc (dùng ffprobe portable nếu có) ---
        probe_info = ffmpeg.probe(input_path, cmd=ffprobe_exe)
        duration = float(probe_info.get("format", {}).get("duration", 0))
        duration_str = time.strftime("%H:%M:%S", time.gmtime(duration)) if duration > 0 else "N/A"
        logger.info(f"File gốc: {Path(input_path).name} | Thời lượng: {duration_str}")

        # Ghi nhận thời lượng audio cho ETA
        if progress:
            progress.set_audio_duration(duration)
            progress.update(0.15, f"🎵 Đang trích xuất audio ({duration_str})...")

        # --- Thực hiện trích xuất bằng FFmpeg ---
        # Sử dụng cmd= để chỉ định đường dẫn ffmpeg portable
        (
            ffmpeg
            .input(input_path)
            .output(
                output_path,
                acodec=config.AUDIO_CODEC,
                ar=config.AUDIO_SAMPLE_RATE,
                ac=config.AUDIO_CHANNELS,
                vn=None,
            )
            .overwrite_output()
            .run(
                cmd=ffmpeg_exe,  # ← Dùng bản portable nếu có
                capture_stdout=True,
                capture_stderr=True,
                quiet=True,
            )
        )

        # --- Kiểm tra kết quả ---
        if not os.path.exists(output_path):
            raise RuntimeError("FFmpeg đã chạy nhưng không tạo được file đầu ra.")

        file_size_mb = os.path.getsize(output_path) / (1024 * 1024)
        logger.info(f"Trích xuất thành công: {output_path} ({file_size_mb:.1f} MB)")

        if progress:
            progress.update(0.25, f"✅ Trích xuất audio hoàn tất ({file_size_mb:.1f} MB)")

        return output_path

    except ffmpeg.Error as e:
        stderr_output = e.stderr.decode("utf-8", errors="replace") if e.stderr else "Không có thông tin lỗi"
        error_msg = f"FFmpeg gặp lỗi khi xử lý file:\n{stderr_output}"
        logger.error(error_msg)
        raise RuntimeError(error_msg) from e

    except Exception as e:
        error_msg = f"Lỗi không xác định khi trích xuất audio: {str(e)}"
        logger.error(error_msg)
        raise RuntimeError(error_msg) from e


# ============================================================
# 2. NHẬN DIỆN GIỌNG NÓI BẰNG FASTER-WHISPER
# ============================================================

# Cache model để không phải tải lại mỗi lần chạy
_cached_model: Optional[WhisperModel] = None
_cached_model_size: Optional[str] = None


def _load_whisper_model(model_size: Optional[str] = None) -> WhisperModel:
    """
    Tải và cache model Faster-Whisper.

    Sử dụng cơ chế singleton để model chỉ được tải 1 lần vào bộ nhớ,
    các lần gọi sau sẽ dùng lại model đã tải.

    Args:
        model_size: Kích thước model (mặc định lấy từ config).

    Returns:
        Đối tượng WhisperModel đã sẵn sàng.
    """
    global _cached_model, _cached_model_size

    if model_size is None:
        model_size = config.WHISPER_MODEL_SIZE

    if _cached_model is not None and _cached_model_size == model_size:
        logger.info(f"Sử dụng model đã tải trong bộ nhớ: {model_size}")
        return _cached_model

    logger.info(f"Đang tải model Whisper '{model_size}' (lần đầu sẽ tải từ Internet)...")

    try:
        model = WhisperModel(
            model_size,
            device=config.WHISPER_DEVICE,
            compute_type=config.WHISPER_COMPUTE_TYPE,
            cpu_threads=config.WHISPER_CPU_THREADS or os.cpu_count(),
            num_workers=config.WHISPER_NUM_WORKERS,
        )
        _cached_model = model
        _cached_model_size = model_size
        logger.info(f"Tải model '{model_size}' thành công!")
        return model

    except Exception as e:
        logger.error(f"Không thể tải model Whisper: {e}")
        raise RuntimeError(
            f"Lỗi khi tải model nhận diện giọng nói '{model_size}'.\n"
            f"Hãy kiểm tra kết nối internet (lần đầu cần tải model) "
            f"và dung lượng ổ đĩa.\nChi tiết: {e}"
        ) from e


def transcribe_audio(
    audio_path: str,
    language: Optional[str] = None,
    model_size: Optional[str] = None,
    progress: Optional[ProgressTracker] = None,
) -> list[dict]:
    """
    Nhận diện giọng nói từ file audio bằng Faster-Whisper.

    Chạy 100% trên máy local, không cần kết nối internet
    (trừ lần đầu tải model).

    Args:
        audio_path: Đường dẫn đến file WAV đã trích xuất.
        language:   Mã ngôn ngữ ISO 639-1 ("vi", "en", ...).
                    Nếu None hoặc "auto", tự động phát hiện.
        model_size: Kích thước model (mặc định lấy từ config).
        progress:   Đối tượng ProgressTracker.

    Returns:
        Danh sách các đoạn phụ đề, mỗi đoạn là dict có dạng:
        {
            "index": int,        # Số thứ tự (bắt đầu từ 1)
            "start": float,      # Thời gian bắt đầu (giây)
            "end": float,        # Thời gian kết thúc (giây)
            "text": str,         # Nội dung văn bản
        }

    Raises:
        FileNotFoundError: Nếu file audio không tồn tại.
        RuntimeError:      Nếu quá trình nhận diện gặp lỗi.
    """
    if not os.path.exists(audio_path):
        raise FileNotFoundError(f"Không tìm thấy file audio: {audio_path}")

    if progress:
        progress.update(0.30, "🤖 Đang tải model nhận diện giọng nói...")

    model = _load_whisper_model(model_size)

    if progress:
        progress.update(0.40, "🎙️ Đang nhận diện giọng nói (có thể mất vài phút)...")

    try:
        transcribe_params = {
            "beam_size": 5,
            "best_of": 5,
            "vad_filter": True,
            "vad_parameters": {
                "min_silence_duration_ms": 500,
            },
            "word_timestamps": False,
        }

        if language and language != "auto":
            transcribe_params["language"] = language
            logger.info(f"Ngôn ngữ được chọn: {language}")
        else:
            logger.info("Chế độ tự động phát hiện ngôn ngữ")

        # --- Thực hiện nhận diện ---
        segments_generator, info = model.transcribe(audio_path, **transcribe_params)

        detected_lang = info.language
        detected_prob = info.language_probability
        logger.info(
            f"Ngôn ngữ phát hiện: {detected_lang} "
            f"(độ tin cậy: {detected_prob:.1%})"
        )

        if progress:
            progress.update(
                0.42,
                f"🎙️ Bắt đầu nhận diện... "
                f"(Ngôn ngữ: {detected_lang}, độ tin cậy: {detected_prob:.1%})"
            )

        # --- Thu thập kết quả từ generator + cập nhật ETA ---
        segments_list = []
        for idx, segment in enumerate(segments_generator, start=1):
            segments_list.append({
                "index": idx,
                "start": segment.start,
                "end": segment.end,
                "text": segment.text.strip(),
            })

            # Cập nhật tiến trình với ETA chính xác dựa trên audio timeline
            if progress:
                progress.update_transcription_progress(
                    segment_end_time=segment.end,
                    segment_count=idx,
                )

        if not segments_list:
            logger.warning("Không nhận diện được nội dung nào trong file audio.")
            if progress:
                progress.update(0.85, "⚠️ Không phát hiện giọng nói trong file.")
            return []

        logger.info(f"Nhận diện hoàn tất: {len(segments_list)} đoạn phụ đề")

        if progress:
            progress.update(0.85, f"✅ Nhận diện xong: {len(segments_list)} đoạn phụ đề")

        return segments_list

    except Exception as e:
        error_msg = f"Lỗi khi nhận diện giọng nói: {str(e)}"
        logger.error(error_msg)
        raise RuntimeError(error_msg) from e


# ============================================================
# 3. AI BIÊN TẬP PHỤ ĐỀ BẰNG GOOGLE GEMINI
# ============================================================
def refine_with_gemini(
    segments: list[dict],
    api_key: str,
    progress: Optional[ProgressTracker] = None,
) -> list[dict]:
    """
    Sử dụng Google Gemini AI để biên tập phụ đề: sửa chính tả, ngữ cảnh, dấu câu.

    Gom các đoạn phụ đề thành từng cụm (batch) rồi gửi cho Gemini xử lý.
    Nếu API gặp lỗi, sẽ giữ nguyên text thô (không crash).

    Args:
        segments:  Danh sách đoạn phụ đề từ Whisper (text thô).
        api_key:   Google AI Studio API Key.
        progress:  Đối tượng ProgressTracker.

    Returns:
        Danh sách đoạn phụ đề đã được AI biên tập (hoặc giữ nguyên nếu lỗi).
    """
    if not api_key or not api_key.strip():
        logger.warning("Không có API Key Gemini, bỏ qua bước biên tập AI.")
        return segments

    if not segments:
        return segments

    try:
        import google.generativeai as genai
    except ImportError:
        logger.error("Thư viện google-generativeai chưa cài. Chạy: pip install google-generativeai")
        return segments

    if progress:
        progress.update(0.86, "✨ Đang kết nối AI biên tập phụ đề (Gemini)...")

    try:
        # --- Cấu hình Gemini ---
        genai.configure(api_key=api_key.strip())
        model = genai.GenerativeModel(
            model_name=config.GEMINI_MODEL,
            system_instruction=config.GEMINI_SYSTEM_PROMPT,
        )

        # --- Chia segments thành các batch ---
        batch_size = config.GEMINI_BATCH_SIZE
        batches = []
        for i in range(0, len(segments), batch_size):
            batches.append(segments[i:i + batch_size])

        total_batches = len(batches)
        logger.info(f"AI biên tập: {len(segments)} đoạn, chia thành {total_batches} cụm (mỗi cụm ~{batch_size} dòng)")

        refined_segments = []

        for batch_idx, batch in enumerate(batches):
            batch_num = batch_idx + 1

            if progress:
                pct = 0.86 + (batch_num / total_batches) * 0.06  # 86% → 92%
                progress.update(
                    min(pct, 0.92),
                    f"✨ AI đang biên tập cụm {batch_num}/{total_batches}..."
                )

            # --- Tạo nội dung gửi cho Gemini ---
            input_lines = []
            for seg in batch:
                input_lines.append(f"[{seg['index']}] {seg['text']}")
            input_text = "\n".join(input_lines)

            # --- Gọi API với retry ---
            refined_text = _call_gemini_with_retry(
                model=model,
                input_text=input_text,
                max_retries=config.GEMINI_MAX_RETRIES,
            )

            # --- Parse kết quả từ Gemini ---
            if refined_text:
                parsed = _parse_gemini_response(refined_text, batch)
                refined_segments.extend(parsed)
            else:
                # API lỗi → giữ nguyên text thô cho batch này
                logger.warning(f"Cụm {batch_num} không nhận được kết quả từ AI, giữ nguyên text thô.")
                refined_segments.extend(batch)

        logger.info(f"AI biên tập hoàn tất: {len(refined_segments)} đoạn đã xử lý.")

        if progress:
            progress.update(0.93, f"✅ AI biên tập xong {len(refined_segments)} đoạn phụ đề")

        return refined_segments

    except Exception as e:
        logger.error(f"Lỗi khi gọi Gemini AI: {e}")
        if progress:
            progress.update(0.93, f"⚠️ AI biên tập gặp lỗi, giữ nguyên text thô.")
        # Fallback an toàn: trả về segments gốc không sửa
        return segments


def _call_gemini_with_retry(
    model,
    input_text: str,
    max_retries: int = 2,
) -> Optional[str]:
    """
    Gọi Gemini API với cơ chế retry khi gặp lỗi tạm thời.

    Args:
        model:       Đối tượng GenerativeModel đã cấu hình.
        input_text:  Nội dung phụ đề cần sửa.
        max_retries: Số lần thử lại tối đa.

    Returns:
        Chuỗi text đã sửa từ Gemini, hoặc None nếu lỗi.
    """
    for attempt in range(max_retries + 1):
        try:
            response = model.generate_content(
                input_text,
                generation_config={
                    "temperature": 0.1,      # Rất thấp = ít sáng tạo, sát nguyên bản
                    "top_p": 0.95,
                    "max_output_tokens": 8192,
                },
            )

            if response and response.text:
                return response.text.strip()
            else:
                logger.warning(f"Gemini trả về response rỗng (lần {attempt + 1})")

        except Exception as e:
            logger.warning(f"Gemini API lỗi (lần {attempt + 1}/{max_retries + 1}): {e}")
            if attempt < max_retries:
                wait_time = 2 ** attempt  # Exponential backoff: 1s, 2s
                time.sleep(wait_time)

    return None


def _parse_gemini_response(response_text: str, original_batch: list[dict]) -> list[dict]:
    """
    Parse kết quả trả về từ Gemini và áp dụng vào danh sách segments gốc.

    Cơ chế an toàn: nếu không parse được dòng nào, giữ nguyên text gốc cho dòng đó.
    Timestamps LUÔN được giữ nguyên từ Whisper (chỉ thay đổi text).

    Args:
        response_text:  Chuỗi text trả về từ Gemini.
        original_batch: Danh sách segments gốc (để fallback và lấy timestamps).

    Returns:
        Danh sách segments với text đã được AI sửa.
    """
    # Tạo dict ánh xạ index → text đã sửa
    refined_map = {}

    for line in response_text.strip().split("\n"):
        line = line.strip()
        if not line:
            continue

        # Parse dòng có dạng: [số] nội dung
        match = re.match(r"^\[(\d+)\]\s*(.+)$", line)
        if match:
            idx = int(match.group(1))
            text = match.group(2).strip()
            if text:  # Chỉ lấy nếu text không rỗng
                refined_map[idx] = text

    # Áp dụng text đã sửa vào segments gốc (giữ nguyên timestamps)
    result = []
    for seg in original_batch:
        new_seg = seg.copy()
        if seg["index"] in refined_map:
            new_seg["text"] = refined_map[seg["index"]]
        else:
            # Không tìm thấy trong kết quả AI → giữ nguyên text gốc
            logger.debug(f"Đoạn [{seg['index']}] không có trong kết quả AI, giữ nguyên.")
        result.append(new_seg)

    matched = len(refined_map)
    total = len(original_batch)
    logger.info(f"Parse AI: {matched}/{total} đoạn được sửa thành công.")

    return result


# ============================================================
# 4. XUẤT FILE PHỤ ĐỀ (.SRT VÀ .VTT)
# ============================================================
def _format_timestamp_srt(seconds: float) -> str:
    """
    Chuyển đổi giây thành định dạng timestamp SRT: HH:MM:SS,mmm

    Args:
        seconds: Thời gian tính bằng giây (ví dụ: 65.432).

    Returns:
        Chuỗi timestamp (ví dụ: "00:01:05,432").
    """
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    millis = int((seconds - int(seconds)) * 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"


def _format_timestamp_vtt(seconds: float) -> str:
    """
    Chuyển đổi giây thành định dạng timestamp VTT: HH:MM:SS.mmm

    Args:
        seconds: Thời gian tính bằng giây.

    Returns:
        Chuỗi timestamp (ví dụ: "00:01:05.432").
    """
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    millis = int((seconds - int(seconds)) * 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d}.{millis:03d}"


def export_srt(segments: list[dict], output_path: str) -> str:
    """
    Xuất danh sách phụ đề thành file định dạng SRT (SubRip).

    Định dạng SRT:
        1
        00:00:01,000 --> 00:00:03,500
        Nội dung phụ đề ở đây.

    Args:
        segments:    Danh sách đoạn phụ đề từ hàm transcribe_audio().
        output_path: Đường dẫn lưu file .srt.

    Returns:
        Đường dẫn tuyệt đối đến file SRT đã tạo.

    Raises:
        ValueError: Nếu danh sách phụ đề rỗng.
        IOError:    Nếu không thể ghi file.
    """
    if not segments:
        raise ValueError("Danh sách phụ đề rỗng, không có gì để xuất.")

    try:
        srt_lines = []
        for seg in segments:
            start_ts = _format_timestamp_srt(seg["start"])
            end_ts = _format_timestamp_srt(seg["end"])
            srt_lines.append(f"{seg['index']}")
            srt_lines.append(f"{start_ts} --> {end_ts}")
            srt_lines.append(seg["text"])
            srt_lines.append("")  # Dòng trống phân cách giữa các đoạn

        srt_content = "\n".join(srt_lines)

        with open(output_path, "w", encoding="utf-8") as f:
            f.write(srt_content)

        logger.info(f"Xuất file SRT thành công: {output_path}")
        return output_path

    except IOError as e:
        error_msg = f"Không thể ghi file SRT tại '{output_path}': {e}"
        logger.error(error_msg)
        raise IOError(error_msg) from e


def export_vtt(segments: list[dict], output_path: str) -> str:
    """
    Xuất danh sách phụ đề thành file định dạng WebVTT.

    Định dạng VTT:
        WEBVTT

        1
        00:00:01.000 --> 00:00:03.500
        Nội dung phụ đề ở đây.

    Args:
        segments:    Danh sách đoạn phụ đề từ hàm transcribe_audio().
        output_path: Đường dẫn lưu file .vtt.

    Returns:
        Đường dẫn tuyệt đối đến file VTT đã tạo.

    Raises:
        ValueError: Nếu danh sách phụ đề rỗng.
        IOError:    Nếu không thể ghi file.
    """
    if not segments:
        raise ValueError("Danh sách phụ đề rỗng, không có gì để xuất.")

    try:
        vtt_lines = ["WEBVTT", ""]  # Header bắt buộc của WebVTT
        for seg in segments:
            start_ts = _format_timestamp_vtt(seg["start"])
            end_ts = _format_timestamp_vtt(seg["end"])
            vtt_lines.append(f"{seg['index']}")
            vtt_lines.append(f"{start_ts} --> {end_ts}")
            vtt_lines.append(seg["text"])
            vtt_lines.append("")  # Dòng trống phân cách

        vtt_content = "\n".join(vtt_lines)

        with open(output_path, "w", encoding="utf-8") as f:
            f.write(vtt_content)

        logger.info(f"Xuất file VTT thành công: {output_path}")
        return output_path

    except IOError as e:
        error_msg = f"Không thể ghi file VTT tại '{output_path}': {e}"
        logger.error(error_msg)
        raise IOError(error_msg) from e


# ============================================================
# 5. HÀM XỬ LÝ TỔNG HỢP (Pipeline chính)
# ============================================================
def process_file(
    input_path: str,
    language: Optional[str] = None,
    model_size: Optional[str] = None,
    output_dir: Optional[str] = None,
    export_formats: Optional[list[str]] = None,
    progress_callback: Optional[Callable] = None,
    gemini_enabled: bool = False,
    gemini_api_key: Optional[str] = None,
) -> dict:
    """
    Pipeline xử lý hoàn chỉnh:
    Nhận file → Trích xuất audio → Nhận diện → [AI Biên tập] → Xuất phụ đề.

    Đây là hàm chính mà giao diện Streamlit sẽ gọi. Hàm này kết nối
    tất cả các bước xử lý thành một luồng liền mạch.

    Args:
        input_path:        Đường dẫn file video/audio đầu vào.
        language:          Mã ngôn ngữ ("vi", "en", "auto").
        model_size:        Kích thước model Whisper.
        output_dir:        Thư mục lưu file phụ đề.
                           Mặc định = cùng thư mục với file gốc.
        export_formats:    Danh sách định dạng xuất (["srt", "vtt"]).
                           Mặc định = cả hai.
        progress_callback: Hàm callback (percentage, message) để cập nhật UI.
        gemini_enabled:    Bật/tắt AI biên tập phụ đề bằng Gemini.
        gemini_api_key:    API Key Google AI Studio.

    Returns:
        Dict chứa kết quả xử lý:
        {
            "success":          bool,
            "input_file":       str,
            "language":         str,
            "total_segments":   int,
            "segments":         list,
            "output_files":     dict,
            "output_dir":       str,
            "processing_time":  float,
            "ai_refined":       bool,   # True nếu đã qua AI biên tập
            "error":            str,
        }
    """
    start_time = time.time()
    progress = ProgressTracker(callback=progress_callback)

    # Kết quả mặc định
    result = {
        "success": False,
        "input_file": input_path,
        "language": None,
        "total_segments": 0,
        "segments": [],
        "output_files": {},
        "output_dir": None,
        "processing_time": 0.0,
        "ai_refined": False,
        "error": None,
    }

    # Thiết lập giá trị mặc định
    if export_formats is None:
        export_formats = ["srt", "vtt"]

    if output_dir is None:
        output_dir = os.path.dirname(os.path.abspath(input_path))

    result["output_dir"] = output_dir
    audio_temp_path = None  # Để dọn dẹp file tạm sau khi xong

    try:
        # ---- BƯỚC 1: Trích xuất audio ----
        progress.update(0.05, "📂 Bắt đầu xử lý file...")
        input_ext = Path(input_path).suffix.lower()

        # Kiểm tra xem file có phải audio thuần hay không
        is_audio_file = input_ext in [fmt.lower() for fmt in config.SUPPORTED_AUDIO_FORMATS]

        if is_audio_file and input_ext == ".wav":
            audio_path = input_path
            progress.update(0.25, "✅ File WAV, bỏ qua bước trích xuất.")
        else:
            audio_path = extract_audio(input_path, progress=progress)
            audio_temp_path = audio_path

        # ---- BƯỚC 2: Nhận diện giọng nói ----
        segments = transcribe_audio(
            audio_path=audio_path,
            language=language,
            model_size=model_size,
            progress=progress,
        )

        result["segments"] = segments
        result["total_segments"] = len(segments)

        if not segments:
            result["error"] = "Không phát hiện giọng nói trong file."
            progress.update(1.0, "⚠️ Hoàn tất - Không phát hiện giọng nói.")
            return result

        # ---- BƯỚC 2.5 (TÙY CHỌN): AI biên tập phụ đề ----
        if gemini_enabled and gemini_api_key:
            progress.update(0.86, "✨ Đang gửi phụ đề cho AI biên tập...")
            segments = refine_with_gemini(
                segments=segments,
                api_key=gemini_api_key,
                progress=progress,
            )
            result["segments"] = segments
            result["ai_refined"] = True
            logger.info("Phụ đề đã được AI Gemini biên tập.")
        elif gemini_enabled and not gemini_api_key:
            logger.warning("Đã bật AI biên tập nhưng chưa nhập API Key. Bỏ qua.")
            if progress:
                progress.update(0.86, "⚠️ Chưa có API Key Gemini, bỏ qua AI biên tập.")

        # ---- BƯỚC 3: Xuất file phụ đề ----
        progress.update(0.93, "💾 Đang xuất file phụ đề...")

        base_name = Path(input_path).stem
        os.makedirs(output_dir, exist_ok=True)

        if "srt" in export_formats:
            srt_path = os.path.join(output_dir, f"{base_name}.srt")
            export_srt(segments, srt_path)
            result["output_files"]["srt"] = srt_path

        if "vtt" in export_formats:
            vtt_path = os.path.join(output_dir, f"{base_name}.vtt")
            export_vtt(segments, vtt_path)
            result["output_files"]["vtt"] = vtt_path

        # ---- HOÀN TẤT ----
        result["success"] = True
        elapsed = time.time() - start_time
        result["processing_time"] = elapsed
        elapsed_str = time.strftime("%M phút %S giây", time.gmtime(elapsed))

        progress.update(1.0, f"🎉 Hoàn tất! ({len(segments)} đoạn, {elapsed_str})")
        logger.info(f"Xử lý hoàn tất trong {elapsed_str}")

        return result

    except FileNotFoundError as e:
        result["error"] = str(e)
        logger.error(f"File không tồn tại: {e}")
        return result

    except RuntimeError as e:
        result["error"] = str(e)
        logger.error(f"Lỗi xử lý: {e}")
        return result

    except Exception as e:
        result["error"] = f"Lỗi không mong đợi: {str(e)}"
        logger.error(f"Lỗi không mong đợi: {e}", exc_info=True)
        return result

    finally:
        if audio_temp_path and os.path.exists(audio_temp_path):
            try:
                os.remove(audio_temp_path)
                logger.info(f"Đã xóa file tạm: {audio_temp_path}")
            except OSError:
                logger.warning(f"Không thể xóa file tạm: {audio_temp_path}")


# ============================================================
# 6. KIỂM TRA PHỤ THUỘC (Dependencies Check)
# ============================================================
def check_ffmpeg_installed() -> bool:
    """
    Kiểm tra xem FFmpeg đã sẵn sàng chưa (portable hoặc hệ thống).

    Returns:
        True nếu FFmpeg sẵn sàng, False nếu không tìm thấy.
    """
    # Kiểm tra bản portable trước
    if config.is_ffmpeg_portable():
        logger.info(f"FFmpeg portable tìm thấy tại: {config.FFMPEG_BIN_DIR}")
        return True

    # Fallback: kiểm tra trong PATH hệ thống
    try:
        ffmpeg_cmd = config.get_ffmpeg_path()
        result = subprocess.run(
            [ffmpeg_cmd, "-version"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode == 0:
            version_line = result.stdout.split("\n")[0]
            logger.info(f"FFmpeg hệ thống: {version_line}")
            return True
        return False
    except (FileNotFoundError, subprocess.TimeoutExpired):
        logger.warning("FFmpeg chưa được cài đặt (không có portable lẫn hệ thống).")
        return False


def check_system_requirements() -> dict:
    """
    Kiểm tra tất cả yêu cầu hệ thống trước khi chạy.

    Returns:
        Dict chứa trạng thái từng yêu cầu:
        {
            "ffmpeg": {"ok": bool, "message": str, "portable": bool},
            "disk_space": {"ok": bool, "message": str},
        }
    """
    import shutil

    results = {}

    # Kiểm tra FFmpeg
    ffmpeg_ok = check_ffmpeg_installed()
    if ffmpeg_ok and config.is_ffmpeg_portable():
        ffmpeg_msg = f"FFmpeg Portable đã sẵn sàng ✅ (thư mục bin/)"
    elif ffmpeg_ok:
        ffmpeg_msg = "FFmpeg hệ thống đã sẵn sàng ✅"
    else:
        ffmpeg_msg = (
            "⚠️ FFmpeg chưa có. Bỏ ffmpeg.exe & ffprobe.exe vào thư mục bin/ "
            "hoặc cài vào PATH hệ thống."
        )

    results["ffmpeg"] = {
        "ok": ffmpeg_ok,
        "message": ffmpeg_msg,
        "portable": config.is_ffmpeg_portable(),
    }

    # Kiểm tra dung lượng ổ đĩa
    try:
        disk = shutil.disk_usage(os.path.expanduser("~"))
        free_gb = disk.free / (1024 ** 3)
        results["disk_space"] = {
            "ok": free_gb >= 2.0,
            "message": f"Dung lượng trống: {free_gb:.1f} GB ✅" if free_gb >= 2.0
                       else f"⚠️ Chỉ còn {free_gb:.1f} GB trống. Cần ít nhất 2 GB.",
        }
    except Exception:
        results["disk_space"] = {
            "ok": True,
            "message": "Không thể kiểm tra dung lượng ổ đĩa.",
        }

    return results
