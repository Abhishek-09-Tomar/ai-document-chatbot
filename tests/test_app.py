"""UI regression tests, using the CPU-only app."""
from streamlit.testing.v1 import AppTest
from pathlib import Path

APP = Path(__file__).resolve().parents[1] / 'app.py'


def test_empty_demo_followup_and_reset(monkeypatch):
    monkeypatch.delenv('HF_TOKEN', raising=False)
    app = AppTest.from_file(APP, default_timeout=30).run()
    assert not app.exception
    assert app.chat_input[0].disabled
    app.button(key='demo_button').click().run()
    assert not app.exception
    assert not app.chat_input[0].disabled
    app.chat_input[0].set_value('What is the launch date?').run()
    assert not app.exception
    assert len(app.session_state.messages) == 2
    assert '15 March 2027' in app.session_state.messages[-1]['content']
    assert app.session_state.messages[-1]['sources'][0]['metadata']['source'] == 'aurora-handbook.txt'
    app.session_state.budget.last_query -= 2
    app.chat_input[0].set_value('Who leads it?').run()
    assert len(app.session_state.messages) == 4
    assert 'Maya Chen' in app.session_state.messages[-1]['content']
    app.button(key='clear').click().run()
    assert app.session_state.messages == []
    assert app.session_state.store is not None
    app.button(key='reset').click().run()
    assert not app.exception
    assert app.session_state.store is None
    assert app.chat_input[0].disabled


def test_two_browser_sessions_are_isolated():
    first = AppTest.from_file(APP, default_timeout=30).run()
    first.button(key='demo_button').click().run()
    second = AppTest.from_file(APP, default_timeout=30).run()
    assert first.session_state.store is not None
    assert second.session_state.store is None
    assert not second.exception


def test_anonymous_user_cannot_spend_server_token(monkeypatch):
    monkeypatch.setenv('HF_TOKEN', 'hf_' + 'x' * 32)
    app = AppTest.from_file(APP, default_timeout=30).run()
    assert not app.exception
    widget = app.text_input(key='personal_token')
    assert widget.proto.type == widget.proto.PASSWORD
    assert app.toggle(key='use_api').disabled


def test_clear_and_reset_do_not_reset_request_budget():
    app = AppTest.from_file(APP, default_timeout=30).run()
    app.button(key='demo_button').click().run()
    app.chat_input[0].set_value('What is the launch date?').run()
    app.session_state.budget.queries = 20
    app.button(key='clear').click().run()
    assert app.session_state.budget.queries == 20
    app.chat_input[0].set_value('Another question').run()
    assert app.warning
    assert app.session_state.messages == []
    app.button(key='reset').click().run()
    assert app.session_state.budget.queries == 20


def test_cooldown_blocks_an_immediate_follow_up():
    import time
    app = AppTest.from_file(APP, default_timeout=30).run()
    app.button(key='demo_button').click().run()
    app.chat_input[0].set_value('What is the launch date?').run()
    app.session_state.budget.last_query = time.monotonic()
    app.chat_input[0].set_value('Who leads it?').run()
    assert app.warning
    assert app.session_state.budget.queries == 1
    assert len(app.session_state.messages) == 2
