# JooYoup HeatTransfer

Interactive **marimo / NumPy / SciPy / Plotly / Autograd** implementations of three reduced models for condensation on biphilic surfaces.

| Notebook | What it explores |
|---|---|
| `notebooks/01_xie2020.py` | Droplet suction/sliding, spatially averaged dropwise flux, and coupled film drainage |
| `notebooks/02_croce2024.py` | Coating-dependent nucleation, drop populations, rivulet flow and flooding |
| `notebooks/03_lee2020.py` | Humid-air energy balance and four-hour condensate recovery |
| `notebooks/04_compare_optimize.py` | Feasibility maps, implicit Autograd sensitivities and constrained geometry searches |

## Run

Python 3.12 and [uv](https://docs.astral.sh/uv/) are required. From this directory:

```sh
uv sync --extra dev --extra properties
uv run marimo run notebooks
```

Open the local address printed by marimo. To edit a notebook:

```sh
uv run marimo edit notebooks/01_xie2020.py
```

Alternatively, install into an existing uv virtual environment with `uv pip install -e ".[dev,properties]"`. CoolProp is optional; the default models use explicit fixed saturation properties. If a restricted Windows environment cannot access the default uv cache, set `UV_CACHE_DIR` to a writable local directory (for example `.uv-cache`).

## Scientific status

The equations are implemented, numerical checks pass, and all four notebooks execute. **This is not a claim of complete experimental validation.** Read [the equation ledger](docs/equation_ledger.md) and [validation report](docs/validation.md) before interpreting predictions.

- Xie's printed Eq. (11) has a liquid-resistance prefactor inconsistent with the baseline and published curves. Default `convention="kim"` restores the Kim–Kim form; `convention="xie"` exposes the printed form.
- Croce Eqs. (8) and (13) contain apparent omissions. The implementation documents and tests the derived corrections. The pure-DWC Fig. 7a still differs materially from the paper; this remains unresolved. Optimization therefore gives exploratory model optima.
- Lee Eq. (6) is treated as **mass collected in four hours**, following the figure axes. Measured, paper-theoretical and independently computed film baselines are distinct selectable options.
- The steam-model disk radius is an explicit **10 mm working assumption**. The attached model sections define R but do not establish its value. Lee's 40 mm square specimen is specified in its paper.
- Three manually read points per selected **published model curve** are included as approximate figure checks. They are not original experimental measurements. Detailed experimental digitization, full parameter-map reproduction, and reconciliation of Croce Fig. 7a remain future validation work.
- Flooded Croce geometries return `valid=False` and undefined total flux. Xie's uniform-film model has no flooding criterion. Humid-air recovery is not compared numerically with pure-steam heat flux.

## Numerical design

Pure functions and immutable inputs use SI units. Reference computations use SciPy quadrature and bracketed roots. Autograd computations use fixed-node quadrature and first-order implicit derivatives of nucleation and film roots. The smooth sensitivity/gradient optimization example is a **rectangular plate extension**: disk stripe counts are discrete and cannot be treated as smooth variables.

JSON downloads include parameters, numerical settings, model convention and package versions. No source PDFs or extracted full paper text are redistributed.

## Reproduce checks

```sh
uv run --extra dev pytest -q
uv run --extra dev ruff check src tests scripts
uv run marimo check --strict notebooks/01_xie2020.py notebooks/02_croce2024.py notebooks/03_lee2020.py notebooks/04_compare_optimize.py
uv run python scripts/validate.py
uv run python scripts/reproduce.py --paper all
uv run --extra properties python scripts/check_dwcmod.py
uv run marimo export html notebooks/01_xie2020.py -o output/xie.html
```

`scripts/validate.py` writes numerical results and optimization checks to `output/validation.json`. `scripts/reproduce.py` generates eight paper-oriented Plotly studies and their JSON data under `output/figures` (coating, widths, departure modes, nucleation, flooding boundary, and curve checks). Those sweeps are model studies, not a declaration of exact agreement with every published figure. The optional DWCmod comparison downloads a reviewed, pinned MIT-licensed upstream revision into ignored `tmp/`, then compares matched inputs. See [references](docs/references.md).

## Repository branch

`HeatTransfer` is an independent orphan branch. It contains only this implementation and its documentation, without inheriting the existing repository's unrelated project history.
