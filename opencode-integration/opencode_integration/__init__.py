import os
import sys
from pathlib import Path

_LAAP_ROOT = os.environ.get("LAAP_ROOT", "")
if not _LAAP_ROOT:
    _LAAP_ROOT = str(Path(__file__).resolve().parent.parent.parent)
if _LAAP_ROOT not in sys.path:
    sys.path.insert(0, _LAAP_ROOT)

from opencode_integration.integrator import (
    OpenCodeIntegrator,
    OpenCodeIntegrationConfig,
)

__all__ = ["OpenCodeIntegrator", "OpenCodeIntegrationConfig"]
