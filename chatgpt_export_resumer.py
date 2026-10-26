#!/usr/bin/env python3
from __future__ import annotations

import argparse
import re
import shutil
import subprocess
import sys
import tempfile
import time
import zipfile
from pathlib import Path
from typing import Dict, List, Optional
from urllib.parse import urlparse


DEFAULT_OUTPUT = "chatgpt-export.zip"
DEFAULT_EXTRACT_DIR = "chatgpt-export-estratto"

KEEP_COOKIE_NAMES = {
	"cf_clearance",
	"__cf_bm",
	"__cflb",
	"_cfuvid",
	"_puid",
	"oai-sc",
	"oai-chat-web-route",
	"oai-hlib",
	"oai-did",
	"__Secure-oai-is",
}

ZIP_SIGNATURES = {
	b"PK\x05\x06": "EOCD normale",
	b"PK\x06\x06": "EOCD ZIP64",
	b"PK\x06\x07": "ZIP64 locator",
}

CURL_WRITE_OUT = (
	"\nHTTP_CODE: %{http_code}\n"
	"CONTENT_TYPE: %{content_type}\n"
	"SIZE_DOWNLOAD: %{size_download}\n"
	"TIME_TOTAL: %{time_total}\n"
)


def die(message: str, code: int = 1) -> None:
	print(f"ERRORE: {message}", file=sys.stderr)
	sys.exit(code)


def now_string() -> str:
	return time.strftime("%Y-%m-%d %H:%M:%S")


def redact_url(url: str) -> str:
	parsed = urlparse(url)

	if not parsed.scheme or not parsed.netloc:
		return "[REDACTED_URL]"

	clean = f"{parsed.scheme}://{parsed.netloc}{parsed.path}"

	if parsed.query:
		clean += "?[REDACTED_QUERY]"

	return clean


def sanitize_text(text: str) -> str:
	text = re.sub(
		r"https://chatgpt\.com/backend-api/estuary/content\?[^\s'\"<>]+",
		"https://chatgpt.com/backend-api/estuary/content?[REDACTED_QUERY]",
		text,
	)

	text = re.sub(r"(sig=)[^&\s'\"<>]+", r"\1[REDACTED]", text)
	text = re.sub(r"(id=)[^&\s'\"<>]+", r"\1[REDACTED]", text)
	text = re.sub(r"(token=)[^&\s'\"<>]+", r"\1[REDACTED]", text)

	sensitive_cookie_names = [
		"__Secure-next-auth.session-token.0",
		"__Secure-next-auth.session-token.1",
		"__Secure-oai-is",
		"cf_clearance",
		"__cf_bm",
		"__cflb",
		"_cfuvid",
		"_puid",
		"oai-sc",
		"oai-chat-web-route",
		"oai-did",
	]

	for name in sensitive_cookie_names:
		escaped = re.escape(name)
		text = re.sub(
			rf"({escaped}=)[^;\s]+",
			rf"\1[REDACTED]",
			text,
		)

	text = re.sub(
		r"(cookie:\s*)[^\n\r]+",
		r"\1[REDACTED]",
		text,
		flags=re.IGNORECASE,
	)

	return text


def curl_config_quote(value: str) -> str:
	value = value.replace("\\", "\\\\")
	value = value.replace('"', '\\"')
	value = value.replace("\n", "\\n")
	return f'"{value}"'


def write_text(path: Path, content: str, mode: int = 0o644) -> None:
	path.write_text(content, encoding="utf-8")

	try:
		path.chmod(mode)
	except PermissionError:
		pass


def write_sensitive_text(path: Path, content: str) -> None:
	write_text(path, content, 0o600)


def safe_unlink(path: Path) -> None:
	try:
		path.unlink()
	except FileNotFoundError:
		pass


def file_size(path: Path) -> int:
	return path.stat().st_size if path.exists() else 0


def human_size(num: int) -> str:
	units = ["B", "KiB", "MiB", "GiB", "TiB"]
	value = float(num)

	for unit in units:
		if value < 1024.0 or unit == units[-1]:
			return f"{value:.2f} {unit}"
		value /= 1024.0

	return f"{num} B"


def parse_int(value: Optional[str]) -> Optional[int]:
	if value is None:
		return None

	try:
		return int(float(value))
	except ValueError:
		return None


