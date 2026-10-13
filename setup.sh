#!/usr/bin/env bash
# Source this entry point to install TauFW or activate a completed installation.
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

_taufw_setup_main() {
  local checkout record result='' status=0 argument install=false
  local release installed cms_setup arch runtime options shopts had_errexit=false
  local -a arguments=() state=()
  checkout=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P) || return 1
  for argument in "$@"; do
    case $argument in
      -h | --help)
        printf '%s\n' 'Usage: source setup.sh [--install] [installer options]' \
          'Without options: activate a recorded installation, or install first.' \
          '--install: reopen installation even when already installed.'
        bash "$checkout/Utilities/FastSetup.sh" --help
        return $? ;;
      --install) install=true ;;
      *) install=true; arguments+=("$argument") ;;
    esac
  done
  record=$checkout/.git/taufw-setup-state
  if ! $install && [[ -r $record ]]; then
    mapfile -d '' -t state < "$record" || state=()
  fi
  while :; do
    if [[ ${#state[@]} == 5 && ${state[0]} == taufw-setup-v1 &&
        ${state[1]} == /*/CMSSW_14_1_0_pre4 &&
        ${state[2]} == "${state[1]}/src/TauFW" && ${state[3]} == /* &&
        (${state[4]} == el8_amd64_gcc12 || ${state[4]} == el9_amd64_gcc12) &&
        -d ${state[1]}/.SCRAM/${state[4]} && -d ${state[2]}/.git &&
        -f ${state[2]}/setup.sh && -r ${state[2]}/.git/taufw-setup-state &&
        -d ${state[2]}/PicoProducer &&
        -d ${state[2]}/Fitter && -r ${state[3]} &&
        ! -e ${state[1]}/.FastSetup-needs-clean ]] &&
        cmp -s -- "$record" "${state[2]}/.git/taufw-setup-state"; then
      break
    fi
    if [[ -n $result ]]; then
      rm -f -- "$result"
      printf 'TauFW setup did not return a usable installation record.\n' >&2
      return 1
    fi
    result=$(mktemp "${TMPDIR:-/tmp}/TauFW-setup-result.XXXXXX") || return 1
    if [[ $result != /* ]]; then
      record=$(realpath -- "$result") || { rm -f -- "$result"; return 1; }
      result=$record
    fi
    if FASTSETUP_RESULT_FILE=$result bash "$checkout/Utilities/FastSetup.sh" "${arguments[@]}"; then
      record=$result
      mapfile -d '' -t state < "$result" || state=()
    else
      status=$?
      rm -f -- "$result"
      return "$status"
    fi
  done
  [[ -z $result ]] || rm -f -- "$result"
  release=${state[1]}; installed=${state[2]}; cms_setup=${state[3]}; arch=${state[4]}
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
    printf 'TauFW environment activation failed. Check CMS software and the release area.\n' >&2
    return "$status"
  fi
  printf 'TauFW environment active: %s\n' "$installed"
}

# Conditional invocation prevents caller errexit/ERR traps from interrupting
# cleanup. Only the final return status is exposed to the caller.
_taufw_setup_return() {
  local status=$1
  unset -f _taufw_setup_main _taufw_setup_return
  return "$status"
}
if _taufw_setup_main "$@"; then
  _taufw_setup_return 0
else
  _taufw_setup_return "$?"
fi
return $?
