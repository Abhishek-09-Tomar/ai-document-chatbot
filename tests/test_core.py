"""Core regression tests; no model downloads or credentials required."""
from io import BytesIO
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from pypdf import PdfWriter
from pypdf.generic import DictionaryObject, NameObject, DecodedStreamObject
from document_processor.loader import _chunk, load_documents, DocumentError
from embeddings.embedder import EmbeddingEngine
from retrieval.faiss_store import VectorStore
from llm.generator import answer_question, NOT_FOUND
from utils.conversation import retrieval_query


def upload(name, data):
    file = BytesIO(data)
    file.name = name
    return file


def pdf_bytes(text=None, encrypted=False):
    writer = PdfWriter()
    page = writer.add_blank_page(width=612, height=792)
    if text:
        font = DictionaryObject({NameObject('/Type'): NameObject('/Font'),
                                 NameObject('/Subtype'): NameObject('/Type1'),
                                 NameObject('/BaseFont'): NameObject('/Helvetica')})
        page[NameObject('/Resources')] = DictionaryObject({
            NameObject('/Font'): DictionaryObject({NameObject('/F1'): writer._add_object(font)})})
        stream = DecodedStreamObject()
        stream.set_data(f'BT /F1 12 Tf 50 700 Td ({text}) Tj ET'.encode())
        page[NameObject('/Contents')] = writer._add_object(stream)
    if encrypted:
        writer.encrypt('password')
    result = BytesIO()
    writer.write(result)
    return result.getvalue()


def make_store(texts):
    store = VectorStore(EmbeddingEngine('tfidf'))
    store.build_or_load([{'text': text, 'metadata': {'source': f'{n}.txt', 'page': 1}}
                         for n, text in enumerate(texts)])
    return store


def test_chunk_overlap_and_page():
    chunks = _chunk('one two three four five six seven', 'a.txt', 2, 4, 1)
    assert [d['text'] for d in chunks] == ['one two three four', 'four five six seven']
    assert chunks[1]['metadata'] == {'source': 'a.txt', 'page': 2}


@pytest.mark.parametrize('size,overlap', [(0, 0), (3, 3), (3, 4), (3, -1)])
def test_invalid_chunk_parameters(size, overlap):
    with pytest.raises(ValueError):
        _chunk('text', 'a', 1, size, overlap)


def test_txt_multiple_files_cursor_and_bom():
    file = upload('a.txt', b'\xef\xbb\xbfAurora launch is March.')
    file.read()
    docs = load_documents([file, upload('b.TXT', b'Budget is 25000 dollars.')])
    assert len(docs) == 2
    assert docs[0]['text'] == 'Aurora launch is March.'
    assert docs[1]['metadata']['source'] == 'b.TXT'


def test_pdf_text_and_metadata():
    docs = load_documents([upload('handbook.pdf', pdf_bytes('The launch is 15 March 2027.'))])
    assert '15 March 2027' in docs[0]['text']
    assert docs[0]['metadata'] == {'source': 'handbook.pdf', 'page': 1}


@pytest.mark.parametrize('name,data,match', [
    ('empty.txt', b'', 'nonempty'),
    ('blank.txt', b'  \n', 'no readable'),
    ('broken.pdf', b'%PDF broken', 'could not be read'),
    ('bad.txt', b'\xff\xfe\xff', 'UTF-8'),
    ('wrong.csv', b'hello', 'only PDF'),
    ('scan.pdf', pdf_bytes(), 'OCR'),
    ('locked.pdf', pdf_bytes('Secret', True), 'unlocked'),
])
def test_friendly_file_errors(name, data, match):
    with pytest.raises(DocumentError, match=match):
        load_documents([upload(name, data)])


def test_file_limits():
    with pytest.raises(DocumentError, match='between'):
        load_documents([upload('a.txt', b'a')] * 11)
    with pytest.raises(DocumentError, match='under 10'):
        load_documents([upload('big.txt', b'a' * (10 * 1024 * 1024 + 1))])


def test_faiss_retrieval_accuracy_and_no_duplicates():
    store = make_store(['Bananas are yellow fruit.', 'The launch date is March 15.', 'Penguins live in Antarctica.'])
    hits = store.search('launch date', top_k=10)
    assert hits[0]['metadata']['source'] == '1.txt'
    assert len(hits) == 1
    assert hits[0]['score'] > 0


def test_unrelated_query():
    assert make_store(['The launch date is March.']).search('volcanoes') == []


def test_sessions_and_rebuild_are_isolated(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    first = make_store(['Alpha private report.'])
    second = make_store(['Beta different report.'])
    assert second.search('Alpha') == []
    assert first.search('Alpha')[0]['text'] == 'Alpha private report.'
    first.build_or_load([{'text': 'Replacement report.', 'metadata': {'source': 'new', 'page': 1}}])
    assert first.search('Alpha') == []
    assert list(tmp_path.iterdir()) == []


def test_empty_store():
    store = VectorStore(EmbeddingEngine('tfidf'))
    assert store.search('test') == []
    with pytest.raises(ValueError):
        store.build_or_load([])


def test_fallback_and_citations_without_token():
    hits = make_store(['The launch date is 15 March 2027.']).search('launch')
    result = answer_question('When is launch?', hits)
    assert result.mode == 'Source excerpts'
    assert '15 March 2027' in result.text
    assert 'Source [1]' in result.text
    assert answer_question('Question', []).text == NOT_FOUND


def test_provider_failure_is_safe():
    hits = make_store(['The launch date is March.']).search('launch')
    with patch('llm.generator.InferenceClient', side_effect=RuntimeError('sensitive-token')):
        result = answer_question('launch?', hits, token='sensitive-token')
    assert result.mode == 'Source excerpts'
    assert result.notice
    assert 'sensitive-token' not in result.text + result.notice


def test_hosted_generation_includes_history_and_sources():
    hits = make_store(['The launch date is March.']).search('launch')
    client = MagicMock()
    client.chat_completion.return_value = SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content='March [1]'))])
    factory = MagicMock()
    factory.return_value.__enter__.return_value = client
    history = [{'role': 'user', 'content': 'Tell me about launch'}]
    with patch('llm.generator.InferenceClient', factory):
        result = answer_question('When is it?', hits, token='fake', history=history)
    assert result.text == 'March [1]'
    sent = client.chat_completion.call_args.kwargs['messages']
    assert history[0]['content'] in sent[1]['content']
    assert '<context>' in sent[-1]['content']
    assert '0.txt' in sent[-1]['content']


def test_follow_up_retrieval():
    history = [{'role': 'user', 'content': 'What is Project Aurora?'}]
    assert 'Project Aurora' in retrieval_query('Who leads it?', history)
