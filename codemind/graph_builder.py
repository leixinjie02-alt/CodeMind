import networkx as nx
import json
from pathlib import Path
from networkx.readwrite import json_graph

class GraphBuilder:
    """Builds and manages the codebase knowledge graph using networkx."""
    
    def __init__(self):
        self.graph = nx.DiGraph()

    def build_graph(self, parsed_data: dict, file_path: str = None):
        """
        Populate the graph from parsed data.
        """
        # 1. Add Function nodes
        for func in parsed_data.get("functions", []):
            self.graph.add_node(
                func["name"], 
                type="function",
                docstring=func.get("docstring", ""),
                params=func.get("params", ""),
                start_line=func.get("start_line"),
                end_line=func.get("end_line"),
                file_path=file_path
            )

        # 2. Add Class nodes
        for cls in parsed_data.get("classes", []):
            self.graph.add_node(cls["name"], type="class", file_path=file_path)

        # 3. Add Call edges (caller -> callee)
        for caller, callee in parsed_data.get("calls", []):
            # We ensure nodes exist even if they weren't explicitly defined in this file
            if not self.graph.has_node(caller):
                self.graph.add_node(caller, type="function", external=True)
            if not self.graph.has_node(callee):
                self.graph.add_node(callee, type="function", external=True)
            
            self.graph.add_edge(caller, callee, relation="calls")

        # 4. Add Inheritance edges (child -> parent)
        for child, parent in parsed_data.get("inheritance", []):
            if not self.graph.has_node(child):
                self.graph.add_node(child, type="class", external=True)
            if not self.graph.has_node(parent):
                self.graph.add_node(parent, type="class", external=True)
            
            self.graph.add_edge(child, parent, relation="inherits")

    def who_calls(self, function_name: str) -> list[str]:
        """Returns all functions that call the given function."""
        if not self.graph.has_node(function_name):
            return []
        
        callers = []
        for u, v, data in self.graph.in_edges(function_name, data=True):
            if data.get("relation") == "calls":
                callers.append(u)
        return list(set(callers))

    def called_by(self, function_name: str) -> list[str]:
        """Returns all functions called by the given function."""
        if not self.graph.has_node(function_name):
            return []
        
        callees = []
        for u, v, data in self.graph.out_edges(function_name, data=True):
            if data.get("relation") == "calls":
                callees.append(v)
        return list(set(callees))

    def save_graph(self, path: str):
        """Export the graph as a JSON file."""
        data = json_graph.node_link_data(self.graph)
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    def load_graph(self, path: str):
        """Load the graph from a JSON file."""
        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        self.graph = json_graph.node_link_graph(data)
