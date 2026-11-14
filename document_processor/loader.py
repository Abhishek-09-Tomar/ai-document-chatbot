"""Bounded, page-aware extraction. Uploaded content is never written to disk."""
from io import BytesIO
from pathlib import Path
from pypdf import PdfReader

MAX_FILE_BYTES = 10 * 1024 * 1024
MAX_FILES = 10
MAX_PAGES = 200
MAX_CHARACTERS = 1_000_000
MAX_CHUNKS = 2000


class DocumentError(ValueError):
    """A document cannot be processed or has no readable text."""


def _chunk(text, source_name, page_no, chunk_size=180, overlap=30):
    if chunk_size <= 0 or not 0 <= overlap < chunk_size:
        raise ValueError('Overlap must be smaller than a positive chunk size.')
    words = text.split()
    chunks = []
    for start in range(0, len(words), chunk_size - overlap):
        chunks.append({'text': ' '.join(words[start:start + chunk_size]),
                       'metadata': {'source': source_name, 'page': page_no}})
        if start + chunk_size >= len(words):
            break
    return chunks


def load_documents(files, chunk_size=180, overlap=30):
    if not files or len(files) > MAX_FILES:
        raise DocumentError(f'Choose between 1 and {MAX_FILES} documents.')
    docs, characters = [], 0
    for file in files:
        name = Path(file.name).name
        data = file.getvalue() if hasattr(file, 'getvalue') else file.read(MAX_FILE_BYTES + 1)
        if not data or len(data) > MAX_FILE_BYTES:
            raise DocumentError(f'{name}: choose a nonempty file under 10 MB.')
        try:
            suffix = Path(name).suffix.lower()
            if suffix == '.pdf':
                reader = PdfReader(BytesIO(data))
                if reader.is_encrypted:
                    raise DocumentError(f'{name}: upload an unlocked PDF.')
                if len(reader.pages) > MAX_PAGES:
                    raise DocumentError(f'{name}: the limit is {MAX_PAGES} pages per PDF.')
                pages = ((n, page.extract_text() or '') for n, page in enumerate(reader.pages, 1))
            elif suffix == '.txt':
                pages = [(1, data.decode('utf-8-sig'))]
            else:
                raise DocumentError(f'{name}: only PDF and UTF-8 TXT files are supported.')
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
        except DocumentError:
            raise
        except UnicodeDecodeError:
            raise DocumentError(f'{name}: save the text file with UTF-8 encoding and try again.') from None
        except Exception:
            raise DocumentError(f'{name}: this file could not be read. Try exporting a fresh PDF or TXT copy.') from None
    return docs
