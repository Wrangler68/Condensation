# JooYoup HeatTransfer

[Open the interactive app on GitHub Pages](https://chetools.github.io/jooyoup/) · [Open in molab](https://molab.marimo.io/github/chetools/jooyoup/blob/HeatTransfer/HeatTransfer.py) · [Download the notebook](https://raw.githubusercontent.com/chetools/jooyoup/HeatTransfer/HeatTransfer.py)

One standalone **marimo / NumPy / SciPy / Plotly / Autograd** notebook, with sections for Xie (2020), Croce (2024), Lee (2020), design optimization, numerical verification, extended figure studies, equations, and references.

- `HeatTransfer.py` contains every model, constant, preset, curve reading, numerical test, and reference. Its PEP 723 metadata installs dependencies in molab or a uv sandbox. No local modules or data files are needed.
- `HeatTransfer.html` contains the same executable notebook for WebAssembly. It loads the versioned marimo frontend and Pyodide/packages from CDNs; it needs an internet connection and HTTP(S) hosting, not a Python server. It is a single HTML file with no adjacent assets directory, but is not an offline bundle.

Run locally with [uv](https://docs.astral.sh/uv/):

```sh
uv run --with marimo==0.24.2 marimo edit --sandbox HeatTransfer.py
uv run HeatTransfer.py --self-test
```

To serve the included HTML locally:

```sh
uv run --no-project python -m http.server 8000
```

Open `http://localhost:8000/HeatTransfer.html`. The sidebar outline navigates between sections. Forms apply changes on submission; longer searches and figure studies run on demand. JSON downloads include assumptions and runtime package versions.

The GitHub Actions workflow checks the notebook, runs its 17 embedded numerical checks, rebuilds the single HTML, and deploys GitHub Pages on pushes to `HeatTransfer`. The workflow contains the export transformation: asset URLs point to the matching marimo CDN release, with a same-origin blob entry for module workers. Ordinary `marimo export html-wasm` produces an HTML plus assets; the workflow converts that output to the one-file distribution.

Validation: 17 checks passed natively, in an isolated notebook environment, and in browser WebAssembly. Default outputs exactly match the former split implementation. Browser checks exercise reactive inputs, numerical verification and constrained searches. Original supporting evidence is embedded in the notebook. The old split notebooks, package, data, documentation and test scripts have been consolidated and removed; source PDFs remain local and are not published.

Scientific limitations remain explicit: Croce Fig. 7a differs by roughly 27–39%, the 10 mm disk radius is unconfirmed, and Lee's empirical four-hour mass law is restricted to its experimental setting. These are numerically checked model studies, not fully validated design recommendations. The portable notebook uses embedded saturation tables; the prior CoolProp/DWCmod cross-check is retained as recorded evidence.
