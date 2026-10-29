# Author: Yagizhan Dinckurt (October 2026) (yagizdkurt)
"""TauFW release metadata and advisory version checks; no work is done on import.

The tracked _internal/version.json owns the version and the HTTPS update source.
Only (major, minor) determines whether to notify; the third number identifies
beta/nonstable changes. A newer major/minor is advertised even with a nonzero
third number. This is TauFW's version policy, not Semantic Versioning.

VersionChecker.status() starts at most one daemon thread and returns immediately.
check() refreshes explicitly on the caller's thread (the version --check CLI).
Nothing downloads or modifies TauFW code, and failures never prevent using it.
"""
import hashlib
import json
import os
from pathlib import Path
import re
import tempfile
import threading
import time
from urllib.parse import urlsplit
from urllib.request import Request, urlopen

__all__ = ['current_version', 'is_newer_version', 'VersionChecker']

MANIFEST_PATH = Path(__file__).resolve().parent / 'version.json'
SUCCESS_TTL = 24 * 60 * 60  # seconds before checking a successful answer again
FAILURE_TTL = 60 * 60       # seconds before retrying a failed request
HTTP_TIMEOUT = 3           # seconds per blocking socket operation, not a total deadline
MAX_MANIFEST_BYTES = 64 * 1024
VERSION_PATTERN = re.compile(r'(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)', re.ASCII)


def _parts(version):
    if not isinstance(version, str) or not VERSION_PATTERN.fullmatch(version):
        raise ValueError('TauFW version must have three nonnegative integers: X.Y.Z')
    return tuple(int(part) for part in version.split('.'))


def is_newer_version(installed, latest):
    """Whether latest has a greater (major, minor); beta-only changes never notify."""
    return _parts(latest)[:2] > _parts(installed)[:2]


def _manifest(raw):
    if len(raw) > MAX_MANIFEST_BYTES:
        raise ValueError('Version manifest is too large')
    data = json.loads(raw)
    if not isinstance(data, dict) or data.get('project') != 'TauFW':
        raise ValueError('Not a TauFW version manifest')
    if type(data.get('schema_version')) is not int or data['schema_version'] != 1:
        raise ValueError('Unsupported TauFW version manifest schema')
    _parts(data.get('version'))
    return data


def _read_manifest(path):
    with Path(path).open('rb') as stream:
        return _manifest(stream.read(MAX_MANIFEST_BYTES + 1))


def current_version(manifest_path=None):
    """The local version only; no network, Git, cache, or environment required."""
    return _read_manifest(MANIFEST_PATH if manifest_path is None else manifest_path)['version']


def _fetch_manifest(source):
    request = Request(source, headers={'User-Agent': 'TauFW-version-check', 'Accept': 'application/json'})
    with urlopen(request, timeout=HTTP_TIMEOUT) as response:
        if urlsplit(response.geturl()).scheme != 'https':
            raise ValueError('Version source redirected outside HTTPS')
        return _manifest(response.read(MAX_MANIFEST_BYTES + 1))


