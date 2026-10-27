# Author: Yagizhan Dinckurt (October 2026) (yagizdkurt)
"""Analysis bundles: one directory with the recipe, every config file it uses and its own Python steps.

    Analyses/tes_id_2025/
      recipe.yml                  the recipe (taufw.py plan Analyses/tes_id_2025)
      config_coarse_TT.yml        a stage option `config: config_coarse_TT.yml` uses this file instead of the
                                  module's own config (whole file, no merging)
      steps/fit_summary.py        a `- stage: python` step

Every path is relative to the directory of recipe.yml; the layout inside it is free (the bundled examples keep
their configs next to recipe.yml and their Python steps in steps/).

The path options of a stage (the fields named in its Spec's `_paths`) and `pico.config` follow one rule (CL §38):

    absolute path                       ─▶ used as is                                        'absolute'
    relative, above the bundle (../x)   ─▶ the recipe's directory + path (not copied)        'outside'
    relative, a file in the bundle      ─▶ that file of the bundle                           'bundle'
    Configs/..., not in the bundle      ─▶ the template in TauFW/Configs/ (absolute path)    'template'
    a channel name (mutau), only for    ─▶ unchanged: the Histogrammer reads                 'channel'
      an option in the Spec's              Configs/Histogrammer/setups/setup_<name>.yml
      `_channel_paths` (controlhists configs)
    relative, otherwise                 ─▶ not found: a recipe error (recipe.py)              'missing'

No module directory is searched: a file of Fitter/ or Histogrammer/ (e.g. the fit's
TauES/config/defaultFitSetupTES_mutau.yml, a default of the old scripts) is copied into the bundle, or named by
its absolute path. Recipe.load() makes an 'outside' path absolute, so a run (which reads its own copy of the bundle)
reads the file where it is; like a template, it is not part of the run.

A template (CL §22) is named the same way in every stage, e.g. `Configs/Fitter/tes_id/config_coarse_TT.yml` or
`Configs/Histogrammer/samples/v15_2025.yml`: the stage's API gets the absolute path, so no module needs to know where
another module's files are. A run reads a template where it is; a bundle copy is what a run keeps (taufw.py init
copies the templates and channel setups a recipe names into the new bundle).

When a run starts, the bundle is copied to <run_dir>/bundle/ (same relative paths), and the run reads it from
there: like the recipe, a run never sees later edits of the bundle. Its copy may still be edited (e.g. a missing
file put there before a retry): snapshot() records the sha256 of every copied file, and every advance compares the
copy with them (CL §44, framework.py). A bundle (a directory with recipe.yml) is copied whole, so a
Python step can import the files next to it and read any bundle file (ctx.path); hidden files, __pycache__ and
taufw_runs/ are left out, and a bundle above MAX_BUNDLE_BYTES is refused (keep data files outside the bundle). For
a loose recipe file, only the files its options name are copied.

Inputs:  a Recipe (its bundle directory and its stages' path options).
Outputs: resolved paths; snapshot() and make_bundle() write files.

Public API:
  resolve(value, bundle_dir, channel), where(value, bundle_dir, channel), resolve_spec(spec, bundle_dir)
  is_absolute(path)                 absolute on lxplus (/afs/...) or on this machine (the one test, Framework BUGS K05)
  path_rows(spec, bundle_dir)       (option, value as written, resolved, where) of a spec's path options
  bundle_files(recipe)              the bundle-relative files a recipe's options name
  snapshot(recipe, target)          copy the bundle (or those files) to a run's bundle/ directory
  bundle_hashes(directory), bundle_changes(before, after), hashes_digest(hashes)
                                    the sha256 of a bundle copy's files, what changed between two of them, one
                                    digest of them all (a run's bundle check, CL §44)
  is_bundle(directory)            True for a directory with a recipe.yml
  make_bundle(recipe_dict, sources, target, files, extra)   a new bundle with copies of the templates and channel
                                    setups and of the source bundle's own files
"""
import hashlib
import json
import os
import posixpath
import shutil
from dataclasses import replace

from TauFW.Framework.defaults import CONFIGS_DIR, RECIPE_NAME, DEFAULT_RUN_ROOT

