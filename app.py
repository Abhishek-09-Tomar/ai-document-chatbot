"""Document chat: uploads and indexes belong exclusively to this browser session."""
from hashlib import sha256
from io import BytesIO
import os

import streamlit as st
from streamlit.errors import StreamlitSecretNotFoundError
from dotenv import load_dotenv
from document_processor.loader import DocumentError, MAX_FILES, MAX_FILE_BYTES, load_documents
from embeddings.embedder import EmbeddingEngine
from retrieval.faiss_store import VectorStore
from llm.generator import answer_question
from utils.conversation import retrieval_query

load_dotenv()
st.set_page_config(page_title='AI document chatbot', page_icon=':material/description:', layout='centered')

DEFAULTS = {'messages': [], 'store': None, 'signature': None, 'active_files': [],
            'uploader_version': 0, 'processed_signature': None, 'demo': False}
for key, value in DEFAULTS.items():
    st.session_state.setdefault(key, value)


def clear_chat():
    st.session_state.messages = []


def reset_documents():
    clear_chat()
    st.session_state.store = None
    st.session_state.signature = None
    st.session_state.processed_signature = None
    st.session_state.active_files = []
    st.session_state.demo = False
    st.session_state.uploader_version += 1


def server_token():
    value = os.getenv('HF_TOKEN', '').strip()
    if value:
        return value
    try:
        return str(st.secrets.get('HF_TOKEN', '')).strip()
    except (FileNotFoundError, StreamlitSecretNotFoundError):
        return ''


def render_message(message):
    with st.chat_message(message['role']):
        # Literal text prevents remote image/HTML injection from documents or models.
        st.text(message['content'], wrap=True)
        if message.get('mode'):
            st.caption(message['mode'])
        if message.get('notice'):
            st.info(message['notice'])
        if message.get('sources'):
            with st.expander('View Source Chunks'):
                for number, doc in enumerate(message['sources'], 1):
                    meta = doc['metadata']
                    st.text(f'[{number}] {meta["source"]} · page {meta["page"]}', wrap=True)
                    st.text(doc['text'], wrap=True)
                    if number < len(message['sources']):
                        st.divider()


with st.sidebar:
    st.header('Your documents', divider='green')
    st.caption('PDF or TXT · up to 10 files · 10 MB each')
    uploaded = st.file_uploader('Upload documents', type=['pdf', 'txt'], accept_multiple_files=True,
                                key=f'uploads_{st.session_state.uploader_version}')
    process = st.button('Process documents', type='primary', icon=':material/upload:',
                        disabled=not uploaded, width='stretch', key='process')
    demo = st.button('Try a sample document', icon=':material/science:', width='stretch', key='demo_button')
    st.divider()
    st.subheader('Answer settings')
    global_token = server_token()
    personal_token = ''
    if not global_token:
        personal_token = st.text_input('Hugging Face token (optional)', type='password', key='personal_token',
                                        help='Kept only in this session. Never added to the index or chat export.')
    else:
        st.caption('A server token is configured.')
    token = personal_token.strip() or global_token
    use_api = st.toggle('Use hosted AI', value=False, key='use_api', disabled=not token,
                         help='Off: find source excerpts locally. On: send relevant passages and recent chat to Hugging Face Inference Providers.')
    st.caption('Source excerpts work without a token. Hosted AI may require inference credits.')
    if use_api:
        st.info('Relevant passages and recent chat will be sent to Hugging Face and its inference provider.')
    st.divider()
    st.button('Clear chat', on_click=clear_chat, key='clear', width='stretch')
    st.button('Reset documents', on_click=reset_documents, key='reset', width='stretch')
    st.caption('Documents stay in session memory and are not saved by this app. Refreshing or closing your session can clear your work.')

st.caption('DOCUMENT WORKSPACE')
st.title('Your documents. Clear answers.')
st.markdown('Upload a document, ask a question, and check the passages behind every answer.')

