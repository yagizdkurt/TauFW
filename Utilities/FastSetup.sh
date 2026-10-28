#!/usr/bin/env bash
# Author: Yagizhan Dinckurt (October 2026) (yagizdkurt)
#
# FastSetup.sh: install TauFW and its dependencies around an existing clone.
#
# Automates the manual installation in README.md. It creates (or reuses) the
# reference CMSSW release, moves this checkout to <release>/src/TauFW, installs
# the extra tools and builds everything with SCRAM. The steps are listed in
# main() below; usage is in `bash Utilities/FastSetup.sh --help` and Docs/Manual/FastSetup.md.
#
# Existing dependency checkouts are validated and kept unchanged. New downloads
# are staged before publication; cross-filesystem copies keep the original.

# Plain POSIX syntax, so that sh, dash or zsh reach this message instead of a
# parse error further down.
if [ -z "${BASH_VERSION:-}" ]; then
  echo 'FastSetup: run this script with bash: bash Utilities/FastSetup.sh' >&2
  return 1 2>/dev/null || exit 1
fi
if [[ ${BASH_SOURCE[0]} != "$0" ]]; then
  printf 'FastSetup: run this script with bash Utilities/FastSetup.sh, rather than sourcing it.\n' >&2
  return 1
fi
if ((BASH_VERSINFO[0] * 100 + BASH_VERSINFO[1] < 404)); then
  printf 'FastSetup: bash 4.4 or newer is required (found %s).\n' "$BASH_VERSION" >&2
  exit 1
fi

# Stop at the first failing command, including inside $(...).
set -Eeuo pipefail
shopt -s inherit_errexit

# =============================================================================
# ==== Configuration ====

readonly RELEASE=CMSSW_14_1_0_pre4
readonly SUPPORTED_ARCHS=(el8_amd64_gcc12 el9_amd64_gcc12)
# Fitting tool versions recommended for CMSSW 14_1_X:
# https://cms-analysis.github.io/HiggsAnalysis-CombinedLimit/v10.6.1/
# https://github.com/cms-analysis/CombineHarvester
readonly COMBINE_TAG=v10.6.1
readonly HARVESTER_TAG=v3.1.0
# Fixed snapshots of the formerly unpinned default branches (2026-10-13).
readonly NANOAODTOOLS_REF=d163c18096fe2c5963ff5a9764bb420b46632178
readonly TAUIDSFS_REF=34f69acfd17c1655a67a709135c594512b84a76f
readonly HTT_REF=a31ca914227f109e08c192d3a1b1c9ea07f929b2

readonly NANOAODTOOLS_URL=https://github.com/cms-nanoAOD/nanoAOD-tools.git
readonly TAUIDSFS_URL=https://github.com/cms-tau-pog/TauIDSFs
readonly HTT_URL=https://github.com/CMS-HTT/LeptonEfficiencies
readonly COMBINE_URL=https://github.com/cms-analysis/HiggsAnalysis-CombinedLimit.git
readonly HARVESTER_URL=https://github.com/cms-analysis/CombineHarvester.git
readonly HTT_PATH=PicoProducer/data/lepton/HTT # relative to the TauFW checkout
readonly SETUP_MANIFEST=Framework/python/_internal/setup_manifest.json # relative to the checkout
readonly NANOAODTOOLS_FILES=(
  python/postprocessing/framework/postprocessor.py
  python/postprocessing/modules/jme/jetmetHelperRun2.py
)
readonly TAUIDSFS_FILES=(python/TauIDSFTool.py)
readonly COMBINE_FILES=(BuildFile.xml python/PhysicsModel.py)
readonly HARVESTER_FILES=(CombineTools/BuildFile.xml CombineTools/python/ch.py)
readonly HTT_FILES=(
  Electron/Run2016_legacy/Electron_Run2016_legacy_Ele25.root
  Electron/Run2016_legacy/Electron_Run2016_legacy_IdIso.root
  Electron/Run2017/Electron_Ele35.root
  Electron/Run2017/Electron_Run2017_IdIso.root
  Electron/Run2018/Electron_Run2018_Ele32orEle35.root
  Electron/Run2018/Electron_Run2018_IdIso.root
  Muon/Run2017/Muon_IsoMu24orIsoMu27.root
)

