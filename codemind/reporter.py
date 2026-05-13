import networkx as nx
from pathlib import Path

class Reporter:
    """Generates comprehensive risk reports in Markdown or HTML."""
    
    def __init__(self, graph_builder):
        self.builder = graph_builder
        self.graph = graph_builder.graph

    def _get_long_functions(self, threshold=100):
        long_funcs = []
        for node, data in self.graph.nodes(data=True):
            if data.get("type") == "function":
                start = data.get("start_line", 0)
                end = data.get("end_line", 0)
                length = end - start
                if length > threshold:
                    long_funcs.append((node, length, data.get("file_path", "unknown")))
        return long_funcs

    def _get_fan_metrics(self, in_threshold=5, out_threshold=10):
        high_fan = []
        for node, data in self.graph.nodes(data=True):
            if data.get("type") == "function":
                fan_in = self.graph.in_degree(node)
                fan_out = self.graph.out_degree(node)
                if fan_in > in_threshold or fan_out > out_threshold:
                    high_fan.append({
                        "name": node,
                        "in": fan_in,
                        "out": fan_out,
                        "file": data.get("file_path", "unknown")
                    })
        return high_fan

    def _get_circular_dependencies(self):
        """Detect cycles at the module (file) level."""
        module_graph = nx.DiGraph()
        for u, v, data in self.graph.edges(data=True):
            if data.get("relation") == "calls":
                file_u = self.graph.nodes[u].get("file_path")
                file_v = self.graph.nodes[v].get("file_path")
                if file_u and file_v and file_u != file_v:
                    module_graph.add_edge(file_u, file_v)
        
        try:
            return list(nx.simple_cycles(module_graph))
        except:
            return []

    def _get_missing_docstrings(self):
        missing = []
        for node, data in self.graph.nodes(data=True):
            if data.get("type") == "function" and not node.startswith("_"):
                if not data.get("docstring"):
                    missing.append((node, data.get("file_path", "unknown")))
        return missing

    def generate_markdown(self):
        long_funcs = self._get_long_functions()
        fan_metrics = self._get_fan_metrics()
        cycles = self._get_circular_dependencies()
        missing_docs = self._get_missing_docstrings()

        md = "# CodeMind Risk Report\n\n"

        # 1. Long Functions
        md += "## 1. Long Functions (>100 lines)\n"
        if long_funcs:
            md += "| Function | Lines | File |\n| --- | --- | --- |\n"
            for name, lines, file in long_funcs:
                md += f"| {name} | {lines} | {file} |\n"
        else:
            md += "✅ No overly long functions detected.\n"
        md += "\n"

        # 2. High Fan-in/Fan-out
        md += "## 2. Complexity Metrics (High Fan-in/Out)\n"
        if fan_metrics:
            md += "| Function | Fan-In (Target) | Fan-Out (Source) | File |\n| --- | --- | --- | --- |\n"
            for item in fan_metrics:
                md += f"| {item['name']} | {item['in']} | {item['out']} | {item['file']} |\n"
        else:
            md += "✅ All functions within complexity thresholds.\n"
        md += "\n"

        # 3. Circular Dependencies
        md += "## 3. Module Circular Dependencies\n"
        if cycles:
            for cycle in cycles:
                md += f"- ⚠️ Cycle detected: `{' -> '.join([Path(f).name for f in cycle])} -> {Path(cycle[0]).name}`\n"
        else:
            md += "✅ No module-level circular dependencies detected.\n"
        md += "\n"

        # 4. Missing Documentation
        md += "## 4. Missing Docstrings (Public Functions)\n"
        if missing_docs:
            md += "| Function | File |\n| --- | --- |\n"
            for name, file in missing_docs:
                md += f"| {name} | {file} |\n"
        else:
            md += "✅ All public functions are documented.\n"
        
        return md

    def generate_html(self):
        md = self.generate_markdown()
        # Minimal conversion (Markdown to basic HTML tags for preview)
        html = f"<html><body>{md.replace('# ', '<h1>').replace('## ', '<h2>').replace('\n', '<br>')}</body></html>"
        return html

    def save_report(self, path, format="markdown"):
        content = self.generate_markdown() if format == "markdown" else self.generate_html()
        with open(path, 'w', encoding='utf-8') as f:
            f.write(content)
        return path
