import json
from codemind.graph_builder import GraphBuilder

def test_graph():
    # Simulated output from extractor
    data = {
      "functions": [
        {"name": "method_a", "params": "(self, x)", "start_line": 7, "end_line": 9},
        {"name": "helper", "params": "(self)", "start_line": 11, "end_line": 12},
        {"name": "top_level_func", "params": "()", "start_line": 14, "end_line": 16}
      ],
      "classes": [
        {"name": "Parent"},
        {"name": "Child"}
      ],
      "calls": [
        ["method_a", "print"],
        ["method_a", "helper"],
        ["top_level_func", "Child"],
        ["top_level_func", "method_a"]
      ],
      "inheritance": [
        ["Child", "Parent"]
      ]
    }

    builder = GraphBuilder()
    builder.build_graph(data)

    print("Who calls 'method_a'?")
    print(builder.who_calls("method_a"))

    print("\nWhat does 'method_a' call?")
    print(builder.called_by("method_a"))

    save_path = "/tmp/opencode/codemind/tests/graph.json"
    builder.save_graph(save_path)
    print(f"\nGraph saved to {save_path}")

    # Test loading
    new_builder = GraphBuilder()
    new_builder.load_graph(save_path)
    print("\nReloaded graph: 'Child' neighbors:")
    print(list(new_builder.graph.neighbors("Child")))

if __name__ == "__main__":
    test_graph()