# Fail instead of waiting for a password if a clone needs credentials.
export GIT_TERMINAL_PROMPT=0

# =============================================================================
# ==== Options and state ====

jobs=4                # --jobs
run2_jme=false         # --run2-jme
tauidsfs=true          # --skip-tauidsfs
htt=true              # --skip-htt
combine=true          # --skip-combine
non_interactive=false # --non-interactive
cmssw_dir=       # --cmssw-dir, or chosen by choose_release_area
repo_dir=        # this checkout; updated once it has been moved
target=          # final checkout location: $cmssw_dir/src/TauFW
cms_setup=       # CMS environment script
moved=false      # whether this run moved the checkout
clean_marker=    # persisted until a requested fitting-tool clean succeeds
copied_from=     # original checkout retained after a cross-filesystem copy
user_config=     # the user config file, once create_user_config has run
error_reported=false
cancelled=false
warnings=()      # repeated in the summary, so they are not lost in build output
cleanup_paths=() # temporary directories, removed on exit
temp_dir=        # output of make_temp_dir
args=("$@")      # for the rerun hint after an error

readonly ERR_TRAP='on_error "$LINENO"'
trap "$ERR_TRAP" ERR
trap on_exit EXIT
trap 'exit 130' INT
trap 'exit 143' TERM

# =============================================================================
# ==== Installation pipeline ====

main() {
  parse_args "$@"
  check_host               # Linux with Git
  locate_checkout          # this TauFW clone
  if ! $non_interactive && [[ -t 0 && -t 1 ]]; then
    local selected=()
    if $tauidsfs; then selected+=(tauidsfs); fi
    if $htt; then selected+=(htt); fi
    if $combine; then selected+=(combine); fi
    if $run2_jme; then selected+=(run2-jme); fi
    exec python3 "$repo_dir/Utilities/python/Installer/setup_runner.py" \
      --script "$repo_dir/Utilities/FastSetup.sh" --selected "${selected[@]}" -- "$@"
  fi
  banner 'Preflight'
  choose_release_area      # where CMSSW_14_1_0_pre4 lives
  select_components       # preserve the selection in resume arguments
  preflight_install       # reject known conflicts before relocating the clone
  invalidate_setup_record
  choose_scram_arch        # el8/el9_amd64_gcc12

  banner 'CMSSW environment'
  load_cms_software        # source cmsset_default.sh
  create_release           # cmsrel, unless the release exists
  activate_release         # cmsenv
  move_checkout            # to $CMSSW_BASE/src/TauFW

  banner 'Dependencies'
  install_nanoaodtools     # only with --run2-jme
  if $tauidsfs; then install_tauidsfs; fi
  if $htt; then install_htt_efficiencies; fi
  if $combine; then install_combine; fi # Combine and CombineHarvester
  banner 'Build'
  build_release            # scram b; clean only when fitting tools require it
  banner 'Verification'
  verify_install
  create_user_config       # Analyses/UserConfig.yaml, never replaced
  write_setup_manifest     # the selected components, for the recipe checks
  publish_setup_record
  if [[ -n ${FASTSETUP_EVENT_FD:-} ]]; then
    local summary
    summary=$(print_summary)
    printf '%s\n' "$summary"
    setup_event summary "$summary"
  elif [[ -n ${FASTSETUP_RESULT_FILE:-} ]]; then
    print_completion_notices
  else
    print_summary
  fi
}

