# Author: Yagizhan Dinckurt (October 2026) (yagizdkurt)
"""Config templates: the data files in Configs/<Module>/ that analyses copy into their bundles and edit there.

    Configs/
      README.md                       the rules (for analysts and maintainers)
      configs.lock                    id, version and content hash of every template (`taufw.py configs update`)
      Plotter/samples/v15_2025.yml    a template: a YAML mapping that starts with the taufw_config header

    taufw_config:                     # set by the maintainers: analysts edit the values below, never these lines
      id: plotter.samples_v15_2025    # unique, never changes; starts with the module directory (Plotter -> plotter)
      version: 3                      # the content version: raised when a value changes
      schema: 1                       # the format version: which reader of the module understands the file
      description: the samples of the v15 tuples for 2025
    <content>                         # read by the module (its reader skips taufw_config)

Maintainers edit a template, then run `taufw.py configs update`: a template whose content changed (the parsed values
without the header: comments and layout do not count) gets version + 1 in its file, and the lock is rewritten. A
version raised by hand is kept. Nothing is written if any template has a problem. Tests/Framework/test_configs.py
fails while the lock is not up to date, so a changed value is never left without a new version.

Analysts copy a template into their bundle (the header comes with it) and edit the values. taufw.py check, plan and
start warn when the template of a copy has a newer version (copy_warnings): the maintainers changed it since the copy.
The warning stays as long as the copy is older; keeping an old copy on purpose is allowed.

Only YAML templates (.yml, .yaml) are allowed in Configs/ (no Python, no JSON: *.json is ignored by git), besides
README.md files and configs.lock.

Inputs:  the Configs/ directory, a bundle directory.
Outputs: scan(), lock_changes() and copy_warnings() read only; update() writes the raised versions and the lock.

Public API:
  scan(directory=None) -> ConfigScan             the templates and the problems of a Configs/ directory
                                                 (every function: directory None -> CONFIGS_DIR)
  lock_changes(directory) -> (ConfigScan, [LockChange])   what `update` would do (empty: the lock is up to date)
  update(directory) -> (ConfigScan, [LockChange])  raise the versions of changed templates, rewrite the lock
  copy_warnings(bundle_dir, directory) -> [(file, message)]   copies in a bundle whose template is newer (or gone)
  read_header(data) -> ConfigHeader              the header of a parsed YAML mapping (ConfigError if invalid)
  content_hash(data) -> str                      sha256 of the values without the header
  ConfigHeader, ConfigTemplate, ConfigScan, LockChange, ConfigError, HEADER_KEY, LOCK_NAME
"""
import hashlib
import json
import os
import re
from dataclasses import dataclass, field
from typing import Optional, Tuple

from TauFW.Framework.defaults import CONFIGS_DIR, RECIPE_NAME, default_file_io

__all__ = ['scan', 'lock_changes', 'update', 'copy_warnings', 'read_header', 'content_hash', 'ConfigHeader',
           'ConfigTemplate', 'ConfigScan', 'LockChange', 'ConfigError', 'HEADER_KEY', 'LOCK_NAME']


# =============================================================================
# ================================= CONSTANTS =================================


HEADER_KEY  = "taufw_config"           # the header mapping at the top of every template (and of its copies)
LOCK_NAME   = "configs.lock"           # in Configs/: id, version and content hash of every template
EXTENSIONS  = ('.yml', '.yaml')        # template files
OTHER_FILES = ('README.md', LOCK_NAME)  # the only other files allowed in Configs/
SKIPPED     = ('__pycache__', 'taufw_runs')  # directories never scanned (nor hidden ones)
IDEXP       = re.compile(r"^[a-z][a-z0-9_]*(\.[a-z0-9_]+)+$")  # e.g. plotter.samples_v15_2025
VERSIONEXP  = re.compile(r"^(?P<head>[ \t]+version:[ \t]*)(?P<number>\d+)", re.M)  # a version line of the header
LOCK_HEADER = ("# Configs/configs.lock: the content version and hash of every template in Configs/.\n"
               "# Written by `taufw.py configs update` (Framework/python/configs.py); do not edit by hand.\n"
               "# id  version  sha256 of the values without the taufw_config header\n")


