import os
import json
import logging
from openai import OpenAI


class CodeAgent:
    """An agent that answers questions about a codebase using native function calling.

    Instead of asking the model to write "Action: ..." lines that we parse as text
    (the old ReAct format), we register the tools with the API. The model then
    returns structured tool calls with JSON arguments, which we run and send back.
    """

    SYSTEM_PROMPT = (
        "You are an expert software engineer helping someone understand a codebase. "
        "You have tools to query the call graph, search code by meaning, and read source files. "
        "Always use the tools to check facts in this codebase before answering; do not answer "
        "from memory. Names in the call graph are short function or class names, for example "
        "'send' rather than 'Session.send'. If the tools show that something does not exist in "
        "this codebase, say so plainly instead of guessing."
    )

    # The tool "menu" we register with the model. Each entry says what the tool does
    # and which arguments it takes (a JSON Schema), so the model fills them in correctly.
    TOOLS = [
        {
            "type": "function",
            "function": {
                "name": "query_graph",
                "description": "Query the call graph: who calls a function, or what a function calls.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "action": {
                            "type": "string",
                            "enum": ["who_calls", "called_by"],
                            "description": "who_calls = callers of `name`; called_by = functions that `name` calls.",
                        },
                        "name": {"type": "string", "description": "Short function name, e.g. 'send'."},
                    },
                    "required": ["action", "name"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "semantic_search",
                "description": "Search functions and classes by meaning. Returns file paths and start lines.",
                "parameters": {
                    "type": "object",
                    "properties": {"query": {"type": "string", "description": "What you are looking for."}},
                    "required": ["query"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "get_file_content",
                "description": "Read lines of a source file, with line numbers. Use a path returned by semantic_search.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "path": {"type": "string"},
                        "start_line": {"type": "integer", "description": "First line to read (default 1)."},
                        "end_line": {"type": "integer", "description": "Last line to read (default start_line + 79)."},
                    },
                    "required": ["path"],
                },
            },
        },
    ]

    MAX_LINES_PER_READ = 200

    def __init__(self, graph_builder, retriever):
        self.graph = graph_builder
        self.retriever = retriever
        self.client = OpenAI(
            api_key=os.getenv("OPENAI_API_KEY"),
            base_url=os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1"),
        )
        self.model = os.getenv("OPENAI_MODEL", "gpt-6-luna")

    def _call_tool(self, action: str, args: dict) -> str:
        """Run one tool. `action` is the tool name, `args` the arguments the model chose."""
        logging.info(f"Agent Action: {action}({args})")
        try:
            if action == "query_graph":
                name = args.get("name", "")
                if args.get("action") == "who_calls":
                    return str(self.graph.who_calls(name))
                if args.get("action") == "called_by":
                    return str(self.graph.called_by(name))
                return f"Unknown graph action: {args.get('action')}"

            if action == "semantic_search":
                results = self.retriever.search(args.get("query", ""), top_k=3)
                output = []
                for r in results:
                    meta = r["metadata"]
                    output.append(
                        f"File: {meta['file_path']}\n"
                        f"Start line: {meta.get('start_line', 'n/a')}\n"
                        f"Snippet: {r['document']}"
                    )
                return "\n---\n".join(output) or "No relevant snippets found."

            if action == "get_file_content":
                path = args.get("path", "")
                if not os.path.isfile(path):
                    return f"File not found: {path}"
                with open(path, "r", encoding="utf-8", errors="ignore") as f:
                    lines = f.readlines()
                start = max(1, int(args.get("start_line") or 1))
                end = int(args.get("end_line") or start + 79)
                end = min(end, start + self.MAX_LINES_PER_READ - 1, len(lines))
                numbered = [f"{i}: {lines[i - 1].rstrip()}" for i in range(start, end + 1)]
                return f"{path} (lines {start}-{end} of {len(lines)})\n" + "\n".join(numbered)

            return f"Unknown tool: {action}"
        except Exception as e:
            return f"Error executing tool: {e}"

    def run(self, query: str, max_iterations: int = 8) -> str:
        messages = [
            {"role": "system", "content": self.SYSTEM_PROMPT},
            {"role": "user", "content": query},
        ]
        kwargs = {}
        effort = os.getenv("OPENAI_REASONING_EFFORT")  # e.g. "none" for gpt-6-luna
        if effort:
            kwargs["reasoning_effort"] = effort

        for _ in range(max_iterations):
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                tools=self.TOOLS,
                **kwargs,
            )
            msg = response.choices[0].message
            logging.info(f"LLM said: {msg.content or ''}")

            # No tool calls means the model is giving its final answer.
            if not msg.tool_calls:
                return (msg.content or "").strip()

            # Keep the model's tool requests in the conversation history...
            messages.append({
                "role": "assistant",
                "content": msg.content or "",
                "tool_calls": [
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {"name": tc.function.name, "arguments": tc.function.arguments},
                    }
                    for tc in msg.tool_calls
                ],
            })
            # ...then run each tool and send its result back, matched by tool_call_id.
            for tc in msg.tool_calls:
                try:
                    args = json.loads(tc.function.arguments or "{}")
                except json.JSONDecodeError:
                    args = {}
                result = self._call_tool(tc.function.name, args)
                messages.append({"role": "tool", "tool_call_id": tc.id, "content": result})

        return "Agent timed out without a final answer."
