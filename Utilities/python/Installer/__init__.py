"""Pre-install filesystem and verification helpers; safe to import without CMSSW."""

from ._installer import rename_directory, verify_modules, verify_htt_files

__all__ = ["rename_directory", "verify_modules", "verify_htt_files"]
