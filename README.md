# Parallely

A local desktop application for searching a folder and its subfolders for a keyword. Parallely checks both each file's name and readable text contents, then shows matching files, match counts, and a short content preview.

## What the App Does

- Recursively scans a folder you choose.
- Filters by one file extension, or scans all extensions.
- Searches the filename (without its extension) and readable file contents.
- Supports case-sensitive matching and optional whole-word matching.
- Shows where a match was found, the number of occurrences, file size, and a preview from the first matching content line.
- Runs scans with a configurable number of worker threads. Scans can be cancelled, and unreadable or binary files are listed in the Skipped tab.
- Double-clicks a result to open it, or use its context menu to reveal it in File Explorer.

With a blank keyword, the app lists readable text files in the selected scope. Binary files can still appear when their filename matches a non-blank keyword.

## Keyword Matching

The keyword is checked separately against the filename stem and each line of file content. A match cannot span multiple lines.

- Matching is case-insensitive by default using Unicode `casefold`; enable **Case-sensitive** to preserve capitalization.
- With **Whole word** enabled, an escaped regular expression with word-boundary lookarounds prevents matches inside longer words.
- Otherwise, Python's `str.count()` counts literal, non-overlapping occurrences.
- The preview shows a short excerpt around the first matching content occurrence. Filename-only matches have no content preview.

## Search Algorithm and Concurrency

**Algorithm type:** exhaustive (linear) file traversal with literal string matching, also commonly called brute-force search. The scanner checks every candidate file; it does not prune candidates using branch-and-bound, and it does not use binary search because files and keywords are not stored in a sorted index. The binary-file check described below is only a way to avoid decoding likely binary data; it is unrelated to binary search.

### Search Steps

1. The producer initializes a FIFO `collections.deque` with the selected folder. It removes directories from the front and uses `os.scandir()` to inspect entries, appending child directories to the back. This is breadth-first search (BFS): directories are visited level by level.
2. Each discovered file is checked against the extension filter. Matching paths are accumulated into batches of up to 16 and submitted as soon as a batch is ready; the full candidate-file list is never built in advance.
3. A worker counts keyword occurrences in the filename stem (the name without its extension), then reads text from beginning to end, one UTF-8 line at a time. Invalid UTF-8 bytes are ignored; a null byte in the first 8 KB marks a file as binary and skips content search.
4. In regular mode, Python's `str.count()` finds literal, non-overlapping occurrences. In whole-word mode, an escaped keyword is matched with a regular expression using `(?<!\w)` and `(?!\w)` boundaries.
5. Filename and content counts are added. The scanner records the first matching content line for the preview and reports the source of each match.

This is exhaustive search: every eligible file is visited, even after a match is found, because the app reports occurrence counts. It is not branch-and-bound because there is no pruning, and it is not binary search because there is no sorted index to search. The binary-file check is unrelated to binary search.

For `E` directory entries inspected and `C` bytes of candidate text content read, work grows approximately with `E + C`. The directory queue stores the current BFS frontier; file batches and their results are bounded by the in-flight batch limit. Results shown in the UI remain in memory for the duration of the session.

### Concurrent Processing

- **Producer:** the scan coordinator performs BFS directory discovery and streams each batch of up to 16 matching file paths into the pool.
- **Thread-pool consumers:** `ThreadPoolExecutor` runs up to `W` batch workers concurrently, where `W` is the configured worker count. Each worker scans its own batch and returns per-file results; workers do not share matching state.
- **Backpressure:** the coordinator keeps at most `2 * W` batch futures in flight. When that limit is reached, it waits instead of discovering and queuing an unbounded number of files.
- **Result consumer:** the coordinator waits for the first completed future, collects its results, updates counts, and emits progress and matches to the UI through Qt signals. Discovery totals are emitted incrementally as batches are submitted.
- A shared `threading.Event` provides cooperative cancellation during directory traversal and between files or text lines. Cancellation does not instantly interrupt a file read already in progress.

The thread pool overlaps file I/O; it does not change the exhaustive search algorithm or guarantee a speedup, since disk performance and worker count affect elapsed time. This is literal text searching, not OCR or semantic search. The current scanner does not extract text from PDF or office-document formats.

## File Types and Roadmap

The current extension field is generic: you can enter one suffix or choose **Include all file types**. Content search reads files as UTF-8 text and skips files detected as binary. There are no format-specific parsers yet, so entering an extension does not guarantee that its file contents can be searched.

The next update is planned to add explicit support for:

- Source and data files: `.json`, `.py`, `.c++`, `.c`, and `.java`.
- PDF keyword matching through text extraction. OCR for scanned, image-only PDFs may follow separately.
- Excel workbooks (`.xlsx`) and Word documents (`.docx`), with legacy `.doc` support to be evaluated.

Until those updates are implemented, PDF and office-document contents are not extracted; binary files are reported in the Skipped tab unless their filenames match the keyword.

## Privacy and Storage

Scans run locally against the folder you select. Parallely does not upload or save file contents and results to a database; results remain in the current app session and can be removed with **Clear Results**.

## Run

```powershell
python -m pip install -r requirements.txt
python main.py
```
