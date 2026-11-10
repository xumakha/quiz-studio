# Quiz Studio cho Windows và macOS

App dùng chung một bộ mã nguồn và tự nhận hệ điều hành. Windows phát âm thanh bằng `winsound`, mở thư mục bằng Explorer; macOS phát bằng `afplay`, mở thư mục bằng Finder. Không cần sửa code hoặc chọn hệ điều hành trong app.

| Thao tác | Windows | macOS |
| --- | --- | --- |
| Khởi động | `run.bat` | `run.command` |
| Đóng gói bản mới | `build.bat` → `release-history/QuizStudio/QuizStudio.exe` | `build-macos.command` → `.app` |
| Môi trường Python | `.venv` | `.venv-macos` |

Khi chuyển mã nguồn giữa hai máy, cài thư viện riêng bằng launcher trên mỗi máy; không sao chép môi trường Python. Bản `.exe`/`.app` cũ không tự cập nhật theo mã nguồn: cần đóng gói lại trên hệ điều hành tương ứng để dùng các sửa đổi mới. `run.bat` ưu tiên mở bản `.exe` đã có; nếu muốn dùng mã nguồn mới trực tiếp, chạy `.venv\Scripts\python.exe app.py` sau khi cài thư viện.

Sau khi clone, cài Python 3.11 trở lên rồi chạy `run.bat` để cài thư viện và mở app từ mã nguồn nếu chưa có bản đóng gói. Chạy `build.bat` để tạo bản `.exe` tại `release-history/QuizStudio`.

Nhấp đúp **Mo-QuizStudio.bat** để mở bản mới nhất tại `release-history/QuizStudio/QuizStudio.exe`. Khi chuyển sang máy khác, sao chép cả thư mục `release-history/QuizStudio`, bao gồm `_internal`. Không chạy file trong thư mục `build-tabs`: đó là file đóng gói trung gian.

## Chạy trên macOS

Cài Python **3.11 trở lên có Tkinter**, sau đó nhấp đúp `run.command` hoặc chạy `./run.command` trong Terminal. Lần đầu cần Internet để cài thư viện vào `.venv-macos` riêng; các lần sau vẫn kiểm tra thư viện trước khi mở app. Windows tiếp tục dùng các file `.bat` như trước.

Launcher tự tìm Python 3.11+ có Tkinter trong môi trường dự án, PATH, Homebrew và bộ cài python.org; vì vậy vẫn chạy được khi lệnh `python3` trỏ tới Python cũ của macOS. Có thể chọn trình thông dịch bằng `QUIZ_PYTHON=/duong/dan/python3 ./run.command`. Nếu thiếu Tkinter, dùng bộ cài Python từ python.org hoặc cài gói Homebrew `python-tk` khớp phiên bản Python đang dùng.

Nếu Python Homebrew báo lỗi `pyexpat` / `Symbol not found: _XML_SetAllocTrackerActivationThreshold`, chạy `brew install expat` rồi mở lại. Launcher sẽ dùng thư viện Expat này riêng cho tiến trình app khi cần, không thay thư viện hệ thống.

Chạy `./build-macos.command` trên Mac để tạo **`release-macos/QuizStudio.app`**, sau đó mở bằng Finder. Bản build theo kiến trúc Python của máy đóng gói (Apple Silicon hoặc Intel); nên build trên từng kiến trúc nếu cần phát hành cho cả hai. Bản `.app` chưa được ký bằng Developer ID hoặc notarize. Nếu macOS chặn mở, dùng **System Settings → Privacy & Security → Open Anyway** sau khi xác nhận nguồn ứng dụng.

Cài đặt và thư viện media trên Mac được lưu tại `~/Library/Application Support/QuizStudio`. Nút mở thư mục sử dụng Finder; video xuất xong được chọn sẵn trong Finder. Font render dùng Arial có sẵn trên macOS, bao gồm tiếng Việt và IPA.

Chạy kiểm tra: `.venv-macos/bin/python -m unittest discover -v`.

## Tạo video

Mỗi lần mở app có sẵn năm tab theo thứ tự **Một chút English**, **Easy Prep**, **ASVAB-Prep**, **easy-pass.app**, **dmv-prep.org**, và chọn tab đầu tiên. Mỗi tab tự nhớ riêng giọng đọc, nền, nhạc, logo, ảnh kết thúc, câu kết và các tùy chỉnh video, kể cả sau khi đóng rồi mở lại app. Khi nâng cấp, cài đặt đã lưu của bản cũ được giữ cho tab **Một chút English**. Bốn tab còn lại bắt đầu với thông số cơ bản, chữ watermark theo tên tab và câu kết để trống; hãy chọn ảnh và chỉnh thông số riêng cho từng kênh. Tab **easy-pass.app** dùng giao diện **easy-pass.app · Xanh nhạt**, nền màu #D9EDF7 mặc định. Tab **dmv-prep.org** dùng mẫu **dmv-prep.org · Luyện thi lái xe**, màu chủ đạo **#4471FD**, bố cục làn đường và thẻ câu hỏi riêng. JSON mẫu: `examples/dmv_questions.json`.