def extract_url(curl_text: str) -> str:
	patterns = [
		r"curl\s+'([^']+)'",
		r'curl\s+"([^"]+)"',
		r"curl\s+([^\s\\]+)",
	]

	for pattern in patterns:
		match = re.search(pattern, curl_text)

		if not match:
			continue

		url = match.group(1).strip()
		parsed = urlparse(url)

		if parsed.scheme in {"http", "https"}:
			return url

	die("Non trovo l'URL nel file Copy as cURL.")


def extract_cookie_string(curl_text: str) -> str:
	patterns = [
		r"-b\s+'([^']*)'",
		r'-b\s+"([^"]*)"',
		r"--cookie\s+'([^']*)'",
		r'--cookie\s+"([^"]*)"',
		r"-H\s+'cookie:\s*([^']*)'",
		r'-H\s+"cookie:\s*([^"]*)"',
	]

	for pattern in patterns:
		match = re.search(pattern, curl_text, re.IGNORECASE | re.DOTALL)

		if match:
			return match.group(1).strip()

	die("Non trovo cookie nel comando. Usa Copy as cURL da Chrome sulla richiesta dello ZIP.")


def minimize_cookies(cookie_string: str) -> str:
	cookies = [cookie.strip() for cookie in cookie_string.split(";") if cookie.strip()]
	kept: List[str] = []

	for cookie in cookies:
		if "=" not in cookie:
			continue

		name = cookie.split("=", 1)[0].strip()

		if name.startswith("__Secure-next-auth.session-token."):
			kept.append(cookie)
		elif name in KEEP_COOKIE_NAMES:
			kept.append(cookie)

	if not kept:
		die("Dopo la pulizia non è rimasto nessun cookie utile.")

	return "; ".join(kept)


def make_curl_config(
	url: str,
	cookies: str,
	output: Path,
	headers_file: Path,
	resume: bool,
	quiet: bool,
	no_progress: bool,
) -> Path:
	lines = [
		f"url = {curl_config_quote(url)}",
		"location",
	]

	if resume:
		lines.append('continue-at = "-"')

	if quiet or no_progress:
		lines.extend([
			"silent",
			"show-error",
		])
	else:
		lines.extend([
			"show-error",
			"progress-bar",
		])

	lines.extend([
		"retry = 5",
		"retry-delay = 2",
		"retry-all-errors",
		f"header = {curl_config_quote('cookie: ' + cookies)}",
		f"header = {curl_config_quote('accept: application/zip,application/octet-stream,*/*')}",
		f"header = {curl_config_quote('referer: https://chatgpt.com/')}",
		f"header = {curl_config_quote('user-agent: Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/149.0.0.0 Safari/537.36')}",
		f"dump-header = {curl_config_quote(str(headers_file))}",
		f"output = {curl_config_quote(str(output))}",
	])

	tmp = tempfile.NamedTemporaryFile(
		mode="w",
		encoding="utf-8",
		prefix=".curl-chatgpt-export-",
		suffix=".conf",
		dir=".",
		delete=False,
	)

	tmp_path = Path(tmp.name)

	try:
		tmp.write("\n".join(lines))
		tmp.write("\n")
		tmp.close()
		tmp_path.chmod(0o600)
	except Exception:
		tmp.close()
		safe_unlink(tmp_path)
		raise

	return tmp_path


def tail_text(path: Path, max_lines: int = 80) -> str:
	if not path.exists():
		return "Non presente."

	lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
	selected = lines[-max_lines:]
	return sanitize_text("\n".join(selected))


def stream_process(
	cmd: List[str],
	result_file: Path,
	display_command: str,
	echo_output: bool,
) -> int:
	print()
	print(display_command)

	with result_file.open("w", encoding="utf-8", errors="replace") as log:
		log.write(display_command + "\n\n")

		process = subprocess.Popen(
			cmd,
			stdout=subprocess.PIPE,
			stderr=subprocess.STDOUT,
			text=True,
			errors="replace",
			bufsize=1,
		)

		assert process.stdout is not None

		for line in process.stdout:
			sanitized = sanitize_text(line)

			if echo_output:
				print(sanitized, end="")

			log.write(sanitized)

		return_code = process.wait()

	if not echo_output and return_code != 0:
		print()
		print("Output errore:")
		print(tail_text(result_file, max_lines=40))

	return return_code