usage() {
  cat <<EOF
Usage: bash Utilities/FastSetup.sh [options]

Creates or reuses $RELEASE, moves this checkout to its src/TauFW,
offers a component checklist on interactive terminals, then builds with SCRAM.
TauIDSFs, HTT efficiencies, Combine $COMBINE_TAG and CombineHarvester
$HARVESTER_TAG are selected by default; standalone NanoAODTools is optional.
Space/Enter toggles a component. Select Start install to begin; Esc cancels.
Setup stays on screen through completion. L opens the log; Ctrl+C cancels.
Enter closes the result screen. The full log is retained in TMPDIR (or /tmp).
Without a terminal, the defaults and command-line options are used.

Options:
  --cmssw-dir PATH  Release area to create or reuse; its name must be
                    $RELEASE. Default: the release containing this
                    checkout, otherwise a new one beside the checkout (or beside
                    the other release that contains it).
  --jobs N          Build parallelism (default: 4).
  --run2-jme        Install standalone NanoAODTools for Run 2 JEC/JER.
                    Otherwise use the framework shipped with CMSSW.
  --non-interactive Skip the checklist (for automation).
  --skip-tauidsfs   Do not install or verify TauIDSFs.
  --skip-htt        Do not install or verify HTT lepton efficiencies.
  --skip-combine    Do not install or verify Combine/CombineHarvester.
  -h, --help        Show this help.
Values can also be given as --cmssw-dir=PATH and --jobs=N.

Requires Linux with bash 4.4+, Python 3 (plain text questions if curses is unavailable),
CMS software (normally via CVMFS), Git and network access. SCRAM_ARCH may be set to ${SUPPORTED_ARCHS[0]} or ${SUPPORTED_ARCHS[1]};
otherwise it is detected from /etc/os-release. CMS_SETUP may override
/cvmfs/cms.cern.ch/cmsset_default.sh.

Measured-SF edits and TauPOG-internal correction production remain manual.
Fresh downloads use fixed versions and shallow histories. Cross-filesystem
copies keep the original checkout. See Docs/Manual/FastSetup.md for recovery details.
EOF
}

# =============================================================================
# ==== Reporting and cleanup ====

# The interactive supervisor supplies a separate pipe; normal CLI output stays intact.
setup_event() {
  if [[ ${FASTSETUP_EVENT_FD:-} =~ ^[0-9]+$ ]]; then
    printf '%s\0%s\0' "$1" "$2" >&"$FASTSETUP_EVENT_FD" || true
  fi
}
banner() { setup_event stage "$*"; printf '\n%s\n==== %s ====\n' '=============================================================================' "$*"; }
log()  { setup_event activity "$*"; printf '\n[FastSetup] %s\n' "$*"; }
warn() { setup_event warning "[FastSetup] WARNING: $*"; printf '[FastSetup] WARNING: %s\n' "$*" >&2; warnings+=("$*"); }
die()  { setup_event error "FastSetup: $*"; printf 'FastSetup: %s\n' "$*" >&2; exit 1; }

# ERR trap: report the failing line and how to resume. The checkout may have
# moved by now, so the hint uses its current location.
on_error() {
  [[ $BASHPID == "$$" ]] || return 0 # report once, from the main shell
  error_reported=true
  setup_event error "FastSetup failed at line $1."
  printf 'FastSetup failed at line %s.\n' "$1" >&2
  print_retry
}

print_retry() {
  local script=${repo_dir:+$repo_dir/Utilities/FastSetup.sh} message argument
  # A signal may arrive just after the checkout was renamed.
  if [[ ! -f ${script:-$0} && -f ${target:-}/Utilities/FastSetup.sh ]]; then script=$target/Utilities/FastSetup.sh; fi
  printf -v message 'Fix the error above, then rerun:\n  bash %q' "${script:-$0}"
  for argument in "${args[@]}"; do
    printf -v argument ' %q' "$argument"
    message+=$argument
  done
  printf '%s\n' "$message" >&2
  setup_event retry "$message"
}

on_exit() {
  local status=$?
  [[ $BASHPID == "$$" ]] || return "$status"
  trap - ERR
  set +e
  if ((status != 0)) && ! $cancelled && ! $error_reported; then print_retry; fi
  cleanup
  return "$status"
}

# EXIT trap: remove temporary directories left by an interrupted step.
cleanup() {
  local path
  for path in "${cleanup_paths[@]}"; do rm -rf -- "$path"; done
}

# =============================================================================
# ==== Filesystem and environment helpers ====

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

# Run directly from the current checkout, including after it has moved.
# The helper imports only standard libraries until a verification is requested.
installer_python() {
  python3 "$repo_dir/Utilities/python/Installer/setup_tools.py" "$@"
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
# rename that into place. Keep SRC: edits made while copying must not be lost.
move_dir() { # SRC DST
  local src=$1 dst=$2 status=0
  installer_python rename "$src" "$dst" || status=$?
  case $status in
    0) return ;;
    3) ;;
    *) die "Could not move $src to $dst." ;;
  esac
  log "The destination is on another filesystem; copying and keeping the original."
  make_temp_dir "$(dirname -- "$dst")" move
  cp -a -- "$src/." "$temp_dir/"
  chmod --reference="$src" -- "$temp_dir" # mktemp made it private
  [[ ! -e $dst && ! -L $dst ]] || die "Destination appeared while copying: $dst."
  mv -T -- "$temp_dir" "$dst"
  copied_from=$src
  warn "Original checkout retained at $src. Finish any edits there before manually removing it."
}

