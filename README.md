# Quiz Studio cho Windows

Repository chứa mã nguồn và JSON mẫu; không chứa thư viện cài đặt, video xuất hay bản `.exe`. Sau khi clone, cài Python 3.11 trở lên rồi chạy `run.bat` để cài thư viện và mở app từ mã nguồn. Chạy `build.bat` để tạo bản `.exe` tại `release-clear/QuizStudio`.

Nhấp đúp **Mo-QuizStudio.bat** để mở bản mới nhất tại `release-clear/QuizStudio/QuizStudio.exe`. Khi chuyển sang máy khác, sao chép cả thư mục `release-clear/QuizStudio`, bao gồm `_internal`. Không chạy file trong thư mục `build`: đó là file đóng gói trung gian.

## Tạo video

1. Mở JSON trong app; có mẫu tại `examples/questions.json` và nội dung tiếng Anh tại `examples/tieng-anh-co-ban-6-phut.json`.
2. Chỉnh giọng Việt/Anh, tốc độ, cao độ và thời gian suy nghĩ trong tab Giọng đọc. Đoạn `[en]...[/en]` dùng giọng tiếng Anh riêng.
3. Trong tab Nền, chọn ảnh/nhạc và chỉnh mức làm tối, âm lượng. Ảnh và nhạc nền được sao chép vào `%LOCALAPPDATA%\QuizStudio` để lần sau tự nạp lại, kể cả khi file gốc bị di chuyển hoặc xóa. Bỏ ảnh / nhạc nền cũng xóa cả hai lựa chọn đã lưu.
4. Trong tab Video, dùng lựa chọn Giao diện cho toàn bộ video để chuyển giữa Toán, Tiếng Anh, Quiz nhiều màu hoặc tự động theo môn học của câu đầu tiên. Mỗi video chỉ dùng một giao diện cho tất cả câu hỏi, đếm ngược và đáp án; xem trước cũng dùng giao diện đó. Bật/tắt watermark và sửa chữ; chọn độ phân giải.
5. Kiểm tra & xem trước, chọn câu và bật hiện đáp án để xem bố cục. Danh sách câu hỏi cho phép chọn nhanh.
6. Xuất video MP4, theo dõi phần trăm và bước xử lý. Khi hoàn tất, Mở trong thư mục chọn sẵn file video. Nút Hủy dừng tác vụ mà không ghi đè file đích chưa hoàn tất.

Video H.264/AAC, 30 fps, 9:16, 720×1280 hoặc 1080×1920. Một file chứa toàn bộ câu hỏi theo thứ tự: đọc câu hỏi/lựa chọn → đếm ngược → đáp án/giải thích. Không có tấm nền xám lớn bao quanh nội dung; dấu tick được vẽ bằng nét.

Câu hỏi, lựa chọn, giải thích và watermark nằm phía trên khoảng trống ở đáy video để tránh tên page và mô tả khi xem trên mạng xã hội.

Khi bật giọng đọc, phần đáp án chỉ đọc ký tự phương án, ví dụ “Đáp án đúng là C.”; nội dung lựa chọn và giải thích vẫn hiển thị trên màn hình. Sau khi đọc xong đáp án và phần giải thích cuối cùng (nếu bật đọc giải thích), video hiện ảnh `assets/ending-img.png` khoảng 3 giây và đọc “theo dõi một chút english để học thêm một chút tiếng anh mỗi ngày nhé!”. Nếu giọng đọc dài hơn, ảnh được giữ đến khi đọc xong. Khi tắt giọng đọc, ảnh kết thúc vẫn hiện 3 giây.

Các tùy chỉnh tự lưu khi thay đổi và khi đóng app: giọng chính/tiếng Anh, tốc độ, cao độ, thời gian suy nghĩ, đọc lựa chọn, bật giọng đọc, giao diện video, độ phân giải, chữ/bật watermark, âm lượng nhạc, độ tối nền và chế độ xem đáp án. Mở app lại sẽ khôi phục các giá trị này. Cài đặt và media nằm ngoài thư mục bản `.exe`, nên vẫn giữ khi cập nhật app; dữ liệu ảnh nền của bản trước cũng được giữ lại.

Giọng Google Việt/Anh là mặc định và cần Internet. Giọng Edge nam/nữ cũng có trong danh sách nhưng có thể gặp lỗi kết nối dịch vụ. Bỏ chọn Tạo giọng đọc để xuất offline. Chưa có nhái giọng hoặc tự đăng mạng xã hội.

Âm thanh được ghép ở dạng PCM và mã hóa AAC một lần khi hoàn thiện MP4, tránh lỗi timestamp ở điểm nối giữa các giây đếm ngược và đáp án. Nhạc nền được lặp và trộn trên một dòng thời gian liên tục. Khi ảnh kết thúc xuất hiện, nhạc nền giảm dần về 0 đúng cuối video; âm lượng giọng đọc giữ nguyên.

## JSON

Nhận mảng câu hỏi hoặc `{ "title": "...", "questions": [...] }`. `question`, `options` (2–6 chuỗi) và đáp án là bắt buộc. `answer` nhận A–F, nguyên văn lựa chọn hoặc số nguyên từ **0**; cũng nhận `correct_answer`/`answer_index`. `explanation` không bắt buộc. `subject` và `lesson` giúp tự nhận diện môn học; sau đó xét tiêu đề và thẻ `[en]`. Môn chưa nhận diện dùng mẫu Quiz nhiều màu. Mẫu này cũng nhận `grade`/`class` để hiển thị lớp.

## Mã nguồn và đóng gói

- `app.py`, `modern_ui.py`, `icons.py`: giao diện và thao tác app.
- `engine.py`, `video_themes.py`, `video_classic.py`: giọng đọc, xuất MP4 và các mẫu video.
- `preferences.py`: lưu cài đặt người dùng, ảnh nền và nhạc nền.
- `requirements.txt`, `.venv`: thư viện chạy từ mã nguồn; `run.bat` hỗ trợ khởi động.
- `build.bat`: đóng gói bản mới vào `release-clear`; đóng app trước khi đóng gói lại.
- `test_*.py`: kiểm tra dữ liệu, render, chọn mẫu, watermark và lưu ảnh nền.

Chạy kiểm tra: `.venv\Scripts\python.exe -m unittest discover -v`. Chạy từ mã nguồn cần Python 3.11 trở lên.
