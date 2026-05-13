import json
from codemind.extractor import CodeExtractor

def test():
    extractor = CodeExtractor()
    results = extractor.parse_file("/tmp/opencode/codemind/tests/sample_code.py")
    print(json.dumps(results, indent=2))

if __name__ == "__main__":
    test()
