# 🎬 Auto Subtitle Generator

Công cụ tạo phụ đề tự động chạy **100% trên máy tính cá nhân** — không cần API, không phát sinh chi phí.

## ✨ Tính năng

- 🎙️ Nhận diện giọng nói bằng **Faster-Whisper** (hỗ trợ Tiếng Việt, Tiếng Anh, và nhiều ngôn ngữ khác)
- 🎬 Hỗ trợ file Video (`.mp4`, `.mkv`, `.avi`, `.mov`) và Audio (`.mp3`, `.wav`, `.flac`)
- 📄 Xuất phụ đề định dạng **SRT** và **WebVTT**
- 💻 Giao diện web trực quan bằng **Streamlit**
- ⚡ Tối ưu cho CPU với `compute_type="int8"`

## 📦 Yêu cầu hệ thống

- **Python**: 3.9 trở lên
- **FFmpeg**: Cài đặt và thêm vào PATH ([Tải tại đây](https://ffmpeg.org/download.html))
- **RAM**: Tối thiểu 4GB (khuyến nghị 8GB)
- **Ổ đĩa**: 2GB trống (cho model AI)

## 🚀 Cài đặt

### 1. Cài FFmpeg

**Windows:**
```bash
# Dùng Chocolatey
choco install ffmpeg

# Hoặc tải trực tiếp từ https://ffmpeg.org/download.html
# Giải nén và thêm thư mục bin vào biến môi trường PATH
```

### 2. Cài đặt thư viện Python

```bash
pip install -r requirements.txt
```

### 3. Chạy ứng dụng

```bash
Run_Tool.batch
streamlit run app.py
```

Trình duyệt sẽ tự động mở tại `http://localhost:8501`

## 📁 Cấu trúc dự án

```
Tool Tạo Phụ Đề/
├── .streamlit/
│   └── config.toml          # Cấu hình giao diện Streamlit
├── app.py                   # Giao diện người dùng (Streamlit)
├── core_processor.py        # Logic xử lý cốt lõi
├── config.py                # Cấu hình tập trung
├── requirements.txt         # Danh sách thư viện
├── README.md                # Tài liệu hướng dẫn
└── temp/                    # Thư mục tạm (tự tạo khi chạy)
```

## ⚙️ Tùy chỉnh

Mở file `config.py` để thay đổi:

| Tham số | Mô tả | Mặc định |
|---------|--------|----------|
| `WHISPER_MODEL_SIZE` | Kích thước model AI | `"base"` |
| `WHISPER_DEVICE` | CPU hoặc GPU | `"cpu"` |
| `WHISPER_COMPUTE_TYPE` | Kiểu tính toán | `"int8"` |
| `AUDIO_SAMPLE_RATE` | Tần số lấy mẫu | `16000` |

## 📝 Ghi chú

- Lần đầu chạy sẽ tự động tải model AI (~150MB cho `base`), cần kết nối Internet.
- Các lần chạy sau sẽ hoạt động hoàn toàn offline.
- File phụ đề được lưu cùng thư mục với file gốc (mặc định).
