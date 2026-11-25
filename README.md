# CodeMind

CodeMind is a CLI tool that answers questions about a Python codebase. It combines a call graph, semantic search and an LLM agent that uses both as tools.

## Features
- **Code extraction**: parses Python with `tree-sitter` and records functions, classes, calls and inheritance.
- **Call graph**: a `NetworkX` graph. Every function has a qualified ID such as `sessions.py::Session.send`, so methods with the same name in different classes stay separate. Each call edge is marked **certain** or **uncertain**.
- **Semantic search**: function signatures and docstrings are embedded with `all-MiniLM-L6-v2` and stored in `ChromaDB`.
- **AI agent**: uses native function calling with three tools: `query_graph`, `semantic_search` and `get_file_content` (reads a file by line range).
- **Report**: flags long functions, high fan-in/fan-out, call cycles and missing docstrings, using certain call edges only.

## Setup

1. **Create a virtual environment** (Python 3.12; `tree-sitter-languages` has no wheel for 3.13):
   ```bash
   python -m venv venv
   source venv/bin/activate   # Linux/macOS
   .\venv\Scripts\activate    # Windows
   ```

2. **Install dependencies** (versions are pinned; newer `tree-sitter` releases break `tree-sitter-languages`):
   ```bash
   pip install -r requirements.txt
   pip install -e .
   ```

3. **Configure the LLM**: copy `.env.example` to `.env` and fill in your key. Any OpenAI-compatible endpoint works. Never commit `.env`.

## Usage
```bash
codemind build ./src
codemind ask "Which functions call Session.send?"
codemind report
```

## How call edges are resolved
| Call in the source | Edge |
|---|---|
| `self.foo()` inside a class that defines `foo` | certain (plus subclass overrides as uncertain) |
| `foo()` defined in the same file, or unique in the project | certain |
| `module.foo()` | certain |
| `obj.foo()` where the type of `obj` is unknown | uncertain, linked to every method named `foo` |

Uncertain edges keep recall high; the agent is told to check them in the source before relying on them.

## Evaluation

20 questions about [`requests`](https://github.com/psf/requests) v2.34.2 (`eval/questions.jsonl`): call chains, callers, callees, inheritance, locating code, plus two trap questions about features `requests` does not have. Every gold answer was checked against the source.

Each answer is scored by hand: 1 = correct and complete, 0.5 = partly correct or includes wrong items, 0 = wrong or timed out. Each version was run twice to measure run-to-run noise. Raw answers and tool-call traces are in `eval/results/`.

```bash
python eval/run_eval.py --tag my-run
```

| Version | Change | Run 1 | Run 2 | Mean |
|---|---|---|---|---|
| v0 | ReAct text parsing | 5.5 | 8.5 | 7.0 |
| v1 | Native function calling; read files by line range | 17.5 | 15.5 | 16.5 |
| v2 | Qualified names; certain / uncertain edges | 17.5 | 19.0 | **18.25** |

The four questions most affected by duplicate method names (q02, q03, q04, q12) scored **3 / 8** across v1's two runs and **6.5 / 8** across v2's.

Model: `openai/gpt-6-luna` via OpenRouter.

### Known limitations
- **Relative paths**: the agent sometimes asks `get_file_content` for `sessions.py` instead of the full path and gets "File not found", which wastes tool calls (one v2 timeout, q02).
- **Search covers signatures and docstrings only**: logic inside a function body (for example the `max_redirects` check, q19) is hard to find by semantic search.
- **Small, single-repo benchmark**: 20 questions on one library the model may already know; the trap questions check that it does not answer from memory.