__all__ = ['resolve', 'where', 'leaves_bundle', 'is_absolute', 'resolve_spec', 'path_rows', 'bundle_files', 'snapshot',
           'bundle_hashes', 'bundle_changes', 'hashes_digest', 'is_bundle', 'make_bundle', 'source_files',
           'BundleError', 'STEP_TEMPLATE', 'MAX_BUNDLE_BYTES']


# =============================================================================
# ================================= CONSTANTS =================================


MAX_BUNDLE_BYTES = 50 * 1024 * 1024                 # largest bundle a run copies (configs and code, not data)
SKIPPED_DIRS = ('__pycache__', DEFAULT_RUN_ROOT)    # never copied into a run (nor hidden files and directories)
TEMPLATES = os.path.basename(CONFIGS_DIR)           # 'Configs': a path option starting with it names a template


# =============================================================================
# ================================= RESOLVING =================================


def resolve(value, bundle_dir, channel=False):
    """The path a stage reads for a path option (see the rule at the top of this file); channel: the option takes
    a channel name."""
    kind = where(value, bundle_dir, channel)
    if kind in ('bundle', 'outside') and bundle_dir:
        return os.path.normpath(os.path.join(bundle_dir, value))
    if kind == 'template':
        return os.path.normpath(os.path.join(os.path.dirname(CONFIGS_DIR), value))
    return value


def where(value, bundle_dir, channel=False):
    """'absolute', 'outside', 'bundle', 'template', 'channel' or 'missing': which rule applies to a path option
    (channel: the option takes a channel name, see the Spec's `_channel_paths`)."""
    if is_absolute(value):
        return 'absolute'
    if leaves_bundle(value):
        return 'outside'
    if bundle_dir and os.path.isfile(os.path.join(bundle_dir, value)):
        return 'bundle'
    if os.path.normpath(value).split(os.sep)[0] == TEMPLATES:
        return 'template'
    if channel and is_channel(value):
        return 'channel'
    return 'missing'


def is_channel(value):
    """fillhists.py's rule: a name without '/' and without .yml is a channel (setup_<name>.yml)."""
    return '/' not in value and os.sep not in value and not value.endswith('.yml')


def is_absolute(path):
    """An absolute path on lxplus (/afs/..., /eos/...) or on this machine. posixpath: on Windows os.path.isabs
    says False for /afs/... (Framework BUGS K05)."""
    return posixpath.isabs(path) or os.path.isabs(path)


def leaves_bundle(value):
    """True for a relative path that goes above its base directory (e.g. ../../x.json): never a bundle file."""
    return not is_absolute(value) and os.path.normpath(value).split(os.sep)[0] == os.pardir


def resolve_spec(spec, bundle_dir):
    """A copy of a stage's Spec with its path options resolved (the Spec itself keeps the values as written)."""
    changes = {}
    for name in _path_fields(spec):
        value = getattr(spec, name)
        channel = name in _channel_fields(spec)
        if isinstance(value, tuple):
            changes[name] = tuple(resolve(item, bundle_dir, channel) for item in value)
        elif isinstance(value, str) and value:
            changes[name] = resolve(value, bundle_dir, channel)
    return replace(spec, **changes) if changes else spec


def path_rows(spec, bundle_dir):
    """(option, value as written, resolved path, where) for every path option of a Spec, e.g. for taufw.py plan."""
    rows = []
    for name in _path_fields(spec):
        value, channel = getattr(spec, name), name in _channel_fields(spec)
        for item in (value if isinstance(value, tuple) else (value,)):
            if isinstance(item, str) and item:
                rows.append((name, item, resolve(item, bundle_dir, channel), where(item, bundle_dir, channel)))
    return tuple(rows)


# =============================================================================
# ================================ RUN SNAPSHOT ===============================


def bundle_files(recipe):
    """The bundle-relative paths of the files a recipe's options name (path options and pico.config), in recipe
    order."""
    values = [recipe.pico_config] if recipe.pico_config else []
    for stage_spec in recipe.stages:
        values.extend(row[1] for row in path_rows(stage_spec.spec, recipe.bundle_dir))
    return tuple(dict.fromkeys(os.path.normpath(value) for value in values
                               if where(value, recipe.bundle_dir) == 'bundle'))