# =============================================================================
# ==== Dependency validation and downloads ====

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

# Reject incomplete checkouts before they can be reused or published. Existing
# forks are allowed when their repository name and required files match.
check_repo() { # URL PATH REQUIRED_FILE...
  local url=$1 path=$2 top origin have want
  shift 2
  top=$(git -C "$path" rev-parse --show-toplevel 2>/dev/null) ||
    die "$path exists but is not a Git checkout. Move it away and rerun."
  [[ -z $(git -C "$path" rev-parse --show-cdup) ]] || # PATH must be the checkout's root
    die "$path is inside another Git checkout ($top), not a clone of $url."
  git -C "$path" rev-parse --verify 'HEAD^{commit}' >/dev/null 2>&1 ||
    die "$path has no checked-out commit. Move the incomplete checkout away and rerun."
  origin=$(git -C "$path" remote get-url origin 2>/dev/null) ||
    die "$path has no 'origin' remote; expected a clone of $url."
  have=$(normalize_remote "$origin")
  want=$(normalize_remote "$url")
  if [[ $have != "$want" && ${have##*/} != "${want##*/}" ]]; then
    die "$path is a clone of $origin, not $url. Move it away and rerun."
  fi
  check_payload "$path" "$@"
}

check_payload() { # PATH REQUIRED_FILE...
  local path=$1 file
  shift
  for file in "$@"; do
    [[ -s $path/$file ]] || die "Missing or empty dependency file: $path/$file. Restore it or move the incomplete checkout away and rerun."
  done
}

report_repo() { # URL PATH REF
  local url=$1 path=$2 ref=$3 origin head expected
  origin=$(git -C "$path" remote get-url origin)
  head=$(git -C "$path" rev-parse HEAD)
  expected=$(git -C "$path" rev-parse -q --verify "$ref^{commit}" || true)
  log "Dependency $path: $head"
  if [[ $(normalize_remote "$origin") != "$(normalize_remote "$url")" ]]; then
    warn "$path uses fork or mirror $origin; it was kept unchanged."
  fi
  if [[ $head != "$expected" ]]; then
    warn "$path is at $head, not the pinned $ref; it was kept unchanged."
  fi
  if [[ -n $(git -C "$path" status --porcelain --untracked-files=normal) ]]; then
    warn "$path has local changes; its files were kept unchanged."
  fi
}

download_repo() { # URL PATH REF (PATH must not exist)
  local url=$1 path=$2 ref=$3
  if [[ $ref =~ ^[0-9a-f]{40}$ ]]; then
    git init --quiet "$path"
    git -C "$path" remote add origin "$url"
    git -C "$path" fetch --depth 1 --no-tags origin "$ref"
    git -C "$path" -c advice.detachedHead=false checkout --quiet --detach FETCH_HEAD
  else
    git -c advice.detachedHead=false clone --depth 1 --branch "$ref" -- "$url" "$path"
  fi
}

install_repo() { # URL PATH REF REQUIRED_FILE...
  local url=$1 path=$2 ref=$3
  shift 3
  if [[ ! -e $path && ! -L $path ]]; then
    log "Downloading $url ($ref) into $path"
    mkdir -p -- "$(dirname -- "$path")"
    make_temp_dir "$(dirname -- "$path")" clone
    local stage=$temp_dir/checkout
    # Persist the requirement before changing fitting packages, including on failure.
    if [[ $url == "$COMBINE_URL" || $url == "$HARVESTER_URL" ]]; then
      touch -- "$clean_marker"
    fi
    download_repo "$url" "$stage" "$ref"
    check_repo "$url" "$stage" "$@"
    [[ ! -e $path && ! -L $path ]] || die "Destination appeared during download: $path."
    mv -T -- "$stage" "$path"
  else
    check_repo "$url" "$path" "$@"
    log "Reusing $path"
  fi
  report_repo "$url" "$path" "$ref"
}

# =============================================================================
# ==== Arguments and preflight ====

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
      --non-interactive) non_interactive=true; shift ;;
      --skip-tauidsfs) tauidsfs=false; shift ;;
      --skip-htt) htt=false; shift ;;
      --skip-combine) combine=false; shift ;;
      -h | --help) usage; exit 0 ;;
      *) die "Unknown option or missing value: $1 (see --help)." ;;
    esac
  done
  [[ $jobs =~ ^[1-9][0-9]*$ ]] || die '--jobs must be a positive integer.'
}