def curl_download(
	url: str,
	cookies: str,
	output: Path,
	resume: bool,
	headers_file: Path,
	result_file: Path,
	quiet: bool,
	no_progress: bool,
	http1: bool = False,
) -> int:
	if not shutil.which("curl"):
		die("curl non trovato nel PATH.")

	config_path = make_curl_config(
		url=url,
		cookies=cookies,
		output=output,
		headers_file=headers_file,
		resume=resume,
		quiet=quiet,
		no_progress=no_progress,
	)

	cmd = ["curl", "--config", str(config_path), "-w", CURL_WRITE_OUT]

	if http1:
		cmd.insert(1, "--http1.1")

	mode = "resume" if resume else "download"

	display_command = (
		f"+ curl {redact_url(url)} "
		f"[{mode}, config temporaneo, cookie redatti] "
		f"-o {output}"
	)

	try:
		return stream_process(
			cmd=cmd,
			result_file=result_file,
			display_command=display_command,
			echo_output=not quiet,
		)
	finally:
		safe_unlink(config_path)


def read_result_field(result_file: Path, field: str) -> Optional[str]:
	if not result_file.exists():
		return None

	text = result_file.read_text(encoding="utf-8", errors="replace")
	match = re.search(rf"^{re.escape(field)}:\s*(.+)$", text, re.MULTILINE)

	if not match:
		return None

	return match.group(1).strip()


def looks_like_html(path: Path) -> bool:
	if not path.exists():
		return False

	with path.open("rb") as file:
		chunk = file.read(2048).lstrip().lower()

	# Check only the beginning: an uncompressed ZIP entry can contain HTML
	# within its first 2 KiB without the archive itself being an HTML page.
	return chunk.startswith(b"<html") or chunk.startswith(b"<!doctype html")


def check_zip_with_python(path: Path, quiet: bool) -> bool:
	try:
		with zipfile.ZipFile(path, "r") as archive:
			bad_file = archive.testzip()

			if bad_file:
				print(f"ZIP presente, ma file corrotto dentro l'archivio: {bad_file}")
				return False

			if quiet:
				print("ZIP valido secondo Python zipfile.")

			return True

	except zipfile.BadZipFile as exc:
		if quiet:
			print("ZIP non valido o incompleto secondo Python zipfile.")
		else:
			print(f"ZIP non valido secondo Python: {exc}")

		return False


def check_zip_with_unzip(path: Path, quiet: bool) -> bool:
	if not path.exists():
		print("File ZIP non presente.")
		return False

	if looks_like_html(path):
		print("Il file scaricato sembra HTML, non ZIP. Probabile login, challenge o errore server.")
		return False

	if not shutil.which("unzip"):
		return check_zip_with_python(path, quiet=quiet)

	cmd = ["unzip", "-tq", str(path)] if quiet else ["unzip", "-t", str(path)]

	process = subprocess.run(
		cmd,
		stdout=subprocess.PIPE,
		stderr=subprocess.STDOUT,
		text=True,
		errors="replace",
	)

	output = sanitize_text(process.stdout)

	if quiet:
		if process.returncode == 0:
			print("ZIP valido secondo unzip.")
		else:
			print("ZIP non valido o incompleto secondo unzip.")
	else:
		print(output)

	return process.returncode == 0


def find_zip_end_signatures(path: Path, tail_bytes: int = 20_000_000) -> Dict[str, Optional[int]]:
	size = file_size(path)

	if size == 0:
		return {name: None for name in ZIP_SIGNATURES.values()}

	with path.open("rb") as file:
		if size > tail_bytes:
			file.seek(size - tail_bytes)

		data = file.read()

	found: Dict[str, Optional[int]] = {}

	for signature, name in ZIP_SIGNATURES.items():
		pos = data.rfind(signature)

		if pos >= 0:
			absolute = size - len(data) + pos
			found[name] = absolute
		else:
			found[name] = None

	return found


def print_zip_signature_report(path: Path, quiet: bool) -> bool:
	found = find_zip_end_signatures(path)
	any_found = False

	if quiet:
		parts = []

		for name, pos in found.items():
			if pos is None:
				parts.append(f"{name}=no")
			else:
				parts.append(f"{name}=sì")
				any_found = True

		print("Firme finali ZIP: " + ", ".join(parts))
		return any_found

	print()
	print("Controllo firme finali ZIP negli ultimi 20 MB...")

	for name, pos in found.items():
		if pos is None:
			print(f"- {name}: NON trovata")
		else:
			print(f"- {name}: trovata a offset {pos}")
			any_found = True

	return any_found


