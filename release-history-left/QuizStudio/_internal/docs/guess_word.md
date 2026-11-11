# Đoán từ qua nghĩa tiếng Việt

Watermark chữ ở đáy video dùng cỡ 42 px trên khung 1080 px, chữ đậm và nét dày hơn; tên dài tự co để vừa khung. Ngay dưới chữ có logo nhỏ căn giữa, dùng cùng ảnh đã chọn trong mục Logo chìm nhưng hiện rõ màu gốc, không làm mờ. Logo giữ đúng tỷ lệ, vừa khung tối đa 240 × 64 px; tắt watermark ở đáy sẽ ẩn cả chữ và logo nhỏ. Thanh đếm ngược thu ngắn liên tục ở 30 fps, trong khi số giây vẫn đổi mỗi giây. Phát xem trước và tua đến giữa giây cũng hiển thị đúng phần thời gian còn lại.

App mở sẵn bốn tab **Một chút English**, **Easy Prep**, **ASVAB-Prep**, **easy-pass.app** và chọn tab đầu tiên. Giọng đọc, nền, nhạc, logo, ảnh kết thúc và các tùy chỉnh được lưu riêng cho từng tab, tự khôi phục khi mở lại app. Cài đặt từ bản cũ được giữ cho **Một chút English**; ba tab còn lại dùng thông số cơ bản, chữ watermark theo tên tab và câu kết để trống cho đến khi bạn tùy chỉnh. Tab **easy-pass.app** dùng giao diện **easy-pass.app · Xanh nhạt**, nền màu #D9EDF7 mặc định.