check_host() {
  [[ $(uname -s) == Linux ]] || die 'CMSSW needs Linux; run this script on a CMS node or in a CMS container.'
  command -v git >/dev/null || die 'Git is required.'
  command -v python3 >/dev/null || die 'Python 3 is required.'
}

locate_checkout() {
  repo_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd -P)
  [[ -f $repo_dir/README.md && -d $repo_dir/PicoProducer && -d $repo_dir/Fitter ]] ||
    die 'Keep FastSetup.sh in Utilities inside the TauFW checkout.'
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
    die "Destination already exists: $target. Source its setup.sh or choose another --cmssw-dir."
  fi
}

preflight_repo() { # URL PATH REQUIRED_FILE...
  local url=$1 path=$2
  shift 2
  if [[ -e $path || -L $path ]]; then check_repo "$url" "$path" "$@"; fi
}

check_checkout_move() {
  if [[ $repo_dir != "$target" ]]; then
    local worktrees
    worktrees=$(git -C "$repo_dir" worktree list --porcelain | grep -c '^worktree ')
    ((worktrees == 1)) || die 'This clone owns linked worktrees. Use a separate clone for installation; moving this one would break those worktrees.'
  fi
}

check_htt_link() { # LINK EXPECTED_DESTINATION
  if [[ -e $1 || -L $1 ]]; then
    [[ -L $1 && $(realpath -m -- "$1") == "$(realpath -m -- "$2")" ]] ||
      die "HTT destination already contains other files or a different link: $1. Keep it unchanged with --skip-htt, or move it away before rerunning."
  fi
}

uses_local_htt() { # HTT_DIRECTORY
  [[ (-d $1/Electron && ! -L $1/Electron) || (-d $1/Muon && ! -L $1/Muon) ]]
}

preflight_install() {
  clean_marker=$cmssw_dir/.FastSetup-needs-clean
  check_checkout_move
  if [[ -e $cmssw_dir || -L $cmssw_dir ]]; then
    [[ -d $cmssw_dir/src && -d $cmssw_dir/.SCRAM ]] ||
      die "Not a complete CMSSW release area: $cmssw_dir. Move the incomplete area away and rerun."
  fi

  local nano=$cmssw_dir/src/PhysicsTools/NanoAODTools
  if $run2_jme; then
    preflight_repo "$NANOAODTOOLS_URL" "$nano" "${NANOAODTOOLS_FILES[@]}"
  elif [[ -e $nano || -L $nano ]]; then
    die "Standalone NanoAODTools already overrides the release ($nano). Rerun with --run2-jme, or move it outside src."
  fi
  if $tauidsfs; then
    preflight_repo "$TAUIDSFS_URL" "$cmssw_dir/src/TauPOG/TauIDSFs" "${TAUIDSFS_FILES[@]}"
  fi
  if $combine; then
    preflight_repo "$COMBINE_URL" "$cmssw_dir/src/HiggsAnalysis/CombinedLimit" "${COMBINE_FILES[@]}"
    preflight_repo "$HARVESTER_URL" "$cmssw_dir/src/CombineHarvester" "${HARVESTER_FILES[@]}"
  fi
  if $htt; then
    local path=$repo_dir/$HTT_PATH external=$cmssw_dir/external/LeptonEfficiencies component
    if [[ -e $path || -L $path ]]; then
      [[ -d $path && ! -L $path ]] || die "HTT must be a directory: $path. Use --skip-htt to preserve a custom layout."
    fi
    if [[ -e $path/.git || -L $path/.git ]]; then
      check_repo "$HTT_URL" "$path" "${HTT_FILES[@]}"
    elif uses_local_htt "$path"; then
      check_payload "$path" "${HTT_FILES[@]}"
    else
      preflight_repo "$HTT_URL" "$external" "${HTT_FILES[@]}"
      for component in Electron Muon; do check_htt_link "$path/$component" "$external/$component"; done
    fi
  fi
}

