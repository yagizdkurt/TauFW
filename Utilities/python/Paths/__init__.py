"""Shared infrastructure locations and side-effect-free path builders.

    from TauFW.Utilities import Paths

    home = Paths.eos_user("alice")
    source = Paths.xrootd_url(Paths.CMS_GLOBAL_XROOTD, "/store/mc/file.root")

Infrastructure paths and endpoints are strings; checkout and CMSSW paths are
native pathlib.Path objects. Importing this package needs only the standard
library, without ROOT, CMSSW activation, network access, or directory creation.
"""

from ._paths import (
    CVMFS_ROOT, CMS_CVMFS_ROOT, CMS_SETUP_SCRIPT, CVMFS_UNPACKED_ROOT,
    CMSSW_EL7_IMAGE, CERN_EOS_ROOT, CERN_EOS_USER_ROOT, CERN_EOS_CMS_ROOT,
    CERN_AFS_ROOT, CERN_AFS_USER_ROOT, CERN_AFS_WORK_ROOT,
    CMS_STORE_ROOT, CMS_STORE_USER_ROOT, CMS_STORE_GROUP_ROOT,
    TAUFW_EOS_GROUP_ROOT, TAUFW_EOS_NANO_ROOT, TAUFW_EOS_NANOV10_ROOT,
    PSI_T3_PNFS_ROOT, PSI_T3_STORE_ROOT, PSI_T3_USER_ROOT,
    PSI_T2_PNFS_ROOT, PSI_T2_STORE_ROOT, PSI_T2_USER_ROOT,
    DESY_PNFS_ROOT, GRIDKA_NRG_MOUNT, TMP_ROOT, SCRATCH_ROOT, UCL_SCRATCH_ROOT,
    CMS_GLOBAL_XROOTD, CMS_EUROPE_XROOTD, CMS_US_XROOTD, EOS_USER_XROOTD,
    PSI_T3_XROOTD, PSI_T3_GSIFTP, PSI_T2_XROOTD, PSI_T2_GSIFTP,
    GRIDKA_XROOTD, DESY_SRM_ENDPOINT,
    TAUFW_ROOT, UTILITIES_ROOT, PICO_PRODUCER_ROOT, PICO_DATA_DIR,
    PICO_SAMPLES_DIR, PLOTTER_ROOT, PLOTTER_DATA_DIR, FITTER_ROOT,
    eos_user, afs_home, afs_work,
    cms_user, psi_t3_user, psi_t2_user,
    scratch_user, cmssw_src, xrootd_url,
)
from ._paths import __all__
