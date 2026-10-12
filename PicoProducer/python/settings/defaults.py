# Author: Izaak Neutelings (May 2020)
"""Default PicoProducer configuration and the site guesses it is built from.

Inputs:  the current user name and host name.
Outputs: an ordered dictionary with one default value per configuration key.

Public API:
  DTYPES                   allowed sample data types ('mc', 'data', 'embed')
  user, host               current user name and host name
  guess_sedir()            storage element directory for this user and host
  guess_tmpdirs()          temporary directories (skimming, hadd) for this host
  guess_batch()            batch system name for this host
  getdefaultconfig(verb)   default configuration (built on first call, then cached)
"""

# ===== Imports =====
import getpass, platform
from collections import OrderedDict
from TauFW.PicoProducer import basedir
from TauFW.common.tools.log import Logger

__all__ = ['DTYPES', 'user', 'host', 'guess_sedir', 'guess_tmpdirs', 'guess_batch', 'getdefaultconfig']


# ===== Constants =====
LOG          = Logger('GLOB')
DTYPES       = ['mc','data','embed']
user         = getpass.getuser()
host         = platform.node()
_cfgdefaults = OrderedDict() # filled once by getdefaultconfig


# ===== Site guesses =====

def guess_sedir():
  """Guess the storage element path for a given user and host."""
  sedir = ""
  if 'lxplus' in host:
    sedir = "/eos/user/%s/%s/"%(user[0],user)
  elif "t3" in host and "psi.ch" in host:
    sedir = "/pnfs/psi.ch/cms/trivcat/store/user/%s/"%(user)
  elif "etp" in host:
    sedir = "/store/user/{}/".format(user)
  return sedir


def guess_tmpdirs():
  """Guess the temporary directory for a given user and host."""
  tmphadddir = "/tmp/%s/"%(user) # temporary dir for creating intermediate hadd files
  tmpskimdir = ""                # temporary dir for creating skimmed file before copying to outdir
  if 'lxplus' in host:
    tmphadddir = "/eos/user/%s/%s/"%(user[0],user)
  elif "t3" in host and "psi.ch" in host:
    tmphadddir = basedir.rstrip('/')+'/' #output/$ERA/$CHANNEL/$SAMPLE/ #"/scratch/%s/"%(user)
  elif "etp" in host:
    tmphadddir = "/tmp/{}/".format(user)
  return tmpskimdir, tmphadddir


def guess_batch():
  """Guess the batch system for a host."""
  host = platform.node()
  batch = "HTCondor"
  if "etp" in host:
    batch = "HTCondor_KIT"
  elif "desy" in host:
    batch = "HTCondor_DESY"
  ###elif "etp" in host:
  ###  batch = "HTCondor_NAF"
  elif "t3" in host and "psi.ch" in host:
    batch = "SLURM"
  elif "ucl" in host:
    batch = "SLURM_UCL"
  return batch


# ===== Default configuration =====

def getdefaultconfig(verb=0):
  """Get default configuration dictionary. Initiate if it does not exist yet."""
  global _cfgdefaults
  if _cfgdefaults: # initiate
    LOG.verb(">>> getdefaultconfig: _cfgdefaults already initiated",verb,level=3)
  else:
    LOG.verb(">>> getdefaultconfig: Initiating _cfgdefaults...",verb,level=3)
    eras          = OrderedDict([
      ('2016','samples_2016.py'),
      ('2017','samples_2017.py'),
      ('2018','samples_2018.py')
    ])
    channels      = OrderedDict([
      ('skim',    'skimjob.py'),
      ('skim-jec','skimjob.py --jec-sys'),
      ('gen',     'GenDumper'),
      ('sumw',    'SumWeights'),
      ('pileup',  'PileUp'),
      ('mutau',   'ModuleMuTauSimple')
    ])
    sedir         = guess_sedir()                    # guess storage element on current host
    tmpskimdir, tmphadddir = guess_tmpdirs()         # tmphadddir: temporary dir for creating intermediate hadd files
                                                     # tmpskimdir: temporary dir for creating skimmed file before copying to outdir
    jobdir        = "output/$ERA/$CHANNEL/$SAMPLE"   # for job config and log files
    outdir        = tmphadddir+jobdir                # for job output
    picodir       = sedir+"analysis/$ERA/$GROUP"     # for storage of analysis ("pico") tuples after hadd
    nanodir       = sedir+"samples/nano/$ERA/$DAS"   # for storage of (skimmed) nanoAOD
    filelistdir   = "samples/files/$ERA/$SAMPLE.txt" # location to save list of files
    batchsystem   = guess_batch()                    # batch system (HTCondor, SLURM, ...)
    batchqueue    = ""                               # batch queue / job flavor
    batchopts     = ""                               # extra batch options
    nfilesperjob  = 1                                # group files per job
    maxevtsperjob = -1                               # maximum number of events per job (split large files)
    maxopenfiles  = 500                              # maximum number of open files during hadd
    ncores        = 4                                # number of cores for parallel event counting & validating of files
    haddcmd       = ""                               # alternative command for hadd'ing, e.g. 'python3 /.../.../haddnano.py'
    _cfgdefaults  = OrderedDict([                    # ordered dictionary with defaults
      ('channels',channels), ('eras',eras),
      ('jobdir',jobdir),     ('outdir',outdir), ('nanodir',nanodir), ('picodir',picodir),
      ('tmpskimdir',tmpskimdir),
      ('batch',batchsystem), ('queue',batchqueue), ('batchopts',batchopts),
      ('nfilesperjob',nfilesperjob), ('maxevtsperjob',maxevtsperjob),
      ('filelistdir',filelistdir),
      ('maxopenfiles',maxopenfiles), ('haddcmd', haddcmd ), # for pico.py hadd
      ('ncores',ncores),
    ])
  return _cfgdefaults

