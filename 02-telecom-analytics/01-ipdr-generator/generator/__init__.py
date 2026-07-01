"""IPDR generator package — synthetic telecom traffic records."""

from .ipdr_generator import IPDRGenerator, generate_batch
from .schema import IPDRRecord

__all__ = ["IPDRGenerator", "IPDRRecord", "generate_batch"]
