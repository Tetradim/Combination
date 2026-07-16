"""Integration facade for the Sentinel Chain and Sentinel Iron experiment."""

from .components import COMPONENTS, ComponentPin
from .contracts import AssetClass, ExperimentEnvelope, ExperimentMode, InstrumentRef

__all__ = [
    "AssetClass",
    "COMPONENTS",
    "ComponentPin",
    "ExperimentEnvelope",
    "ExperimentMode",
    "InstrumentRef",
]

__version__ = "0.1.0"
