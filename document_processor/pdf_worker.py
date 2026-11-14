"""Isolated PDF-to-text worker. JSON only; no pickle, uploads on disk, or secrets."""
from io import BytesIO
import json
import logging
import sys

from document_processor.limits import (
    MAX_FILE_BYTES, MAX_PAGES, MAX_CHARACTERS, PDF_MEMORY_BYTES,
    PDF_CPU_SECONDS, PDF_STREAM_BYTES, MAX_WORKER_RESPONSE,
)


def apply_limits():
    if sys.platform == 'linux':
        import resource
        resource.setrlimit(resource.RLIMIT_AS, (PDF_MEMORY_BYTES, PDF_MEMORY_BYTES))
        resource.setrlimit(resource.RLIMIT_CPU, (PDF_CPU_SECONDS, PDF_CPU_SECONDS + 1))
        resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
        resource.setrlimit(resource.RLIMIT_FSIZE, (0, 0))
        resource.setrlimit(resource.RLIMIT_NOFILE, (32, 32))


def extract_pdf(data):
    from pypdf import PdfReader, apply_configuration
    # Decoder limits supplement (and do not replace) the worker's OS limits.
    with apply_configuration(
        maximum_declared_stream_length=PDF_STREAM_BYTES,
        array_based_stream_maximum_output_length=PDF_STREAM_BYTES,
        zlib_maximum_output_length=PDF_STREAM_BYTES,
        lzw_maximum_output_length=PDF_STREAM_BYTES,
        run_length_maximum_output_length=PDF_STREAM_BYTES,
        jbig2_maximum_output_length=PDF_STREAM_BYTES,
        brotli_maximum_output_length=PDF_STREAM_BYTES,
        stream_decoding_work_maximum_length=4 * PDF_STREAM_BYTES,
        stream_parsing_work_maximum_count=100_000,
        stream_filters_maximum_length=4,
        page_tree_maximum_entries=1000,
        page_tree_maximum_depth=20,
        xform_maximum_invocations_per_extraction=100,
    ):
        reader = PdfReader(BytesIO(data), strict=True)
        if reader.is_encrypted:
            return {'error': 'encrypted'}
        if len(reader.pages) > MAX_PAGES:
            return {'error': 'pages'}
        pages, characters = [], 0
        for number, page in enumerate(reader.pages, 1):
            text = page.extract_text() or ''
            characters += len(text)
            if characters > MAX_CHARACTERS:
                return {'error': 'text_limit'}
            if text.strip():
                pages.append([number, text])
        return {'pages': pages} if pages else {'error': 'empty'}


def main():
    logging.disable(logging.CRITICAL)
    try:
        apply_limits()
        data = sys.stdin.buffer.read(MAX_FILE_BYTES + 1)
        if len(data) > MAX_FILE_BYTES:
            result = {'error': 'unreadable'}
        else:
            result = extract_pdf(data)
        payload = json.dumps(result, ensure_ascii=True).encode('utf-8')
        if len(payload) > MAX_WORKER_RESPONSE:
            payload = b'{"error":"text_limit"}'
    except Exception:
        # Do not send parser exceptions or paths over the process boundary.
        payload = b'{"error":"unreadable"}'
    sys.stdout.buffer.write(payload)


if __name__ == '__main__':
    main()
