#!/usr/bin/env bash
#
# FastSetup.sh: install TauFW and its dependencies around an existing clone.
#
# Automates the manual installation in README.md. It creates (or reuses) the
# reference CMSSW release, moves this checkout to <release>/src/TauFW, installs
# the extra tools and builds everything with SCRAM. The steps are listed in
# main() below; usage is in `bash FastSetup.sh --help` and docs/FastSetup.md.
#
# The script is safe to rerun after an interruption or a failure: each step
# skips work that is already done, and nothing is force-overwritten or deleted
# without a backup.

# Plain POSIX syntax, so that sh, dash or zsh reach this message instead of a
# parse error further down.
if [ -z "${BASH_VERSION:-}" ]; then
  echo 'FastSetup: run this script with bash: bash FastSetup.sh' >&2
  return 1 2>/dev/null || exit 1
fi
if [[ ${BASH_SOURCE[0]} != "$0" ]]; then
  printf 'FastSetup: run this script with bash FastSetup.sh, rather than sourcing it.\n' >&2
  return 1
fi
if ((BASH_VERSINFO[0] * 100 + BASH_VERSINFO[1] < 404)); then
  printf 'FastSetup: bash 4.4 or newer is required (found %s).\n' "$BASH_VERSION" >&2
  exit 1
fi

# Stop at the first failing command, including inside $(...).
set -Eeuo pipefail
shopt -s inherit_errexit

# ─── Configuration ───────────────────────────────────────────────────────────

readonly RELEASE=CMSSW_14_1_0_pre4
readonly SUPPORTED_ARCHS=(el8_amd64_gcc12 el9_amd64_gcc12)
# Fitting tool versions recommended for CMSSW 14_1_X:
# https://cms-analysis.github.io/HiggsAnalysis-CombinedLimit/v10.6.1/
# https://github.com/cms-analysis/CombineHarvester
readonly COMBINE_TAG=v10.6.1
readonly HARVESTER_TAG=v3.1.0

readonly NANOAODTOOLS_URL=https://github.com/cms-nanoAOD/nanoAOD-tools.git
readonly TAUIDSFS_URL=https://github.com/cms-tau-pog/TauIDSFs
readonly HTT_URL=https://github.com/CMS-HTT/LeptonEfficiencies
readonly COMBINE_URL=https://github.com/cms-analysis/HiggsAnalysis-CombinedLimit.git
readonly HARVESTER_URL=https://github.com/cms-analysis/CombineHarvester.git
readonly HTT_PATH=PicoProducer/data/lepton/HTT # relative to the TauFW checkout

# Fail instead of waiting for a password if a clone needs credentials.
export GIT_TERMINAL_PROMPT=0

# ─── State ───────────────────────────────────────────────────────────────────

jobs=4           # --jobs
run2_jme=false   # --run2-jme
cmssw_dir=       # --cmssw-dir, or chosen by choose_release_area
repo_dir=        # this checkout; updated once it has been moved
target=          # final checkout location: $cmssw_dir/src/TauFW
cms_setup=       # CMS environment script
moved=false      # whether this run moved the checkout
need_clean=false # whether this run cloned a package, so the build starts clean
warnings=()      # repeated in the summary, so they are not lost in build output
cleanup_paths=() # temporary directories, removed on exit
temp_dir=        # output of make_temp_dir
args=("$@")      # for the rerun hint after an error

readonly ERR_TRAP='on_error "$LINENO"'
trap "$ERR_TRAP" ERR
trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM

# ─── Pipeline ────────────────────────────────────────────────────────────────

main() {
  parse_args "$@"
  check_host               # Linux with Git
  locate_checkout          # this TauFW clone
  choose_release_area      # where CMSSW_14_1_0_pre4 lives
  choose_scram_arch        # el8/el9_amd64_gcc12
  load_cms_software        # source cmsset_default.sh
  create_release           # cmsrel, unless the release exists
  activate_release         # cmsenv
  move_checkout            # to $CMSSW_BASE/src/TauFW
  install_nanoaodtools     # only with --run2-jme
  install_tauidsfs
  install_htt_efficiencies
  install_combine          # Combine and CombineHarvester
  build_release            # scram b
  verify_install
  print_summary
}

