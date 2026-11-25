from pathlib import Path

from tree_sitter_languages import get_language, get_parser


class CodeExtractor:
    """Uses tree-sitter to extract classes, functions, calls and inheritance from Python files.

    Every function gets a qualified name (`qualname`) such as `Session.send`, so two
    methods called `send` in different classes no longer look identical. Every call
    records its receiver (`self`, `adapter`, ...) so the graph builder can decide
    which `send` was meant.
    """

    def __init__(self, language_name: str = "python"):
        self.language = get_language(language_name)
        self.parser = get_parser(language_name)

    def _get_node_text(self, node, source_code: bytes) -> str:
        return source_code[node.start_byte:node.end_byte].decode("utf-8")

    def _get_docstring(self, node, source_code: bytes) -> str:
        """Extract the docstring if it is the first statement in the body."""
        body = node.child_by_field_name("body")
        if body and body.children:
            first_child = body.children[0]
            if first_child.type == "expression_statement" and first_child.children:
                grandchild = first_child.children[0]
                if grandchild.type == "string":
                    return self._get_node_text(grandchild, source_code).strip('"\'')
        return ""

    def parse_file(self, file_path: str):
        results = {"functions": [], "classes": [], "calls": [], "inheritance": []}
        path = Path(file_path)
        if not path.exists():
            return results

        source_code = path.read_bytes()
        root_node = self.parser.parse(source_code).root_node

        def walk(node, class_stack, func_stack):
            """Visit every node, remembering which class and function we are inside."""
            if node.type == "class_definition":
                class_name = self._get_node_text(node.child_by_field_name("name"), source_code)
                results["classes"].append({"name": class_name, "start_line": node.start_point[0] + 1})
                superclasses = node.child_by_field_name("superclasses")
                if superclasses:
                    for arg in superclasses.children:
                        if arg.type in ("identifier", "attribute"):
                            results["inheritance"].append((class_name, self._get_node_text(arg, source_code)))
                for child in node.children:
                    walk(child, class_stack + [class_name], func_stack)
                return

            if node.type == "function_definition":
                name = self._get_node_text(node.child_by_field_name("name"), source_code)
                # A method's qualified name includes its class: "Session.send".
                # A nested function includes its outer function: "outer.inner".
                owner = func_stack[-1] if func_stack else ".".join(class_stack)
                qualname = f"{owner}.{name}" if owner else name
                params_node = node.child_by_field_name("parameters")
                results["functions"].append({
                    "name": name,
                    "qualname": qualname,
                    "class_name": class_stack[-1] if class_stack and not func_stack else None,
                    "docstring": self._get_docstring(node, source_code),
                    "start_line": node.start_point[0] + 1,
                    "end_line": node.end_point[0] + 1,
                    "params": self._get_node_text(params_node, source_code) if params_node else "()",
                })
                for child in node.children:
                    walk(child, class_stack, func_stack + [qualname])
                return

            if node.type == "call" and func_stack:
                func_node = node.child_by_field_name("function")
                callee, receiver = "", None
                if func_node.type == "identifier":          # foo()
                    callee = self._get_node_text(func_node, source_code)
                elif func_node.type == "attribute":         # something.foo()
                    attr = func_node.child_by_field_name("attribute")
                    obj = func_node.child_by_field_name("object")
                    if attr:
                        callee = self._get_node_text(attr, source_code)
                        receiver = self._get_node_text(obj, source_code) if obj else None
                if callee:
                    results["calls"].append({"caller": func_stack[-1], "callee": callee, "receiver": receiver})

            for child in node.children:
                walk(child, class_stack, func_stack)

        walk(root_node, [], [])
        return results
