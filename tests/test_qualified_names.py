"""Tests for qualified names and certain/uncertain call resolution.

Run with:  pytest tests/test_qualified_names.py
"""
from codemind.extractor import CodeExtractor
from codemind.graph_builder import GraphBuilder

SAMPLE = '''
class Base:
    def send(self, x):
        pass

class Adapter(Base):
    def send(self, x):
        return helper(x)

class Session:
    def send(self, req):
        adapter = self.get_adapter()
        return adapter.send(req)

    def get_adapter(self):
        return Adapter()

    def request(self, req):
        return self.send(req)

def helper(x):
    return len(x)
'''


def build(tmp_path):
    src = tmp_path / "sample.py"
    src.write_text(SAMPLE)
    builder = GraphBuilder()
    builder.build_graph(CodeExtractor().parse_file(str(src)), file_path=str(src), root=str(tmp_path))
    builder.resolve_calls()
    return builder


def test_same_short_name_gives_separate_nodes(tmp_path):
    builder = build(tmp_path)
    assert builder.find_nodes("send") == [
        "sample.py::Adapter.send", "sample.py::Base.send", "sample.py::Session.send"]


def test_self_call_is_certain(tmp_path):
    builder = build(tmp_path)
    result = builder.who_calls("Session.send")["sample.py::Session.send"]
    assert result["certain"] == ["sample.py::Session.request"]


def test_unknown_receiver_is_uncertain_and_lists_every_candidate(tmp_path):
    builder = build(tmp_path)
    result = builder.who_calls("Adapter.send")["sample.py::Adapter.send"]
    assert result["certain"] == []
    assert result["uncertain"] == ["sample.py::Session.send"]


def test_bare_calls_resolve_and_builtins_are_dropped(tmp_path):
    builder = build(tmp_path)
    callees = builder.called_by("Adapter.send")["sample.py::Adapter.send"]
    assert callees["certain"] == ["sample.py::helper"]           # helper() resolved
    assert not builder.find_nodes("len")                         # built-in len() not added


def test_class_instantiation_and_inheritance(tmp_path):
    builder = build(tmp_path)
    assert "sample.py::Adapter" in builder.called_by("Session.get_adapter")["sample.py::Session.get_adapter"]["certain"]
    assert builder.graph.has_edge("sample.py::Adapter", "sample.py::Base")
