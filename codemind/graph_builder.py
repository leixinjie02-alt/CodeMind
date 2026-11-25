import json
from collections import defaultdict
from pathlib import Path

import networkx as nx
from networkx.readwrite import json_graph


class GraphBuilder:
    """Builds and queries the call graph.

    Node IDs are qualified: "sessions.py::Session.send", so methods with the same
    short name in different classes or files stay separate.

    Building happens in two steps:
      1. build_graph() adds the functions and classes of one file, and stores each
         function's raw calls (callee name + receiver) on its node.
      2. resolve_calls() runs once all files are in, and turns raw calls into edges.
         An edge is "certain" when static analysis can tell exactly which function is
         called (e.g. self.send() inside Session), and "uncertain" when it can't
         (e.g. adapter.send(): we don't know the type of `adapter`). Uncertain edges
         go to every plausible target and are labelled, so nothing real is lost and
         the agent can check them against the source.
    """

    def __init__(self):
        self.graph = nx.DiGraph()

    # ---------- building ----------

    @staticmethod
    def _module_name(file_path, root):
        if not file_path:
            return "<unknown>"
        if root:
            try:
                return Path(file_path).resolve().relative_to(Path(root).resolve()).as_posix()
            except ValueError:
                pass
        return Path(file_path).name

    def build_graph(self, parsed_data: dict, file_path: str = None, root: str = None):
        """Add one file's functions and classes. Call resolve_calls() after the last file."""
        module = self._module_name(file_path, root)

        # Re-building a changed file: drop its old nodes first so nothing stale remains.
        old = [n for n, d in self.graph.nodes(data=True) if d.get("module") == module]
        self.graph.remove_nodes_from(old)

        for func in parsed_data.get("functions", []):
            qualname = func.get("qualname", func["name"])
            self.graph.add_node(
                f"{module}::{qualname}",
                type="function",
                name=func["name"],
                qualname=qualname,
                class_name=func.get("class_name"),
                module=module,
                file_path=file_path,
                docstring=func.get("docstring", ""),
                params=func.get("params", ""),
                start_line=func.get("start_line"),
                end_line=func.get("end_line"),
                raw_calls=[],
            )

        for cls in parsed_data.get("classes", []):
            self.graph.add_node(
                f"{module}::{cls['name']}",
                type="class",
                name=cls["name"],
                qualname=cls["name"],
                module=module,
                file_path=file_path,
                start_line=cls.get("start_line"),
                bases=[],
            )

        for child, parent in parsed_data.get("inheritance", []):
            node = f"{module}::{child}"
            if self.graph.has_node(node):
                self.graph.nodes[node]["bases"].append(parent)

        for call in parsed_data.get("calls", []):
            if isinstance(call, dict):
                caller, callee, receiver = call["caller"], call["callee"], call.get("receiver")
            else:  # old (caller, callee) format
                (caller, callee), receiver = call, None
            node = f"{module}::{caller}"
            if self.graph.has_node(node):
                self.graph.nodes[node]["raw_calls"].append([callee, receiver])

    def _index(self):
        """Lookup tables used to resolve names to node IDs."""
        idx = {
            "top": {},                              # (module, name) -> top-level function or class
            "top_by_name": defaultdict(list),       # name -> top-level functions and classes
            "methods": {},                          # (module, class, method) -> node
            "methods_by_name": defaultdict(list),   # method name -> nodes
            "classes_by_name": defaultdict(list),   # class name -> nodes
            "module_by_stem": {},                   # "sessions" -> "sessions.py"
        }
        for n, d in self.graph.nodes(data=True):
            module = d.get("module")
            idx["module_by_stem"][Path(module or "").stem] = module
            if d.get("type") == "class":
                idx["classes_by_name"][d["name"]].append(n)
                idx["top"][(module, d["name"])] = n
                idx["top_by_name"][d["name"]].append(n)
            elif d.get("type") == "function":
                if d.get("class_name"):
                    idx["methods"][(module, d["class_name"], d["name"])] = n
                    idx["methods_by_name"][d["name"]].append(n)
                elif "." not in d["qualname"]:
                    idx["top"][(module, d["name"])] = n
                    idx["top_by_name"][d["name"]].append(n)
        return idx

    def _resolve_class(self, idx, module, name):
        """Find the class node a name refers to (same file first, then a unique match)."""
        short = name.split(".")[-1]
        if (module, short) in idx["top"] and self.graph.nodes[idx["top"][(module, short)]]["type"] == "class":
            return idx["top"][(module, short)]
        candidates = idx["classes_by_name"].get(short, [])
        return candidates[0] if len(candidates) == 1 else None

    def _ancestors(self, cls_node):
        return [p for p in nx.descendants(self._inherit_view(), cls_node)]

    def _descendants(self, cls_node):
        return [c for c in nx.ancestors(self._inherit_view(), cls_node)]

    def _inherit_view(self):
        return nx.subgraph_view(self.graph, filter_edge=lambda u, v: self.graph[u][v].get("relation") == "inherits")

    def _find_method(self, idx, cls_node, method):
        """Look for `method` in a class, then in its parent classes."""
        for c in [cls_node] + self._ancestors(cls_node):
            d = self.graph.nodes[c]
            hit = idx["methods"].get((d["module"], d["name"], method))
            if hit:
                return hit
        return None

    def _resolve(self, idx, caller, callee, receiver):
        """Return (targets, certain) for one raw call made inside `caller`."""
        d = self.graph.nodes[caller]
        module = d["module"]

        if receiver in ("self", "cls") and d.get("class_name"):
            cls_node = self._resolve_class(idx, module, d["class_name"])
            if cls_node:
                hit = self._find_method(idx, cls_node, callee)
                # A subclass may override the method, so self.send() in a mixin can
                # really run the subclass's send(): those are possible, not certain.
                overrides = [idx["methods"].get((self.graph.nodes[s]["module"], self.graph.nodes[s]["name"], callee))
                             for s in self._descendants(cls_node)]
                overrides = [o for o in overrides if o and o != hit]
                if hit:
                    return [(hit, True)] + [(o, False) for o in overrides]
                if overrides:
                    return [(o, False) for o in overrides]
            return [(m, False) for m in idx["methods_by_name"].get(callee, [])]

        if receiver is None:                                   # foo()
            if (module, callee) in idx["top"]:
                return [(idx["top"][(module, callee)], True)]
            candidates = idx["top_by_name"].get(callee, [])
            if len(candidates) == 1:
                return [(candidates[0], True)]
            return [(c, False) for c in candidates]              # none -> built-in/external, dropped

        stem_module = idx["module_by_stem"].get(receiver)     # sessions.Session()
        if stem_module and (stem_module, callee) in idx["top"]:
            return [(idx["top"][(stem_module, callee)], True)]

        # obj.method(): we can't know obj's type, so every method with that name is possible.
        return [(m, False) for m in idx["methods_by_name"].get(callee, [])]

    def resolve_calls(self):
        """Turn the raw calls and base-class names stored on nodes into graph edges."""
        self.graph.remove_edges_from([(u, v) for u, v, r in self.graph.edges(data="relation")
                                      if r in ("calls", "inherits")])
        idx = self._index()

        for n, d in list(self.graph.nodes(data=True)):
            if d.get("type") == "class":
                for base in d.get("bases", []):
                    parent = self._resolve_class(idx, d["module"], base)
                    if parent and parent != n:
                        self.graph.add_edge(n, parent, relation="inherits")

        for n, d in list(self.graph.nodes(data=True)):
            for callee, receiver in d.get("raw_calls", []):
                for target, certain in self._resolve(idx, n, callee, receiver):
                    if self.graph.has_edge(n, target):
                        self.graph[n][target]["certain"] |= certain
                    else:
                        self.graph.add_edge(n, target, relation="calls", certain=certain)

    # ---------- querying ----------

    def find_nodes(self, name: str) -> list[str]:
        """Accept 'send', 'Session.send' or 'sessions.py::Session.send'."""
        if self.graph.has_node(name):
            return [name]
        return sorted(
            n for n, d in self.graph.nodes(data=True)
            if d.get("qualname") == name or d.get("name") == name
            or (d.get("qualname") or "").endswith("." + name)
        )

    def _neighbours(self, name, incoming):
        out = {}
        for node in self.find_nodes(name):
            edges = self.graph.in_edges(node, data=True) if incoming else self.graph.out_edges(node, data=True)
            certain, uncertain = [], []
            for u, v, data in edges:
                if data.get("relation") != "calls":
                    continue
                other = u if incoming else v
                (certain if data.get("certain") else uncertain).append(other)
            out[node] = {"certain": sorted(certain), "uncertain": sorted(uncertain)}
        return out

    def who_calls(self, function_name: str) -> dict:
        """Callers of every function matching the name, split into certain and uncertain."""
        return self._neighbours(function_name, incoming=True)

    def called_by(self, function_name: str) -> dict:
        """Functions called by every function matching the name, split into certain and uncertain."""
        return self._neighbours(function_name, incoming=False)

    # ---------- saving ----------

    def save_graph(self, path: str):
        data = json_graph.node_link_data(self.graph)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    def load_graph(self, path: str):
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        self.graph = json_graph.node_link_graph(data)
