# Setup Guide

No installation is performed by this template. To run validation, an existing Python environment must already provide `jsonschema` with Draft 2020-12 support and `pytest`.

Check availability:

```powershell
python -c "from importlib.metadata import version; print('jsonschema=' + version('jsonschema')); print('pytest=' + version('pytest'))"
```

If either dependency is unavailable, report validation as `not_run`. Do not install it automatically. No UiPath component is required to inspect or validate these template files.
