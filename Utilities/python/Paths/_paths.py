"""Named defaults collected from TauFW's current scripts and storage backends.

These values describe existing conventions, not service availability. Selecting
a site, overriding an analysis directory, and checking access belong to callers.
No personal analysis areas, campaign filenames, or credentials are stored here.

Infrastructure strings use POSIX separators even on Windows. Directory constants
omit trailing slashes; endpoint constants retain them. Use xrootd_url for ROOT
URLs rather than filesystem joins, which can damage the protocol or double slash.
Checkout paths follow this imported copy of Utilities, independently of cwd and
CMSSW_BASE. CMSSW_BASE is read only when cmssw_src is called.
"""

import os
from pathlib import Path
import posixpath
from typing import Optional, Union
from urllib.parse import urlsplit


# CMS software and the container image used by the existing SLURM templates.
CVMFS_ROOT = "/cvmfs"
CMS_CVMFS_ROOT = CVMFS_ROOT + "/cms.cern.ch"
CMS_SETUP_SCRIPT = CMS_CVMFS_ROOT + "/cmsset_default.sh"
CVMFS_UNPACKED_ROOT = CVMFS_ROOT + "/unpacked.cern.ch"
CMSSW_EL7_IMAGE = CVMFS_UNPACKED_ROOT + "/registry.hub.docker.com/cmssw/el7:x86_64"

# CERN mounts and CMS logical storage namespaces are different kinds of location.
CERN_EOS_ROOT = "/eos"
CERN_EOS_USER_ROOT = CERN_EOS_ROOT + "/user"
CERN_EOS_CMS_ROOT = CERN_EOS_ROOT + "/cms"
CERN_AFS_ROOT = "/afs/cern.ch"
CERN_AFS_USER_ROOT = CERN_AFS_ROOT + "/user"
CERN_AFS_WORK_ROOT = CERN_AFS_ROOT + "/work"
CMS_STORE_ROOT = "/store"
CMS_STORE_USER_ROOT = CMS_STORE_ROOT + "/user"
CMS_STORE_GROUP_ROOT = CMS_STORE_ROOT + "/group"
TAUFW_EOS_GROUP_ROOT = CERN_EOS_CMS_ROOT + CMS_STORE_GROUP_ROOT + "/phys_tau/TauFW"
TAUFW_EOS_NANO_ROOT = TAUFW_EOS_GROUP_ROOT + "/nano"
TAUFW_EOS_NANOV10_ROOT = TAUFW_EOS_GROUP_ROOT + "/nanoV10"

# Other sites used by the current storage backends and sample catalogs.
PSI_T3_PNFS_ROOT = "/pnfs/psi.ch"
PSI_T3_STORE_ROOT = PSI_T3_PNFS_ROOT + "/cms/trivcat/store"
PSI_T3_USER_ROOT = PSI_T3_STORE_ROOT + "/user"
PSI_T2_PNFS_ROOT = "/pnfs/lcg.cscs.ch"
PSI_T2_STORE_ROOT = PSI_T2_PNFS_ROOT + "/cms/trivcat/store"
PSI_T2_USER_ROOT = PSI_T2_STORE_ROOT + "/user"
DESY_PNFS_ROOT = "/pnfs/desy.de"
GRIDKA_NRG_MOUNT = "/storage/gridka-nrg"

# Unix defaults, not assertions about the current host or its writable mounts.
TMP_ROOT = "/tmp"
SCRATCH_ROOT = "/scratch"
UCL_SCRATCH_ROOT = "/nfs/scratch/fynu"

# Endpoints copied from active code; choosing the correct server is explicit.
CMS_GLOBAL_XROOTD = "root://cms-xrd-global.cern.ch/"
CMS_EUROPE_XROOTD = "root://xrootd-cms.infn.it/"
CMS_US_XROOTD = "root://cmsxrootd.fnal.gov/"
EOS_USER_XROOTD = "root://eosuser.cern.ch/"
PSI_T3_XROOTD = "root://t3dcachedb03.psi.ch/"
PSI_T3_GSIFTP = "gsiftp://t3se01.psi.ch/"
PSI_T2_XROOTD = "root://storage01.lcg.cscs.ch/"
PSI_T2_GSIFTP = "gsiftp://storage01.lcg.cscs.ch/"
GRIDKA_XROOTD = "root://cmsxrootd-kit.gridka.de/"
DESY_SRM_ENDPOINT = "srm://dcache-se-cms.desy.de:8443/srm/managerv2"

# Resources in the checkout containing this module, without importing stages.
TAUFW_ROOT = Path(__file__).resolve().parents[3]
UTILITIES_ROOT = TAUFW_ROOT / "Utilities"
PICO_PRODUCER_ROOT = TAUFW_ROOT / "PicoProducer"
PICO_DATA_DIR = PICO_PRODUCER_ROOT / "data"
PICO_SAMPLES_DIR = PICO_PRODUCER_ROOT / "samples"
HISTOGRAMMER_ROOT = TAUFW_ROOT / "Histogrammer"  # the former Plotter (CL §24)
HISTOGRAMMER_DATA_DIR = HISTOGRAMMER_ROOT / "data"
PLOTTER_ROOT = TAUFW_ROOT / "Plotter"
PLOTTER_DATA_DIR = PLOTTER_ROOT / "data"  # does not exist since CL §24: HISTOGRAMMER_DATA_DIR; TODO §8
FITTER_ROOT = TAUFW_ROOT / "Fitter"


