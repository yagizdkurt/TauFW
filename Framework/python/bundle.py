# Author: Yagizhan Dinckurt (October 2026) (yagizdkurt)
"""Analysis bundles: one directory with the recipe, every config file it uses and its own Python steps.

    Analyses/tes_id_2025/
      recipe.yml                  the recipe (taufw.py plan Analyses/tes_id_2025)
      config_coarse_TT.yml        a stage option `config: config_coarse_TT.yml` uses this file instead of the
                                  module's own config (whole file, no merging)
      steps/fit_summary.py        a `- stage: python` step

Every path is relative to the directory of recipe.yml; the layout inside it is free (the bundled examples keep
their configs next to recipe.yml and their Python steps in steps/).

The path options of a stage (the fields named in its Spec's `_paths`) and `pico.config` follow one rule:

    absolute path                       ─▶ used as is                                        'absolute'
    relative, a file in the bundle      ─▶ that file of the bundle (not above it: ../x)      'bundle'
    relative, not in the bundle         ─▶ unchanged: the module resolves it, as before       'module'
                                           (Fitter/ or Plotter/; a Plotter channel name such as mutau)

When a run starts, the bundle is copied to <run_dir>/bundle/ (same relative paths), and the run reads it from
there: like the recipe, a run never sees later edits. A bundle (a directory with recipe.yml) is copied whole, so a
Python step can import the files next to it and read any bundle file (ctx.path); hidden files, __pycache__ and
taufw_runs/ are left out, and a bundle above MAX_BUNDLE_BYTES is refused (keep data files outside the bundle). For
a loose recipe file, only the files its options name are copied.

Inputs:  a Recipe (its bundle directory and its stages' path options).
Outputs: resolved paths; snapshot() and make_bundle() write files.

Public API:
  resolve(value, bundle_dir), where(value, bundle_dir), resolve_spec(spec, bundle_dir)
  path_rows(spec, bundle_dir)       (option, value as written, resolved, where) of a spec's path options
  bundle_files(recipe)              the bundle-relative files a recipe's options name
  snapshot(recipe, target)          copy the bundle (or those files) to a run's bundle/ directory
  is_bundle(directory)              True for a directory with a recipe.yml
  make_bundle(recipe_dict, sources, target, files, extra)   a new bundle with copies of the module configs and of
                                    the source bundle's own files
"""
import os
import shutil
from dataclasses import replace

from TauFW.Framework.defaults import RECIPE_NAME, DEFAULT_RUN_ROOT

__all__ = ['resolve', 'where', 'leaves_bundle', 'resolve_spec', 'path_rows', 'bundle_files', 'snapshot',
           'is_bundle', 'make_bundle', 'source_files', 'BundleError', 'STEP_TEMPLATE', 'MAX_BUNDLE_BYTES']


# =============================================================================
# ================================= CONSTANTS =================================


MAX_BUNDLE_BYTES = 50 * 1024 * 1024                 # largest bundle a run copies (configs and code, not data)
SKIPPED_DIRS = ('__pycache__', DEFAULT_RUN_ROOT)    # never copied into a run (nor hidden files and directories)


# =============================================================================
# ================================= RESOLVING =================================


def resolve(value, bundle_dir):
    """The path a stage reads for a path option (see the rule at the top of this file)."""
    if where(value, bundle_dir) == 'bundle':
        return os.path.normpath(os.path.join(bundle_dir, value))
    return value


def where(value, bundle_dir):
    """'absolute', 'bundle' or 'module': which rule applies to a path option."""
    if os.path.isabs(value):
        return 'absolute'
    if bundle_dir and not leaves_bundle(value) and os.path.isfile(os.path.join(bundle_dir, value)):
        return 'bundle'
    return 'module'


def leaves_bundle(value):
    """True for a relative path that goes above its base directory (e.g. ../../x.json): never a bundle file."""
    return os.path.normpath(value).split(os.sep)[0] == os.pardir


def resolve_spec(spec, bundle_dir):
    """A copy of a stage's Spec with its path options resolved (the Spec itself keeps the values as written)."""
    changes = {}
    for name in _path_fields(spec):
        value = getattr(spec, name)
        if isinstance(value, tuple):
            changes[name] = tuple(resolve(item, bundle_dir) for item in value)
        elif isinstance(value, str) and value:
            changes[name] = resolve(value, bundle_dir)
    return replace(spec, **changes) if changes else spec


def path_rows(spec, bundle_dir):
    """(option, value as written, resolved path, where) for every path option of a Spec, e.g. for taufw.py plan."""
    rows = []
    for name in _path_fields(spec):
        value = getattr(spec, name)
        for item in (value if isinstance(value, tuple) else (value,)):
            if isinstance(item, str) and item:
                rows.append((name, item, resolve(item, bundle_dir), where(item, bundle_dir)))
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
    return {'source': recipe.bundle_dir, 'files': list(files)}


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


def _bundle_tree(directory):
    """Every file of a bundle (relative paths, sorted), without hidden files, __pycache__ and run directories."""
    files = []
    for parent, dirs, names in os.walk(directory):
        dirs[:] = sorted(d for d in dirs if not d.startswith('.') and d not in SKIPPED_DIRS)
        files.extend(os.path.relpath(os.path.join(parent, name), directory) for name in sorted(names)
                     if not name.startswith('.') and not name.endswith('.pyc'))
    return tuple(files)


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