def snapshot(recipe, target):
    """Copy the recipe's bundle (or, for a loose recipe file, the files its options name) to `target` (a run's
    bundle/ directory), keeping the relative paths. Nothing is copied if the bundle is too large (BundleError).
    Returns the record saved in run.json: {source: bundle directory, files: [relative paths]}."""
    if is_bundle(recipe.bundle_dir):
        files = _bundle_tree(recipe.bundle_dir)
    else:
        files = bundle_files(recipe)
    size = sum(os.path.getsize(os.path.join(recipe.bundle_dir, relative)) for relative in files)
    if size > MAX_BUNDLE_BYTES:
        raise BundleError("bundle %s has %.0f MB of files (at most %.0f MB): keep data files outside the bundle"
                          % (recipe.bundle_dir, size / 1024.0**2, MAX_BUNDLE_BYTES / 1024.0**2))
    for relative in files:
        destination = os.path.join(target, relative)
        os.makedirs(os.path.dirname(destination), exist_ok=True)
        shutil.copy2(os.path.join(recipe.bundle_dir, relative), destination)
    record = {'source': recipe.bundle_dir, 'files': list(files)}
    if files:  # what every advance compares the copy with (CL §44); without files there is nothing to compare
        record['sha256'] = bundle_hashes(target)
    return record


def bundle_hashes(directory):
    """{relative path: sha256} of every file of a run's bundle copy (the files a run would copy: no hidden files,
    __pycache__ or run directories); {} if the directory does not exist."""
    if not os.path.isdir(directory):
        return {}
    return {relative: _sha256(os.path.join(directory, relative)) for relative in _bundle_tree(directory)}


def bundle_changes(before, after):
    """{relative path: 'added', 'changed' or 'removed'} from one bundle_hashes() to another, sorted by path."""
    changes = {}
    for relative in sorted(set(before) | set(after)):
        if relative not in before:
            changes[relative] = 'added'
        elif relative not in after:
            changes[relative] = 'removed'
        elif before[relative] != after[relative]:
            changes[relative] = 'changed'
    return changes


def hashes_digest(hashes):
    """One sha256 of a whole bundle_hashes(): equal digests, equal bundle copies."""
    return hashlib.sha256(json.dumps(hashes, sort_keys=True).encode('utf-8')).hexdigest()


def is_bundle(directory):
    """True for an analysis bundle: a directory with a recipe.yml."""
    return bool(directory) and os.path.isfile(os.path.join(directory, RECIPE_NAME))


# =============================================================================
# ================================ NEW BUNDLE =================================


def make_bundle(recipe_dict, sources, target, files, extra=None):
    """Write a new bundle: target/recipe.yml, the files of the source bundle (extra), the module configs it uses
    copied next to recipe.yml, and target/steps/example.py (unless the source bundle has a steps/ directory).

    recipe_dict: the recipe as a dict (Recipe.to_dict()); its path options are rewritten to the copies.
    sources:     {(stage id, option, value): (group, absolute source file)} for every module config to copy
                 (the Framework finds them through the stages' module APIs; see Framework.make_bundle).
    files:       a TauFW.Utilities FileIO.
    extra:       {path relative to the bundle: absolute source file}: the source bundle's own files (its configs,
                 copies of Configs/ templates with their taufw_config header, Python steps), copied to the same
                 relative path, so the recipe's values stay valid.
    Raises BundleError if the target exists."""
    if os.path.exists(target):
        raise BundleError("%s exists already: choose another name" % (target))
    extra = dict(extra or {})
    copies = {}  # absolute source -> path relative to the bundle
    for group, source in sorted(sources.values()):
        if source not in copies:
            copies[source] = _free_name(list(copies.values()) + list(extra), group, source)
    for entry in recipe_dict['stages']:
        stage_id = entry['id']
        for option, value in list(entry.items()):
            if isinstance(value, list):
                entry[option] = [_copied(sources, copies, stage_id, option, item) for item in value]
            elif isinstance(value, str):
                entry[option] = _copied(sources, copies, stage_id, option, value)
    files.make_directory(os.path.join(target, 'steps'))
    for relative, source in sorted(extra.items()):
        copies[source] = relative
    for source, relative in copies.items():
        files.make_directory(os.path.dirname(os.path.join(target, relative)))
        files.copy_file(source, os.path.join(target, relative))
    if not any(relative.replace(os.sep, '/').startswith('steps/') for relative in extra):  # the source's steps instead
        files.write_text(os.path.join(target, 'steps', 'example.py'), STEP_TEMPLATE)
    files.write_yaml(os.path.join(target, RECIPE_NAME), recipe_dict)
    return tuple(sorted(copies.values()))


