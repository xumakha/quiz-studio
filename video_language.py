"""Language of generated video copy; authored lesson content stays untouched."""

ENGLISH_TEMPLATES = frozenset(("exam", "military", "tech", "dmv"))

CONTENT_LABELS_EN = {
    "guess_word": "Guess the word", "multiple_choice": "Multiple choice",
    "error_correction": "Error correction", "fill_blank": "Fill in the blank",
    "word_order": "Word order", "translation": "Quick translation",
    "listening": "Listening practice", "dialogue": "Complete the dialogue",
    "true_false": "True or false", "multiple_meanings": "Multiple meanings",
    "sentence_upgrade": "Sentence upgrade", "phrase_lesson": "Phrase practice",
}

COPY_EN = {
    "Tìm và sửa lỗi sai": "Find and correct the error",
    "Phần cần sửa": "Find the error", "Câu đã sửa": "Corrected sentence",
    "Điền từ vào chỗ trống": "Fill in the blank", "Câu hoàn chỉnh": "Complete sentence",
    "Sắp xếp từ": "Put the words in order",
    "Sắp xếp các từ thành câu.": "Put the words in order to make a sentence.",
    "Dịch nhanh": "Translate the sentence", "Cách nói gợi ý": "Suggested translation",
    "Nghe và đoán câu": "Listen and identify the sentence", "Lắng nghe": "Listen carefully",
    "Câu vừa nghe": "Transcript", "Hoàn thành hội thoại": "Complete the dialogue",
    "Câu đáp gợi ý": "Suggested response", "Đúng hay sai?": "True or false?",
    "Đáp án": "Answer", "Câu ban đầu": "Original sentence",
    "Thêm một cách nói": "Another way to say it", "Học theo cụm": "Learn a phrase",
    "Nghĩa": "Meaning", "Ví dụ": "Example", "Chuẩn bị": "Get ready",
    "Giải thích": "Explanation",
}


def english_video(settings):
    return settings.template in ENGLISH_TEMPLATES


def generated_copy(text, settings):
    return COPY_EN.get(text, text) if english_video(settings) else text
