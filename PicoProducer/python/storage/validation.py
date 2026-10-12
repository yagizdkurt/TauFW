# Author: Izaak Neutelings (May 2020)
"""Inspect ROOT files on storage: count events and check job output for corruption.

Inputs:  ROOT file names (NanoAOD with an 'Events' tree, or pico tuples with 'tree' and 'cutflow').
Outputs: event counts; -1 marks an unreadable or corrupt file.

Public API:
  getnevents(fname, treename)                 number of entries in a tree
  isvalid(fname, hname, bin)                  processed events of a job output file, or -1 if corrupt
  itervalid(fnames, checkevts, ncores, ...)   yield (nevents, fname) for job outputs, optionally in parallel
  iterevts(fnames, tree, filenevts, ...)      yield (nevents, fname) for input files, using a cache
"""

# ===== Imports =====
from TauFW.common.tools.root import ensureTFile
from TauFW.PicoProducer.storage.log import LOG
from ROOT import TFile

__all__ = ['getnevents', 'isvalid', 'itervalid', 'iterevts']


# ===== Public API =====

def getnevents(fname,treename='Events',verb=0):
  """Help function to get number of entries in a tree."""
  if verb>=3:
    print(">>> storage.utils.getnevents: opening %s:%r"%(fname,treename))
  file = ensureTFile(fname)
  tree = file.Get(treename)
  if not tree:
    LOG.warning(">>> storage.utils.getnevents: No %r tree in events in %r!"%(treename,fname))
    return 0
  nevts = tree.GetEntries()
  file.Close()
  return nevts
  

def isvalid(fname,hname='cutflow',bin=1):
  """Check if a given file is valid, or corrupt."""
  nevts = -1
  try:
    file = TFile.Open(fname,'READ')
  except OSError as err:
    print(err)
    file = None
  if file and not file.IsZombie():
    if file.GetListOfKeys().Contains('Events'): # NANOAOD
      nevts = file.Get('Events').GetEntries()
      if nevts<=0:
        LOG.warning("'Events' tree of file %r has nevts=%s<=0..."%(fname,nevts))
    elif file.GetListOfKeys().Contains('tree') and file.GetListOfKeys().Contains(hname): # pico
      hist = file.Get(hname)
      if hist:
        nevts = hist.GetBinContent(bin)
        if nevts<=0:
          LOG.warning("Cutflow of file %r has nevts=%s<=0..."%(fname,nevts))
      else: # corrupted ?
        LOG.warning("Could not open cutflow %s:%s..."%(fname,hname))
  return nevts
  

def itervalid(fnames,checkevts=True,nchunks=None,ncores=4,verb=0,**kwargs):
  """Iterate over file names and get number of events processed & check for corruption."""
  if not checkevts: # just skip validation step and return 0
    for fname in fnames:
      yield 0, fname
  elif ncores>=2 and len(fnames)>5: # run validation in parallel
    from TauFW.common.tools.parallel import MultiProcessor
    from TauFW.common.tools.math import partition
    processor = MultiProcessor(max=ncores)
    def loopvalid(fnames_,**kwargs):
      """Help function for parallel running on subsets."""
      return [(isvalid(f,**kwargs),f) for f in fnames_]
    if not nchunks:
      nchunks = 10 if len(fnames)<100 else 20 if len(fnames)<500 else 50 if len(fnames)<1000 else 100
      nchunks = max(nchunks,2*ncores)
    if nchunks>=len(fnames):
      nchunks = len(fnames)-1
    if verb>=2:
      print(">>> storage.utils.itervalid: partitioning %d files into %d chunks for ncores=%d"%(len(fnames),nchunks,ncores))
    for i, subset in enumerate(partition(fnames,nchunks)): # process in ncores chunks
      if not subset: break
      name = "itervalid_%d"%(i)
      processor.start(loopvalid,subset,kwargs,name=name)
    for process in processor:
      if verb>=2:
        print(">>> storage.utils.itervalid: joining process %r..."%(process.name))
      nevtfiles = process.join()
      for nevts, fname in nevtfiles:
        yield nevts, fname
  else:  # run validation in series
    for fname in fnames:
      if verb>=2:
        print(">>> storage.utils.itervalid:  Validating job output '%s'..."%(fname))
      nevts = isvalid(fname)
      yield nevts, fname
  

def iterevts(fnames,tree,filenevts,refresh=False,nchunks=None,ncores=0,verb=0):
  """Help function for Sample._getnevents to iterate over file names and get number of events processed."""
  if ncores>=2 and len(fnames)>5: # run events check in PARALLEL
    from TauFW.common.tools.parallel import MultiProcessor
    from TauFW.common.tools.math import partition
    def loopevts(fnames_):
      """Help function for parallel running on subsets."""
      return [(getnevents(f,tree,verb=verb),f) for f in fnames_]
    processor = MultiProcessor(max=ncores)
    if not nchunks:
      nchunks = 10 if len(fnames)<100 else 20 if len(fnames)<500 else 50 if len(fnames)<1000 else 100
      nchunks = max(nchunks,2*ncores)
    if nchunks>=len(fnames):
      nchunks = len(fnames)-1
    if verb>=2:
      print(">>> storage.utils.iterevts: partitioning %d files into %d chunks for ncores=%d..."%(len(fnames),nchunks,ncores))
    for i, subset in enumerate(partition(fnames,nchunks)): # process in ncores chunks
      for fname in subset[:]: # check cache
        if not refresh and fname in filenevts:
          nevts = filenevts[fname]
          subset.remove(fname) # don't run again
          yield nevts, fname
      if not subset:
        break
      name = "iterevts_%d"%(i)
      processor.start(loopevts,subset,name=name)
    for process in processor: # collect output from parallel processes
      if verb>=2:
        print(">>> storage.utils.iterevts: joining process %r..."%(process.name))
      nevtfiles = process.join()
      for nevts, fname in nevtfiles:
        yield nevts, fname
  else: # run events check in SERIES
    if verb>=2:
      print(">>> storage.utils.iterevts: retrieving number of events for %d files (in series)..."%(len(fnames)))
    for fname in fnames:
      if refresh or fname not in filenevts:
        nevts = getnevents(fname,tree,verb=verb)
      else: # get from cache or efficiency
        nevts = filenevts[fname]
      yield nevts, fname
  
