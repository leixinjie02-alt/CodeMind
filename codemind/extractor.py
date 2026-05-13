import tree_sitter
from tree_sitter_languages import get_language, get_parser
from pathlib import Path

class CodeExtractor:
    """Uses tree-sitter to extract classes, functions, and relationships."""
    
    def __init__(self, language_name: str = "python"):
        self.language = get_language(language_name)
        self.parser = get_parser(language_name)
        self._set_queries()

    def _set_queries(self):
        """Define tree-sitter queries for Python."""
        # Note: tree-sitter-python fields can vary between versions.
        # We'll use positional matching or more generic patterns where fields fail.
        self.function_query = self.language.query("""
            (function_definition
                name: (identifier) @name
                parameters: (parameters) @params
            ) @func
        """)
        
        # Simplified class query to avoid field name issues
        self.class_query = self.language.query("""
            (class_definition
                name: (identifier) @name
            ) @class
            (class_definition
                name: (identifier)
                superclasses: (argument_list (identifier) @parent)
            ) @class_with_parent
        """)

    def _get_node_text(self, node, source_code: bytes) -> str:
        return source_code[node.start_byte:node.end_byte].decode("utf-8")

    def _get_docstring(self, node, source_code: bytes) -> str:
        """Extract docstring if it's the first statement in the body."""
        body = node.child_by_field_name("body")
        if body and body.children:
            first_child = body.children[0]
            # In some versions it might be an expression_statement
            if first_child.type == "expression_statement":
                grandchild = first_child.children[0]
                if grandchild.type == "string":
                    return self._get_node_text(grandchild, source_code).strip('"\'')
        return ""

    def parse_file(self, file_path: str):
        path = Path(file_path)
        if not path.exists():
            return {"functions": [], "classes": [], "calls": [], "inheritance": []}

        source_code = path.read_bytes()
        tree = self.parser.parse(source_code)
        root_node = tree.root_node

        results = {
            "functions": [],
            "classes": [],
            "calls": [],
            "inheritance": []
        }

        # 1. Extract Functions
        captures = self.function_query.captures(root_node)
        for node, tag in captures:
            if tag == "func":
                name_node = node.child_by_field_name("name")
                name = self._get_node_text(name_node, source_code)
                params_node = node.child_by_field_name("parameters")
                
                func_info = {
                    "name": name,
                    "docstring": self._get_docstring(node, source_code),
                    "start_line": node.start_point[0] + 1,
                    "end_line": node.end_point[0] + 1,
                    "params": self._get_node_text(params_node, source_code)
                }
                results["functions"].append(func_info)

        # 2. Extract Classes & Inheritance
        # We'll use a manual walk for inheritance to be more robust
        def walk_classes(node):
            if node.type == "class_definition":
                name_node = node.child_by_field_name("name")
                class_name = self._get_node_text(name_node, source_code)
                results["classes"].append({"name": class_name})
                
                # Check for inheritance
                superclasses = node.child_by_field_name("superclasses")
                if superclasses:
                    for arg in superclasses.children:
                        if arg.type in ["identifier", "attribute"]:
                            parent_name = self._get_node_text(arg, source_code)
                            results["inheritance"].append((class_name, parent_name))
            
            for child in node.children:
                walk_classes(child)

        walk_classes(root_node)

        # 3. Extract Calls (with Scope Tracking)
        def traverse_calls(node, current_caller=None):
            new_caller = current_caller
            if node.type == "function_definition":
                name_node = node.child_by_field_name("name")
                new_caller = self._get_node_text(name_node, source_code)
            
            if node.type == "call":
                func_node = node.child_by_field_name("function")
                callee = ""
                if func_node.type == "identifier":
                    callee = self._get_node_text(func_node, source_code)
                elif func_node.type == "attribute":
                    # Get the attribute name (the method name)
                    attr_node = func_node.child_by_field_name("attribute")
                    if attr_node:
                        callee = self._get_node_text(attr_node, source_code)
                
                if callee:
                    results["calls"].append((current_caller or "global", callee))

            for child in node.children:
                traverse_calls(child, new_caller)

        traverse_calls(root_node)
        
        return results