# =============================================================================
# ================================= PIPELINE ==================================


def scan(directory=None, files=None):
    """The templates of a Configs/ directory (default: CONFIGS_DIR) and its problems (never raises for a bad
    template)."""
    directory = directory or CONFIGS_DIR
    files = files or default_file_io()
    templates, problems = [], []
    for relative in _tree(directory):
        name = os.path.basename(relative)
        if os.path.splitext(name)[1] not in EXTENSIONS:
            if name not in OTHER_FILES:
                problems.append("%s: not a YAML template (Configs/ holds only .yml/.yaml data files, README.md "
                                "and %s)" % (relative, LOCK_NAME))
            continue
        try:
            templates.append(_read_template(directory, relative, files))
        except ConfigError as error:
            problems.append("%s: %s" % (relative, error))
    seen = {}
    for template in templates:
        if template.header.id in seen:
            problems.append("%s: id %r is also used by %s" % (template.path, template.header.id,
                                                              seen[template.header.id]))
        seen.setdefault(template.header.id, template.path)
    lock = _read_lock(directory, files, problems)
    return ConfigScan(directory=directory, templates=tuple(templates), problems=tuple(problems), lock=lock)


def lock_changes(directory=None, files=None):
    """(ConfigScan, [LockChange]): what `update` would change. No changes and no problems: the lock is up to date."""
    configs = scan(directory, files)
    changes = []
    for template in configs.templates:
        header, locked = template.header, configs.lock.get(template.header.id)
        if locked is None:
            changes.append(LockChange(template, 'new', header.version))
        elif template.sha == locked[1] and header.version == locked[0]:
            continue
        elif header.version < locked[0]:
            changes.append(LockChange(template, 'lowered', locked[0]))
        elif header.version > locked[0]:  # raised by hand, with or without a changed value
            changes.append(LockChange(template, 'raised' if template.sha != locked[1] else 'raised only',
                                      header.version))
        else:
            changes.append(LockChange(template, 'changed', header.version + 1))
    known = {template.header.id for template in configs.templates}
    changes.extend(LockChange(None, 'removed', version, config_id=config_id)
                   for config_id, (version, _) in sorted(configs.lock.items()) if config_id not in known)
    return configs, changes


def update(directory=None, files=None):
    """Raise the version of every template whose values changed, and rewrite the lock. Nothing is written if a
    template has a problem or a version was lowered (see ConfigScan.problems and the 'lowered' changes)."""
    files = files or default_file_io()
    configs, changes = lock_changes(directory, files)
    directory = configs.directory
    if configs.problems or any(change.kind == 'lowered' for change in changes):
        return configs, changes
    for change in changes:
        if change.kind == 'changed':
            _raise_version(os.path.join(directory, change.template.path), change.version, files)
    entries = {t.header.id: (t.header.version, t.sha) for t in configs.templates}
    entries.update({c.template.header.id: (c.version, c.template.sha) for c in changes if c.kind == 'changed'})
    if changes or not os.path.isfile(os.path.join(directory, LOCK_NAME)):
        lines = ["%s %d %s\n" % (config_id, version, sha) for config_id, (version, sha) in sorted(entries.items())]
        files.write_bytes(os.path.join(directory, LOCK_NAME), (LOCK_HEADER + "".join(lines)).encode('utf-8'),
                          overwrite=True)
    return configs, changes


