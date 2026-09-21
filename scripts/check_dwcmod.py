"""Optional independent check against reviewed MIT-licensed DWCmod revision.

Downloads only that pinned source into ignored tmp/. Requires the properties extra.
No upstream source is vendored into the package.
"""

import importlib.util
import json
from pathlib import Path
from urllib.request import urlopen

import numpy as np
from CoolProp.CoolProp import PropsSI

from condensation.populations import flux_components
from condensation.properties import water

REVISION = "b18786ffc7d824e42407137c56c7c609d5d4cd75"
URL = f"https://raw.githubusercontent.com/JSablowski/DWCmod/{REVISION}/DWC_models.py"


def main():
    path = Path("tmp/DWCmod_reference.py")
    path.parent.mkdir(exist_ok=True)
    with urlopen(URL, timeout=30) as response:
        path.write_bytes(response.read())
    spec = importlib.util.spec_from_file_location("dwc_reference", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    p = water(373.15, backend="coolprop")
    pressure = PropsSI("P", "T", 373.15, "Q", 1, "Water") / 100
    results = []
    for dt in (2.0, 6.0, 10.0):
        q, qn, qN, r0, re, rm, *_ = module.KimKim2011(
            p_steam=pressure,
            deltaT_sub=dt,
            Theta=120,
            Theta_a=142,
            Theta_r=102,
            k_coat=0.2,
            delta_coat=3.39e-7 * 0.2,
        )
        components = flux_components(dt, 2 * np.pi / 3, 3.39e-7, p, r0, re, rm, reference=True)
        computed = float(sum(components))
        relative = computed / q - 1
        assert abs(relative) < 1e-4, (dt, q, computed, relative)
        results.append(
            {
                "subcooling_K": dt,
                "upstream_flux": q,
                "implemented_flux": computed,
                "relative_error": relative,
                "rmax_m": rm,
            }
        )
    out = Path("output")
    out.mkdir(exist_ok=True)
    (out / "dwcmod_check.json").write_text(
        json.dumps(
            {"revision": REVISION, "url": URL, "license": "MIT", "results": results}, indent=2
        ),
        encoding="utf-8",
    )
    print(json.dumps(results, indent=2))


if __name__ == "__main__":
    main()
