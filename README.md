# ChatGPT Export Resumer

[English](README.md) | [Italiano](README.it.md)

**Resume interrupted ChatGPT data export downloads and recover ZIP files that appear corrupted.**

ChatGPT Export Resumer is a Python command-line tool that uses an authenticated request copied from Chrome, minimizes unnecessary cookies and downloads the ZIP through `curl`. If the export was downloaded only partially, it attempts to resume the transfer and validates the archive before extracting it. **No third-party Python packages are required.**

Developed by **Antonio Troise (Levysoft)**. Once you have prepared `chrome-curl.txt` with Chrome DevTools, you can run:

```bash
./chatgpt_export_resumer.py chrome-curl.txt --extract
```

## Why this exists

Sometimes a ChatGPT data export downloads only partially.

The file may look like a ZIP:

```bash
file chatgpt-export.zip
```

Example:

```text
chatgpt-export.zip: Zip archive data, at least v2.0 to extract, compression method=deflate
```

But then `unzip` fails:

```bash
unzip -t chatgpt-export.zip
```

Example:

```text
End-of-central-directory signature not found.
Either this file is not a zipfile, or it constitutes one disk of a multi-part archive.
```

This usually means that the beginning of the ZIP is present, but the end of the file is missing.

In ZIP archives, the central directory is stored at the end of the file. If the download is truncated, the file can still start like a real ZIP, but tools such as `unzip` cannot open it because the final index is missing.

This script automates the recovery workflow:

1. Reads a Chrome "Copy as cURL" command.
2. Extracts the ChatGPT export URL.
3. Extracts cookies from the browser request.
4. Removes unnecessary cookies, such as `conv_key_*`.
5. Downloads the export ZIP using `curl`.
6. Validates the archive with `unzip -t`.
7. Checks for ZIP end signatures:
   - normal EOCD,
   - ZIP64 EOCD,
   - ZIP64 locator.
8. If the file is incomplete, resumes the download with `curl -C -`.
9. Generates a sanitized technical report.
10. Optionally extracts the ZIP and opens `chat.html`.

## Features

