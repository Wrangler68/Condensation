# Sources and reuse

## Attached papers

- Xie, She, Xu, Liang & Li (2020). *Mixed dropwise-filmwise condensation heat transfer on biphilic surface*. [DOI](https://doi.org/10.1016/j.ijheatmasstransfer.2019.119273).
- Croce & Suzzi (2024). *Optimization of Dropwise Condensation of Steam over Hybrid Hydrophobic-Hydrophilic Surfaces via Enhanced Statistically Based Heat Transfer Modelization*. [DOI](https://doi.org/10.3390/en17112742).
- Lee, Lee & Lee (2020). *Improved humid air condensation heat transfer through promoting condensate drainage on vertically stripe patterned bi-philic surfaces*. [DOI](https://doi.org/10.1016/j.ijheatmasstransfer.2020.120206).

The source PDFs remain local and are ignored by Git. Approximate model-line readings and cited scientific formulas are included; full paper text and figures are not redistributed.

## Supporting models

- [Kim & Kim 2011](https://doi.org/10.1115/1.4003742): single-drop resistances and population balance.
- [Liu & Cheng 2015, Part I](https://doi.org/10.1016/j.ijheatmasstransfer.2014.11.009) and [Part II](https://doi.org/10.1016/j.ijheatmasstransfer.2014.11.008): coating-dependent nucleation and population density.
- [Peng et al. 2014](https://doi.org/10.1016/j.ijheatmasstransfer.2014.05.052): hybrid DWC/FWC model.
- Peng et al. 2015, IJHMT 83, 27-38: common steam experimental benchmark cited by Xie and Croce. Comparisons against the two papers are not independent experimental validation datasets.
- [Croce & Suzzi 2023](https://air.uniud.it/handle/11390/1269787): individual-droplet simulation background.
- [Suzzi & Croce 2024 companion paper](https://doi.org/10.1088/1742-6596/2766/1/012143): coating and revised populations.

## Public code examined

- [JSablowski/DWCmod](https://github.com/JSablowski/DWCmod), MIT, revision `b18786ffc7d824e42407137c56c7c609d5d4cd75`. Used as an independently executed Kim-Kim numerical check, not vendored. `scripts/check_dwcmod.py` records the exact revision and comparison. Its pressure inputs are mbar and nucleation density uses 1e9/m2, so unit conversion is explicit.
- [CalebBell/ht](https://github.com/CalebBell/ht) and [condensation documentation](https://ht.readthedocs.io/en/latest/ht.condensation.html): Nusselt correlation reference.
- [CoolProp](https://github.com/CoolProp/CoolProp) and [humid-air documentation](https://coolprop.org/fluid_properties/HumidAir.html): optional property backend; not differentiated.
- [MahdiNabil/CFD-PC](https://github.com/MahdiNabil/CFD-PC): related OpenFOAM phase-change work, not a dependency.
- [HIPS/autograd](https://github.com/HIPS/autograd): differentiable NumPy and custom primitive derivatives.
- [marimo documentation](https://docs.marimo.io/guides/working_with_data/plotting/): reactive Plotly interface.

No verified public repository implementing the exact three attached papers was found in the planning search. No upstream solver is claimed to be author code for these papers.
