import os
import threading
import time
from collections import deque
from collections.abc import Iterator
from concurrent.futures import FIRST_COMPLETED, Future, ThreadPoolExecutor, wait

from PySide6.QtCore import QObject, Signal

from preprocess import count_filename_matches, count_keyword_matches, normalize_extension


class ScanSignals(QObject):
    discovered = Signal(int)
    progress = Signal(int, int)
    match = Signal(str, int, int, str, str)
    skipped = Signal(str, str)
    finished = Signal(int, int, float, bool)


def iter_candidate_files(folder: str, extension: str, cancel_event: threading.Event) -> Iterator[str]:
    directories = deque([folder])
    while directories and not cancel_event.is_set():
        current_directory = directories.popleft()
        try:
            with os.scandir(current_directory) as entries:
                for entry in entries:
                    if cancel_event.is_set():
                        return
                    try:
                        if entry.is_dir(follow_symlinks=False):
                            directories.append(entry.path)
                        elif entry.is_file() and (not extension or entry.name.casefold().endswith(extension)):
                            yield entry.path
                    except OSError:
                        continue
        except OSError:
            continue


def scan_batch(
    paths: list[str],
    keyword: str,
    case_sensitive: bool,
    cancel_event: threading.Event,
    whole_word: bool,
) -> list[tuple[str, int | None, int, str | None, str, str]]:
    results = []
    for path in paths:
        if cancel_event.is_set():
            break
        filename_matches = count_filename_matches(path, keyword, case_sensitive, whole_word)
        file_matches, error, preview = count_keyword_matches(
            path,
            keyword,
            case_sensitive,
            cancel_event,
            whole_word,
        )
        if file_matches is None and error is None and cancel_event.is_set():
            break
        if error is not None and filename_matches:
            file_matches = 0
            error = None
        try:
            size = os.path.getsize(path)
        except OSError:
            size = 0
        if error is not None or file_matches is None:
            results.append((path, None, size, error, "", ""))
            continue

        content_matches = file_matches
        total_matches = filename_matches + content_matches
        if not keyword:
            match_source = "All files"
        elif filename_matches and content_matches:
            match_source = "File name + contents"
        elif filename_matches:
            match_source = "File name"
        else:
            match_source = "Contents"
        results.append((path, total_matches, size, None, match_source, preview))
    return results


def scan_folder(
    folder: str,
    extension: str,
    keyword: str,
    case_sensitive: bool,
    worker_count: int,
    cancel_event: threading.Event,
    signals: ScanSignals,
    file_paths: list[str] | None = None,
    whole_word: bool = False,
):
    started_at = time.perf_counter()
    scanned = 0
    matches = 0
    extension = normalize_extension(extension)
    candidate_files = iter(file_paths) if file_paths is not None else iter_candidate_files(folder, extension, cancel_event)
    discovered = 0
    exhausted = False
    batch_size = 16
    pending_limit = worker_count * 2
    pending: dict[Future, list[str]] = {}
    pool = ThreadPoolExecutor(max_workers=worker_count)
    signals.discovered.emit(discovered)
    signals.progress.emit(0, 0)
    try:
        while pending or not exhausted:
            while (
                not cancel_event.is_set()
                and not exhausted
                and len(pending) < pending_limit
            ):
                batch = []
                for _ in range(batch_size):
                    if cancel_event.is_set():
                        break
                    try:
                        batch.append(next(candidate_files))
                    except StopIteration:
                        exhausted = True
                        break

                if batch:
                    discovered += len(batch)
                    signals.discovered.emit(discovered)
                    pending[pool.submit(
                        scan_batch,
                        batch,
                        keyword,
                        case_sensitive,
                        cancel_event,
                        whole_word,
                    )] = batch

            if cancel_event.is_set():
                exhausted = True
            if not pending:
                break

            completed, _ = wait(pending, timeout=0.1, return_when=FIRST_COMPLETED)
            for future in completed:
                batch = pending.pop(future)
                try:
                    batch_results = future.result()
                except Exception as error:
                    batch_results = [
                        (path, None, 0, f"Worker error: {error}", "", "")
                        for path in batch
                    ]
                for path, total_matches, size, error, match_source, preview in batch_results:
                    if total_matches is None and error is None and cancel_event.is_set():
                        continue
                    scanned += 1
                    if error is not None:
                        signals.skipped.emit(path, error)
                    elif total_matches is not None:
                        matches += total_matches
                        if total_matches or not keyword:
                            signals.match.emit(path, total_matches, size, match_source, preview)
                signals.progress.emit(scanned, matches)
    finally:
        pool.shutdown(wait=True, cancel_futures=True)
        duration = time.perf_counter() - started_at
        signals.finished.emit(scanned, matches, duration, cancel_event.is_set())