Bấm **+** trên thanh tab để mở thêm video; **Ctrl+T** tạo tab, **Ctrl+W** đóng tab, **Ctrl+Tab / Ctrl+Shift+Tab** chuyển tab (macOS hỗ trợ thêm **Cmd+T / Cmd+W**). Mỗi tab giữ riêng JSON, bản nháp từng dạng, giọng đọc, nền, nhạc, logo, ảnh kết thúc, xem trước và tiến độ. Có thể xuất video ở nhiều tab cùng lúc; phần trăm hiển thị ngay trên tab. Chuyển tab dừng phát thử âm thanh, còn tác vụ xuất tiếp tục chạy. Nút **Hủy tác vụ** chỉ tác động tới tab hiện tại. Hai tab đang xuất không được ghi cùng một file.

Nhấp đúp vào tên tab hoặc chuột phải → **Đổi tên tab…** để đặt tên riêng (1–80 ký tự). Tên tab được lưu cho lần mở sau; đổi tên không thay đổi bộ cài đặt của tab. Tab mới sao chép cài đặt của tab đang chọn rồi lưu độc lập. Các tab mở thêm còn mở khi thoát app cũng được khôi phục cùng tên và cài đặt.

Bấm **Lịch sử video** trên thanh tab để mở danh sách dùng chung cho mọi tab. Mỗi lần xuất MP4 thành công sẽ lưu tên video từ `title`, dạng video và caption tại thời điểm xuất. Chọn một bản ghi để xem caption đầy đủ, **Sao chép caption** hoặc **Mở thư mục**. Lịch sử được lưu trong `history.sqlite3` dưới thư mục dữ liệu người dùng, còn khi đóng và mở lại app. Video xuất trước khi có tính năng này không tự xuất hiện trong lịch sử.

Trong **Tùy chỉnh video → Video → Câu kết cuối video**, tự nhập lời đọc khi hiện ảnh kết thúc. Bấm **Nghe thử câu kết** để xem/nghe riêng đoạn kết; dùng **Dùng câu kết mặc định** để khôi phục. Để trống để chỉ hiện ảnh, không đọc câu kết. Cần bật **Tạo giọng đọc** trong tab Giọng đọc; nội dung dùng giọng chính, còn đoạn `[en]…[/en]` dùng giọng tiếng Anh. Ảnh kết thúc giữ ít nhất 3 giây và kéo dài đến khi đọc xong. Mỗi tab giữ câu kết riêng; câu kết tự lưu cùng cài đặt cho lần mở sau.

Đóng tab đang xử lý hoặc có JSON chưa lưu sẽ yêu cầu xác nhận. Khi đóng tab đang xuất, app hủy và đợi tác vụ dừng trước khi bỏ tab. JSON và bản nháp chỉ giữ trong phiên làm việc; dùng **Lưu JSON** để giữ nội dung. Đóng một trong bốn tab mặc định chỉ ẩn tab trong phiên hiện tại; lần mở app tiếp theo tab xuất hiện lại với tên và cài đặt đã lưu. Tab mở thêm đã đóng sẽ không tự mở lại. Xuất nhiều video đồng thời sử dụng thêm CPU và RAM, tốc độ tùy cấu hình máy.

Trong **Tùy chỉnh video → Video**, mục **Logo chìm → Chọn ảnh logo** thay logo mờ sau nội dung. **Logo góc trái** và **Ảnh chibi góc phải** điều khiển hai ảnh ở đầu video, mỗi mục có bật/tắt và chọn ảnh riêng. Mục **Ảnh cuối video → Chọn ảnh cuối video** thay ảnh đoạn kết; **Xem trước ảnh kết thúc** kiểm tra ngay trong khung xem trước. Các mục đều có nút **Dùng ảnh mặc định**. PNG, JPG, WebP và BMP được sao chép vào thư viện `branding/images` trong thư mục dữ liệu người dùng; di chuyển file gốc không làm mất ảnh đã chọn. Mỗi tab có thể dùng ảnh và bật/tắt hai góc khác nhau. Tắt ảnh góc vẫn giữ lựa chọn ảnh để bật lại; không ảnh hưởng logo chìm hoặc chữ watermark. Lựa chọn tự lưu cùng cài đặt. Khi nâng cấp từ bản chưa có hai mục góc, logo góc trái giữ ảnh logo đã chọn trước đó.

