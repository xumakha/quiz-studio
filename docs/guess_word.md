# Đoán từ qua nghĩa tiếng Việt

Chọn **Đoán từ qua nghĩa tiếng Việt** trong DẠNG VIDEO, sau đó chọn **Dùng dữ liệu mẫu** hoặc mở `examples/guess_word.json` (10 câu). JSON có `mode` hoặc `type` ở cấp tài liệu là `guess_word` sẽ tự chọn chế độ này. Trong video tổng hợp, đặt `type: guess_word` trên từng item.

Dùng **Chỉnh qua form** để sửa nghĩa, đáp án, trình độ, loại từ, ngữ cảnh, IPA, giải thích và ví dụ. Các thao tác thêm, nhân bản, xóa, đổi thứ tự, lưu JSON và cấu hình logo/nền/nhạc dùng chung với các dạng khác. Không có lựa chọn ABCD.

**Câu này** xem một câu, **Toàn video** xem toàn bộ. Thanh bên dưới cho phép tua theo timeline đã chuẩn bị, bao gồm âm thanh. Nút hiện đáp án dùng để kiểm tra bố cục tĩnh. Xuất video dùng cùng scene và thời lượng âm thanh với preview.

Đọc nghĩa/ngữ cảnh → đếm ngược → đọc đáp án tiếng Anh và hiện IPA → giải thích → ví dụ. Mặc định suy nghĩ 5 giây, có thể ghi đè bằng số nguyên 1–30 ở item hoặc settings. Đếm ngược bắt đầu sau đoạn TTS câu hỏi và khoảng nghỉ 0,5 giây của engine hiện có. Thanh đếm ngược cập nhật mỗi giây.

Đáp án chỉ nhận một từ A–Z, 2–20 chữ cái; khoảng trắng đầu/cuối được trim. Thẻ [en] chỉ dùng trong giải thích/ví dụ, không dùng trong answer. Mọi lỗi được báo theo câu; từ trùng và số câu trong tiêu đề không khớp được cảnh báo. Trình độ đọc từ JSON, không tự sinh hoặc random.

Bản EXE cập nhật nằm tại `release-current/QuizStudio/QuizStudio.exe`. Mở `Mo-QuizStudio.bat` để chạy bản này. `build.bat` cũng xuất bản mới vào `release-current`; các thư mục release cũ được giữ lại.

Kiểm thử: 32 bài kiểm tra content/engine/preferences/guess_word đã qua, gồm xuất MP4 thật ở mixed mode. Đã xuất mẫu 10 câu có TTS tại `outputs/guess-word-10-tts.mp4`, độ phân giải kiểm thử 180×320; dùng cấu hình chung để xuất 720×1280 hoặc 1080×1920. Kiểm thử âm thanh tự động xác nhận thời lượng theo audio và khoảng im lặng đếm ngược; chưa nghe nghiệm thu thủ công toàn bộ video.

Hai kiểm thử giao diện Tk không chạy được vì môi trường Python báo không tìm thấy Tcl `init.tcl`, kể cả khi trỏ sang runtime đi kèm bản đóng gói. Vì vậy form, thanh tua và phát âm thanh khi tua cần kiểm tra trực tiếp trên máy có Tcl/Tk hoạt động. Không xem các kiểm thử này là đã đạt.

Cập nhật kiểm tra bản đóng gói: `release-current/QuizStudio/QuizStudio.exe --self-check` đã chạy thành công ngoài sandbox, khởi tạo giao diện, dựng preview cho đủ 12 dạng nội dung và kiểm tra FFmpeg. Lỗi Tcl nói trên xảy ra trong sandbox. Kết quả lưu tại `outputs/current-self-check-unrestricted.json`; kiểm tra này chưa bao gồm thao tác tua và nghe âm thanh khi tua.