usage() {
  cat <<EOF
Usage: bash FastSetup.sh [options]

Creates or reuses $RELEASE, moves this checkout to its src/TauFW,
installs TauIDSFs, the HTT lepton efficiencies, Combine $COMBINE_TAG and
CombineHarvester $HARVESTER_TAG, then builds everything with SCRAM.

Options:
  --cmssw-dir PATH  Release area to create or reuse; its name must be
                    $RELEASE. Default: the release containing this
                    checkout, otherwise a new one beside the checkout (or beside
                    the other release that contains it).
  --jobs N          Build parallelism (default: 4).
  --run2-jme        Install standalone NanoAODTools for Run 2 JEC/JER.
                    Otherwise use the framework shipped with CMSSW.
  -h, --help        Show this help.
Values can also be given as --cmssw-dir=PATH and --jobs=N.

Requires Linux with bash 4.4+, CMS software (normally via CVMFS), Git and
network access. SCRAM_ARCH may be set to ${SUPPORTED_ARCHS[0]} or ${SUPPORTED_ARCHS[1]};
otherwise it is detected from /etc/os-release. CMS_SETUP may override
/cvmfs/cms.cern.ch/cmsset_default.sh.

Measured-SF edits and TauPOG-internal correction production remain manual.
EOF
}

# ─── Helpers ─────────────────────────────────────────────────────────────────

log()  { printf '\n[FastSetup] %s\n' "$*"; }
warn() { printf '[FastSetup] WARNING: %s\n' "$*" >&2; warnings+=("$*"); }
die()  { printf 'FastSetup: %s\n' "$*" >&2; exit 1; }

# ERR trap: report the failing line and how to resume. The checkout may have
# moved by now, so the hint uses its current location.
on_error() {
  [[ $BASHPID == "$$" ]] || return 0 # report once, from the main shell
  local script=${repo_dir:+$repo_dir/FastSetup.sh}
  printf 'FastSetup failed at line %s. Fix the error above, then rerun:\n  bash %q' "$1" "${script:-$0}" >&2
  if ((${#args[@]})); then printf ' %q' "${args[@]}" >&2; fi
  printf '\n' >&2
}

# EXIT trap: remove temporary directories left by an interrupted step.
cleanup() {
  local path
  for path in "${cleanup_paths[@]}"; do rm -rf -- "$path"; done
}

# Run a command from CMS's own setup scripts. They are not written for strict
# mode, so strict mode and the error trap are paused while they run. Their exit
# status is not reliable, so callers check the result instead.
relaxed() {
  local status=0
  set +Eeuo pipefail
  trap - ERR
  "$@" || status=$?
  set -Eeuo pipefail
  trap "$ERR_TRAP" ERR
  return "$status"
}

# Create a directory in PARENT, sets $temp_dir, and removes it on exit if it is
# still there. Keep PARENT on the destination's filesystem so that the result
# can be renamed into place.
make_temp_dir() { # PARENT LABEL
  temp_dir=$(mktemp -d "$1/.FastSetup-$2.XXXXXX")
  cleanup_paths+=("$temp_dir")
}

# Print the CMSSW release area (a directory with .SCRAM) that contains the
# absolute PATH, if any.
enclosing_release() { # PATH
  local dir=$1
  while [[ $dir != / && $dir != . ]]; do
    dir=$(dirname -- "$dir")
    if [[ -d $dir/.SCRAM ]]; then
      printf '%s\n' "$dir"
      return 0
    fi
  done
  return 1
}

# Rename SRC to DST. A rename is impossible across filesystems, including
# separate AFS volumes. In that case copy SRC to a staging directory beside DST,
# rename that into place, and only then delete SRC, so that DST is either
# complete or absent.
move_dir() { # SRC DST
  local src=$1 dst=$2 status=0
  python3 - "$src" "$dst" <<'EOF' || status=$?
import errno, os, sys
try:
    os.rename(sys.argv[1], sys.argv[2])
except OSError as err:
    sys.exit(3 if err.errno == errno.EXDEV else str(err))
EOF
  case $status in
    0) return ;;
    3) ;;
    *) die "Could not move $src to $dst." ;;
  esac
  log "The destination is on another filesystem; copying instead (this can take a while)."
  make_temp_dir "$cmssw_dir" move
  cp -a -- "$src/." "$temp_dir/"
  chmod --reference="$src" -- "$temp_dir" # mktemp made it private
  mv -T -- "$temp_dir" "$dst"
  rm -rf -- "$src"
}