Mỗi mục có danh sách **Ảnh đã tải lên** và nút **Dùng ảnh đã chọn** để chọn lại ảnh cũ. Các danh sách dùng chung thư viện ảnh, vì vậy có thể dùng một ảnh cho logo, chibi và đoạn kết. **Làm mới thư viện ảnh** cập nhật file mới; **Mở thư mục ảnh đã tải** mở thư viện. Khôi phục ảnh mặc định không xóa ảnh đã tải. Ảnh từ bản trước vẫn được tìm thấy, kể cả khi chưa có thông tin tên gốc (khi đó hiển thị tên file đã lưu).

Trong tab **Nền → Thư viện nền đã tải lên**, chọn ảnh hoặc video đã lưu rồi bấm **Dùng ảnh này** / **Dùng video này**. Hai thư mục riêng nằm tại `%LOCALAPPDATA%\QuizStudio\backgrounds\images` và `%LOCALAPPDATA%\QuizStudio\backgrounds\videos`; có nút mở từng thư mục ngay trong ứng dụng. Bấm **Làm mới thư viện** sau khi thêm file trực tiếp vào thư mục. Bỏ nền hiện tại không xóa các file trong thư viện. Các nền từ phiên bản cũ cũng được đưa vào thư viện; file cũ không còn thông tin tên gốc sẽ hiển thị tên file đã lưu.

1. Mở JSON trong app; có mẫu tại `examples/questions.json` và nội dung tiếng Anh tại `examples/tieng-anh-co-ban-6-phut.json`.
2. Chỉnh giọng Việt/Anh, tốc độ, cao độ và thời gian suy nghĩ trong tab Giọng đọc. Đoạn `[en]...[/en]` dùng giọng tiếng Anh riêng.
3. Trong tab Nền, chọn ảnh hoặc video nền (MP4, MOV, MKV, WebM, AVI, M4V), chọn nhạc và chỉnh mức làm tối, âm lượng. Video nền tự lặp, chạy liên tục qua các câu hỏi, được cắt giữa để phủ kín khung hình và tắt âm thanh gốc. Video chạy ngay trong khung xem trước và khi phát thử nội dung; đoạn kết vẫn dùng ảnh kết thúc riêng. Ảnh/video và nhạc nền được sao chép vào `%LOCALAPPDATA%\QuizStudio` để lần sau tự nạp lại, kể cả khi file gốc bị di chuyển hoặc xóa. Bỏ nền / nhạc nền xóa cả hai lựa chọn đã lưu.
4. Trong tab Video, dùng lựa chọn Giao diện cho toàn bộ video để chuyển giữa Toán, Tiếng Anh, Quiz nhiều màu hoặc tự động theo môn học của câu đầu tiên. Mỗi video chỉ dùng một giao diện cho tất cả câu hỏi, đếm ngược và đáp án; xem trước cũng dùng giao diện đó. Bật/tắt watermark và sửa chữ; chọn độ phân giải.
5. Kiểm tra & xem trước, chọn câu và bật hiện đáp án để xem bố cục. Danh sách câu hỏi cho phép chọn nhanh.
6. Xuất video MP4, theo dõi phần trăm và bước xử lý. Khi hoàn tất, Mở trong thư mục chọn sẵn file video. Nút Hủy dừng tác vụ mà không ghi đè file đích chưa hoàn tất.

Video H.264/AAC, 30 fps, 9:16, 720×1280 hoặc 1080×1920. Một file chứa toàn bộ câu hỏi theo thứ tự: đọc câu hỏi/lựa chọn → đếm ngược → đáp án/giải thích. Không có tấm nền xám lớn bao quanh nội dung; dấu tick được vẽ bằng nét.

Câu hỏi, lựa chọn, giải thích và watermark nằm phía trên khoảng trống ở đáy video để tránh tên page và mô tả khi xem trên mạng xã hội.

Khi bật giọng đọc, phần đáp án chỉ đọc ký tự phương án, ví dụ “Đáp án đúng là C.”; nội dung lựa chọn và giải thích vẫn hiển thị trên màn hình. Sau khi đọc xong đáp án và phần giải thích cuối cùng (nếu bật đọc giải thích), video hiện ảnh kết thúc đã chọn khoảng 3 giây và đọc câu kết của tab đó. Ảnh mặc định là `assets/ending-img.png`; câu kết mặc định của **Một chút English** là “theo dõi một chút english để học thêm một chút tiếng anh mỗi ngày nhé!”. **Easy Prep** và **ASVAB-Prep** ban đầu để trống câu kết. Nếu giọng đọc dài hơn, ảnh được giữ đến khi đọc xong. Khi tắt giọng đọc, ảnh kết thúc vẫn hiện 3 giây.