def grep_useful_headers(path: Path) -> str:
	if not path.exists():
		return "Non presente."

	useful_lines: List[str] = []

	pattern = re.compile(
		r"(HTTP/|content-length|content-range|accept-ranges|content-type|content-encoding|etag|last-modified|x-oai-request-id|cf-ray|cf-mitigated|location)",
		re.IGNORECASE,
	)

	for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
		if pattern.search(line):
			useful_lines.append(sanitize_text(line))

	return "\n".join(useful_lines) if useful_lines else "Nessun header utile trovato."


def build_summary_lines(stats: Dict[str, object], output: Path) -> List[str]:
	lines: List[str] = []

	lines.append("RIEPILOGO")
	lines.append("-" * 60)

	initial = stats.get("initial")

	if isinstance(initial, dict):
		http_code = initial.get("http_code") or "?"
		downloaded = parse_int(str(initial.get("size_download"))) if initial.get("size_download") is not None else None
		file_after = initial.get("file_size_after")

		if downloaded is not None:
			lines.append(f"- Download iniziale: HTTP {http_code}, {downloaded} byte, {human_size(downloaded)}")
		else:
			lines.append(f"- Download iniziale: HTTP {http_code}")

		if isinstance(file_after, int):
			lines.append(f"- Dimensione dopo download iniziale: {file_after} byte, {human_size(file_after)}")
	else:
		lines.append("- Download iniziale: non eseguito, file già presente.")

	resumes = stats.get("resumes")

	if isinstance(resumes, list) and resumes:
		for item in resumes:
			if not isinstance(item, dict):
				continue

			attempt = item.get("attempt")
			http_code = item.get("http_code") or "?"
			downloaded_raw = item.get("size_download")
			downloaded = parse_int(str(downloaded_raw)) if downloaded_raw is not None else None
			after = item.get("file_size_after")

			if downloaded is not None:
				lines.append(f"- Resume {attempt}: HTTP {http_code}, +{downloaded} byte, {human_size(downloaded)}")
			else:
				lines.append(f"- Resume {attempt}: HTTP {http_code}")

			if isinstance(after, int):
				lines.append(f"  Dimensione dopo resume {attempt}: {after} byte, {human_size(after)}")
	else:
		lines.append("- Resume: non necessario o non eseguito.")

	final_size = file_size(output)

	if final_size:
		lines.append(f"- Dimensione finale: {final_size} byte, {human_size(final_size)}")

	zip_valid = stats.get("zip_valid")

	if zip_valid is True:
		lines.append("- ZIP: valido")
	elif zip_valid is False:
		lines.append("- ZIP: non valido")
	else:
		lines.append("- ZIP: stato non determinato")

	signatures = stats.get("signatures")

	if isinstance(signatures, dict):
		for name, pos in signatures.items():
			if pos is None:
				lines.append(f"- {name}: non trovata")
			else:
				lines.append(f"- {name}: trovata a offset {pos}")

	extracted_to = stats.get("extracted_to")

	if extracted_to:
		lines.append(f"- Estratto in: {extracted_to}")

	report = stats.get("report")

	if report:
		lines.append(f"- Report: {report}")

	return lines


def print_summary(stats: Dict[str, object], output: Path) -> None:
	print()
	for line in build_summary_lines(stats, output):
		print(line)


def create_report(output: Path, report: Path, files: List[Path], stats: Dict[str, object]) -> None:
	lines: List[str] = []

	lines.append("REPORT EXPORT CHATGPT")
	lines.append("=" * 60)
	lines.append(f"Data: {now_string()}")
	lines.append("")

	lines.extend(build_summary_lines(stats, output))
	lines.append("")

	if output.exists():
		size = file_size(output)

		lines.append("FILE ZIP")
		lines.append("-" * 60)
		lines.append(f"Percorso: {output}")
		lines.append(f"Dimensione byte: {size}")
		lines.append(f"Dimensione leggibile: {human_size(size)}")
		lines.append("")

		lines.append("Firme finali ZIP")
		lines.append("-" * 60)

		found = find_zip_end_signatures(output)

		for name, pos in found.items():
			lines.append(f"- {name}: {pos if pos is not None else 'NON trovata'}")

		lines.append("")
	else:
		lines.append("File ZIP non presente.")
		lines.append("")

	for path in files:
		lines.append(f"FILE: {path}")
		lines.append("-" * 60)

		if path.name.startswith("headers"):
			lines.append(grep_useful_headers(path))
		else:
			lines.append(tail_text(path))

		lines.append("")

	write_text(report, "\n".join(lines), 0o600)
	stats["report"] = str(report)
	print(f"\nReport scritto in: {report}")