- **Authenticated downloads**: reads the ChatGPT export URL and cookies from Chrome's **Copy as cURL** request.
- **Cookie filtering**: discards unnecessary cookies such as `conv_key_*` and retains the ones generally needed for the request.
- **Automatic resume**: continues incomplete downloads using `curl -C -`, without starting from zero when the server supports byte-range requests.
- **ZIP validation**: tests the archive with `unzip` (or Python's `zipfile` fallback) and checks EOCD/ZIP64 signatures.
- **Flexible output**: detailed or quiet execution, progress control, diagnostic reports, optional extraction and opening of `chat.html` on macOS.
- **Cleanup**: removes temporary request and diagnostic files with `--cleanup`, also available as a standalone command.

The tool does not bypass ChatGPT authentication. You must have a valid export link and an authenticated browser request, and recovery depends on server support for resuming the download.

## Official context

OpenAI sends ChatGPT data exports by email. The download link expires after 24 hours and the downloaded file should be a ZIP archive containing chat history and other account data.

Reference: [OpenAI Help, exporting ChatGPT data](https://help.openai.com/en/articles/7260999-how-do-i-export-my-chatgpt-history-and-data).

OpenAI also warns that diagnostic files such as HAR files may contain personal or sensitive data. The same principle applies to Chrome "Copy as cURL" commands because they can include cookies, temporary signed URLs and session tokens.

Reference: [OpenAI Help, contacting support](https://help.openai.com/en/articles/6614161-how-can-i-contact-support).

## Requirements

- macOS, Linux or another Unix-like environment
- Python 3.9 or newer
- `curl`
- `unzip`

No external Python package is required.

On macOS, `python3` is often already available if Xcode or the Xcode Command Line Tools are installed. The exact version can vary, so check it with:

```bash
python3 --version
```

If needed, install a newer Python with Homebrew:

```bash
brew install python
```

## Why Python 3.9 compatibility?

The first draft of the script used type hints such as:

```python
Path | None
```

That syntax is supported from Python 3.10 onward. On Python 3.9 it can produce:

```text
TypeError: unsupported operand type(s) for |: 'type' and 'NoneType'
```

To make the tool easier to run on default or older macOS setups, the script is written to work with Python 3.9 and includes:

```python
from __future__ import annotations
```

It also avoids requiring third-party dependencies.

## Installation

Clone the repository:

```bash
git clone https://github.com/levysoft/chatgpt-export-resumer.git
cd chatgpt-export-resumer
```

Make the script executable:

```bash
chmod +x chatgpt_export_resumer.py
```

## How to get `chrome-curl.txt`

1. Request your ChatGPT export.
2. Open the export email in Chrome.
3. Open Chrome DevTools:

```text
Cmd + Option + I
```

4. Go to the Network tab.
5. Enable Preserve log.
6. Click the export download link.
7. Find the request to something like:

```text
/backend-api/estuary/content?id=...
```

8. Right-click the request.
9. Choose:

```text
Copy > Copy as cURL
```

10. Save the copied command into a file:

```bash
vi chrome-curl.txt
```

Press `i`, paste the command, then press `Esc` and type `:wq` to save and close.

Important: do not publish `chrome-curl.txt`. It can contain cookies and session tokens.

## Basic usage

```bash
./chatgpt_export_resumer.py chrome-curl.txt --extract
```

This will:

- parse the URL and cookies from `chrome-curl.txt`;
- minimize the cookie header;
- download the ZIP;
- test the ZIP;
- resume the download if needed;
- generate `report-export-chatgpt.txt`;
- extract the archive into `chatgpt-export-estratto/`.

## Recommended usage on macOS

```bash
./chatgpt_export_resumer.py chrome-curl.txt --extract --open-html --quiet --cleanup
```

This will also:

- open `chat.html` after extraction;
- delete temporary and diagnostic files;
- keep `chatgpt-export.zip` and `chatgpt-export-estratto/`.

## Output modes

By default the tool is intentionally verbose.

This is useful when recovering very large exports because you can see that the process is alive. In default mode it shows:

- the `curl` progress bar;
- `unzip -t` testing output;
- extraction output with `inflating: ...`;
- diagnostic information about HTTP status, ZIP signatures and final size.

### Default verbose mode

```bash
./chatgpt_export_resumer.py chrome-curl.txt --extract
```

Use this when you want to see everything.

### Quiet mode

```bash
./chatgpt_export_resumer.py chrome-curl.txt --extract --quiet
```

`--quiet` hides most of the long output and shows only the main steps, errors and final summary.

Example style:

```text
Download iniziale: HTTP 200, 2.69 GiB
ZIP incompleto: EOCD non trovata
Resume 1/5: HTTP 206, +1.24 GiB
ZIP valido: 3.93 GiB
Export estratto in: chatgpt-export-estratto
Report scritto in: report-export-chatgpt.txt
```

### No progress mode

```bash
./chatgpt_export_resumer.py chrome-curl.txt --extract --no-progress
```

`--no-progress` disables only the `curl` progress bar, but keeps detailed ZIP validation and extraction output.

This is useful when your terminal, log file or remote shell does not render the progress bar cleanly.

## Options

### `curl_file`

Optional positional argument.

The file containing the Chrome "Copy as cURL" command.

It is required for download, resume, validation and extraction operations:

```bash
./chatgpt_export_resumer.py chrome-curl.txt
```

It is not required when using standalone cleanup mode:

```bash
./chatgpt_export_resumer.py --cleanup
```

### `-o`, `--output`

Set the output ZIP filename.

Default:

```text
chatgpt-export.zip
```

Example:

```bash
./chatgpt_export_resumer.py chrome-curl.txt -o my-export.zip
```

### `--extract`

Extract the ZIP after successful validation.

Example:

```bash
./chatgpt_export_resumer.py chrome-curl.txt --extract
```

Default extraction directory:

```text
chatgpt-export-estratto/
```

### `--extract-dir`

Set a custom extraction directory.

Example:

```bash
./chatgpt_export_resumer.py chrome-curl.txt --extract --extract-dir export
```

### `--open-html`

Open `chat.html` after extraction.

Currently useful mainly on macOS, where it uses the `open` command.

Example:

```bash
./chatgpt_export_resumer.py chrome-curl.txt --extract --open-html
```

### `--http1`

Force HTTP/1.1 for curl.

This can be useful if HTTP/2 behaves strangely or if a proxy/network path has issues.

Example:

```bash
./chatgpt_export_resumer.py chrome-curl.txt --extract --http1
```

### `--force`

Delete an existing ZIP and restart the download from zero.

Without `--force`, if `chatgpt-export.zip` already exists, the script first verifies it and then tries resume if needed.

Example:

```bash
./chatgpt_export_resumer.py chrome-curl.txt --extract --force
```

### `--max-resume`

Set the maximum number of resume attempts.

Default:

```text
5
```

Example:

```bash
./chatgpt_export_resumer.py chrome-curl.txt --extract --max-resume 10
```

### `--quiet`

Show only the essential output.

Example:

```bash
./chatgpt_export_resumer.py chrome-curl.txt --extract --quiet
```

In quiet mode:

- `curl` progress bar is hidden;
- long `unzip -t` output is hidden;
- extraction output is hidden;
- the final summary remains visible.

### `--no-progress`

Disable only the `curl` progress bar.

Example:

```bash
./chatgpt_export_resumer.py chrome-curl.txt --extract --no-progress
```

Unlike `--quiet`, this still shows verbose ZIP validation and extraction output.

### `--cleanup`

Delete temporary and diagnostic files, leaving the script, README, ZIP file and extracted export untouched.

It removes:

```text
chrome-curl.txt
cookies-minimi.txt
headers-*.txt
result-*.txt
unzip-extract-result.txt
report-export-chatgpt.txt
.curl-chatgpt-export-*.conf
```

It does not remove:

```text
chatgpt_export_resumer.py
README.md
README.it.md
chatgpt-export.zip
chatgpt-export-estratto/
```

After a normal download workflow:

```bash
./chatgpt_export_resumer.py chrome-curl.txt --extract --quiet --cleanup
```

Or as a standalone cleanup command after a previous run:

```bash
./chatgpt_export_resumer.py --cleanup
```

## Generated files

### `chatgpt-export.zip`

The downloaded and resumed ZIP export.

### `chatgpt-export-estratto/`

The extracted export folder.

Usually contains files such as:

```text
chat.html
conversation_asset_file_names.json
conversations-000.json
conversations-001.json
...
library_files.json
message_feedback.json
shared_conversations.json
user.json
user_settings.json
export_manifest.json
```

Large exports may split conversations into multiple files:

```text
conversations-000.json
conversations-001.json
conversations-002.json
...
```

### `report-export-chatgpt.txt`

A sanitized report with:

- ZIP size;
- ZIP end signature status;
- useful HTTP headers;
- curl result summaries;
- resume result summaries;
- final recovery summary.

This report is intended to be safe enough to inspect and share after review, but always check it manually before posting or sending it.

### `cookies-minimi.txt`

Temporary sensitive file containing minimized cookies.

Do not publish it.

Use:

```bash
rm -f cookies-minimi.txt
```

or run the standalone cleanup command:

```bash
./chatgpt_export_resumer.py --cleanup
```

### `headers-*.txt` and `result-*.txt`

Diagnostic files.

They are sanitized in the generated report, but raw files may still contain sensitive data depending on the environment.

Review before sharing.

## Security warning

The file `chrome-curl.txt` can contain:

- session cookies;
- signed URLs;
- temporary export tokens;
- Cloudflare cookies;
- account-related cookies.

Do not:

- commit it to GitHub;
- paste it into public forums;
- attach it to GitHub issues;
- share it in bug reports without sanitizing it.

After a successful run, clean sensitive files with:

```bash
./chatgpt_export_resumer.py --cleanup
```

or manually:

```bash
rm -f chrome-curl.txt cookies-minimi.txt
```

You can also clean them automatically at the end of a normal workflow:

```bash
./chatgpt_export_resumer.py chrome-curl.txt --extract --quiet --cleanup
```

For extra safety, log out of ChatGPT and log back in.

## Recommended `.gitignore`

```gitignore
chrome-curl.txt
cookies-minimi.txt
headers-*.txt
result-*.txt
unzip-extract-result.txt
report-export-chatgpt.txt
*.zip
chatgpt-export-estratto/
.curl-chatgpt-export-*.conf
```

## Real documented case, quiet mode

This is a real sanitized log from a successful recovery using `--quiet`.

The first download returned `HTTP 200` and `application/octet-stream`, but the ZIP was incomplete:

```text
ChatGPT Export Resumer
============================================================
URL trovato: https://chatgpt.com/backend-api/estuary/content?[REDACTED_QUERY]
Lunghezza cookie originale: 10043 byte
Lunghezza cookie minima: 7059 byte

Download iniziale...

+ curl https://chatgpt.com/backend-api/estuary/content?[REDACTED_QUERY] [download, config temporaneo, cookie redatti] -o chatgpt-export.zip

HTTP iniziale: 200
Content-Type iniziale: application/octet-stream
Byte scaricati iniziali: 2889875456
Dimensione dopo download iniziale: 2889875456 byte, 2.69 GiB

Verifica ZIP...
ZIP non valido o incompleto secondo unzip.
Firme finali ZIP: EOCD normale=no, EOCD ZIP64=no, ZIP64 locator=no

Tentativo resume 1/5
Dimensione prima del resume: 2889875456 byte, 2.69 GiB

+ curl https://chatgpt.com/backend-api/estuary/content?[REDACTED_QUERY] [resume, config temporaneo, cookie redatti] -o chatgpt-export.zip

HTTP resume: 206
Byte scaricati nel resume: 1330561245
Dimensione dopo resume: 4220436701 byte, 3.93 GiB

Verifica ZIP dopo resume...
ZIP valido secondo unzip.
Firme finali ZIP: EOCD normale=sì, EOCD ZIP64=sì, ZIP64 locator=sì

Report scritto in: report-export-chatgpt.txt

ZIP valido.

+ unzip -q -o chatgpt-export.zip -d chatgpt-export-estratto

Export estratto in: chatgpt-export-estratto
File HTML principale: chatgpt-export-estratto/chat.html

RIEPILOGO
------------------------------------------------------------
- Download iniziale: HTTP 200, 2889875456 byte, 2.69 GiB
- Dimensione dopo download iniziale: 2889875456 byte, 2.69 GiB
- Resume 1: HTTP 206, +1330561245 byte, 1.24 GiB
  Dimensione dopo resume 1: 4220436701 byte, 3.93 GiB
- Dimensione finale: 4220436701 byte, 3.93 GiB
- ZIP: valido
- EOCD normale: trovata a offset 4220436679
- EOCD ZIP64: trovata a offset 4220436603
- ZIP64 locator: trovata a offset 4220436659
- Estratto in: chatgpt-export-estratto
- Report: report-export-chatgpt.txt

Nota sicurezza: elimina chrome-curl.txt e cookies-minimi.txt, oppure esegui: ./chatgpt_export_resumer.py --cleanup
Dopo l'uso valuta logout e login da ChatGPT.
```

In this case the initial download stopped at `2.69 GiB`. The ZIP started correctly, but did not contain the final ZIP directory records. The tool detected the missing EOCD and ZIP64 records, resumed the download with `curl -C -`, received `HTTP 206 Partial Content`, downloaded the missing `1.24 GiB`, and produced a valid `3.93 GiB` archive.

## What happened technically?

The initial response was successful:

```text
HTTP_CODE: 200
CONTENT_TYPE: application/octet-stream
```

So the server did return binary data.

However, the local file was incomplete. It started like a ZIP, but did not contain the end-of-central-directory records required to make the archive readable.

After the script ran curl in resume mode:

```bash
curl -C -
```

the server answered:

```text
HTTP_CODE: 206
```

`206` means Partial Content. In this case, the server sent the missing tail of the file, and the ZIP became valid.

## Troubleshooting

### `HTTP_CODE: 403`

This usually means the request is not authenticated or is being redirected to login/challenge.

Use Chrome DevTools and copy the authenticated request with:

```text
Copy > Copy as cURL
```

### `Warning: skipped provided cookie, the cookie header would go over 8200 bytes`

Chrome copied too many cookies.

This script removes many unnecessary cookies, especially `conv_key_*`, and keeps only the cookies usually needed for authentication and download.

### `End-of-central-directory signature not found`

The ZIP is probably incomplete.

Run the script again without `--force`, or let it resume automatically.

### The ZIP exists already

The script checks the existing ZIP first.

If it is valid, it stops.

If it is incomplete, it attempts resume.

To restart from zero:

```bash
./chatgpt_export_resumer.py chrome-curl.txt --force
```

### The link expired

ChatGPT export links expire after 24 hours.

Request a new export and repeat the workflow.

## Download and source code

- [GitHub repository and issue tracker](https://github.com/levysoft/chatgpt-export-resumer)
- [Python script](chatgpt_export_resumer.py)
- [Italian documentation](README.it.md)
- [Levysoft website](https://www.levysoft.it/)

To use the tool, clone the repository as shown in **Installation**. No packaged release is required.

## License and acknowledgments

Released under the **MIT License**. See [LICENSE](LICENSE).

Author: **Antonio Troise (Levysoft)**  
Project website: https://www.levysoft.it/  
Author website: https://www.levysoft.it/  
GitHub: https://github.com/levysoft/

The project grew out of troubleshooting a large, incomplete ChatGPT data export download. It uses the standard `curl` resume feature and the Python standard library.
