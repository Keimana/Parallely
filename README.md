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

## Algorithms and Concurrency

- `os.walk()` traverses the selected folder tree and discovers candidate files. An extension suffix filter is applied during discovery unless **Include all file types** is selected.
- The scanner checks each filename stem, then reads text content line by line as UTF-8. Invalid UTF-8 bytes are ignored. A null byte in the first 8 KB is used as a basic binary-file check; detected binary files are skipped for content search.
- Candidate paths are divided into batches and processed by `concurrent.futures.ThreadPoolExecutor`. Batch size scales with the number of files and workers, with a maximum of 16 files per batch and at most two outstanding batches per worker.
- A `threading.Event` provides cooperative cancellation during folder traversal, between files, and between text lines. Qt signals send progress and results back to the interface.

This is literal text searching, not OCR or semantic search. The current scanner does not extract text from PDF or office-document formats.

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