def copy_warnings(bundle_dir, directory=None, files=None):
    """[(file relative to the bundle, message)] for the copies of templates in a bundle whose template has another
    version (or is gone), and for copies with an invalid header. Files without a taufw_config header are skipped."""
    files = files or default_file_io()
    if not bundle_dir or not os.path.isdir(bundle_dir):
        return []
    templates = {template.header.id: template for template in scan(directory, files).templates}
    warnings = []
    for relative in _tree(bundle_dir):
        if os.path.splitext(relative)[1] not in EXTENSIONS or relative == RECIPE_NAME:
            continue
        path = os.path.join(bundle_dir, relative)
        if HEADER_KEY not in files.read_text(path):  # quick: most bundle files are not copies of templates
            continue
        try:
            copy = read_header(files.read_yaml(path))
        except Exception as error:  # YAML syntax or header problem
            warnings.append((relative, "invalid %s header: %s" % (HEADER_KEY, error)))
            continue
        if copy is None:
            continue
        template = templates.get(copy.id)
        if template is None:
            warnings.append((relative, "copy of %s, which is not in Configs/ any more (renamed or removed): see "
                                       "Configs/README.md" % (copy.id)))
        elif template.header.version > copy.version:
            warnings.append((relative, "copy of %s version %d, but Configs/%s is version %d now: the maintainers "
                                       "changed it since it was copied. Compare the two, and take over the changes "
                                       "or keep your copy on purpose"
                             % (copy.id, copy.version, _posix(template.path), template.header.version)))
        elif template.header.version < copy.version:
            warnings.append((relative, "copy of %s version %d, but Configs/%s is version %d: analysts edit the "
                                       "values of a copy, never its %s header"
                             % (copy.id, copy.version, _posix(template.path), template.header.version, HEADER_KEY)))
    return warnings


# =============================================================================
# ================================== HEADER ===================================


def read_header(data):
    """The ConfigHeader of a parsed YAML file, or None if it has no taufw_config key. Raises ConfigError."""
    if not isinstance(data, dict) or HEADER_KEY not in data:
        return None
    header = data[HEADER_KEY]
    if not isinstance(header, dict):
        raise ConfigError("%s must be a mapping with id, version, schema and description" % (HEADER_KEY))
    unknown = sorted(set(header) - set(ConfigHeader.KEYS))
    if unknown:
        raise ConfigError("unknown %s key(s) %s (known: %s)" % (HEADER_KEY, ', '.join(map(str, unknown)),
                                                                ', '.join(ConfigHeader.KEYS)))
    config_id, description = header.get('id'), header.get('description')
    if not isinstance(config_id, str) or not IDEXP.match(config_id):
        raise ConfigError("id must be <module>.<name> in lower case letters, digits and '_' (got %r)" % (config_id,))
    for key in ('version', 'schema'):
        if not isinstance(header.get(key), int) or isinstance(header.get(key), bool) or header.get(key) < 1:
            raise ConfigError("%s must be a whole number >= 1 (got %r)" % (key, header.get(key)))
    if not isinstance(description, str) or not description.strip():
        raise ConfigError("description must be a non-empty text")
    return ConfigHeader(id=config_id, version=header['version'], schema=header['schema'],
                        description=description.strip())


def content_hash(data):
    """sha256 of the values of a template without its header: comments, layout and key order do not count."""
    values = {key: value for key, value in data.items() if key != HEADER_KEY}
    text = json.dumps(values, sort_keys=True, ensure_ascii=False, separators=(',', ':'), default=str)
    return hashlib.sha256(text.encode('utf-8')).hexdigest()


# =============================================================================
# ================================== RECORDS ==================================


@dataclass(frozen=True)
class ConfigHeader:
    """The taufw_config header of a template or of a copy."""
    KEYS = ('id', 'version', 'schema', 'description')
    id:          str
    version:     int
    schema:      int
    description: str


@dataclass(frozen=True)
class ConfigTemplate:
    """One template of Configs/. path: relative to Configs/; sha: content_hash of its values."""
    path:   str
    header: ConfigHeader
    sha:    str


@dataclass(frozen=True)
class ConfigScan:
    """The templates of a Configs/ directory, its problems and its lock ({id: (version, sha)})."""
    directory: str
    templates: Tuple[ConfigTemplate, ...] = ()
    problems:  Tuple[str, ...] = ()
    lock:      dict = field(default_factory=dict)


