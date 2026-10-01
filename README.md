# Parallely

A local desktop app for finding keyword matches in filenames and readable file contents, using a configurable thread pool.

## Privacy and Storage

Parallely does not use a database. Scans run locally against the folder you select; file contents and results are not uploaded or saved to a database. Results stay in the current app session and can be removed with **Clear Results**.

## Run

```powershell
python -m pip install -r requirements.txt
python main.py
```

## Search

Choose a folder and an extension, or select **Include all file types**. Enter a keyword to search both the filename (without its extension) and readable text contents. The **Matched in** and **Match preview** columns show where a match was found. Binary files are skipped unless their filename matches the keyword. Use the **Skipped** tab to review skipped paths and reasons.