# Selection changes invalidate the old index before another question can use it.
if uploaded and len(uploaded) <= MAX_FILES and all(f.size <= MAX_FILE_BYTES for f in uploaded):
    signature = tuple((f.name, sha256(f.getvalue()).hexdigest()) for f in uploaded)
elif uploaded:
    signature = ('invalid',)
else:
    signature = ()
if signature != st.session_state.signature:
    st.session_state.signature = signature
    st.session_state.store = None
    st.session_state.active_files = []
    st.session_state.messages = []
    st.session_state.demo = False

if demo:
    sample = BytesIO(b'Project Aurora handbook. The launch date is 15 March 2027. The project lead is Maya Chen. The pilot budget is 25000 dollars. Support is available Monday to Friday, 9 AM to 5 PM. The refund window is 30 days after purchase.')
    sample.name = 'aurora-handbook.txt'
    files_to_process = [sample]
elif process:
    files_to_process = uploaded
else:
    files_to_process = None

if files_to_process:
    with st.status('Preparing your documents...', expanded=True) as status:
        progress = st.progress(0, text='Reading and splitting documents')
        try:
            docs = load_documents(files_to_process)
            progress.progress(50, text='Building your private search index')
            new_store = VectorStore(EmbeddingEngine())
            new_store.build_or_load(docs)
            st.session_state.store = new_store
            st.session_state.messages = []
            st.session_state.active_files = [f.name for f in files_to_process]
            st.session_state.processed_signature = signature
            st.session_state.demo = bool(demo)
            progress.progress(100, text='Ready to chat')
            status.update(label=f'{len(files_to_process)} document(s) ready · {len(docs)} source chunks', state='complete', expanded=False)
        except (DocumentError, ValueError) as exc:
            st.warning(str(exc))
            status.update(label='Please check your documents', state='error', expanded=True)
        except Exception:
            st.error('We could not prepare these documents. Try a smaller selection or reset and upload again.')
            status.update(label='Processing could not finish', state='error', expanded=True)

store = st.session_state.store
if store is not None:
    with st.container(horizontal=True):
        st.badge(f'{len(st.session_state.active_files)} document(s)', icon=':material/description:', color='green')
        st.badge(f'{len(store.docs)} searchable chunks', color='gray')
        st.badge('Hosted AI' if use_api and token else 'Source excerpts', color='blue')
    with st.expander('Documents in this conversation'):
        for name in st.session_state.active_files:
            st.text(name)
else:
    with st.container(border=True):
        st.subheader('Start with something you want to understand')
        st.markdown('1. Add PDFs or text files in the sidebar.\n2. Select **Process documents**.\n3. Ask a question below.')
        st.caption('Just exploring? Select “Try a sample document” to start instantly.')

if store is not None and not st.session_state.messages:
    st.info('Ask a specific question, such as “What is the launch date?” or “Who is the project lead?”')
for message in st.session_state.messages:
    render_message(message)

question = st.chat_input('Ask about your documents...', key='question', disabled=store is None,
                          max_chars=2000, submit_mode='disable')
if question and question.strip() and store is not None:
    question = question.strip()[:2000]
    history = st.session_state.messages
    user_message = {'role': 'user', 'content': question}
    render_message(user_message)
    with st.spinner('Finding the relevant passages...'):
        try:
            sources = store.search(retrieval_query(question, history))
            result = answer_question(question, sources, token=token, history=history, use_api=bool(use_api))
            assistant_message = {'role': 'assistant', 'content': result.text, 'sources': sources,
                                 'mode': result.mode, 'notice': result.notice}
        except Exception:
            assistant_message = {'role': 'assistant', 'content': 'Search could not finish. Please try again or reset your documents.'}
    st.session_state.messages = (history + [user_message, assistant_message])[-40:]
    render_message(assistant_message)

if st.session_state.messages:
    export = '\n\n'.join(f'{m["role"].upper()}: {m["content"]}' for m in st.session_state.messages)
    st.download_button('Download conversation', export, 'document-chat.txt', mime='text/plain', key='download')
st.caption('Answers can be incomplete. Check the source chunks before relying on a result.')