# =============================================================================
# ==== Component selection ====

select_components() {
  # The Python runner passes checklist choices as flags before starting Bash.
  # Preserve the exact selection in failure/resume hints, including menu edits.
  args=(--non-interactive --cmssw-dir "$cmssw_dir" --jobs "$jobs")
  if ! $tauidsfs; then args+=(--skip-tauidsfs); fi
  if ! $htt; then args+=(--skip-htt); fi
  if ! $combine; then args+=(--skip-combine); fi
  if $run2_jme; then args+=(--run2-jme); fi
}

# =============================================================================
# ==== CMSSW environment ====

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
  cms_setup=$(realpath -- "$cms_setup")
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
  case $cms_setup in "$repo_dir/"*) cms_setup=$target/${cms_setup#"$repo_dir/"} ;; esac
  repo_dir=$target
  moved=true
}

# =============================================================================
# ==== Selected dependencies ====

# PicoProducer uses the NanoAODTools in CMSSW by default. A standalone checkout
# in src overrides that, so it is only accepted when it was asked for.
install_nanoaodtools() {
  local path=$cmssw_dir/src/PhysicsTools/NanoAODTools
  if $run2_jme; then
    install_repo "$NANOAODTOOLS_URL" "$path" "$NANOAODTOOLS_REF" "${NANOAODTOOLS_FILES[@]}"
  elif [[ -e $path || -L $path ]]; then
    die "Standalone NanoAODTools already overrides the release ($path). Rerun with --run2-jme, or move that checkout outside src and rerun."
  fi
}

install_tauidsfs() {
  install_repo "$TAUIDSFS_URL" "$cmssw_dir/src/TauPOG/TauIDSFs" "$TAUIDSFS_REF" "${TAUIDSFS_FILES[@]}"
}

# Keep the tracked placeholder. Only untracked correction-directory links are
# added; there is no directory swap to roll back and no hidden tracked changes.
install_htt_efficiencies() {
  local htt=$repo_dir/$HTT_PATH external=$cmssw_dir/external/LeptonEfficiencies component exclude
  if [[ -e $htt/.git ]]; then
    # Preserve installations made by the old script or the manual instructions.
    install_repo "$HTT_URL" "$htt" "$HTT_REF" "${HTT_FILES[@]}"
  elif uses_local_htt "$htt"; then
    check_payload "$htt" "${HTT_FILES[@]}"
    warn "Using existing local HTT corrections at $htt; their version is not pinned and their files were kept unchanged."
  else
    install_repo "$HTT_URL" "$external" "$HTT_REF" "${HTT_FILES[@]}"
    mkdir -p -- "$htt"
    exclude=$repo_dir/.git/info/exclude
    mkdir -p -- "$(dirname -- "$exclude")"
    for component in Electron Muon; do
      check_htt_link "$htt/$component" "$external/$component"
      grep -qxF -- "/$HTT_PATH/$component" "$exclude" 2>/dev/null ||
        printf '/%s/%s\n' "$HTT_PATH" "$component" >>"$exclude"
      if [[ ! -L $htt/$component ]]; then ln -s -- "$external/$component" "$htt/$component"; fi
    done
  fi
  # Undo only the old installer's skip-worktree flags. Tracked edits stay visible.
  if git -C "$repo_dir" ls-files -v -- "$HTT_PATH" | grep '^[Ss] ' >/dev/null; then
    log 'Restoring visibility of tracked HTT files in TauFW Git'
    git -C "$repo_dir" ls-files -z -- "$HTT_PATH" | xargs -0 -r git -C "$repo_dir" update-index --no-skip-worktree --
  fi
}

install_combine() {
  install_repo "$COMBINE_URL" "$cmssw_dir/src/HiggsAnalysis/CombinedLimit" "$COMBINE_TAG" "${COMBINE_FILES[@]}"
  install_repo "$HARVESTER_URL" "$cmssw_dir/src/CombineHarvester" "$HARVESTER_TAG" "${HARVESTER_FILES[@]}"
}

# =============================================================================
# ==== Build and verification ====