def _user_dir(root: str, user: str, sharded: bool = False) -> str:
    if not isinstance(user, str):
        raise TypeError("user must be a string")
    if not user or user in (".", "..") or any(c in user for c in "/\\") or any(c.isspace() for c in user):
        raise ValueError("user must be a nonempty directory name without separators or whitespace")
    return posixpath.join(root, user[0], user) if sharded else posixpath.join(root, user)


def eos_user(user: str) -> str:
    """Return /eos/user/<initial>/<user>; username selection stays with callers."""
    return _user_dir(CERN_EOS_USER_ROOT, user, sharded=True)


def afs_home(user: str) -> str:
    """Return the user's CERN AFS home directory."""
    return _user_dir(CERN_AFS_USER_ROOT, user, sharded=True)


def afs_work(user: str) -> str:
    """Return the user's CERN AFS work directory."""
    return _user_dir(CERN_AFS_WORK_ROOT, user, sharded=True)


def cms_user(user: str) -> str:
    """Return a logical /store/user/<user> path, without selecting a server."""
    return _user_dir(CMS_STORE_USER_ROOT, user)


def psi_t3_user(user: str) -> str:
    """Return a PSI T3 PNFS user directory."""
    return _user_dir(PSI_T3_USER_ROOT, user)


def psi_t2_user(user: str) -> str:
    """Return a PSI T2/CSCS PNFS user directory."""
    return _user_dir(PSI_T2_USER_ROOT, user)


def scratch_user(user: str, root: str = SCRATCH_ROOT) -> str:
    """Return a POSIX scratch directory; pass UCL_SCRATCH_ROOT for UCL."""
    return _user_dir(root, user)


def cmssw_src(base: Optional[Union[str, os.PathLike]] = None) -> Path:
    """Return <base>/src, reading CMSSW_BASE at call time if base is omitted.

    Raise ValueError if neither supplies a base. No existence check is performed,
    so this also works when preparing a release that has not been created yet.
    """
    if base is None:
        base = os.environ.get("CMSSW_BASE")
    if base is None or not os.fspath(base):
        raise ValueError("Provide a CMSSW base directory or set CMSSW_BASE")
    return Path(base) / "src"


def xrootd_url(endpoint: str, logical_path: str) -> str:
    """Combine a root://host[:port]/ endpoint and an absolute POSIX path.

    Example: xrootd_url(CMS_GLOBAL_XROOTD, '/store/mc/file.root') produces
    'root://cms-xrd-global.cern.ch//store/mc/file.root'. Existing URL paths,
    queries and fragments in the endpoint are rejected instead of discarded.
    The path is preserved, apart from normalizing its leading slashes to one.
    """
    parsed = urlsplit(endpoint)
    if (parsed.scheme != "root" or not parsed.netloc or parsed.path not in ("", "/")
            or parsed.query or parsed.fragment):
        raise ValueError("endpoint must be a root://host[:port]/ URL without a file path")
    if not logical_path.startswith("/") or "\\" in logical_path:
        raise ValueError("logical_path must be an absolute POSIX path")
    return "root://" + parsed.netloc + "//" + logical_path.lstrip("/")


__all__ = [
    "CVMFS_ROOT", "CMS_CVMFS_ROOT", "CMS_SETUP_SCRIPT", "CVMFS_UNPACKED_ROOT",
    "CMSSW_EL7_IMAGE", "CERN_EOS_ROOT", "CERN_EOS_USER_ROOT", "CERN_EOS_CMS_ROOT",
    "CERN_AFS_ROOT", "CERN_AFS_USER_ROOT", "CERN_AFS_WORK_ROOT",
    "CMS_STORE_ROOT", "CMS_STORE_USER_ROOT", "CMS_STORE_GROUP_ROOT",
    "TAUFW_EOS_GROUP_ROOT", "TAUFW_EOS_NANO_ROOT", "TAUFW_EOS_NANOV10_ROOT",
    "PSI_T3_PNFS_ROOT", "PSI_T3_STORE_ROOT", "PSI_T3_USER_ROOT",
    "PSI_T2_PNFS_ROOT", "PSI_T2_STORE_ROOT", "PSI_T2_USER_ROOT",
    "DESY_PNFS_ROOT", "GRIDKA_NRG_MOUNT", "TMP_ROOT", "SCRATCH_ROOT", "UCL_SCRATCH_ROOT",
    "CMS_GLOBAL_XROOTD", "CMS_EUROPE_XROOTD", "CMS_US_XROOTD", "EOS_USER_XROOTD",
    "PSI_T3_XROOTD", "PSI_T3_GSIFTP", "PSI_T2_XROOTD", "PSI_T2_GSIFTP",
    "GRIDKA_XROOTD", "DESY_SRM_ENDPOINT",
    "TAUFW_ROOT", "UTILITIES_ROOT", "PICO_PRODUCER_ROOT", "PICO_DATA_DIR",
    "PICO_SAMPLES_DIR", "HISTOGRAMMER_ROOT", "HISTOGRAMMER_DATA_DIR", "PLOTTER_ROOT", "PLOTTER_DATA_DIR", "FITTER_ROOT",
    "eos_user", "afs_home", "afs_work",
    "cms_user", "psi_t3_user", "psi_t2_user",
    "scratch_user", "cmssw_src", "xrootd_url",
]
