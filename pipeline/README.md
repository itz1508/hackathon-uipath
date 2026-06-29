# UiPath Python Hackathon Example

This is a source-only UiPath Python automation project. Generated files stay
outside the final repository until explicitly selected.

## Files UiPath uses

- `uipath.json` declares `main.py:main` as the deployable entrypoint.
- `main.py` defines typed input and output models.
- `pyproject.toml` declares Python and UiPath SDK dependencies.
- `samples/input.json` is a local invocation payload.

## Commands

```powershell
python -m venv .venv
.\.venv\Scripts\python -m pip install -e .
uipath init
uipath run main .\samples\input.json
uipath pack
```

Run `uipath auth` and `uipath publish` only when cloud credentials and the
destination folder are ready. Never commit `.env`.
