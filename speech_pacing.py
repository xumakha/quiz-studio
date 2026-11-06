"""Small, explicit pauses for exam narration without altering displayed content."""
import re


def paced_prep(settings):
    return settings.template in ("exam", "military")


# Keep URLs, fractions, ratios, times and negative numbers intact. Hyphens
# inside words (e.g. well-known) are not phrase separators.
_SEPARATORS = re.compile(
    r"https?://\S+|(?<!\w)[-−]?\d+(?:\.\d+)?\s*[/：:\-−–]\s*[-−]?\d+(?:\.\d+)?\b"
    r"|(?P<separator>\s+-+\s+|[–—]+|[/\\|;；:：•·→]+)"
)


def speech_segments(text):
    """Return (spoken text, following silence, tempo) for one language run."""
    chunks = []
    start = 0
    for match in _SEPARATORS.finditer(text):
        separator = match.group("separator")
        if separator is None:
            continue
        words = text[start:match.start()].strip()
        # Read slash explicitly so alternatives/units retain their separator.
        spoken = "slash" if "/" in separator else "backslash" if "\\" in separator else "to" if "→" in separator else ""
        words = " ".join(filter(None, (words, spoken)))
        if words:
            chunks.append(words)
        start = match.end()
    tail = text[start:].strip()
    if tail:
        chunks.append(tail)
    if not chunks:
        return [(text, 0, 1)]
    # Also slow intact numeric expressions containing slash or colon slightly.
    paced = len(chunks) > 1 or start > 0 or bool(re.search(r"\d\s*[/：:\-−–]\s*[-−]?\d", text))
    return [(chunk, .3 if index < len(chunks)-1 else 0, .94 if paced else 1)
            for index, chunk in enumerate(chunks)]
