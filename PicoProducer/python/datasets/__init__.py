"""Datasets: sample definitions and the catalogs that list them.

A Sample is one physics dataset (one or more DAS paths, or files on a storage system) with its data
type, file list and event counts. Catalogs under PicoProducer/samples/ define a list `samples`.

Public API:
  Sample, MC, Data, Embdedded       sample classes for catalogs (`from TauFW.PicoProducer.datasets import MC as M`)
  getsamples(era, channel, ...)     select samples from the catalog configured for an era
  print_no_samples(...)             explain an empty selection
"""
from TauFW.PicoProducer.datasets.sample import Sample, Data, MC, Embdedded
from TauFW.PicoProducer.datasets.catalog import getsamples, print_no_samples

__all__ = ['Sample', 'Data', 'MC', 'Embdedded', 'getsamples', 'print_no_samples']