# Reduce a Git remote to host/owner/repo, so that the HTTPS, SSH and scp-style
# spellings of the same repository compare equal.
normalize_remote() { # URL
  local url=${1,,} # GitHub names are case-insensitive
  url=${url#*://}  # scheme
  url=${url#*@}    # user and any credentials
  if [[ $url =~ ^([^/:]+):[0-9]+/(.*)$ ]]; then
    url=${BASH_REMATCH[1]}/${BASH_REMATCH[2]} # port
  fi
  url=${url/:/\/} # scp-style host:owner/repo
  url=${url%/}
  printf '%s\n' "${url%.git}"
}

# Clone URL into PATH (at TAG, if given), or reuse an existing checkout of it.
# An existing checkout is never pulled, reset or switched. If it is not at TAG,
# it is kept as it is and a warning names the tested tag.
install_repo() { # URL PATH [TAG]
  local url=$1 path=$2 tag=${3:-} top origin have want
  local clone_opts=()
  if [[ ! -e $path && ! -L $path ]]; then
    log "Cloning $url${tag:+ ($tag)} into $path"
    mkdir -p -- "$(dirname -- "$path")"
    if [[ -n $tag ]]; then clone_opts=(--branch "$tag"); fi
    git -c advice.detachedHead=false clone "${clone_opts[@]}" -- "$url" "$path"
    need_clean=true
    return
  fi

  top=$(git -C "$path" rev-parse --show-toplevel 2>/dev/null) ||
    die "$path exists but is not a Git checkout. Move it away and rerun."
  [[ -z $(git -C "$path" rev-parse --show-cdup) ]] || # PATH must be the checkout's root
    die "$path is inside another Git checkout ($top), not a clone of $url."
  origin=$(git -C "$path" remote get-url origin 2>/dev/null) ||
    die "$path has no 'origin' remote; expected a clone of $url."
  have=$(normalize_remote "$origin")
  want=$(normalize_remote "$url")
  if [[ $have == "$want" ]]; then
    log "Reusing $path"
  elif [[ ${have##*/} == "${want##*/}" ]]; then # same repository name: a fork or mirror
    warn "Reusing $path, which is a clone of $origin rather than $url."
  else
    die "$path is a clone of $origin, not $url. Move it away and rerun."
  fi

  if [[ -n $tag && $(git -C "$path" rev-parse HEAD) != "$(git -C "$path" rev-parse -q --verify "refs/tags/$tag^{commit}" || true)" ]]; then
    warn "$path is at $(git -C "$path" describe --tags --always), not the tested $tag. It was kept as it is; to switch: git -C $path checkout $tag"
  fi
}

# Hide PATH (relative to the TauFW checkout) from TauFW's Git, because a
# separate clone replaced the files that TauFW tracks there. This keeps
# `git status` clean and stops `git add -A` or `git commit -a` from committing
# the swap. To undo: git update-index --no-skip-worktree -- PATH, and delete
# its line from .git/info/exclude.
hide_from_taufw_git() { # PATH
  local rel=$1 exclude=$repo_dir/.git/info/exclude
  mkdir -p -- "$repo_dir/.git/info"
  grep -qxF -- "/$rel/" "$exclude" 2>/dev/null || printf '/%s/\n' "$rel" >>"$exclude"
  git -C "$repo_dir" ls-files -z -- "$rel" | xargs -0 -r git -C "$repo_dir" update-index --skip-worktree --
}

# ─── Pipeline steps ──────────────────────────────────────────────────────────

parse_args() {
  while (($#)); do
    case $1 in
      --cmssw-dir=?*) cmssw_dir=${1#*=}; shift ;;
      --jobs=?*) jobs=${1#*=}; shift ;;
      --cmssw-dir | --jobs)
        (($# >= 2)) && [[ -n $2 && $2 != -* ]] || die "Missing value for $1."
        if [[ $1 == --cmssw-dir ]]; then cmssw_dir=$2; else jobs=$2; fi
        shift 2 ;;
      --run2-jme) run2_jme=true; shift ;;
      -h | --help) usage; exit 0 ;;
      *) die "Unknown option or missing value: $1 (see --help)." ;;
    esac
  done
  [[ $jobs =~ ^[1-9][0-9]*$ ]] || die '--jobs must be a positive integer.'
}

check_host() {
  [[ $(uname -s) == Linux ]] || die 'CMSSW needs Linux; run this script on a CMS node or in a CMS container.'
  command -v git >/dev/null || die 'Git is required.'
}

locate_checkout() {
  repo_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)
  [[ -f $repo_dir/README.md && -d $repo_dir/PicoProducer && -d $repo_dir/Fitter ]] ||
    die 'Keep FastSetup.sh in the root of the TauFW checkout.'
  # A linked worktree only has a .git file that points to its main repository;
  # moving it would break that link.
  [[ -d $repo_dir/.git ]] || die 'Use a standalone Git clone; moving a linked worktree would break its Git metadata.'
}

# Default: reuse the release that already contains the checkout. If the
# checkout is inside a different release (e.g. from an older installation),
# put the new release beside that one, never inside it.
choose_release_area() {
  local outer
  if [[ -z $cmssw_dir ]]; then
    if outer=$(enclosing_release "$repo_dir"); then
      if [[ $(basename -- "$outer") == "$RELEASE" ]]; then
        cmssw_dir=$outer
      else
        cmssw_dir=$(dirname -- "$outer")/$RELEASE
        log "This checkout is inside $outer; $RELEASE goes beside it."
      fi
    else
      cmssw_dir=$(dirname -- "$repo_dir")/$RELEASE
    fi
  fi
  cmssw_dir=$(realpath -m -- "$cmssw_dir") # -m: the release may not exist yet

  [[ $(basename -- "$cmssw_dir") == "$RELEASE" ]] || die "--cmssw-dir must end in $RELEASE."
  case "$cmssw_dir/" in
    "$repo_dir/"*) die 'The CMSSW release must be outside the checkout so the checkout can be moved into it.' ;;
  esac
  if outer=$(enclosing_release "$cmssw_dir"); then
    die "$cmssw_dir would be nested inside the release area $outer. Choose a location outside it with --cmssw-dir."
  fi

  target=$cmssw_dir/src/TauFW
  if [[ $repo_dir != "$target" && (-e $target || -L $target) ]]; then
    die "Destination already exists: $target. Run its FastSetup.sh or choose another --cmssw-dir."
  fi
}

choose_scram_arch() {
  if [[ -z ${SCRAM_ARCH:-} ]]; then
    [[ $(uname -m) == x86_64 ]] || die "This script supports only x86_64 (${SUPPORTED_ARCHS[*]})."
    [[ -r /etc/os-release ]] || die 'Cannot detect the OS; set SCRAM_ARCH explicitly.'
    local os_ids os_major el_like='(^| )(rhel|centos|fedora)( |$)'
    os_ids=$(. /etc/os-release && printf '%s %s' "${ID:-}" "${ID_LIKE:-}")
    os_major=$(. /etc/os-release && printf '%s' "${VERSION_ID:-}")
    os_major=${os_major%%.*}
    [[ $os_ids =~ $el_like && $os_major =~ ^[89]$ ]] ||
      die 'Use an EL8/EL9 CMS node or container (e.g. cmssw-el9), or set SCRAM_ARCH explicitly.'
    export SCRAM_ARCH=el${os_major}_amd64_gcc12
  fi
  [[ " ${SUPPORTED_ARCHS[*]} " == *" $SCRAM_ARCH "* ]] ||
    die "Unsupported SCRAM_ARCH for $RELEASE: $SCRAM_ARCH (use ${SUPPORTED_ARCHS[*]})."
}

load_cms_software() {
  cms_setup=${CMS_SETUP:-/cvmfs/cms.cern.ch/cmsset_default.sh}
  [[ -r $cms_setup ]] || die "CMS setup is unavailable: $cms_setup. Run on a CMS node with CVMFS, or set CMS_SETUP."
  log "Loading CMS software ($SCRAM_ARCH)"
  relaxed source "$cms_setup" || true
  command -v scram >/dev/null || die 'Loading CMS software failed: scram is not available.'
}

create_release() {
  if [[ ! -e $cmssw_dir ]]; then
    log "Creating $cmssw_dir"
    mkdir -p -- "$(dirname -- "$cmssw_dir")"
    # cmsrel is an alias for this command, and aliases do not work in scripts.
    (cd -- "$(dirname -- "$cmssw_dir")" && scram project CMSSW "$RELEASE")
  fi
  [[ -d $cmssw_dir/src && -d $cmssw_dir/.SCRAM ]] ||
    die "Not a complete CMSSW release area: $cmssw_dir. If an earlier run was interrupted while creating it, remove it and rerun."
}

activate_release() {
  local runtime
  cd -- "$cmssw_dir/src"
  # cmsenv is an alias for eval `scram runtime -sh`.
  runtime=$(scram runtime -sh)
  relaxed eval "$runtime" || true
  [[ ${CMSSW_VERSION:-} == "$RELEASE" ]] || die "Expected $RELEASE, got ${CMSSW_VERSION:-no active release}."
  [[ -n ${CMSSW_BASE:-} && $(realpath -- "$CMSSW_BASE") == "$cmssw_dir" ]] ||
    die "SCRAM activated a different release area: ${CMSSW_BASE:-none}."
}

# main() runs from the last line of this file, so bash has already read the
# whole script and can keep running after its file moves.
move_checkout() {
  if [[ $repo_dir == "$target" ]]; then
    log "TauFW is already at $target"
    return
  fi
  log "Moving $repo_dir to $target"
  move_dir "$repo_dir" "$target"
  repo_dir=$target
  moved=true
}

# PicoProducer uses the NanoAODTools in CMSSW by default. A standalone checkout
# in src overrides that, so it is only accepted when it was asked for.
install_nanoaodtools() {
  local path=$cmssw_dir/src/PhysicsTools/NanoAODTools
  if $run2_jme; then
    install_repo "$NANOAODTOOLS_URL" "$path"
  elif [[ -e $path || -L $path ]]; then
    die "Standalone NanoAODTools already overrides the release ($path). Rerun with --run2-jme, or move that checkout outside src and rerun."
  fi
}

install_tauidsfs() {
  install_repo "$TAUIDSFS_URL" "$cmssw_dir/src/TauPOG/TauIDSFs"
}

# TauFW ships a placeholder HTT directory. README.md replaces it with rm -rf.
# This step clones first and swaps afterwards, so a failed clone changes
# nothing, and it keeps the placeholder outside src as a backup.
install_htt_efficiencies() {
  local htt=$repo_dir/$HTT_PATH backup
  if [[ -e $htt && ! -e $htt/.git ]]; then
    make_temp_dir "$cmssw_dir" HTT
    git clone -- "$HTT_URL" "$temp_dir/HTT"
    backup=$(mktemp -d "$cmssw_dir/FastSetup-backup.XXXXXX")
    mv -- "$htt" "$backup/HTT"
    mv -- "$temp_dir/HTT" "$htt"
    log "Original HTT directory saved at $backup/HTT"
  fi
  install_repo "$HTT_URL" "$htt"
  hide_from_taufw_git "$HTT_PATH"
}

install_combine() {
  install_repo "$COMBINE_URL" "$cmssw_dir/src/HiggsAnalysis/CombinedLimit" "$COMBINE_TAG"
  install_repo "$HARVESTER_URL" "$cmssw_dir/src/CombineHarvester" "$HARVESTER_TAG"
}

# Start from a clean build after new packages were cloned, as CombineHarvester
# recommends. A rerun with nothing new resumes the previous build instead of
# starting over.
build_release() {
  cd -- "$cmssw_dir/src"
  if $need_clean; then
    log 'New packages were added; cleaning the previous build'
    scram b clean
  fi
  log "Building all packages with $jobs jobs"
  scram b -j"$jobs"
}

verify_install() {
  log 'Checking the installed tools'
  python3 -c 'import PhysicsTools.NanoAODTools.postprocessing.framework.postprocessor as m; print("NanoAODTools:", m.__file__); import TauPOG.TauIDSFs; import correctionlib' ||
    die 'The build finished, but a Python import failed (see above).'
  command -v combine >/dev/null || die 'The build finished, but combine is not on PATH.'
}

print_summary() {
  log "Setup complete: $repo_dir"
  if ((${#warnings[@]})); then
    printf '\nWarnings from this run:\n'
    printf '  - %s\n' "${warnings[@]}"
  fi
  printf '\nActivate this environment in your terminal now and in each new session:\n'
  printf '  source %q\n  export SCRAM_ARCH=%q\n  cd %q\n  cmsenv\n' "$cms_setup" "$SCRAM_ARCH" "$cmssw_dir/src"
  if $moved; then
    printf '\nThe checkout was moved. A terminal that was inside it still shows the old path; the cd above fixes that.\n'
  fi
  printf '\nTauPOG correction production still requires your measured SFs and the manual instructions in README.md.\n'
}

main "$@"
