
import os
import json
from codemind.retriever import CodeRetriever

def test_retriever():
    # Setup paths
    code_root = "/tmp/opencode/codemind/tests"
    file_path = "/tmp/opencode/codemind/tests/sample_code.py"
    
    # Simulated data from extractor
    parsed_results = {
        file_path: {
            "functions": [
                {"name": "method_a", "start_line": 7, "end_line": 9},
                {"name": "helper", "start_line": 11, "end_line": 12},
                {"name": "top_level_func", "start_line": 14, "end_line": 16}
            ]
        }
    }
    
    retriever = CodeRetriever(db_path="/tmp/opencode/codemind/chroma_db_test")
    
    print("Indexing codebase...")
    retriever.index_codebase(parsed_results, code_root)
    
    print("\nSearching for 'child class method'...")
    results = retriever.search("child class method", top_k=2)
    
    for r in results:
        print(f"Match: {r['metadata']['name']} (Distance: {r['distance']:.4f})")
        print(f"Code:\n{r['content']}")

if __name__ == "__main__":
    # We won't run this here as dependencies might still be installing
    # but the script is ready for the user.
    print("Verification script ready.")
