import json
import xml.etree.ElementTree as ET
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PROJECT = ROOT / "maestro" / "NextFlow-RealCase-Template"
NS = {"bpmn": "http://www.omg.org/spec/BPMN/20100524/MODEL", "uipath": "http://uipath.org/schema/bpmn"}


def process(path):
    return ET.parse(path).getroot().find("bpmn:process", NS)


def test_both_bpmn_processes_have_executable_tasks_and_required_stages():
    required = [
        "01 Scan / Snapshot",
        "02 Analysis / Classification / Recalibration",
        "Build Handoff State",
        "02.5 Build Pre-Simulation Package",
        "03 Simulation Environment",
        "04 Replay / Proof",
        "05 User",
        "06 Explicit",
        "07 Post-Apply Verification",
        "08 Final Result Locked",
    ]
    for name in ["NextFlow-Demo.bpmn", "NextFlow-RealCase.bpmn"]:
        root = process(PROJECT / name)
        assert root is not None
        task_names = "\n".join(element.attrib.get("name", "") for element in list(root))
        for label in required:
            assert label in task_names, (name, label)
        tasks = [element for element in list(root) if element.tag.rsplit("}", 1)[-1].endswith("Task")]
        assert len(tasks) >= 12
        assert all(task.find("bpmn:extensionElements", NS) is not None for task in tasks)


def test_readiness_gateway_contains_all_six_enforced_conditions():
    for name in ["NextFlow-Demo.bpmn", "NextFlow-RealCase.bpmn"]:
        text = (PROJECT / name).read_text(encoding="utf-8")
        for fragment in [
            "simulation_ready == true",
            "required_grader_failures.length == 0",
            "isolation_required == false",
            "reattempt_required == false",
            "confidence_score &gt;= 93.91" if False else "confidence_score >= 93.91",
            "required_dependencies_available == true",
        ]:
            assert fragment in text


def test_real_case_uses_registry_extension_types_and_marks_bindings():
    text = (PROJECT / "NextFlow-RealCase.bpmn").read_text(encoding="utf-8")
    for extension_type in [
        "Orchestrator.StartAgentJob",
        "Orchestrator.StartJob",
        "Orchestrator.ExecuteApiWorkflowAsync",
        "Actions.HITL",
        "BPMN.ScriptTask",
    ]:
        assert extension_type in text
    assert text.count("BIND REQUIRED") >= 7
    assert "__BIND_REQUIRED_" in text


def test_mapping_covers_every_stage_and_labels_binding_requirements():
    mapping = json.loads((ROOT / "cases" / "template" / "mapping.template.json").read_text(encoding="utf-8"))
    assert set(mapping) == {
        "01-scan-snapshot", "02-analysis-recalibration", "02.5-pre-simulation",
        "03-simulation", "04-replay-proof", "05-user-decision",
        "06-apply-relay", "07-post-apply-verification", "08-final-result",
    }
    assert all("implementation_type" in value for value in mapping.values())


def test_entry_points_and_package_descriptor_include_both_processes():
    entries = json.loads((PROJECT / "entry-points.json").read_text(encoding="utf-8"))["entryPoints"]
    files = {entry["filePath"].split("#", 1)[0] for entry in entries}
    assert files == {"/content/NextFlow-Demo.bpmn", "/content/NextFlow-RealCase.bpmn"}
    descriptor = json.loads((PROJECT / "package-descriptor.json").read_text(encoding="utf-8"))["files"]
    assert "NextFlow-Demo.bpmn" in descriptor
    assert "NextFlow-RealCase.bpmn" in descriptor
