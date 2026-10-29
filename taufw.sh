#!/usr/bin/env bash
#
# taufw.sh: TauFW's entry point. Install TauFW once, activate it, define the
# `taufw` command in this shell, then open the interactive menu.
#
# Usage: source taufw.sh [--install] [installer options]
#        source taufw.sh --check      what works and what does not; changes nothing
# Then:  taufw                  the menu
#        taufw COMMAND ...      check, plan, start, advance, ... (taufw --help; Tab completes)
# Installation runs in a child process so the worker can use strict mode and
# its interactive screen. Activation runs here so the environment persists; a
# shell that has this release active already is only taken to the checkout.
# Folders of the python/ trees that hold nothing but __pycache__ (left by moved
# packages) are removed. The menu opens unless the user config says
# open_menu_on_start: false.
# All wrapper helpers and temporary variables are removed before returning;
# the `taufw` function (exported to child shells), its Tab completion and
# $TAUFW_BASE stay.

# =============================================================================
# ==== Shell requirements ====

# Keep the first guard POSIX-compatible so other shells can report the error.
if [ -z "${BASH_VERSION:-}" ]; then
  printf 'TauFW setup requires Bash 4.4 or newer.\n' >&2
  return 1 2>/dev/null || exit 1
fi
if [[ ${BASH_SOURCE[0]} == "$0" ]]; then
  printf 'Run: source %q [options]\n' "$0" >&2
  exit 1
fi
if ((BASH_VERSINFO[0] * 100 + BASH_VERSINFO[1] < 404)); then
  printf 'TauFW setup requires Bash 4.4 or newer.\n' >&2
  return 1
fi

# =============================================================================
# ==== Setup pipeline ====

# source taufw.sh, step by step; the steps follow below in this order:
#   1. the arguments: --help; --check (read-only, _taufw_setup_check); --install or
#      installer options (FastSetup again)
#   2. the installation record (_taufw_setup_record_is_valid); none or not valid:
#      FastSetup.sh installs, once
#   3. the activation (_taufw_setup_activate: cmsenv and the checkout), not again
#      when this shell has the release active (_taufw_setup_is_active)
#   4. stale __pycache__ folders of moved packages (_taufw_setup_stale_caches)
#   5. the taufw command and its Tab completion (_taufw_setup_command)
#   6. taufw --on-start: the menu, unless the user config says open_menu_on_start: false

