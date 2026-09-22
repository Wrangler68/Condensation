# HeatTransfer review notes

Notes from the review of `HeatTransfer.py` on the `HeatTransfer` branch. The three source PDFs are in the repository root. All 17 embedded numerical checks still pass. Separate reads of Xie (2020), Croce (2024), and Lee (2020) found no new formula that the code implements incorrectly.

## Serious corrections

These change the numerical result relative to a literal reading of a misprinted equation. They were already in the notebook and were checked against the papers. None was removed.

- **Xie Eq. 11.** The printed liquid resistance contains an extra \(\pi\). The default `kim` option uses the Kim–Kim resistance. The `xie` option keeps the printed denominator and a growth law consistent with it. The printed interface term \((1+\cos\theta)/(2h_i)\) is the same as \(\sin^2\theta/[2h_i(1-\cos\theta)]\).
- **Croce Eq. 8.** The printed population formula omits the exponential, which would force \(n(r_e)=0\). The code integrates Eq. 7, matching printed Eq. 11.
- **Croce Eq. 13.** The printed \(B\) omits \(\alpha_i\) in the second term. That term is then a fraction of a metre. Restoring \(\alpha_i\) follows Eq. 9 and keeps \(B\) on the scale of the coating term.
- **Croce rivulet factor.** The printed algebraic \(F_\theta\) is \(0/0\) as the contact angle goes to 0. Quadrature gives \(F(0)=16/35\), matches the printed expression at finite angle, and recovers the flooding flow in Eq. 25.
- **Croce Fig. 7a is not fitted.** The model stays about 27–39% above the sampled published curve at 2, 4, and 6 K, with \(r_{\max}\) fixed at 1.25 mm. Turning off radius-dependent sweeping changes that flux by only about 26 kW/m², so it does not explain the gap. Eq. 28 itself gives a departure radius of about 1.26 mm.

## Corrections made in this review

- The equation section was prose in wide tables. It is now display mathematics. Inline math in marimo must use `\(...\)`; `$...$` with subscripts does not render.
- Plot legends sat on the axis titles, the heatmap scale was tight against the frame, and the stripe drawing was stretched. Legends sit below the axes, the color bar has room, and the stripes keep a square scale.
- Duplicate “Numerical verification” and “Extended paper figure studies” headings were removed. The app uses the wide layout.
- **Lee’s 0.355 g/h line is not this energy balance.** With the recorded properties the balance gives about **0.393 g/h** at a 5 °C wall and **0.245 g/h** at 9 °C. It passes through 0.355 g/h near 6.1 °C. Fig. 6 labels a theory curve at 9 °C and quotes 0.355 g/h. That quoted slope stays a separate baseline (`paper_theory`). The formula was not changed to hit 0.355.
- The three papers had been ignored by git. They are now tracked: `Xie-2020-Mixed dropwise-filmwise condensation.pdf`, `Croce-2024-Optimization-of-dropwise-condensati.pdf`, and `Lee-2020-Improved humid air condensation heat.pdf`.

## Left as published limitations

- Disk radius 10 mm is still an assumption. The papers define \(R\) and do not state this value in the sections that were checked.
- Xie samples the right edge of each spatial cell. The notebook uses midpoint cells. On a 0.2 mm stripe the difference is small.
- Lee’s four-hour dropwise fit is an empirical reconstruction of that experiment, not a general mass-transfer law.

## Working notes

These are about the tools, not the condensation models.

- **Marimo math.** `mo.md` runs `cleandoc`, so an indented triple-quoted string is fine. Every bare expression in a cell is shown, so a heading written twice appears twice. `$r_{c}$` is eaten by Markdown emphasis. Use `\(...\)` inline and `\[...\]` for display. Both work inside tables. Long display math needs `overflow-x: auto` on `.katex-display` or it spills on a phone.
- **Marimo figures.** A horizontal legend with `y` below the plot overlaps the axis title. Put the legend at the bottom of the figure container and reserve bottom margin by how many legend rows you expect. A heatmap color bar needs on the order of 100 px of right margin. A stripe schematic without `scaleanchor="x"` is stretched to the chart box. Pass `displayModeBar: "hover"` through `mo.ui.plotly`, or the mode bar sits on the title.
- **Browser checks.** `page.wait_for_selector("text=...")` matches the hidden document title. Wait for a visible `h1`. Plot titles in SVG can share words with later prose, so a text search can scroll to the wrong place. KaTeX inside the marimo page is not visible to `document.querySelector(".katex")` from the top document; a screenshot is the check that works.
- **This machine.** The repository’s `.git` is owned by another Windows account, so git refuses to run until you pass `-c safe.directory=C:/Users/carlo/Documents/Projects/JooYoupHeatTransfer`. Do not set that globally. PowerShell has no `&&`. Write commit messages to a file and use `git commit -F`. Port 8765 on this tree was a plain directory listing, not the notebook. Serve the app with `uv run --with marimo==0.24.2 marimo run --sandbox --headless --no-token --port <free-port> HeatTransfer.py`. `uv run HeatTransfer.py --self-test` runs the 17 checks.