# =============================================================================
# ================================== HELPERS ==================================


def source_files(recipe):
    """{relative path: absolute file} of a recipe's own files, for a new bundle made from it: every file of its
    bundle (as a run copies it, without recipe.yml), or for a loose recipe file the files its options name."""
    relatives = _bundle_tree(recipe.bundle_dir) if is_bundle(recipe.bundle_dir) else bundle_files(recipe)
    return {relative: os.path.join(recipe.bundle_dir, relative) for relative in relatives if relative != RECIPE_NAME}


def _path_fields(spec):
    return getattr(type(spec), '_paths', ())


def _channel_fields(spec):
    return getattr(type(spec), '_channel_paths', ())


def _bundle_tree(directory):
    """Every file of a bundle (relative paths, sorted), without hidden files, __pycache__ and run directories."""
    files = []
    for parent, dirs, names in os.walk(directory):
        dirs[:] = sorted(d for d in dirs if not d.startswith('.') and d not in SKIPPED_DIRS)
        files.extend(os.path.relpath(os.path.join(parent, name), directory) for name in sorted(names)
                     if not name.startswith('.') and not name.endswith('.pyc'))
    return tuple(files)


def _sha256(path):
    digest = hashlib.sha256()
    with open(path, 'rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


def _copied(sources, copies, stage_id, option, value):
    """The bundle path of a copied config, or the value unchanged."""
    found = sources.get((stage_id, option, value))
    return copies[found[1]] if found else value


def _free_name(taken, group, source):
    """The file name of a copied config next to recipe.yml: its own name; if another copy (or recipe.yml) has that
    name, <group>_<name> (e.g. fitter_config.yml), then <group>_<parent directory>_<name>, then with a number."""
    base = os.path.basename(source)
    candidates = [base, "%s_%s" % (group, base), "%s_%s_%s" % (group, os.path.basename(os.path.dirname(source)), base)]
    taken = set(taken) | {RECIPE_NAME}
    for name in candidates:
        if name not in taken:
            return name
    stem, extension = os.path.splitext(candidates[-1])
    number = 2
    while "%s_%d%s" % (stem, number, extension) in taken:
        number += 1
    return "%s_%d%s" % (stem, number, extension)


# =============================================================================
# ================================== ERRORS ===================================


class BundleError(ValueError):
    """A bundle cannot be made (e.g. the directory exists)."""


# =============================================================================
# ================================= TEMPLATES =================================


STEP_TEMPLATE = '''"""Example Python step of this analysis. Add it to recipe.yml to run it:

    - stage: python
      id: example
      inputs: null              # or {name: <id of an earlier stage>, ...}
      file: steps/example.py
      options: {greeting: hello}

It runs in its own Python process, in the bundle directory, after the stages listed before it.
"""


def run(ctx):
    """ctx.options:            the step's options from the recipe
    ctx.input(name, kind):  the artifacts of the stage connected to an input (e.g. ctx.input('fit', kind='fit')
                            for inputs: {fit: fit})
    ctx.artifacts(stage, kind): the artifacts of the input stages, by stage id
    ctx.stage_dir:          the directory for this step's files (<run_dir>/stages/<id>/)
    ctx.path(relative):     a file of the bundle
    ctx.log(message):       a line in the step's log
    Return None, a list of artifacts (dicts), or {'message': ..., 'artifacts': [...]}."""
    ctx.log("%s from %s" % (ctx.options.get('greeting', 'hello'), ctx.stage_id))
    return {'message': "%d upstream artifact(s)" % (len(ctx.artifacts()))}
'''