_taufw_setup_main() {
  local checkout record result='' log_path='' status=0 argument install=false check=false stale
  local -a arguments=() state=()

  # Resolve the checkout from this file, regardless of the caller's directory.
  checkout=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P) || return 1

  # ---- Arguments: plain invocation activates; --check diagnoses; options request installation ----
  for argument in "$@"; do
    case $argument in
      -h | --help)
        printf '%s\n' 'Usage: source taufw.sh [--install] [installer options]' \
          '       source taufw.sh --check' \
          'Without options: activate a recorded installation, or install first; then' \
          'define the taufw command and open the menu (user config: open_menu_on_start).' \
          '--install: reopen installation even when already installed.' \
          '--check: what works and what does not (installation, CMSSW, import, components,' \
          '         Python packages, user config, grid proxy); changes nothing.' \
          'After it: taufw (the menu), taufw COMMAND ... (taufw --help; Tab completes).'
        bash "$checkout/Utilities/FastSetup.sh" --help
        return $? ;;
      --check) check=true ;;
      --install) install=true ;;
      *) install=true; arguments+=("$argument") ;;
    esac
  done
  if $check && (($# != 1)); then
    printf 'source taufw.sh --check takes no other option.\n' >&2
    return 2
  fi

  # ---- Read the saved installation, unless installation was requested ----
  record=$checkout/.git/taufw-setup-state
  if ! $install && [[ -r $record ]]; then
    mapfile -d '' -t state < "$record" || state=()
  fi
  if $check; then
    _taufw_setup_check "$record" "${state[@]}"
    return $?
  fi

  # ---- Reuse a valid record, or install once and validate the returned record ----
  while :; do
    if _taufw_setup_record_is_valid "$record" "${state[@]}"; then
      break
    fi
    if [[ -n $result ]]; then
      rm -f -- "$result" "$result.log-path"
      printf 'TauFW setup did not return a usable installation record.\n' >&2
      return 1
    fi

    # The absolute handoff path remains usable even if the worker moves TauFW.
    result=$(mktemp "${TMPDIR:-/tmp}/TauFW-setup-result.XXXXXX") || return 1
    if [[ $result != /* ]]; then
      record=$(realpath -- "$result") || { rm -f -- "$result" "$result.log-path"; return 1; }
      result=$record
    fi

    # Reserve a private sidecar for the interactive supervisor's retained log.
    (umask 077; set -o noclobber; : > "$result.log-path") || {
      rm -f -- "$result"; return 1;
    }

    # Inherit the terminal for the checklist and run screen; wait for dismissal.
    if FASTSETUP_RESULT_FILE=$result bash "$checkout/Utilities/FastSetup.sh" "${arguments[@]}"; then
      record=$result
      mapfile -d '' -t state < "$result" || state=()
    else
      status=$?
      rm -f -- "$result" "$result.log-path"
      return "$status"
    fi
  done

  # ---- Remove the handoff file and activate the verified installation ----
  if [[ -n $result ]]; then
    IFS= read -r log_path < "$result.log-path" || true
    rm -f -- "$result" "$result.log-path"
  fi
  if [[ -z $result ]] && _taufw_setup_is_active "${state[1]}" "${state[4]}"; then
    # Active already (an earlier source in this shell): no cmsenv again, only the checkout.
    cd -- "${state[2]}" || return 1
    printf '\n'
    _taufw_setup_line success 'TauFW environment active'
  else
    _taufw_setup_activate "${state[1]}" "${state[2]}" "${state[3]}" "${state[4]}" "$log_path" || return $?
  fi

  # Use the verified installed checkout, even when setup moved the original.
  stale=$(_taufw_setup_stale_caches "${state[2]}" remove)
  if ((stale > 0)); then
    _taufw_setup_line success "Removed $stale stale __pycache__ folder(s) of moved packages"
  fi
  _taufw_setup_command "${state[2]}"
  taufw --on-start
}

# =============================================================================
# ==== Installation record validation ====

_taufw_setup_record_is_valid() { # RECORD_FILE VERSION RELEASE CHECKOUT CMS_SETUP ARCH
  # Records contain exactly five NUL-separated fields; never execute their data.
  (($# == 6)) || return 1
  local record=$1 version=$2 release=$3 installed=$4 cms_setup=$5 arch=$6

  [[ $version == taufw-setup-v1 &&
     $release == /*/CMSSW_14_1_0_pre4 &&
     $installed == "$release/src/TauFW" && $cms_setup == /* &&
     ($arch == el8_amd64_gcc12 || $arch == el9_amd64_gcc12) &&
     -d $release/.SCRAM/$arch && -d $installed/.git &&
     -f $installed/taufw.sh && -r $installed/.git/taufw-setup-state &&
     -d $installed/PicoProducer && -d $installed/Fitter &&
     -r $cms_setup && ! -e $release/.FastSetup-needs-clean ]] || return 1

  # A retained original must agree with the installed copy's current record.
  # This prevents activation through an old record after a failed reinstall.
  cmp -s -- "$record" "$installed/.git/taufw-setup-state"
}

# =============================================================================
# ==== Current-shell activation ====

_taufw_setup_is_active() { # RELEASE ARCH
  # True if this shell has the release active already (an earlier source, or cmsenv in it).
  [[ ${CMSSW_VERSION:-} == CMSSW_14_1_0_pre4 && ${SCRAM_ARCH:-} == "$2" && -n ${CMSSW_BASE:-} &&
     $(realpath -- "$CMSSW_BASE" 2>/dev/null) == "$1" ]]
}

_taufw_setup_activate() { # RELEASE CHECKOUT CMS_SETUP ARCH [LOG_PATH]
  local release=$1 installed=$2 cms_setup=$3 arch=$4
  local runtime options shopts status=0 had_errexit=false
  # CMS scripts may change options and are not written for strict-mode callers.
  [[ $- == *e* ]] && had_errexit=true
  options=$(set +o)
  shopts=$(shopt -p)
  set +e +u
  source "$cms_setup" || true
  export SCRAM_ARCH=$arch
  if command -v scram >/dev/null && cd -- "$release/src" && runtime=$(scram runtime -sh); then
    eval "$runtime" || true
    if [[ ${CMSSW_VERSION:-} == CMSSW_14_1_0_pre4 &&
          -n ${CMSSW_BASE:-} && $(realpath -- "$CMSSW_BASE") == "$release" ]]; then
      cd -- "$installed" || status=1
    else
      status=1
    fi
  else
    status=1
  fi
  eval "$shopts"
  eval "$options"
  if $had_errexit; then set -e; else set +e; fi
  if ((status != 0)); then
    _taufw_setup_line failure "TauFW environment activation failed. Check CMS software and the release area." >&2
    return "$status"
  fi
  printf '\n'
  _taufw_setup_line success 'TauFW environment active'
  if [[ -n ${5:-} ]]; then
    printf '\nInstallation log: %s\n' "$5"
  fi

}

# =============================================================================
# ==== Stale __pycache__ folders ====

_taufw_setup_stale_caches() { # CHECKOUT [remove]
  # A folder of a package's python/ tree that holds nothing but __pycache__ is
  # what a moved or deleted package leaves behind; Python would import it as an
  # empty namespace package. Print how many there are; with `remove`, delete
  # them (and a folder that is empty only because of that). Folders with any
  # other file, symbolic links and the python/ folders themselves are kept.
  # A subshell, so the shell options stay the caller's.
  (
    shopt -s nullglob dotglob
    declare -A emptied=()
    local count=0 directory parent
    local -a entries roots=("$1"/*/python)
    if ((${#roots[@]} == 0)); then  # find without a folder would search the current one
      printf '0\n'
      exit 0
    fi
    while IFS= read -r -d '' directory; do
      entries=("$directory"/*)
      if { ((${#entries[@]} == 1)) && [[ ${entries[0]##*/} == __pycache__ && -d ${entries[0]} &&
                                        ! -L ${entries[0]} ]]; } ||
         { ((${#entries[@]} == 0)) && [[ -n ${emptied[$directory]:-} ]]; }; then
        count=$((count + 1))
        if [[ ${2:-} == remove ]]; then
          rm -rf -- "$directory"
          parent=${directory%/*}
          emptied[$parent]=1
        fi
      fi
    done < <(find "${roots[@]}" -mindepth 1 -depth -type d ! -name __pycache__ ! -path '*/__pycache__/*' \
                  -print0 2>/dev/null)
    printf '%s\n' "$count"
  )
}

# =============================================================================
# ==== The taufw command ====

_taufw_setup_command() { # CHECKOUT
  # taufw [COMMAND ...] runs the Framework's command line of this checkout (no
  # arguments: the menu). A script without this shell's functions runs
  # python3 "$TAUFW_BASE/Framework/scripts/taufw.py" instead.
  export TAUFW_BASE=$1
  taufw() { python3 "$TAUFW_BASE/Framework/scripts/taufw.py" "$@"; }
  export -f taufw
  complete -o filenames -F _taufw_complete taufw
}

# Tab completion of taufw (stays after sourcing). The commands and options are
# those of Framework/scripts/taufw.py (build_parser; Tests/Framework checks it):
# a command's arguments complete to folders, recipe files (.yml, .yaml, .json)
# for the commands that take a recipe, and the choices of configs.
_taufw_complete() {
  local current=${COMP_WORDS[COMP_CWORD]} previous=${COMP_WORDS[COMP_CWORD - 1]} command=${COMP_WORDS[1]:-}
  local options=''
  COMPREPLY=()
  if ((COMP_CWORD == 1)); then
    mapfile -t COMPREPLY < <(compgen -W 'check plan start advance retry status init configs userconfig version
                                         -h --help' -- "$current")
    return
  fi
  case $command in
    check) options='-h --help -v --verbose' ;;
    plan) options='-h --help -v --verbose --local -m --maxevts' ;;
    start) options='-h --help -v --verbose --wait --poll --run-root' ;;
    advance) options='-h --help -v --verbose --wait --poll --take-lock' ;;
    retry) options='-h --help -v --verbose --wait --poll --take-lock' ;;
    status) options='-h --help -v --verbose' ;;
    init) options='-h --help -v --verbose --from --root' ;;
    configs) options='-h --help -v --verbose' ;;
    userconfig) options='-h --help -v --verbose' ;;
    version) options='-h --help -v --verbose --check' ;;
    *) return ;;
  esac
  case $previous in
    --poll | -m | --maxevts) return ;;
    --run-root | --root) mapfile -t COMPREPLY < <(compgen -d -- "$current"); return ;;
    --from) mapfile -t COMPREPLY < <(compgen -d -- "$current"; _taufw_complete_recipes "$current")
            return ;;
  esac
  if [[ $current == -* ]]; then
    mapfile -t COMPREPLY < <(compgen -W "$options" -- "$current")
    return
  fi
  case $command in
    check | plan | start)
      mapfile -t COMPREPLY < <(compgen -d -- "$current"; _taufw_complete_recipes "$current") ;;
    advance | retry | status) mapfile -t COMPREPLY < <(compgen -d -- "$current") ;;
    configs) mapfile -t COMPREPLY < <(compgen -W 'list update' -- "$current") ;;
  esac
}

_taufw_complete_recipes() { # WORD
  # Recipe files: .yml, .yaml and .json (without extglob, which the user's shell may not have on).
  local suffix
  for suffix in yml yaml json; do
    compgen -f -X '!*.'"$suffix" -- "$1"
  done
}

# =============================================================================
# ==== Read-only check ====

_taufw_setup_check() { # RECORD_FILE [VERSION RELEASE CHECKOUT CMS_SETUP ARCH]
  # source taufw.sh --check: what works and what does not. Changes nothing in
  # this shell: what needs CMSSW runs in a subshell. Status 1 if TauFW cannot
  # work (no valid installation, no CMSSW, no import); warnings do not count.
  local record=$1
  shift
  _taufw_setup_line heading 'TauFW check (nothing is changed)'
  if ! _taufw_setup_record_is_valid "$record" "$@"; then
    _taufw_setup_line failure 'Installation: no valid installation record (source taufw.sh installs or repairs it)'
    return 1
  fi
  local release=$2 installed=$3 cms_setup=$4 arch=$5
  _taufw_setup_line success "Installation: $installed ($arch)"
  if _taufw_setup_is_active "$release" "$arch"; then
    _taufw_setup_line success 'CMSSW: active in this shell'
  else
    _taufw_setup_line warning 'CMSSW: not active in this shell (source taufw.sh activates it); checked in a subshell'
  fi
  (
    local status=0 error role text timeleft stale
    if ! _taufw_setup_is_active "$release" "$arch" &&
       ! _taufw_setup_activate "$release" "$installed" "$cms_setup" "$arch" >/dev/null 2>&1; then
      _taufw_setup_line failure 'CMSSW: activation failed (check CMS software and the release area)'
      exit 1
    fi
    if error=$(python3 -c 'import TauFW.Framework' 2>&1); then
      _taufw_setup_line success 'TauFW: imports'
    else
      _taufw_setup_line failure "TauFW: import failed: ${error##*$'\n'}"
      status=1
    fi
    # The installed components, the Python packages and the user config: one ROLE<TAB>TEXT line each.
    while IFS=$'\t' read -r role text; do
      _taufw_setup_line "$role" "$text"
    done < <(python3 "$installed/Framework/python/_internal/installer/setup_tools.py" report \
               --manifest "$installed/Framework/python/_internal/setup_manifest.json" 2>&1 ||
             printf 'failure\tsetup_tools.py report failed\n')
    if ! command -v voms-proxy-info >/dev/null; then
      _taufw_setup_line warning 'Grid proxy: voms-proxy-info not found'
    elif timeleft=$(voms-proxy-info --timeleft 2>/dev/null) && [[ $timeleft =~ ^[0-9]+$ ]] && ((timeleft > 0)); then
      _taufw_setup_line success "$(printf 'Grid proxy: valid for %dh %02dm' \
                                    $((timeleft / 3600)) $((timeleft % 3600 / 60)))"
    else
      _taufw_setup_line warning "Grid proxy: none or expired (the menu's Grid Certificate makes one)"
    fi
    stale=$(_taufw_setup_stale_caches "$installed")
    if ((stale > 0)); then
      _taufw_setup_line warning \
        "$stale stale __pycache__ folder(s) of moved packages: the next source taufw.sh removes them"
    fi
    exit "$status"
  )
}

# =============================================================================
# ==== Terminal presentation ====

_taufw_setup_line() { # ROLE TEXT
  local role=$1 text=$2 prefix='' color='' reset=''
  local locale=${LC_ALL:-${LC_CTYPE:-${LANG:-C}}}
  case $role in
    success) prefix='[OK] '; color=32 ;;
    warning) prefix='[!] '; color=33 ;;
    failure) prefix='[FAIL] '; color=31 ;;
    heading) color=36 ;;
  esac
  if [[ ${locale,,} == *utf-8* || ${locale,,} == *utf8* ]]; then
    case $role in success) prefix='✓ ' ;; warning) prefix='! ' ;; failure) prefix='✗ ' ;; esac
  fi
  if [[ -t 1 && ${TERM:-dumb} != dumb && -z ${NO_COLOR:-} && -n $color ]]; then
    reset=$'\e[0m'
    printf '\e[%sm%s%s%s\n' "$color" "$prefix" "$text" "$reset"
  else
    printf '%s%s\n' "$prefix" "$text"
  fi
}

# =============================================================================
# ==== Entry point and helper cleanup ====

_taufw_setup_return() {
  local status=$1
  unset -f _taufw_setup_main _taufw_setup_record_is_valid _taufw_setup_is_active \
    _taufw_setup_activate _taufw_setup_line _taufw_setup_stale_caches _taufw_setup_check \
    _taufw_setup_command _taufw_setup_return
  return "$status"
}

# Conditional invocation prevents caller errexit/ERR traps from interrupting
# cleanup. Only the final return status is exposed to the caller.
if _taufw_setup_main "$@"; then
  _taufw_setup_return 0
else
  _taufw_setup_return "$?"
fi
return $?
