# GitHub Copilot Instructions

## Big picture
- The project is a single Streamlit page; all UI lives in [main.py](main.py#L1-L15).
- Inputs come from the sidebar so keep core controls there (the slider for `age` and the text input for `name`).
- Output happens immediately on the page via `st.title`/`st.write`, with the greeting logic shown in `main.py`.

## Key workflows
1. Create/refresh the virtual environment dependencies with `pip install streamlit` inside `.venv`, mirroring the setup mentioned in [README.md](README.md#L1-L5).
2. Activate the environment (for example `source .venv/bin/activate`) before editing or running the app.
3. Run the UI locally with `streamlit run main.py` and preview the sidebar-based controls.

## Code patterns and conventions
- Keep new controls grouped in the sidebar, respecting the short column of settings before the body text.
- Follow the existing pattern of capturing sidebar values (slider + text field) and then conditionally calling `st.write` only once a name is supplied.
- Because the app uses f-strings for display (`f"{name}さん、{age}歳ですね！"`), maintain UTF-8 text directly in the string literals rather than splitting sentences across multiple calls.

## Testing / debugging cues
- Re-run `streamlit run main.py` after every change; Streamlit reloads automatically but note the explicit command to restart the server when you get stuck.
- Check the terminal where Streamlit runs for Python errors; no separate test suite exists yet, so this manual observation is the only feedback loop.

If anything here is unclear or missing (external files, deeper services, etc.), please flag it so we can refine these instructions.