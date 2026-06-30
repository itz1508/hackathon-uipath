"""Create a large fixture with 20+ files and many different issue types."""
import os

FIXTURE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "tests", "fixtures", "fixture-large-demo")
os.makedirs(FIXTURE, exist_ok=True)

# ── FIXABLE: Syntax errors (3 files) ──
for i in range(1, 4):
    with open(os.path.join(FIXTURE, f"syntax_error_{i}.py"), "w", encoding="utf-8") as f:
        f.write(f'"""Syntax error file {i}."""\n\ndef broken_func_{i}(arg1, arg2\n    return arg1 + arg2\n')

# ── FIXABLE: Missing local imports with typos (3 files) ──
# Create the correct modules first
with open(os.path.join(FIXTURE, "utils.py"), "w", encoding="utf-8") as f:
    f.write('"""Utilities."""\n\ndef helper():\n    return "ok"\n')

with open(os.path.join(FIXTURE, "config.py"), "w", encoding="utf-8") as f:
    f.write('"""Config."""\n\nDEFAULT_TIMEOUT = 30\n')

with open(os.path.join(FIXTURE, "models.py"), "w", encoding="utf-8") as f:
    f.write('"""Models."""\n\nclass Item:\n    pass\n')

# Files with typo imports (will resolve as MISSING_IMPORT with similar module)
with open(os.path.join(FIXTURE, "service_a.py"), "w", encoding="utf-8") as f:
    f.write('"""Service A with typo import."""\n\nfrom utlis import helper\n\ndef run_a():\n    return helper()\n')

with open(os.path.join(FIXTURE, "service_b.py"), "w", encoding="utf-8") as f:
    f.write('"""Service B with typo import."""\n\nfrom confg import DEFAULT_TIMEOUT\n\ndef run_b():\n    return DEFAULT_TIMEOUT\n')

with open(os.path.join(FIXTURE, "service_c.py"), "w", encoding="utf-8") as f:
    f.write('"""Service C with typo import."""\n\nfrom modles import Item\n\ndef run_c():\n    return Item()\n')

# ── UNFIXABLE: Ambiguous imports (4 files) ──
with open(os.path.join(FIXTURE, "api_handler.py"), "w", encoding="utf-8") as f:
    f.write('"""API handler with ambiguous generated import."""\n\nfrom generated_api_client import RestClient\n\ndef handle():\n    return RestClient()\n')

with open(os.path.join(FIXTURE, "auth_module.py"), "w", encoding="utf-8") as f:
    f.write('"""Auth with internal SDK."""\n\nfrom internal_auth_provider import TokenService\n\ndef authenticate():\n    return TokenService().get_token()\n')

with open(os.path.join(FIXTURE, "data_layer.py"), "w", encoding="utf-8") as f:
    f.write('"""Data layer with private connector."""\n\nfrom private_db_connector import Connection\n\ndef get_data():\n    return Connection().query("SELECT 1")\n')

with open(os.path.join(FIXTURE, "event_bus.py"), "w", encoding="utf-8") as f:
    f.write('"""Event bus with generated client."""\n\nfrom generated_event_client import EventPublisher\n\ndef publish(event):\n    return EventPublisher().send(event)\n')

# ── FIXABLE: Dependency issues ──
with open(os.path.join(FIXTURE, "requirements.txt"), "w", encoding="utf-8") as f:
    f.write("# Project dependencies\n")
    f.write("flask==99.0.0\n")  # Broken version (fake)
    f.write("sqlalchemy==1.2  # requires sqlalchemy>=2.0\n")  # Version conflict
    f.write("requests>=2.28\n")  # Valid
    f.write("pydantic>=2.0\n")   # Valid

# ── FIXABLE: More missing dependencies ──
with open(os.path.join(FIXTURE, "worker.py"), "w", encoding="utf-8") as f:
    f.write('"""Worker with undeclared deps."""\n\nimport celery\nimport redis\n\ndef run_task():\n    return celery.current_app\n')

with open(os.path.join(FIXTURE, "reporting.py"), "w", encoding="utf-8") as f:
    f.write('"""Reporting with undeclared deps."""\n\nimport pandas\nimport matplotlib\n\ndef generate_report():\n    return pandas.DataFrame()\n')

# ── CLEAN: Working files (5 files) ──
for i in range(1, 6):
    with open(os.path.join(FIXTURE, f"clean_module_{i}.py"), "w", encoding="utf-8") as f:
        f.write(f'"""Clean module {i} — no issues."""\n\ndef function_{i}(x):\n    return x * {i}\n')

# ── Main entry ──
with open(os.path.join(FIXTURE, "main.py"), "w", encoding="utf-8") as f:
    f.write('"""Main entry — imports clean modules."""\n\nfrom clean_module_1 import function_1\nfrom clean_module_2 import function_2\n\ndef main():\n    return function_1(10) + function_2(20)\n')

print(f"Created fixture: {FIXTURE}")
print(f"Files: {len(os.listdir(FIXTURE))}")
for name in sorted(os.listdir(FIXTURE)):
    print(f"  {name}")