def extract_zip(output: Path, extract_dir: Path, quiet: bool) -> None:
	extract_dir.mkdir(parents=True, exist_ok=True)

	if shutil.which("unzip"):
		if quiet:
			cmd = ["unzip", "-q", "-o", str(output), "-d", str(extract_dir)]
		else:
			cmd = ["unzip", "-o", str(output), "-d", str(extract_dir)]

		display_command = f"+ {' '.join(cmd)}"

		code = stream_process(
			cmd=cmd,
			result_file=Path("unzip-extract-result.txt"),
			display_command=display_command,
			echo_output=not quiet,
		)

		if code != 0:
			die("Estrazione con unzip fallita.")
	else:
		with zipfile.ZipFile(output, "r") as archive:
			archive.extractall(extract_dir)

	print(f"\nExport estratto in: {extract_dir}")

	chat_html = extract_dir / "chat.html"

	if chat_html.exists():
		print(f"File HTML principale: {chat_html}")


def maybe_open_html(extract_dir: Path) -> None:
	chat_html = extract_dir / "chat.html"

	if not chat_html.exists():
		return

	if sys.platform == "darwin" and shutil.which("open"):
		subprocess.call(["open", str(chat_html)])
	else:
		print(f"Apri manualmente: {chat_html}")


def print_security_notice(quiet: bool) -> None:
	print()

	if quiet:
		print("Nota: puoi eliminare file temporanei e diagnostici con: ./chatgpt_export_resumer.py --cleanup")
		print("Dopo l'uso valuta logout e login da ChatGPT.")
		return

	print("Nota:")
	print("- chrome-curl.txt e cookies-minimi.txt possono contenere dati di sessione.")
	print("- headers-*.txt, result-*.txt e report-export-chatgpt.txt sono file diagnostici.")
	print("- Puoi eliminarli con: ./chatgpt_export_resumer.py --cleanup")
	print("- Dopo l'uso, valuta logout e login da ChatGPT.")


def cleanup_files(curl_path: Optional[Path], quiet: bool) -> None:
	files_to_delete: List[Path] = [
		Path("cookies-minimi.txt"),
		Path("unzip-extract-result.txt"),
		Path("report-export-chatgpt.txt"),
	]
	
	for pattern in [
		"headers-*.txt",
		"result-*.txt",
		".curl-chatgpt-export-*.conf",
	]:
		files_to_delete.extend(Path(".").glob(pattern))
	
	if curl_path is not None:
		files_to_delete.append(curl_path)
	else:
		files_to_delete.append(Path("chrome-curl.txt"))
	
	seen = set()
	unique_files: List[Path] = []
	
	for path in files_to_delete:
		key = str(path)
	
		if key in seen:
			continue
	
		seen.add(key)
		unique_files.append(path)
	
	deleted: List[Path] = []
	missing: List[Path] = []
	
	for path in unique_files:
		if path.exists() and path.is_file():
			safe_unlink(path)
			deleted.append(path)
		else:
			missing.append(path)
	
	if quiet:
		if deleted:
			print("File temporanei eliminati: " + ", ".join(str(p) for p in deleted))
		else:
			print("Nessun file temporaneo trovato da eliminare.")
		return
	
	print()
	print("Pulizia file temporanei:")
	
	if deleted:
		print("Eliminati:")
		for path in deleted:
			print(f"- {path}")
	else:
		print("Nessun file temporaneo trovato da eliminare.")
	
	if missing:
		print("Non presenti:")
		for path in missing:
			print(f"- {path}")