class VersionChecker:
    """One menu's checker; the per-user cache stores remote facts, not comparison results.

    manifest_path/cache_dir allow isolated tests. Reading metadata and cache at
    construction never starts a request. Status is plain data for any UI.
    """

    def __init__(self, manifest_path=None, cache_dir=None):
        self._lock = threading.Lock()
        self._checking = False
        self._record = {}
        self._cache_path = None
        self._source = None
        self._local_error = None
        self.installed = 'unknown'
        self.disabled = os.environ.get('TAUFW_NO_VERSION_CHECK', '').lower() in ('1', 'true', 'yes')
        try:
            local = _read_manifest(MANIFEST_PATH if manifest_path is None else manifest_path)
            self.installed = local['version']
            source = local.get('update_manifest_url', '')
            parts = urlsplit(source)
            if parts.scheme != 'https' or not parts.hostname or parts.username or parts.password:
                raise ValueError('update_manifest_url must be an HTTPS URL without credentials')
            self._source = source
        except (OSError, ValueError, TypeError) as error:
            self._local_error = str(error)
            return
        try:
            directory = Path(cache_dir) if cache_dir is not None else (
                Path(os.environ['XDG_CACHE_HOME']) / 'taufw' if os.environ.get('XDG_CACHE_HOME')
                else Path.home() / '.cache' / 'taufw')
            self._cache_path = directory / ('version-' + hashlib.sha256(source.encode()).hexdigest() + '.json')
            self._read_cache()
        except (OSError, ValueError, RuntimeError):
            pass  # A missing/unwritable user cache must not prevent using TauFW.

    def _read_cache(self):
        with self._cache_path.open('rb') as stream:
            raw = stream.read(MAX_MANIFEST_BYTES + 1)
        if len(raw) > MAX_MANIFEST_BYTES:
            return
        record = json.loads(raw)
        if not isinstance(record, dict) or record.get('source') != self._source:
            return
        for key in ('attempted_at', 'checked_at'):
            stamp = record.get(key, 0)
            if type(stamp) not in (int, float) or not 0 <= stamp <= time.time():
                return
        if record.get('latest') is not None:
            _parts(record['latest'])
        if record.get('error') is not None and not isinstance(record['error'], str):
            return
        if (record.get('latest') is None and not record.get('error')) or (
                record.get('latest') is not None and not record.get('checked_at')):
            return
        self._record = record

    def _due(self, now):
        age = now - self._record.get('attempted_at', 0)
        ttl = FAILURE_TTL if self._record.get('error') else SUCCESS_TTL
        return not self._record or age < 0 or age >= ttl

    def status(self, start=True):
        """A snapshot; optionally start a due check without waiting for HTTP."""
        with self._lock:
            now = time.time()
            if start and not self.disabled and not self._local_error and not self._checking and self._due(now):
                self._checking = True
                threading.Thread(target=self._refresh, name='taufw-version-check', daemon=True).start()
            latest = self._record.get('latest')
            checked_at = self._record.get('checked_at')
            available = latest is not None and is_newer_version(self.installed, latest)
            error = self._local_error or self._record.get('error')
            state = ('disabled' if self.disabled else 'checking' if self._checking else
                     'unavailable' if error else 'available' if available else 'current' if latest else 'unchecked')
            return dict(installed=self.installed, latest=latest, status=state, checking=self._checking,
                        available=available, error=error, checked_at=checked_at,
                        stale=bool(checked_at is not None and (error or now - checked_at >= SUCCESS_TTL
                                                               or now < checked_at)))

    def check(self):
        """Force a synchronous check; honor the user's offline switch and share an in-flight request."""
        with self._lock:
            refresh = not self.disabled and not self._local_error and not self._checking
            if refresh:
                self._checking = True
        if refresh:
            self._refresh()
        return self.status(start=False)

    def _refresh(self):
        try:
            latest = _fetch_manifest(self._source)['version']
            error = None
        except Exception as failure:
            latest, error = None, str(failure) or type(failure).__name__
        now = time.time()
        with self._lock:
            record = dict(self._record, source=self._source, attempted_at=now, error=error)
            if error is None:
                record.update(latest=latest, checked_at=now)
            self._record = record
            self._checking = False
        self._write_cache(record)

    def _write_cache(self, record):
        if self._cache_path is None:
            return
        temporary = None
        try:
            self._cache_path.parent.mkdir(parents=True, exist_ok=True)
            with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', dir=self._cache_path.parent,
                                             prefix='.version-', delete=False) as stream:
                temporary = Path(stream.name)
                json.dump(record, stream)
            os.replace(str(temporary), str(self._cache_path))
        except OSError:
            pass  # Retain the in-memory answer on a readonly or unavailable filesystem.
        finally:
            if temporary is not None:
                try:
                    temporary.unlink(missing_ok=True)
                except OSError:
                    pass
