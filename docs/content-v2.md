# Nội dung Một Chút English - JSON v2

Mở app luôn chọn **Trắc nghiệm ABCD**, không nhớ dạng đã chọn lần trước. Nhập JSON v2 hợp lệ sẽ chọn theo `mode`/`type`; nhiều type tự nhận là `mixed` nếu không khai báo mode. Mode khai báo khác mixed phải khớp tất cả item.

Mở `examples/v2` để lấy 11 file mẫu từng dạng và `mixed.json`. Có thể đưa file mẫu và tài liệu này cho AI, yêu cầu tạo nội dung theo đúng cấu trúc. `content-v2.schema.json` là JSON Schema có oneOf theo type; app kiểm tra thêm quan hệ giữa các trường, vị trí highlight, số chỗ trống và thẻ ngôn ngữ.

```json
{
  "schema_version": 2,
  "title": "MỘT CHÚT ENGLISH",
  "mode": "fill_blank",
  "settings": {"thinking_seconds": 5},
  "items": [{
    "id": "fill-01",
    "type": "fill_blank",
    "question": "[en]She ___ a student.[/en]",
    "answer": "[en]is[/en]",
    "explanation": "Chủ ngữ [en]She[/en] dùng [en]is[/en]."
  }]
}
```

`type` bắt buộc trên mỗi item. `id` tùy chọn, nếu có phải duy nhất. `subject`, `prompt` là chuỗi tùy chọn. Các dạng hỏi mặc định suy nghĩ 5 giây theo cài đặt app; settings.thinking_seconds ghi đè cài đặt app, item.thinking_seconds ghi đè settings. Nhận số nguyên 0-30, 0 để bỏ đếm ngược. Các dạng bài học không đếm ngược.

| Type | Trường bắt buộc ngoài type | Trường tùy chọn |
| --- | --- | --- |
| multiple_choice | question, options (đúng 4 chuỗi), answer (A/B/C/D) | explanation |
| error_correction | question, answer, highlight {wrong, correct}, explanation | highlight.occurrence, highlight.start |
| fill_blank | question (đúng một ___), answer, explanation | completed_sentence |
| word_order | tokens [{id, text}], answer_order [id], explanation | |
| translation | source_text, source_language, target_language, suggested_answers, explanation | show_alternatives |
| listening | audio_text, transcript, translation, explanation | replay_count (1-5, mặc định 1) |
| dialogue | dialogue [{speaker, text}], missing_turn_index, suggested_answers, explanation | |
| true_false | statement, answer (boolean), explanation | correction |
| multiple_meanings | word, senses [{phrase, meaning, example}] | |
| sentence_upgrade | original, alternative, nuance | example_context |
| phrase_lesson | phrase, meaning, example | example_translation |

Các chuỗi bắt buộc không được trống. Danh sách bắt buộc không được trống. `source_language`/`target_language`: `vi` hoặc `en`. `suggested_answers[0]` là gợi ý chính; translation có `show_alternatives: true` để hiện thêm cách dịch. Dialogue luôn dùng gợi ý đầu tiên.

Highlight: `occurrence` bắt đầu từ 1, mặc định 1; `start` là vị trí ký tự từ 0 sau khi bỏ thẻ [en], ưu tiên hơn occurrence. Chỉ sửa một lần xuất hiện; answer phải khớp kết quả sửa đó. `completed_sentence` nếu có phải khớp câu sau khi điền đáp án. Token ID không trùng; answer_order phải chứa đúng mỗi ID một lần, kể cả khi nội dung token giống nhau. `missing_turn_index` từ 0; nội dung lượt này bị che trước bật mí kể cả khi JSON có câu thật.

Thẻ `[en]...[/en]` không hiển thị trên video, đọc bằng giọng Anh. Phần ngoài thẻ dùng giọng chính (mặc định Việt). Các trường tiếng Anh rõ ràng như audio_text, transcript, tokens, cụm và ví dụ được tự bọc khi chưa có thẻ. Với question/statement, nên chủ động đặt thẻ để xác định ngôn ngữ. Không lồng thẻ. Dùng xuống dòng `\n` có chủ đích; chia nhỏ nội dung khi app báo quá dài.

Editor: chọn dạng sẽ cất bản nháp hiện tại trong phiên làm việc, không tự nạp mẫu. Bấm **Dùng dữ liệu mẫu** mới thay nội dung. **Chỉnh qua form** mở form item đang chọn; các trường danh sách/object dùng JSON, các trường chuỗi sửa trực tiếp. Áp dụng chỉ thành công khi toàn bộ tài liệu hợp lệ. JSON là nguồn dữ liệu duy nhất; thay JSON khi form đang mở sẽ yêu cầu mở lại form để tránh ghi đè. Form có tiêu đề, thời gian chung và thời gian riêng. Các nút thêm, nhân bản, xóa, lên/xuống thao tác item đang chọn trong preview. Mixed cho chọn type khi thêm item. Bản nháp chỉ giữ trong phiên; lưu JSON trước khi đóng app.

**Thêm** mở form trống cho nội dung mới, không tự bịa câu hỏi/đáp án. Trong tab Giọng đọc, chọn giọng riêng tại **Hội thoại - Nhân vật A** và **Hội thoại - Nhân vật B**. Mặc định A là Jenny (nữ), B là Guy (nam); cả hai đều có thể chọn Jenny, Guy hoặc Google, nhưng phải khác nhau. Các lựa chọn tự lưu. Phần hướng dẫn/giải thích vẫn dùng giọng chính và giọng Anh chung theo thẻ [en]. Speaker A/B luôn dùng đúng giọng A/B; tên nhân vật khác được gán theo thứ tự xuất hiện (nhân vật đầu dùng giọng A, nhân vật thứ hai dùng giọng B; các nhân vật sau luân phiên hai giọng). Các trường lồng nhau (tokens, dialogue, senses, highlight) vẫn cần nhập JSON trong ô của form.

**Chạy item** hoặc **Toàn video** chuẩn bị giọng đọc rồi phát preview cùng scene và thời lượng đo âm thanh như export. **Dừng preview** dừng giọng và hình. Có cache TTS theo chữ, cả hai giọng, tốc độ và cao độ tại `%LOCALAPPDATA%/QuizStudio/tts-cache`. Preview lần đầu cần thời gian tạo giọng; có thể tắt TTS để xem bố cục offline. TTS lỗi chặn tác vụ và báo câu/giai đoạn; bấm chạy lại để thử lại, tận dụng cache đã tạo được. Không xuất âm thầm thiếu tiếng.

JSON cũ `{title, questions}` hoặc mảng câu hỏi vẫn nhận đáp án A-F/chỉ số/nguyên văn và 2-6 lựa chọn như trước. File cũ 4 lựa chọn được lưu sang v2; file 2/3/5/6 lựa chọn giữ schema cũ để không tạo file v2 sai chuẩn.

Chạy: `.venv\Scripts\python.exe app.py`. Kiểm tra: `.venv\Scripts\python.exe -m unittest discover -v`. Tạo lại mẫu/schema: `.venv\Scripts\python.exe generate_content_examples.py`. Bản exe đã đóng gói trước đây cần build lại bằng `build.bat` để có chức năng mới.