def validate_or_resume(
	url: str,
	cookies: str,
	output: Path,
	http1: bool,
	max_resume: int,
	work_files: List[Path],
	stats: Dict[str, object],
	quiet: bool,
	no_progress: bool,
) -> bool:
	print()
	print("Verifica ZIP...")

	ok = check_zip_with_unzip(output, quiet=quiet)
	print_zip_signature_report(output, quiet=quiet)

	if ok:
		stats["zip_valid"] = True
		stats["signatures"] = find_zip_end_signatures(output)
		return True

	if looks_like_html(output):
		print()
		print("Il file sembra HTML. Probabile sessione non valida, cookie scaduti o challenge.")
		stats["zip_valid"] = False
		stats["signatures"] = find_zip_end_signatures(output)
		return False

	for attempt in range(1, max_resume + 1):
		before = file_size(output)

		print()
		print(f"Tentativo resume {attempt}/{max_resume}")
		print(f"Dimensione prima del resume: {before} byte, {human_size(before)}")

		headers_resume = Path(f"headers-resume-{attempt}.txt")
		result_resume = Path(f"result-resume-{attempt}.txt")

		work_files.extend([result_resume, headers_resume])

		code = curl_download(
			url=url,
			cookies=cookies,
			output=output,
			resume=True,
			headers_file=headers_resume,
			result_file=result_resume,
			quiet=quiet,
			no_progress=no_progress,
			http1=http1,
		)

		if code != 0:
			print(f"curl resume ha restituito codice {code}. Provo comunque a verificare.")

		http_code = read_result_field(result_resume, "HTTP_CODE")
		size_download = read_result_field(result_resume, "SIZE_DOWNLOAD")
		after = file_size(output)

		resume_entry = {
			"attempt": attempt,
			"http_code": http_code,
			"size_download": size_download,
			"file_size_before": before,
			"file_size_after": after,
		}

		if isinstance(stats.get("resumes"), list):
			stats["resumes"].append(resume_entry)

		print()
		print(f"HTTP resume: {http_code}")
		print(f"Byte scaricati nel resume: {size_download}")
		print(f"Dimensione dopo resume: {after} byte, {human_size(after)}")

		print()
		print("Verifica ZIP dopo resume...")

		ok = check_zip_with_unzip(output, quiet=quiet)
		print_zip_signature_report(output, quiet=quiet)

		if ok:
			stats["zip_valid"] = True
			stats["signatures"] = find_zip_end_signatures(output)
			return True

		if after <= before:
			print()
			print("La dimensione non è aumentata. Interrompo i tentativi di resume.")
			stats["zip_valid"] = False
			stats["signatures"] = find_zip_end_signatures(output)
			return False

	stats["zip_valid"] = False
	stats["signatures"] = find_zip_end_signatures(output)
	return False


