# Security audit and hardening

Audit date: 14 November 2026. Scope: tracked application source, deployment/configuration files, dependency manifests, tests, notebook contents, and locally reachable Git history.

## Findings before hardening

| Severity | Finding | Remediation |
| --- | --- | --- |
| Critical | No confirmed current credential leak or input-driven code-execution path. A historical .env existed but was empty. | Scanned credential signatures without printing values; added a repeatable redacted history scan to CI. |
| High | PDF extraction ran inside the web process; compressed streams and pathological PDFs could exhaust resources before text limits applied. | Credential-free subprocess with JSON IPC, 20-second timeout, Linux 384 MiB/12-second limits, decoder limits, tree-depth/work bounds, and strict parsing. |
| High | Anonymous visitors could spend the configured server inference credential. No request cooldown or query quota existed. | Server credentials require trusted Streamlit sign-in. Anonymous hosted inference uses personal credentials; per-session/per-key/process budgets and concurrency bounds are enforced server-side. |
| High | Dependency audit returned 98 advisory records across seven core packages (records include duplicates and advisories not necessarily reachable through this app). | Updated and hash-locked core and development environments. Both now scan without known vulnerabilities in the recorded audit. |
| High | Optional local-model dependencies also had reported vulnerabilities; one PyTorch advisory had no listed patched version. | Removed the optional PyTorch/Sentence-Transformers backend and its dependency manifest. Default CPU TF-IDF/FAISS and hosted generation remain. |
| Medium | File extensions were checked without strong content validation; file/page limits were too permissive. | PDF magic bytes, UTF-8/plain-text checks, archive/binary rejection, cross-platform filename normalization, five-file/100-page limits, and aggregate size bounds. |
| Medium | Prompt content had no escaped context structure or model-control-token filtering. | Bounded, XML-escaped context/question/conversation; stripped model delimiters and invisible controls; fixed system policy; no tools. |
| Medium | CORS/XSRF were implicit; key-file patterns were not excluded from Git/container context. | Explicit protections, host allowlist, static serving and agent API disabled, expanded ignores, non-root UID/GID and root-owned code. |
| Medium | Error handling hid exceptions but lacked safe operational diagnostics. | Log event, exception type and HTTP status only. Do not log exception strings, raw tracebacks, credentials, queries, documents, or provider payloads. |

The original app already rendered document/model text literally and used an in-memory FAISS index. No current pickle loading, arbitrary eval/exec, unsafe YAML loading, input-derived shell command, or unsafe_allow_html rendering was found. The audit did not rewrite Git history because it found no exposed credential values.

## Controls and verification

- Upload bytes never become paths, shell commands, Python expressions, or serialized Python objects. No uploaded index/model/attachment is loaded.
- PDF parsing occurs in a separate process. JSON is the only response format. Parser stderr is discarded; failures produce fixed, friendly messages.
- Filename normalization handles Windows and POSIX separators and strips markup/control characters. Filenames are display metadata only.
- CPU/index admission limits are shared within the server process. Active index registrations use weak references and disappear when their sessions are released.
- Clear chat, document reset, and changed uploads do not reset request counters.
- Hosted budgets key records by credential digest; raw keys never enter budget records. Failed hosted attempts consume quota.
- User/document/model data is displayed with st.text, including source chunks; model responses do not become Markdown or HTML.
- Limits apply inside application functions as well as UI widgets. Widget-only constraints are not treated as security boundaries.
- Core/development lock files have exact versions and SHA-256 hashes. Third-party packages are taken from PyPI; the unusual httpx2/httpcore2 dependencies were verified against Hugging Face's official v2.4.0 packaging and Pydantic's upstream project.
- CI uses fixed official action commit hashes and read-only repository permissions.

Bandit suppressions are narrow and documented: B404/B603 for fixed Git/Python subprocess commands with no shell, and B106 for scikit-learn's token_pattern word regex. No general scanner exclusions hide application findings.

## Boundaries and remaining work

No audit proves an application unhackable or a dependency free of unknown vulnerabilities. Prompt injection can still influence plain-text model answers. The model receives no server secrets or execution tools, and its output is never executed.

The worker limits are a resource boundary, not a complete operating-system sandbox. Production runs on Linux; Windows development has the wall timeout but not Linux resource limits. Keep Python, the base container image, the host and scanners patched; apply container-level CPU/memory limits and network policy appropriate to the hosting platform.

Per-process limits reset on process restart and do not coordinate replicas. New anonymous sessions can bypass session counters, though they cannot access the server token. Use a gateway/WAF, durable identity-based quotas, and provider spending limits for a larger public deployment. Framework upload buffers are allocated before the application's post-upload validation; edge/server transport limits remain important.

OIDC is not configured in this demo. Only configure shared server inference after setting up trusted authentication and provider-side spending limits. Personal tokens remain ephemeral and should have inference-only permissions.

Dependency scanners are time-sensitive snapshots, not proof of exploitability or package provenance. The automated secret scan covers common credential signatures and locally reachable Git objects; it cannot identify every arbitrary password, removed remote ref, fork, or third-party copy.

Hugging Face publishing and live-container verification require a write-enabled repository token. The credential available during the audit had repository read access only. A live build/test is not claimed until publishing succeeds.

## Primary references

- [Streamlit configuration and CORS/XSRF controls](https://docs.streamlit.io/develop/api-reference/configuration/config.toml)
- [pypdf security controls](https://pypdf.readthedocs.io/en/latest/user/security.html)
- [Hugging Face v2.4.0 package dependencies](https://github.com/huggingface/huggingface_hub/blob/v2.4.0/setup.py)
- [Pydantic httpx2 project](https://github.com/pydantic/httpx2)
