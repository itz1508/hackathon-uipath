"""Trace exactly where AMBIGUOUS_IMPORT disappears."""
import sys, os, ast
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pathlib import Path
from scanner import (
    scan_target,
    _should_exclude,
    _validate_imports,
    _check_import,
    STDLIB_MODULES,
    DEFAULT_EXCLUDE_PATTERNS,
)

TARGET = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "tests", "fixtures", "fixture-demo-split")
target = Path(TARGET).resolve()

print("=" * 70)
print("STAGE 1: Was the file enumerated by the scanner?")
print("=" * 70)
all_py_files = list(target.rglob("*.py"))
print(f"All .py files found in target: {len(all_py_files)}")
for f in all_py_files:
    rel = str(f.relative_to(target))
    excluded = _should_exclude(rel, DEFAULT_EXCLUDE_PATTERNS)
    print(f"  {rel} | excluded={excluded}")

ambiguous_file = target / "ambiguous_imports.py"
print(f"\nambiguous_imports.py exists: {ambiguous_file.exists()}")
print(f"ambiguous_imports.py excluded: {_should_exclude(str(ambiguous_file.relative_to(target)), DEFAULT_EXCLUDE_PATTERNS)}")

print()
print("=" * 70)
print("STAGE 2: Was the file passed to import-validation?")
print("=" * 70)
# Filter like scanner does
py_files = [f for f in all_py_files if not _should_exclude(str(f.relative_to(target)), DEFAULT_EXCLUDE_PATTERNS)]
print(f"Files passed to import-validation: {len(py_files)}")
for f in py_files:
    print(f"  {f.relative_to(target)}")

ambiguous_in_list = ambiguous_file in py_files
print(f"\nambiguous_imports.py in validation list: {ambiguous_in_list}")

print()
print("=" * 70)
print("STAGE 3: What raw import-validation output was produced?")
print("=" * 70)
# Run import validation manually
req_file = target / "requirements.txt"
# Collect local modules like scanner does
local_modules = set()
for pf in py_files:
    rel = pf.relative_to(target)
    local_modules.add(rel.stem)
    for part in rel.parts[:-1]:
        local_modules.add(part)
print(f"Local modules detected: {sorted(local_modules)}")

# Collect declared deps
import re
declared_deps = set()
if req_file.exists():
    for line in req_file.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#"):
            match = re.match(r"^([a-zA-Z0-9_.-]+)", line)
            if match:
                declared_deps.add(match.group(1).lower().replace("-", "_"))
print(f"Declared deps: {sorted(declared_deps)}")

# Now trace imports from ambiguous_imports.py specifically
print(f"\nParsing ambiguous_imports.py:")
source = ambiguous_file.read_text(encoding="utf-8")
tree = ast.parse(source, filename="ambiguous_imports.py")

imports_found = []
for node in ast.walk(tree):
    if isinstance(node, ast.Import):
        for alias in node.names:
            imports_found.append(("import", alias.name, node.lineno))
    elif isinstance(node, ast.ImportFrom):
        if node.module and node.level == 0:
            imports_found.append(("from", node.module, node.lineno))

print(f"Imports found in AST: {len(imports_found)}")
for kind, name, line in imports_found:
    print(f"  {kind} {name} (line {line})")

# Now trace what _check_import does for each
print(f"\nTracing _check_import for each:")
from models import Finding, FindingCategory, Severity

findings_produced = []

for kind, module_name, line in imports_found:
    top_level = module_name.split(".")[0]
    top_lower = top_level.lower().replace("-", "_")
    
    print(f"\n  Module: {module_name}")
    print(f"    top_level: {top_level}")
    print(f"    top_lower: {top_lower}")
    print(f"    in STDLIB_MODULES: {top_lower in STDLIB_MODULES}")
    print(f"    in declared_deps: {top_lower in declared_deps}")
    print(f"    in local_modules: {top_level in local_modules or top_lower in local_modules}")
    
    # Check if file exists
    module_path = target / module_name.replace(".", "/")
    exists_as_dir = module_path.exists()
    exists_as_file = (target / f"{top_level}.py").exists()
    print(f"    module_path exists: {exists_as_dir}")
    print(f"    {top_level}.py exists: {exists_as_file}")
    
    # THE KEY CHECK: local_modules includes the stem of every .py file
    # Does "generated_client" or "internal_service_sdk" appear as a local module?
    print(f"    '{top_level}' in local_modules check: {top_level in local_modules}")
    print(f"    '{top_lower}' in local_modules check: {top_lower in local_modules}")

print()
print("=" * 70)
print("STAGE 4: ROOT CAUSE IDENTIFIED")
print("=" * 70)
print()
print("The scanner collects local_modules from the STEMS of all .py files:")
print(f"  local_modules = {sorted(local_modules)}")
print()
# Check if ambiguous_imports itself contributes module names
print("Files contributing to local_modules:")
for pf in py_files:
    rel = pf.relative_to(target)
    print(f"  {rel} → stem='{rel.stem}'")
print()

# The answer
if "generated_client" in local_modules:
    print("ANSWER: 'generated_client' IS in local_modules because generated_client.py... wait no")
    print("  Actually let me check: does generated_client.py exist in the fixture?")
    print(f"  generated_client.py exists: {(target / 'generated_client.py').exists()}")
else:
    print("ANSWER: 'generated_client' is NOT in local_modules")
    print("  But the scanner still checks: (target / f'{top_level}.py').exists()")
    print(f"  (target / 'generated_client.py').exists() = {(target / 'generated_client.py').exists()}")
    print(f"  (target / 'internal_service_sdk.py').exists() = {(target / 'internal_service_sdk.py').exists()}")

print()
print("So the _check_import function should reach the 'Not found' branch.")
print("Let me run the actual _validate_imports and capture its output:")
print()

# Run the actual function
record, raw_findings = _validate_imports(target, py_files, req_file)
print(f"import-validation exit_code: {record.exit_code}")
print(f"import-validation findings count: {len(raw_findings)}")
for f in raw_findings:
    print(f"  {f.finding_id} [{f.severity}] {f.category}")
    print(f"    file: {f.file}")
    print(f"    root_cause: {f.root_cause}")
    print(f"    root_cause_confirmed: {f.root_cause_confirmed}")
    print(f"    missing_information: {f.missing_information}")
    print(f"    affected_component: {f.affected_component}")
