import io
import re
import threading
from pathlib import Path
from typing import TextIO


def normalize_extension(extension: str) -> str:
    extension = extension.strip().casefold()
    if extension and not extension.startswith("."):
        extension = "." + extension
    return extension


def normalize_keyword(keyword: str, case_sensitive: bool) -> str:
    return keyword if case_sensitive else keyword.casefold()


def count_filename_matches(
    path: str,
    keyword: str,
    case_sensitive: bool,
    whole_word: bool,
) -> int:
    keyword = normalize_keyword(keyword, case_sensitive)
    if not keyword:
        return 0

    filename = Path(path).stem
    searchable_name = filename if case_sensitive else filename.casefold()
    if whole_word:
        pattern = re.compile(rf"(?<!\w){re.escape(keyword)}(?!\w)")
        return sum(1 for _ in pattern.finditer(searchable_name))
    return searchable_name.count(keyword)


def count_keyword_matches(
    path: str,
    keyword: str,
    case_sensitive: bool,
    cancel_event: threading.Event,
    whole_word: bool = False,
) -> tuple[int | None, str | None, str]:
    keyword = normalize_keyword(keyword, case_sensitive)
    if cancel_event.is_set():
        return None, None, ""

    try:
        with open(path, "rb") as raw_file:
            sample = raw_file.read(8192)
            encoding = "utf-8"
            if sample.startswith((b"\x00\x00\xfe\xff", b"\xff\xfe\x00\x00")):
                encoding = "utf-32"
            elif sample.startswith(b"\xef\xbb\xbf"):
                encoding = "utf-8-sig"
            elif sample.startswith((b"\xfe\xff", b"\xff\xfe")):
                encoding = "utf-16"
            elif b"\x00" in sample:
                return None, "Binary file cannot be searched as text", ""
            raw_file.seek(0)
            with io.TextIOWrapper(raw_file, encoding=encoding) as file:
                return count_matches_in_file(file, keyword, case_sensitive, cancel_event, whole_word)
    except OSError as error:
        return None, f"{type(error).__name__}: {error.strerror or error}", ""
    except UnicodeError as error:
        return None, f"Text decoding error: {error}", ""


def count_matches_in_file(
    file: TextIO,
    keyword: str,
    case_sensitive: bool,
    cancel_event: threading.Event,
    whole_word: bool,
) -> tuple[int | None, str | None, str]:
    pattern = re.compile(rf"(?<!\w){re.escape(keyword)}(?!\w)") if keyword and whole_word else None
    matches = 0
    preview = ""
    for line in file:
        if cancel_event.is_set():
            return None, None, ""
        if not keyword:
            continue
        searchable_line = line if case_sensitive else line.casefold()
        if pattern is None:
            line_matches = searchable_line.count(keyword)
            match_start = searchable_line.find(keyword)
            match_end = match_start + len(keyword) if match_start >= 0 else -1
        else:
            line_matches = sum(1 for _ in pattern.finditer(searchable_line))
            first_match = pattern.search(searchable_line)
            match_start = first_match.start() if first_match else -1
            match_end = first_match.end() if first_match else -1
        matches += line_matches
        if line_matches and not preview:
            display_line = " ".join(line.strip().split())
            display_searchable = display_line if case_sensitive else display_line.casefold()
            if pattern is None:
                folded_match_start = display_searchable.find(keyword)
                folded_match_end = folded_match_start + len(keyword)
            else:
                display_match = pattern.search(display_searchable)
                folded_match_start = display_match.start() if display_match else 0
                folded_match_end = display_match.end() if display_match else folded_match_start
            if case_sensitive:
                match_start, match_end = folded_match_start, folded_match_end
            else:
                match_start = _folded_offset_to_original(display_line, folded_match_start)
                match_end = _folded_offset_to_original(display_line, folded_match_end, end_offset=True)
            start = max(0, match_start - 60)
            end = min(len(display_line), match_end + 60)
            preview = ("..." if start else "") + display_line[start:end] + ("..." if end < len(display_line) else "")
    return matches, None, preview


def _folded_offset_to_original(text: str, offset: int, end_offset: bool = False) -> int:
    folded_offset = 0
    for original_offset, character in enumerate(text):
        next_folded_offset = folded_offset + len(character.casefold())
        if offset < next_folded_offset:
            return original_offset + int(end_offset)
        folded_offset = next_folded_offset
    return len(text)