# Only new fitting packages request a global clean. The marker survives failed
# downloads and interrupted runs, and is removed only after scram clean succeeds.
build_release() {
  cd -- "$cmssw_dir/src"
  if [[ -e $clean_marker ]]; then
    log 'Fitting packages require a clean build'
    scram b clean
    rm -- "$clean_marker"
  fi
  log "Building all packages with $jobs jobs"
  scram b -j"$jobs"
}

verify_python_modules() { # EXPECTED_ROOT MODULE[:SYMBOL]...
  local root=$1
  shift
  installer_python modules --root "$root" "$@" ||
    die 'A Python module is missing, unusable, or comes from another installation (see above).'
}

verify_htt() {
  check_payload "$repo_dir/$HTT_PATH" "${HTT_FILES[@]}"
  installer_python htt "$repo_dir/$HTT_PATH" "${HTT_FILES[@]}" ||
    die 'HTT correction files cannot be read by ROOT (see above).'
}

verify_combine() {
  local executable expected=$cmssw_dir/bin/$SCRAM_ARCH/combine
  executable=$(type -P combine) || die 'combine is not on PATH.'
  [[ $(realpath -- "$executable") == "$(realpath -m -- "$expected")" ]] ||
    die "combine resolves to $executable, not $expected."
  "$executable" --help >/dev/null || die 'The installed combine executable cannot run.'
  verify_python_modules "$cmssw_dir/src/HiggsAnalysis/CombinedLimit" HiggsAnalysis.CombinedLimit.PhysicsModel:PhysicsModel
  installer_python modules --root "$cmssw_dir/src/CombineHarvester" --instantiate \
    CombineHarvester.CombineTools.ch:CombineHarvester ||
    die 'CombineHarvester native bindings cannot be used.'
}

verify_install() {
  local environment_warnings warning
  environment_warnings=$(installer_python environment)
  while IFS= read -r warning; do
    if [[ -n $warning ]]; then warn "$warning"; fi
  done <<< "$environment_warnings"
  log 'Checking TauFW and the selected tools'
  verify_python_modules "$repo_dir" TauFW.PicoProducer TauFW.Histogrammer TauFW.Plotter TauFW.Fitter \
    TauFW.Utilities TauFW.Framework:Framework
  local nano_root
  if $run2_jme; then
    nano_root=$cmssw_dir/src/PhysicsTools/NanoAODTools
  else
    [[ -n ${CMSSW_RELEASE_BASE:-} ]] || die 'The CMSSW release base is unavailable.'
    nano_root=$CMSSW_RELEASE_BASE
  fi
  verify_python_modules "$nano_root" PhysicsTools.NanoAODTools.postprocessing.framework.postprocessor:PostProcessor
  if $run2_jme; then
    verify_python_modules "$nano_root" PhysicsTools.NanoAODTools.postprocessing.modules.jme.jetmetHelperRun2:createJMECorrector
  fi
  installer_python modules correctionlib:CorrectionSet || die 'correctionlib cannot be used.'
  if $tauidsfs; then
    verify_python_modules "$cmssw_dir/src/TauPOG/TauIDSFs" \
      TauPOG.TauIDSFs.TauIDSFTool:TauIDSFTool TauPOG.TauIDSFs.TauIDSFTool:TauESTool
  fi
  if $htt; then verify_htt; fi
  if $combine; then verify_combine; fi
}

# =============================================================================
# ==== User config ====

# Personal and machine settings (Utilities/python/UserConfig): written once,
# never replaced. Created after the move, so it is in the installed checkout.
create_user_config() {
  local path=${TAUFW_USER_CONFIG:-$repo_dir/Analyses/UserConfig.yaml} line
  if line=$(installer_python userconfig --path "$path"); then
    log "$line"
    user_config=$path
  else
    warn "Could not create the user config $path: run python3 taufw.py userconfig later."
  fi
}

# =============================================================================
# ==== Setup manifest ====

# The components this installation selected and verified; recipes that need
# another one get a warning in the menu and in taufw.py check.
write_setup_manifest() {
  local selected=() line
  if $tauidsfs; then selected+=(tauidsfs); fi
  if $htt; then selected+=(htt); fi
  if $combine; then selected+=(combine); fi
  if $run2_jme; then selected+=(run2-jme); fi
  if line=$(installer_python manifest --path "$repo_dir/$SETUP_MANIFEST" "${selected[@]}"); then
    log "$line"
  else
    warn "Could not record the selected components in $repo_dir/$SETUP_MANIFEST: recipes are not checked for them."
  fi
}

