import os
import json
import logging
from openai import OpenAI
from typing import List, Dict, Any

class CodeAgent:
    """A ReAct-style agent that uses graph and vector tools to answer questions."""
    
    SYSTEM_PROMPT = """You are an expert software engineer assistant. You have access to the following tools to analyze a codebase:

1. `query_graph(action, name)`: Query the knowledge graph.
   - action="who_calls": Find functions calling `name`.
   - action="called_by": Find functions called by `name`.
2. `semantic_search(query)`: Search for code snippets related to the query string.
3. `get_file_content(path)`: Read the content of a file.

Use a ReAct pattern:
Question: the input question you must answer
Thought: you should always think about what to do
Action: the action to take, should be one of [query_graph, semantic_search, get_file_content]
Action Input: the input to the action
Observation: the result of the action
... (this Thought/Action/Action Input/Observation can repeat N times)
Thought: I now know the final answer
Final Answer: the final answer to the original input question

Maintain focus on providing technical, accurate answers based on the codebase.
"""

    def __init__(self, graph_builder, retriever):
        self.graph = graph_builder
        self.retriever = retriever
        # DeepSeek or OpenAI
        self.client = OpenAI(
            api_key=os.getenv("OPENAI_API_KEY"),
            base_url=os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")
        )
        self.model = os.getenv("OPENAI_MODEL", "gpt-4-turbo-preview")

    def _call_tool(self, action: str, action_input: str) -> str:
        logging.info(f"Agent Action: {action}({action_input})")
        try:
            if action == "query_graph":
                # Expecting input like 'who_calls,func_name'
                parts = [p.strip() for p in action_input.split(",")]
                if len(parts) != 2: return "Error: query_graph requires 'action,name'"
                act, name = parts
                if act == "who_calls":
                    return str(self.graph.who_calls(name))
                elif act == "called_by":
                    return str(self.graph.called_by(name))
                return f"Unknown graph action: {act}"
            
            elif action == "semantic_search":
                results = self.retriever.search(action_input, top_k=3)
                output = []
                for r in results:
                    output.append(f"File: {r['metadata']['file_path']}\nSnippet: {r['document']}")
                return "\n---\n".join(output) or "No relevant snippets found."
            
            elif action == "get_file_content":
                # Need to handle pathing carefully
                # Assuming the agent uses paths relative to project root
                full_path = action_input
                if os.path.exists(full_path):
                    with open(full_path, 'r', encoding='utf-8', errors='ignore') as f:
                        return f.read()[:2000] # Limit output
                return f"File not found: {full_path}"
            
            return f"Unknown tool: {action}"
        except Exception as e:
            return f"Error executing tool: {str(e)}"

    def run(self, query: str, max_iterations: int = 5) -> str:
        messages = [
            {"role": "system", "content": self.SYSTEM_PROMPT},
            {"role": "user", "content": f"Question: {query}"}
        ]
        
        for _ in range(max_iterations):
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                stop=["Observation:"]
            )
            
            content = response.choices[0].message.content
            messages.append({"role": "assistant", "content": content})
            
            if "Final Answer:" in content:
                return content.split("Final Answer:")[-1].strip()
            
            # Parse Action and Action Input
            try:
                # Basic parsing logic for ReAct
                lines = content.split("\n")
                action = ""
                action_input = ""
                for line in lines:
                    if line.startswith("Action:"):
                        action = line.replace("Action:", "").strip()
                    if line.startswith("Action Input:"):
                        action_input = line.replace("Action Input:", "").strip()
                
                if action:
                    observation = self._call_tool(action, action_input)
                    messages.append({"role": "user", "content": f"Observation: {observation}"})
                else:
                    # If it didn't provide an action but also no final answer, try to nudge it
                    messages.append({"role": "user", "content": "Please continue following the ReAct pattern or provide a Final Answer."})
            except Exception as e:
                messages.append({"role": "user", "content": f"Observation: Error parsing action: {str(e)}"})
        
        return "Agent timed out without a final answer."
