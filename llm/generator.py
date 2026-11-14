"""Hosted generation: bounded untrusted XML data, budgets, and literal-text answers."""
from dataclasses import dataclass
import os
import re
from huggingface_hub import InferenceClient

from utils.prompts import build_messages, sanitize_query, format_context
from utils.security import HOSTED_BUDGET, MAX_SOURCES, log_failure, BudgetError

DEFAULT_MODEL = 'Qwen/Qwen2.5-7B-Instruct'
NOT_FOUND = 'I could not find an answer in the uploaded documents. Try using words from the document or asking a more specific question.'


@dataclass
class Answer:
    text: str
    mode: str
    notice: str = ''


def excerpt_answer(question, docs):
    if not docs:
        return NOT_FOUND
    terms = set(re.findall(r'\w+', question.lower())) - {
        'what', 'when', 'where', 'which', 'how', 'does', 'the', 'is', 'a', 'an', 'it', 'and', 'of', 'to', 'in'}
    excerpts = []
    for i, doc in enumerate(docs[:3], 1):
        sentences = re.split(r'(?<=[.!?])\s+', doc['text'][:3000])
        stemmed = {term.rstrip('s') for term in terms}
        ranked = sorted(enumerate(sentences), key=lambda item: -len(stemmed & {
            term.rstrip('s') for term in re.findall(r'\w+', item[1].lower())}))
        selected = ' '.join(sentence for _, sentence in sorted(ranked[:2]))[:700]
        excerpts.append(f'{selected}\n\nSource [{i}]')
    return 'Here are the closest passages from your documents:\n\n' + '\n\n'.join(excerpts)


def answer_question(question, docs, *, token=None, history=None, use_api=True, shared_token=False):
    question = sanitize_query(question)
    docs = docs[:MAX_SOURCES]
    if not question or not docs:
        return Answer(NOT_FOUND, 'Source excerpts')
    if use_api and token:
        messages = build_messages(question, docs, history)
        model = os.environ.get('HF_MODEL', DEFAULT_MODEL)
        if not re.fullmatch(r'[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+', model):
            model = DEFAULT_MODEL
        try:
            with HOSTED_BUDGET.reserve(token, shared=shared_token):
                with InferenceClient(token=token, timeout=45, provider='auto') as client:
                    response = client.chat_completion(model=model, messages=messages,
                                                      max_tokens=512, temperature=0.2)
                text = response.choices[0].message.content
                if not isinstance(text, str) or not text.strip():
                    raise ValueError('Empty model response')
                return Answer(text.strip()[:6000], 'AI answer')
        except BudgetError as error:
            return Answer(excerpt_answer(question, docs), 'Source excerpts', str(error))
        except Exception as error:
            log_failure('hosted_inference_failed', error)
            return Answer(excerpt_answer(question, docs), 'Source excerpts',
                          'AI generation is unavailable. Check token permissions, model availability, or inference credits. Showing source excerpts instead.')
    return Answer(excerpt_answer(question, docs), 'Source excerpts')


def generate_answer(question, docs=None, **kwargs):
    return answer_question(question, docs or [], **kwargs).text