Các tùy chỉnh tự lưu khi thay đổi và khi đóng app: giọng chính/tiếng Anh, tốc độ, cao độ, thời gian suy nghĩ, đọc lựa chọn, bật giọng đọc, giao diện video, độ phân giải, chữ/bật watermark, âm lượng nhạc, độ tối nền và chế độ xem đáp án. Mở app lại sẽ khôi phục các giá trị riêng của từng tab. Cài đặt nằm trong `profiles/<mã-tab>` dưới thư mục dữ liệu người dùng; danh sách và tên tab nằm trong `tabs.json`. Thư viện ảnh, nền và nhạc vẫn dùng chung, còn lựa chọn của từng tab được lưu riêng. Cài đặt và media nằm ngoài thư mục bản `.exe`, nên vẫn giữ khi cập nhật app; dữ liệu ảnh nền của bản trước cũng được giữ lại.

Giọng Google Việt/Anh là mặc định và cần Internet. Giọng Edge nam/nữ cũng có trong danh sách nhưng có thể gặp lỗi kết nối dịch vụ. App tự thử tối đa 3 lần khi dịch vụ lỗi hoặc không trả âm thanh, giữ nguyên giọng đã chọn. Nếu vẫn lỗi, thông báo ghi rõ giọng và hướng dẫn chọn Google Việt/Anh tương ứng trong tab Giọng đọc. Dạng Đoán từ cũng giữ lựa chọn Google English cho phần giải thích. Bỏ chọn Tạo giọng đọc để xuất offline. Chưa có nhái giọng hoặc tự đăng mạng xã hội.

Âm thanh được ghép ở dạng PCM và mã hóa AAC một lần khi hoàn thiện MP4, tránh lỗi timestamp ở điểm nối giữa các giây đếm ngược và đáp án. Nhạc nền được lặp và trộn trên một dòng thời gian liên tục. Khi ảnh kết thúc xuất hiện, nhạc nền giảm dần về 0 đúng cuối video; âm lượng giọng đọc giữ nguyên.

## JSON

App luôn mở ở dạng **Trắc nghiệm ABCD**. Có bộ chọn 11 dạng học và video tổng hợp; mỗi dạng giữ bản nháp riêng trong phiên. Xem [tài liệu JSON v2 và editor](docs/content-v2.md), [JSON Schema](docs/content-v2.schema.json) và [các mẫu sẵn dùng](examples/v2). Chạy `.venv\Scripts\python.exe app.py` để dùng mã nguồn mới; bản exe cũ cần đóng gói lại.

Nhận mảng câu hỏi hoặc `{ "title": "...", "questions": [...] }`. `question`, `options` (2–6 chuỗi) và đáp án là bắt buộc. `answer` nhận A–F, nguyên văn lựa chọn hoặc số nguyên từ **0**; cũng nhận `correct_answer`/`answer_index`. `explanation` không bắt buộc. `subject` và `lesson` giúp tự nhận diện môn học; sau đó xét tiêu đề và thẻ `[en]`. Môn chưa nhận diện dùng mẫu Quiz nhiều màu. Mẫu này cũng nhận `grade`/`class` để hiển thị lớp.

Thêm `"caption": "Nội dung đăng video\n#quiz"` ở cấp ngoài cùng, cùng cấp với `title` trong JSON v2 hoặc JSON `{title, questions}`. Caption là chuỗi tùy chọn; dùng `\n` để xuống dòng, `\"` để viết dấu ngoặc kép, hoặc bỏ qua khi không cần. Caption được giữ nguyên khi sửa item và lưu JSON, dùng trong **Lịch sử video**; không đưa vào hình hoặc giọng đọc của video.

## Mã nguồn và đóng gói

- `app.py`, `modern_ui.py`, `icons.py`: cửa sổ nhiều tab, giao diện và thao tác app.
- `engine.py`, `video_themes.py`, `video_classic.py`: giọng đọc, xuất MP4 và các mẫu video.
- `preferences.py`, `workspace_profiles.py`: lưu cài đặt riêng theo tab và quản lý thư viện media dùng chung.
- `requirements.txt`, `.venv`: thư viện chạy từ mã nguồn; `run.bat` hỗ trợ khởi động.
- `build.bat`: đóng gói bản mới vào `release-history`; đóng app trước khi đóng gói lại.
- `test_*.py`: kiểm tra dữ liệu, render, chọn mẫu, watermark và lưu ảnh nền.

Chạy kiểm tra: `.venv\Scripts\python.exe -m unittest discover -v`. Chạy từ mã nguồn cần Python 3.11 trở lên.