@dataclass(frozen=True)
class LockChange:
    """What `update` does for one template. kind:
        new           not in the lock yet: locked with its version
        changed       values changed, same version: the file gets `version` (+1) and is locked
        raised        values changed and the version was raised by hand: locked with it
        raised only   the version was raised by hand, the values did not change: locked with it
        lowered       the version is lower than the locked one: a problem, nothing is written
        removed       in the lock, but no template has the id any more: removed from the lock"""
    template:  Optional[ConfigTemplate]
    kind:      str
    version:   int
    config_id: str = ""

    def __post_init__(self):
        if self.template is not None and not self.config_id:
            object.__setattr__(self, 'config_id', self.template.header.id)

    def __str__(self):
        where = " (%s)" % (_posix(self.template.path)) if self.template else ""
        texts = {'new': "new, locked with version %d", 'changed': "values changed: version raised to %d",
                 'raised': "version raised by hand to %d", 'raised only': "version raised to %d without a change",
                 'lowered': "version lower than the locked version %d: never lower a version",
                 'removed': "removed from Configs/ (was version %d)"}
        return "%s%s: %s" % (self.config_id, where, texts[self.kind] % (self.version))


class ConfigError(ValueError):
    """A template or a copy with an invalid taufw_config header."""


# =============================================================================
# ================================== HELPERS ==================================


def _read_template(directory, relative, files):
    """The ConfigTemplate of one file of Configs/ (raises ConfigError)."""
    try:
        data = files.read_yaml(os.path.join(directory, relative))
    except Exception as error:
        raise ConfigError("cannot read the YAML: %s" % (error))
    header = read_header(data)
    if header is None:
        raise ConfigError("no %s header (every template starts with one, see Configs/README.md)" % (HEADER_KEY))
    if '/' not in _posix(relative):
        raise ConfigError("templates live in Configs/<Module>/, not directly in Configs/")
    module = _posix(relative).split('/')[0].lower()
    if header.id.split('.')[0] != module:
        raise ConfigError("id %r must start with %r (its module directory)" % (header.id, module))
    text = files.read_bytes(os.path.join(directory, relative)).decode('utf-8')
    start, end = _header_span(text)
    if len(VERSIONEXP.findall(text[start:end])) != 1:
        raise ConfigError("write the %s header as a block, one key per line, so `update` can raise the version"
                          % (HEADER_KEY))
    return ConfigTemplate(path=relative, header=header, sha=content_hash(data))


def _header_span(text):
    """(start, end) of the taufw_config block in a template's text: from its key to the first line that is neither
    indented, empty nor a comment; (0, 0) if there is no block."""
    match = re.search(r"^%s:[ \t]*(#.*)?$" % (HEADER_KEY), text, re.M)
    if not match:
        return 0, 0
    end = match.start()
    for number, line in enumerate(text[match.start():].splitlines(True)):
        if number and line.strip() and line[0] not in ' \t' and not line.lstrip().startswith('#'):
            break
        end += len(line)
    return match.start(), end


def _raise_version(path, version, files):
    """Write `version` into the header of a template, keeping every other byte (line endings included)."""
    text = files.read_bytes(path).decode('utf-8')
    start, end = _header_span(text)
    block = VERSIONEXP.sub(lambda match: match.group('head') + str(version), text[start:end], count=1)
    files.write_bytes(path, (text[:start] + block + text[end:]).encode('utf-8'), overwrite=True)


def _read_lock(directory, files, problems):
    """{id: (version, sha)} of configs.lock ({} if there is none); bad lines are added to `problems`."""
    path = os.path.join(directory, LOCK_NAME)
    if not os.path.isfile(path):
        return {}
    lock = {}
    for number, line in enumerate(files.read_text(path).splitlines(), 1):
        fields = line.split()
        if not fields or line.startswith('#'):
            continue
        if len(fields) != 3 or not fields[1].isdigit():
            problems.append("%s:%d: not '<id> <version> <sha256>': %r" % (LOCK_NAME, number, line))
            continue
        lock[fields[0]] = (int(fields[1]), fields[2])
    return lock


def _tree(directory):
    """Every file under a directory (relative paths, sorted), without hidden files and SKIPPED directories."""
    found = []
    if not os.path.isdir(directory):
        return found
    for parent, dirs, names in os.walk(directory):
        dirs[:] = sorted(d for d in dirs if not d.startswith('.') and d not in SKIPPED)
        found.extend(os.path.relpath(os.path.join(parent, name), directory) for name in sorted(names)
                     if not name.startswith('.') and not name.endswith('.pyc'))
    return found


def _posix(path):
    return path.replace('\\', '/')
