"""Resolve short follow-ups for retrieval."""
import re


def retrieval_query(question, messages):
    follow_up = re.search(r'\b(it|its|they|them|their|that|those|this|these|also|more)\b', question, re.I)
    if follow_up or len(question.split()) <= 4:
        previous = next((m['content'] for m in reversed(messages) if m['role'] == 'user'), '')
        return f'{question} {previous[:500]}'.strip()
    return question