# =============================================================================
# ==== Completion summary ====

# Successful setup state is data, never executable shell code.
invalidate_setup_record() {
  rm -f -- "$repo_dir/.git/taufw-setup-state" "$target/.git/taufw-setup-state"
}

write_setup_record() { # DESTINATION
  local destination=$1 stage
  stage=$(mktemp "${destination}.XXXXXX")
  cleanup_paths+=("$stage")
  printf '%s\0' taufw-setup-v1 "$cmssw_dir" "$repo_dir" "$cms_setup" "$SCRAM_ARCH" > "$stage"
  mv -f -- "$stage" "$destination"
}

publish_setup_record() {
  write_setup_record "$repo_dir/.git/taufw-setup-state"
  if [[ -n $copied_from ]]; then
    write_setup_record "$copied_from/.git/taufw-setup-state"
  fi
  if [[ -n ${FASTSETUP_RESULT_FILE:-} ]]; then
    write_setup_record "$FASTSETUP_RESULT_FILE"
  fi
}

summary_line() { # ROLE TEXT
  local role=$1 text=$2 prefix='' color=''
  local locale=${LC_ALL:-${LC_CTYPE:-${LANG:-C}}}
  case $role in
    success) prefix='[OK] '; color=32 ;;
    warning) prefix='[!] '; color=33 ;;
    heading) color=36 ;;
    skipped) color=2 ;;
  esac
  # Event summaries stay plain ASCII; the curses renderer applies its styling.
  if [[ -z ${FASTSETUP_EVENT_FD:-} && (${locale,,} == *utf-8* || ${locale,,} == *utf8*) ]]; then
    case $role in success) prefix='? ' ;; warning) prefix='? ' ;; esac
  fi
  if [[ -z ${FASTSETUP_EVENT_FD:-} && -t 1 && ${TERM:-dumb} != dumb && -z ${NO_COLOR:-} && -n $color ]]; then
    printf '\e[%sm%s%s\e[0m\n' "$color" "$prefix" "$text"
  else
    printf '%s%s\n' "$prefix" "$text"
  fi
}

selection_label() { # SELECTED LABEL
  if "$1"; then
    summary_line success "  $2: Verified this run"
  else
    summary_line skipped "  $2: Not selected"
  fi
}

print_completion_notices() {
  if ((${#warnings[@]})); then
    summary_line heading 'Warnings:'
    local warning
    for warning in "${warnings[@]}"; do summary_line warning "$warning"; done
  fi
  if [[ -n $copied_from ]]; then
    printf '\nOriginal checkout retained at: %s\n' "$copied_from"
  fi
}

print_summary() {
  summary_line success 'Setup complete'
  printf '\nCMSSW        %s\nArchitecture %s\nTauFW        %s\n' "${RELEASE#CMSSW_}" "$SCRAM_ARCH" "$repo_dir"
  if [[ -n $user_config ]]; then printf 'User config  %s (review it)\n' "$user_config"; fi
  printf '\n'
  summary_line heading 'Optional components'
  if ! $tauidsfs && ! $htt && ! $combine && ! $run2_jme; then
    summary_line skipped '  None selected'
  else
    selection_label "$tauidsfs" 'TauIDSFs'
    selection_label "$htt" 'HTT efficiencies'
    selection_label "$combine" 'Combine + CombineHarvester'
    selection_label "$run2_jme" 'Standalone NanoAODTools'
  fi
  if ! $run2_jme; then printf '  NanoAODTools: using the CMSSW version\n'; fi
  # The supervisor collects diagnostics separately; do not repeat its warnings.
  if [[ -z ${FASTSETUP_EVENT_FD:-} ]]; then
    print_completion_notices
  elif [[ -n $copied_from ]]; then
    printf '\nOriginal checkout retained at: %s\n' "$copied_from"
  fi
  if [[ -n ${FASTSETUP_RESULT_FILE:-} ]]; then
    printf '\nPress Enter to close and activate the environment.\n'
  else
    printf '\nActivate in your terminal:\n  source %q\n' "$repo_dir/setup.sh"
  fi
}

main "$@"
