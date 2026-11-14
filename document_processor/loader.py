"""Validate and bound uploads; parse PDFs in a killable, credential-free process."""
import json
import os
from pathlib import Path, PurePosixPath
import re
# Only a fixed Python module is launched; no command is taken from uploaded content.
import subprocess  # nosec B404
import sys
import textwrap
import unicodedata

from document_processor.limits import (
    MAX_FILE_BYTES, MAX_BATCH_BYTES, MAX_FILES, MAX_PAGES, MAX_CHARACTERS,
    MAX_CHUNKS, PDF_WALL_SECONDS, MAX_WORKER_RESPONSE,
)
from utils.security import processing_slot, log_failure


class DocumentError(ValueError):
    """A deliberately safe user-facing upload validation failure."""


def safe_filename(name):
    leaf = PurePosixPath(str(name).replace('\\', '/')).name
    leaf = ''.join(c for c in leaf if unicodedata.category(c) not in {'Cc', 'Cf', 'Cs'})
    leaf = re.sub(r'[^\w .()-]', '_', leaf).strip(' .')
    suffix = PurePosixPath(leaf).suffix
    stem = leaf[:-len(suffix)] if suffix else leaf
    return (stem[:100] + suffix[:10]) or 'document'


def _chunk(text, source_name, page_no, chunk_size=180, overlap=30):
    if chunk_size <= 0 or not 0 <= overlap < chunk_size:
        raise ValueError('Overlap must be smaller than a positive chunk size.')
    words = text.split()
    chunks = []
    for start in range(0, len(words), chunk_size - overlap):
        for part in textwrap.wrap(' '.join(words[start:start + chunk_size]), width=4000,
                                  break_long_words=True, break_on_hyphens=False):
            chunks.append({'text': part, 'metadata': {'source': source_name, 'page': page_no}})
        if start + chunk_size >= len(words):
            break
    return chunks


def _pdf_pages(data, name):
    # Inherit neither HF_TOKEN nor Streamlit secrets through process environment.
    environment = {key: os.environ[key] for key in ('SYSTEMROOT', 'WINDIR') if key in os.environ}
    environment.update(PYTHONDONTWRITEBYTECODE='1', PYTHONUTF8='1')
    try:
        # The executable/module are fixed and uploads travel only over stdin.
        result = subprocess.run(  # nosec B603
            [sys.executable, '-m', 'document_processor.pdf_worker'],
            input=data, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
            timeout=PDF_WALL_SECONDS, check=False, shell=False,
            cwd=str(Path(__file__).resolve().parents[1]), env=environment)
        if result.returncode != 0 or len(result.stdout) > MAX_WORKER_RESPONSE:
            raise DocumentError(f'{name}: PDF processing exceeded its safety limits or could not finish.')
        reply = json.loads(result.stdout)
        errors = {
            'encrypted': f'{name}: upload an unlocked PDF.',
            'pages': f'{name}: the limit is {MAX_PAGES} pages per PDF.',
            'empty': f'{name}: no readable text found. Scanned PDFs need OCR before upload.',
            'text_limit': 'These documents contain too much text. Upload a smaller selection.',
            'unreadable': f'{name}: this PDF could not be read. Try exporting a fresh PDF or TXT copy.',
        }
        if reply.get('error'):
            raise DocumentError(errors.get(reply['error'], errors['unreadable']))
        pages = reply['pages']
        if not isinstance(pages, list) or len(pages) > MAX_PAGES:
            raise DocumentError(errors['unreadable'])
        return pages
    except subprocess.TimeoutExpired as error:
        log_failure('pdf_timeout', error)
        raise DocumentError(f'{name}: PDF processing took too long. Try a simpler PDF or TXT file.') from None
    except DocumentError:
        raise
    except Exception as error:
        log_failure('pdf_worker_failed', error)
        raise DocumentError(f'{name}: this PDF could not be read. Try exporting a fresh copy.') from None


def _text_pages(data, name):
    if data.startswith((b'%PDF', b'PK\x03\x04', b'PK\x05\x06', b'PK\x07\x08', b'\x1f\x8b', b'\x7fELF', b'MZ', b'\x89PNG', b'\xff\xd8\xff')):
        raise DocumentError(f'{name}: the content is not a plain text file.')
    try:
        text = data.decode('utf-8-sig')
    except UnicodeDecodeError:
        raise DocumentError(f'{name}: save the text file with UTF-8 encoding and try again.') from None
    if len(text) > MAX_CHARACTERS:
        raise DocumentError('These documents contain too much text. Upload a smaller selection.')
    if any(unicodedata.category(c) in {'Cc', 'Cs'} and c not in '\r\n\t' for c in text):
        raise DocumentError(f'{name}: the content is not a plain text file.')
    return [(1, text)]


def load_documents(files, chunk_size=180, overlap=30):
    if not files or len(files) > MAX_FILES:
        raise DocumentError(f'Choose between 1 and {MAX_FILES} documents.')
    if chunk_size <= 0 or not 0 <= overlap < chunk_size:
        raise ValueError('Overlap must be smaller than a positive chunk size.')
    docs, characters, batch_bytes = [], 0, 0
    with processing_slot():
        for file in files:
            name = safe_filename(file.name)
            suffix = PurePosixPath(name).suffix.lower()
            if suffix not in {'.pdf', '.txt'}:
                raise DocumentError(f'{name}: only PDF and UTF-8 TXT files are supported.')
            data = file.getvalue() if hasattr(file, 'getvalue') else file.read(MAX_FILE_BYTES + 1)
            if not isinstance(data, bytes) or not data or len(data) > MAX_FILE_BYTES:
                raise DocumentError(f'{name}: choose a nonempty file under 10 MB.')
            batch_bytes += len(data)
            if batch_bytes > MAX_BATCH_BYTES:
                raise DocumentError('The combined upload limit is 25 MB. Upload a smaller selection.')
            if suffix == '.pdf':
                if not re.match(rb'%PDF-[12]\.\d', data[:8]):
                    raise DocumentError(f'{name}: the content is not a valid PDF and could not be read.')
                pages = _pdf_pages(data, name)
            else:
                pages = _text_pages(data, name)
            file_chunks = []
            for number, text in pages:
                characters += len(text)
                if characters > MAX_CHARACTERS:
                    raise DocumentError('These documents contain too much text. Upload a smaller selection.')
                file_chunks.extend(_chunk(text, name, number, chunk_size, overlap))
                if len(docs) + len(file_chunks) > MAX_CHUNKS:
                    raise DocumentError('Too many text chunks. Upload a smaller selection.')
            if not file_chunks:
                raise DocumentError(f'{name}: no readable text found. Scanned PDFs need OCR before upload.')
            docs.extend(file_chunks)
    return docs
