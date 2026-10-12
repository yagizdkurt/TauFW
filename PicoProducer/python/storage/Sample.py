# DEPRECATED LOCATION -- kept only so existing sample catalogs keep working.
"""Compatibility re-export of the sample classes, which moved to TauFW.PicoProducer.datasets (2026).

Sample catalogs used to start with
  from TauFW.PicoProducer.storage.Sample import MC as M, Data as D
New catalogs should use
  from TauFW.PicoProducer.datasets import MC as M, Data as D
This is the only compatibility shim of the PicoProducer restructuring; see docs/Refactor-2025.md.
"""
from TauFW.PicoProducer.datasets.sample import Sample, Data, MC, Embdedded

__all__ = ['Sample', 'Data', 'MC', 'Embdedded']