def main() -> None:
	parser = argparse.ArgumentParser(
		description="Scarica, riprende e verifica un export ZIP di ChatGPT partendo da Copy as cURL."
	)

	parser.add_argument(
		"curl_file",
		nargs="?",
		help="File contenente il comando Copy as cURL di Chrome.",
	)

	parser.add_argument(
		"-o",
		"--output",
		default=DEFAULT_OUTPUT,
		help=f"Nome del file ZIP finale. Default: {DEFAULT_OUTPUT}",
	)

	parser.add_argument(
		"--extract",
		action="store_true",
		help="Estrae lo ZIP se valido.",
	)

	parser.add_argument(
		"--extract-dir",
		default=DEFAULT_EXTRACT_DIR,
		help=f"Cartella di estrazione. Default: {DEFAULT_EXTRACT_DIR}",
	)

	parser.add_argument(
		"--open-html",
		action="store_true",
		help="Apre chat.html dopo l'estrazione, su macOS.",
	)

	parser.add_argument(
		"--http1",
		action="store_true",
		help="Forza HTTP/1.1.",
	)

	parser.add_argument(
		"--force",
		action="store_true",
		help="Riscarica da zero anche se il file ZIP esiste già.",
	)

	parser.add_argument(
		"--max-resume",
		type=int,
		default=5,
		help="Numero massimo di tentativi di resume. Default: 5.",
	)

	parser.add_argument(
		"--quiet",
		action="store_true",
		help="Mostra solo riepilogo, errori e risultato finale.",
	)

	parser.add_argument(
		"--no-progress",
		action="store_true",
		help="Disabilita la progress bar di curl ma mantiene output diagnostico verboso.",
	)

	parser.add_argument(
		"--cleanup",
		action="store_true",
		help="Cancella file temporanei e diagnostici, lasciando script, README, ZIP ed export estratto.",
	)

	args = parser.parse_args()
	
	quiet = bool(args.quiet)
	no_progress = bool(args.no_progress)
	
	curl_path = Path(args.curl_file) if args.curl_file else None
	output = Path(args.output)
	extract_dir = Path(args.extract_dir)
	
	if args.cleanup and curl_path is None:
		cleanup_files(curl_path=None, quiet=quiet)
		print()
		print("Pulizia completata.")
		return
	
	if curl_path is None:
		parser.error("devi specificare curl_file, oppure usare --cleanup da solo per eliminare i file temporanei")

	stats: Dict[str, object] = {
		"initial": None,
		"resumes": [],
		"zip_valid": None,
		"signatures": {},
		"extracted_to": None,
		"report": None,
	}

	if not curl_path.exists():
		die(f"File non trovato: {curl_path}")

	curl_text = curl_path.read_text(encoding="utf-8", errors="replace")

	url = extract_url(curl_text)
	original_cookie_string = extract_cookie_string(curl_text)
	cookies = minimize_cookies(original_cookie_string)

	print("ChatGPT Export Resumer")
	print("=" * 60)
	print(f"URL trovato: {redact_url(url)}")
	print(f"Lunghezza cookie originale: {len(original_cookie_string)} byte")
	print(f"Lunghezza cookie minima: {len(cookies)} byte")

	if len(cookies) > 7800:
		print()
		print("Attenzione: i cookie minimi sono ancora molto lunghi.")
		print("Se curl segnala limiti sul cookie header, potrebbe servire ridurre ulteriormente i cookie.")

	cookies_path = Path("cookies-minimi.txt")
	write_sensitive_text(cookies_path, cookies)

	work_files: List[Path] = []

	if output.exists() and not args.force:
		print()
		print(f"File esistente trovato: {output}")
		print(f"Dimensione: {file_size(output)} byte, {human_size(file_size(output))}")
		print("Provo prima a verificarlo, poi eventualmente faccio resume.")
	else:
		if output.exists() and args.force:
			print()
			print(f"--force attivo, elimino file esistente: {output}")
			safe_unlink(output)

		print()
		print("Download iniziale...")

		headers_download = Path("headers-download.txt")
		result_download = Path("result-download.txt")
		work_files.extend([result_download, headers_download])

		code = curl_download(
			url=url,
			cookies=cookies,
			output=output,
			resume=False,
			headers_file=headers_download,
			result_file=result_download,
			quiet=quiet,
			no_progress=no_progress,
			http1=args.http1,
		)

		if code != 0:
			print(f"curl ha restituito codice {code}. Provo comunque a verificare.")

		http_code = read_result_field(result_download, "HTTP_CODE")
		content_type = read_result_field(result_download, "CONTENT_TYPE")
		size_download = read_result_field(result_download, "SIZE_DOWNLOAD")

		stats["initial"] = {
			"http_code": http_code,
			"content_type": content_type,
			"size_download": size_download,
			"file_size_after": file_size(output) if output.exists() else 0,
		}

		print()
		print(f"HTTP iniziale: {http_code}")
		print(f"Content-Type iniziale: {content_type}")
		print(f"Byte scaricati iniziali: {size_download}")

		if output.exists():
			print(f"Dimensione dopo download iniziale: {file_size(output)} byte, {human_size(file_size(output))}")

	if not output.exists():
		create_report(output, Path("report-export-chatgpt.txt"), work_files, stats)
		print_summary(stats, output)
		print_security_notice(quiet=quiet)
		die("Il file ZIP non è stato creato.")

	ok = validate_or_resume(
		url=url,
		cookies=cookies,
		output=output,
		http1=args.http1,
		max_resume=args.max_resume,
		work_files=work_files,
		stats=stats,
		quiet=quiet,
		no_progress=no_progress,
	)

	create_report(
		output=output,
		report=Path("report-export-chatgpt.txt"),
		files=work_files,
		stats=stats,
	)

	if not ok:
		print_summary(stats, output)
		print()
		print("Lo ZIP non è ancora valido.")
		print("Controlla report-export-chatgpt.txt.")
		print_security_notice(quiet=quiet)
		sys.exit(2)

	print()
	print("ZIP valido.")

	if args.extract:
		extract_zip(output, extract_dir, quiet=quiet)
		stats["extracted_to"] = str(extract_dir)

		if args.open_html:
			maybe_open_html(extract_dir)

	print_summary(stats, output)

	if args.cleanup:
		cleanup_files(curl_path=curl_path, quiet=quiet)
	else:
		print_security_notice(quiet=quiet)


if __name__ == "__main__":
	main()
