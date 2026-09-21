"""Explicit finite and paper-approximate stripe geometry."""

import numpy as np


def disk_heights(radius, dwc_width, fwc_width):
    """Croce Eq.29 centers, retaining only centers strictly inside the disk.

    Fractional n is floored by the integer loop. This convention is recorded in the ledger.
    """
    pitch = dwc_width + fwc_width
    n = int(np.floor(2 * radius / pitch))
    if n < 1:
        raise ValueError("No full stripe period fits inside the disk")
    k = np.arange(1, n + 1)
    x = pitch * k - dwc_width - fwc_width / 2 - radius
    x = x[np.abs(x) < radius]
    return 2 * np.sqrt(radius**2 - x**2)


def finite_stripes(dwc_width, fwc_width, width=0.04, height=0.04):
    """Start with a DWC stripe at the left edge; clip the last stripe exactly."""
    if min(dwc_width, fwc_width) <= 0 or width <= 0 or height <= 0:
        raise ValueError("Finite hybrid stripes require positive dimensions")
    if width / min(dwc_width, fwc_width) > 100000:
        raise ValueError("Too many stripes")
    position = 0.0
    segments = []
    hydrophilic = 0.0
    while position < width - 1e-14:
        for kind, span in (("DWC", dwc_width), ("FWC", fwc_width)):
            stop = min(position + span, width)
            if stop > position + 1e-14:
                segments.append((position, stop, kind))
                if kind == "FWC":
                    hydrophilic += stop - position
            position = stop
    return {
        "sar": hydrophilic / width,
        "interface_length": (len(segments) - 1) * height,
        "area": width * height,
        "segments": segments,
    }