Bấm **+** hoặc **Ctrl+T** để thêm tab; tab mới sao chép cài đặt tab đang chọn rồi lưu độc lập. Tên và các tab còn mở được nhớ cho lần sau. Đóng tab mặc định chỉ ẩn trong phiên hiện tại; mở lại app sẽ khôi phục cả ba với cài đặt đã lưu. Tab mở thêm đã đóng sẽ không tự mở lại. JSON và bản nháp vẫn chỉ giữ trong phiên, cần **Lưu JSON** để giữ nội dung. Mở `Mo-QuizStudio.bat` để chạy bản mới tại `release-history/QuizStudio/QuizStudio.exe`. Xem [hướng dẫn nhiều tab](../README.md#tạo-video).

Bấm **Lịch sử video** ở thanh tab để xem các video đã xuất thành công từ mọi tab, gồm tên video, dạng video và caption. Danh sách chia thành từng nhóm theo ngày xuất trên máy, ngày mới nhất ở trên; mỗi nhóm có nhãn ngày và số video, có thể thu gọn hoặc mở rộng. Tìm kiếm chỉ hiện các nhóm có video phù hợp. Chọn bản ghi để xem toàn bộ caption, **Sao chép caption** hoặc **Mở thư mục**. Lịch sử lưu trong `history.sqlite3` ở thư mục dữ liệu người dùng và được giữ khi mở lại app. Video đã xuất trước khi có tính năng này không tự được bổ sung.

Bấm **Xuất Excel** trong cửa sổ lịch sử để lưu toàn bộ video của mọi kênh thành file `.xlsx`, kể cả khi đang tìm kiếm. File gồm ngày giờ xuất, kênh, loại video, tên video, caption đầy đủ, đường dẫn file và thời lượng. Caption giữ nguyên xuống dòng; caption vượt giới hạn một ô Excel được chia sang các cột **Caption (tiếp …)** theo thứ tự. Mở file bằng Excel để lấy caption ngay cả khi không mở được app. Xuất lại khi cần cập nhật các video mới.

Dán caption vào trường `caption` ở cấp ngoài cùng của JSON, cùng cấp với `title` và `mode`, ví dụ `"caption": "Bạn đoán đúng bao nhiêu từ?\n#tienganh #doantu"`. Caption là chuỗi tùy chọn, có thể để trống hoặc bỏ qua; app giữ nguyên nội dung, xuống dòng khi lưu JSON và chỉnh item. Caption dùng cho lịch sử video, không đưa vào giọng đọc hoặc hình video. Xem [mẫu JSON có caption](content-v2.md).

Nhấp đúp tên tab hoặc chuột phải → **Đổi tên tab…** để đổi tên; tên được lưu và bộ cài đặt của tab được giữ nguyên. Trong **Tùy chỉnh video → Video**, dùng **Chọn ảnh logo** và **Chọn ảnh cuối video** để thay ảnh cho tab hiện tại. Cả hai đều có danh sách **Ảnh đã tải lên** → **Dùng ảnh đã chọn** để dùng lại ảnh cũ; thư viện ảnh dùng chung vẫn giữ ảnh khi khôi phục mặc định hoặc xóa file gốc.

Mục **Video → Câu kết cuối video** cho phép gõ lời đọc khi hiện ảnh kết thúc và **Nghe thử câu kết**. Bật **Tạo giọng đọc** để phát; để trống nếu chỉ muốn hiện ảnh. Câu kết được lưu riêng theo tab và khôi phục cùng cài đặt khi mở lại app.

Mục **Video → Logo góc trái / Ảnh chibi góc phải** cho phép bật/tắt từng ảnh ở đầu video, tải ảnh thay thế hoặc chọn ảnh đã tải từ thư viện. Hai mục giữ ảnh, trạng thái riêng theo tab và tự lưu; logo chìm phía sau nội dung có lựa chọn riêng. Xem trước và xuất video dùng cùng cài đặt.

Chọn **Đoán từ qua nghĩa tiếng Việt** trong DẠNG VIDEO, sau đó chọn **Dùng dữ liệu mẫu** hoặc mở `examples/guess_word.json` (10 câu). JSON có `mode` hoặc `type` ở cấp tài liệu là `guess_word` sẽ tự chọn chế độ này. Trong video tổng hợp, đặt `type: guess_word` trên từng item.

Dùng **Chỉnh qua form** để sửa nghĩa, đáp án, trình độ, loại từ, ngữ cảnh, IPA, giải thích và ví dụ. Các thao tác thêm, nhân bản, xóa, đổi thứ tự, lưu JSON và cấu hình logo/nền/nhạc dùng chung với các dạng khác. Không có lựa chọn ABCD.

Dòng chú thích nhỏ ngay dưới nghĩa tiếng Việt lấy từ `context_hint`, ví dụ `"meaning_vi": "Cải thiện", "context_hint": "Làm một việc gì đó tốt hơn so với lần trước"`. Dòng này hiện trong lúc đọc câu hỏi, suy nghĩ và bật mí. Bỏ trống hoặc thiếu trường thì tự ẩn gọn; không ghi đáp án tiếng Anh trong chú thích.

**Câu này** xem một câu, **Toàn video** xem toàn bộ. Thanh bên dưới cho phép tua theo timeline đã chuẩn bị, bao gồm âm thanh. Nút hiện đáp án dùng để kiểm tra bố cục tĩnh. Xuất video dùng cùng scene và thời lượng âm thanh với preview.

Đọc nghĩa/ngữ cảnh → đếm ngược → hiện đáp án và IPA trong 1 giây, không đọc riêng đáp án → đọc giải thích → ví dụ. Ví dụ giải thích “Hello nghĩa là xin chào” chỉ được đọc một lượt, không có lượt “Hello” riêng phía trước. Tắt đọc giải thích thì bước này cũng không phát giọng đọc. Mặc định suy nghĩ 5 giây, có thể ghi đè bằng số nguyên 1–30 ở item hoặc settings. Đếm ngược bắt đầu sau đoạn TTS câu hỏi và khoảng nghỉ 0,5 giây của engine hiện có. Thanh đếm ngược cập nhật mỗi giây.

Đáp án chỉ nhận một từ A–Z, 2–20 chữ cái; khoảng trắng đầu/cuối được trim. Thẻ [en] chỉ dùng trong giải thích/ví dụ, không dùng trong answer. Mọi lỗi được báo theo câu; từ trùng và số câu trong tiêu đề không khớp được cảnh báo. Trình độ đọc từ JSON, không tự sinh hoặc random.

Trường `ipa` là tùy chọn, chỉ hiển thị sau khi bật mí, ngay dưới đáp án (font Segoe UI, 48 px trên khung 1080 px; tự co tối đa đến 34 px). Không tự sinh IPA và không đọc IPA. Trong giải thích, đoạn có thẻ `[en]` dùng Google English hoặc giọng `en-US` đã chọn; các giọng vùng khác chuyển sang `en-US-JennyNeural`, phần tiếng Việt vẫn dùng giọng Việt đã chọn. Khoảng hiện đáp án im lặng 1 giây dùng chung trong preview, tua và xuất video; thời lượng được căn theo frame 30 fps.

Nếu dịch vụ giọng đọc không trả âm thanh, app tự thử tối đa 3 lần với cùng giọng. Khi vẫn thất bại, thông báo nêu rõ giọng bị lỗi; có thể chọn Google Việt/Anh tương ứng trong tab Giọng đọc rồi nghe thử lại.

Đã kiểm tra font IPA, thời điểm bật mí, trường hợp thiếu IPA và việc không gửi IPA vào TTS. Bản kiểm tra mới `outputs/guess-word-ipa-check.mp4` bỏ hoàn toàn audio ở bước hiện đáp án; mốc chi tiết nằm trong `outputs/guess-word-ipa-timeline.json`. Chưa nghe đánh giá thủ công chất lượng phát âm.

Bản EXE cập nhật nằm tại `release-history/QuizStudio/QuizStudio.exe`. Mở `Mo-QuizStudio.bat` để chạy bản này. `build.bat` cũng xuất bản mới vào `release-history`; các thư mục release cũ được giữ lại.

Kiểm thử: 32 bài kiểm tra content/engine/preferences/guess_word đã qua, gồm xuất MP4 thật ở mixed mode. Đã xuất mẫu 10 câu có TTS tại `outputs/guess-word-10-tts.mp4`, độ phân giải kiểm thử 180×320; dùng cấu hình chung để xuất 720×1280 hoặc 1080×1920. Kiểm thử âm thanh tự động xác nhận thời lượng theo audio và khoảng im lặng đếm ngược; chưa nghe nghiệm thu thủ công toàn bộ video.

Hai kiểm thử giao diện Tk không chạy được vì môi trường Python báo không tìm thấy Tcl `init.tcl`, kể cả khi trỏ sang runtime đi kèm bản đóng gói. Vì vậy form, thanh tua và phát âm thanh khi tua cần kiểm tra trực tiếp trên máy có Tcl/Tk hoạt động. Không xem các kiểm thử này là đã đạt.

Cập nhật kiểm tra bản đóng gói: `release-current/QuizStudio/QuizStudio.exe --self-check` đã chạy thành công ngoài sandbox, khởi tạo giao diện, dựng preview cho đủ 12 dạng nội dung và kiểm tra FFmpeg. Lỗi Tcl nói trên xảy ra trong sandbox. Kết quả lưu tại `outputs/current-self-check-unrestricted.json`; kiểm tra này chưa bao gồm thao tác tua và nghe âm thanh khi tua.
