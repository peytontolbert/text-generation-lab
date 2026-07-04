import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPT_DIR))

from program_state_call_graph_extractor import extract_python_call_graph
from program_state_data_control_flow_extractor import extract_python_data_control_flow
from program_state_type_signature_extractor import extract_python_type_signatures


SAMPLE = '\nfrom pathlib import Path\n\nclass Greeter:\n    def hello(self, name: str) -> str:\n        message = "hi " + name\n        if name:\n            return message\n        return "hi"\n\ndef main(path: Path) -> str:\n    greeter = Greeter()\n    return greeter.hello(str(path))\n'


def test_type_signature_extractor_finds_annotations_and_opaque_ids():
    packet = extract_python_type_signatures(SAMPLE, row_id="r1", path="sample.py")
    assert packet.failures == []
    names = {signature["qualified_name"]: signature for signature in packet.signatures}
    assert names["Greeter::hello"]["signature"]["returns"] == "str"
    assert names["main"]["signature"]["args"][0]["annotation"] == "Path"
    assert packet.edges
    assert all("Greeter" not in signature["signature_id"] for signature in packet.signatures)


def test_call_graph_extractor_records_callsite_edges():
    packet = extract_python_call_graph(SAMPLE, row_id="r1", path="sample.py")
    assert packet.failures == []
    names = {node["name"] for node in packet.call_nodes}
    assert "Greeter" in names
    assert "greeter.hello" in names
    assert "str" in names
    edge_types = {edge["edge_type"] for edge in packet.edges}
    assert "contains_callsite" in edge_types
    assert "calls_reference" in edge_types


def test_data_control_flow_extractor_records_def_use_and_control():
    packet = extract_python_data_control_flow(SAMPLE, row_id="r1", path="sample.py")
    assert packet.failures == []
    data_names = {node["name"] for node in packet.data_nodes}
    control_kinds = {node["control_kind"] for node in packet.control_nodes}
    assert "message" in data_names
    assert "name" in data_names
    assert "function_entry" in control_kinds
    assert "assign" in control_kinds
    assert "if" in control_kinds
    assert "return" in control_kinds
    assert any(edge["edge_type"] == "data_depends_on" for edge in packet.edges)
    assert any(edge["edge_type"] == "control_next" for edge in packet.edges)


def test_semantic_flow_extractors_return_syntax_error_packets():
    bad = "def broken(:\n"
    assert extract_python_type_signatures(bad).failures[0].startswith("syntax_error")
    assert extract_python_call_graph(bad).failures[0].startswith("syntax_error")
    assert extract_python_data_control_flow(bad).failures[0].startswith("syntax_error")
