# CodeMind

CodeMind is a CLI tool for intelligent codebase analysis, dependency mapping, and QA.

## Features
- **Code Knowledge Construction**: Extract relationships via `tree-sitter`.
- **Vector Search**: Semantic code retrieval using `ChromaDB`.
- **Graph Analysis**: Query call chains and dependencies via `NetworkX`.
- **AI Agent**: ReAct-based agent for natural language interaction.

## Setup

1. **Create Virtual Environment**:
   ```bash
   python3 -m venv venv
   source venv/bin/activate  # Linux/macOS
   # or
   .\venv\Scripts\activate  # Windows
   ```

2. **Install Dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

3. **Development Mode**:
   ```bash
   pip install -e .
   ```

## Usage
```bash
codemind build ./src
codemind ask "How is the authentication flow implemented?"
codemind report
```
