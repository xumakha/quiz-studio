# Giao diện Easy Prep và ASVAB-Prep

Trong tab **Video**, mục **Giao diện cho toàn bộ video** có các lựa chọn:

- **Một chút English · Học ngôn ngữ**: mẫu học tiếng Anh.
- **Luyện thi · Chứng chỉ**: xanh navy, câu hỏi và các đáp án xếp dọc.
- **Quân sự · ASVAB**: xanh olive, bố cục luyện thi.
- **Tin học · Công nghệ**: xanh cyan, bố cục luyện thi chứng chỉ công nghệ.

Easy Prep mặc định dùng Luyện thi; ASVAB-Prep mặc định dùng Quân sự. Mỗi tab lưu lựa chọn riêng. Tab cũ đang chọn Tự động được chuyển sang mẫu tương ứng một lần; mẫu đã chọn thủ công được giữ lại. Khi chuyển tự động, logo/chibi mặc định English được tắt nếu chưa có ảnh riêng. Có thể bật lại trong phần thương hiệu. Các mẫu prep cũng có trang kết bài riêng nếu chưa chọn ảnh kết.

Ba mẫu Luyện thi, Quân sự và Tin học dùng tiếng Anh cho toàn bộ chữ hệ thống trên video: hướng dẫn, đếm ngược, đáp án, tên dạng câu hỏi và trang kết. Lời dẫn tự sinh cũng bằng tiếng Anh, sử dụng giọng English đã chọn (bao gồm VoiceStudio). Một chút English giữ chữ hệ thống tiếng Việt. Tiêu đề, câu hỏi, giải thích, prompt và ảnh do người dùng nhập cần được soạn bằng ngôn ngữ mong muốn; app không tự dịch dữ liệu hay chữ trong ảnh.

Mẫu áp dụng cả preview và video xuất, hỗ trợ 2–6 lựa chọn và các dạng nội dung khác. Ảnh/video nền và ảnh thương hiệu riêng vẫn dùng được.

**Logo chìm** có công tắc **Hiện logo chìm** riêng, độc lập với watermark chữ ở đáy. Chọn ảnh mới hoặc dùng ảnh đã lưu sẽ tự bật logo chìm cho tab hiện tại. Logo được co/phóng vừa khung và vẽ mờ trên các ô nội dung để không bị che mất. Có thể tắt riêng logo và lưu trạng thái cho lần mở sau.

Thời gian suy nghĩ ưu tiên `thinking_seconds` của từng câu, sau đó `settings.thinking_seconds` của JSON, cuối cùng là thanh **Thời gian suy nghĩ** trong tab Giọng đọc. Preview tĩnh và thanh tiến độ dùng cùng thời gian này. Đoán từ không còn cố định 5 giây khi JSON không khai báo thời gian. Mỗi số đếm ngược chiếm đúng một giây trong timeline, sau khi đọc xong câu hỏi.

Giọng đọc có khoảng đệm 250 ms trước khi bắt đầu để thiết bị âm thanh kịp mở. Các đoạn âm thanh được đặt lại timestamp trước khi ghép, giữ nguyên mẫu âm đầu; cache cũ tự được bỏ qua. Đây là biện pháp xử lý khởi động phát âm thanh; chất lượng phát âm từ dịch vụ TTS và việc tai nghe Bluetooth có cắt âm hay không vẫn cần nghe thực tế.

Mở `Mo-QuizStudio.bat` để dùng bản mới tại `release-watermark/QuizStudio/QuizStudio.exe`. `build.bat` đóng gói vào cùng thư mục.

Kiểm tra: `test_prep_updates.py` kiểm tra nâng cấp cấu hình một lần, ưu tiên thời gian, thời lượng mỗi giây, ba bố cục ở 2/4/6 lựa chọn và tín hiệu âm đầu với FFmpeg thật. `outputs/prep-layouts.jpg` là ảnh so sánh, các file `outputs/{exam,military,tech}-preview.mp4` là video mẫu không giọng đọc. Script `outputs/check_prep_layouts.py` kiểm tra đủ 12 dạng nội dung ở cả ba mẫu.
