#!/usr/bin/env bash
#
# taufw.sh: TauFW's entry point. Install TauFW once, activate it, define the
# `taufw` command in this shell, then open the interactive menu.
#
# Usage: source taufw.sh [--install] [installer options]
# Then:  taufw                  the menu
#        taufw COMMAND ...      check, plan, start, advance, ... (taufw --help)
# Installation runs in a child process so the worker can use strict mode and
# its interactive screen. Activation runs here so the environment persists.
# The menu opens unless the user config says open_menu_on_start: false.
# All wrapper helpers and temporary variables are removed before returning;
# the `taufw` function and $TAUFW_BASE stay (exported to child shells).

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
# ==== Terminal presentation ====

_taufw_setup_line() { # ROLE TEXT
  local role=$1 text=$2 prefix='' color='' reset=''
  local locale=${LC_ALL:-${LC_CTYPE:-${LANG:-C}}}
  case $role in
    success) prefix='[OK] '; color=32 ;;
    failure) prefix='[FAIL] '; color=31 ;;
    heading) color=36 ;;
  esac
  if [[ ${locale,,} == *utf-8* || ${locale,,} == *utf8* ]]; then
    case $role in success) prefix='? ' ;; failure) prefix='? ' ;; esac
  fi
  if [[ -t 1 && ${TERM:-dumb} != dumb && -z ${NO_COLOR:-} && -n $color ]]; then
    reset=$'\e[0m'
    printf '\e[%sm%s%s%s\n' "$color" "$prefix" "$text" "$reset"
  else
    printf '%s%s\n' "$prefix" "$text"
  fi
}

# =============================================================================
# ==== Current-shell activation ====

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
# ==== The taufw command ====

_taufw_setup_command() { # CHECKOUT
  # taufw [COMMAND ...] runs the Framework's command line of this checkout (no
  # arguments: the menu). A script without this shell's functions runs
  # python3 "$TAUFW_BASE/Framework/scripts/taufw.py" instead.
  export TAUFW_BASE=$1
  taufw() { python3 "$TAUFW_BASE/Framework/scripts/taufw.py" "$@"; }
  export -f taufw
}

# =============================================================================
# ==== Setup pipeline ====

_taufw_setup_main() {
  local checkout record result='' log_path='' status=0 argument install=false
  local -a arguments=() state=()

  # Resolve the checkout from this file, regardless of the caller's directory.
  checkout=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P) || return 1

  # ---- Arguments: plain invocation activates; options request installation ----
  for argument in "$@"; do
    case $argument in
      -h | --help)
        printf '%s\n' 'Usage: source taufw.sh [--install] [installer options]' \
          'Without options: activate a recorded installation, or install first; then' \
          'define the taufw command and open the menu (user config: open_menu_on_start).' \
          '--install: reopen installation even when already installed.' \
          'After it: taufw (the menu), taufw COMMAND ... (taufw --help).'
        bash "$checkout/Utilities/FastSetup.sh" --help
        return $? ;;
      --install) install=true ;;
      *) install=true; arguments+=("$argument") ;;
    esac
  done

  # ---- Read the saved installation, unless installation was requested ----
  record=$checkout/.git/taufw-setup-state
  if ! $install && [[ -r $record ]]; then
    mapfile -d '' -t state < "$record" || state=()
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
  _taufw_setup_activate "${state[1]}" "${state[2]}" "${state[3]}" "${state[4]}" "$log_path" || return $?

  # Use the verified installed checkout, even when setup moved the original.
  _taufw_setup_command "${state[2]}"
  taufw --on-start
}

# =============================================================================
# ==== Entry point and helper cleanup ====

_taufw_setup_return() {
  local status=$1
  unset -f _taufw_setup_main _taufw_setup_record_is_valid \
    _taufw_setup_activate _taufw_setup_line _taufw_setup_command _taufw_setup_return
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
