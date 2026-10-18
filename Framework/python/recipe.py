# Author: Yagizhan Dinckurt (October 2026) (yagizdkurt)
"""Recipe: what a run should do. It is read from a YAML (or JSON) file and checked before anything runs.

    name: mutau_2022_postEE
    run_root: /afs/cern.ch/work/u/user/taufw_runs   # where the runs go (see run_root below)
    pico: {config: null}              # PicoProducer configuration; null -> PicoProducer/config/config.json
    stages:
      - stage: production             # the stage type; options: see ProductionSpec (stages/production.py)
        id: production                # required, unique; the stage's directory in the run
        description: mutau tuples     # optional, free text (shown, never used for anything else)
        inputs: null                  # required; production reads no other stage's output
        eras: [2022_postEE]
        channels: [mutau]
      - stage: controlhists           # options: see ControlHistsSpec (stages/controlhists.py)
        id: hists
        inputs: {tuples: production}  # every input slot of the stage -> the id of an earlier stage, or null
        eras: [2022_postEE]
      - stage: controlplots           # options: see ControlPlotsSpec (stages/controlplots.py); then shapes, fit
        id: plots
        inputs: {hists: hists}        # the control-histogram files of the stage above
      - stage: python                 # a Python file of the bundle (stages/python_step.py); anywhere, any number
        id: check_yields
        inputs: {plots: plots}        # any names; null: no inputs
        file: steps/check_yields.py

Every stage has the keys `stage`, `id` and `inputs`, and may have `description`; the other keys are its options.

    id:       letters, digits, '_', '.', '-' (not '.' or '..'); unique. It names the stage's directories in the run:
              <run_dir>/stages/<id>/ (output) and <run_dir>/logs/<id>/ (logs).
    inputs:   which earlier stage's output the stage reads, per input slot (Stage.inputs):
                production    no slots                     inputs: null
                controlhists  tuples   <- tuples           null: the tuples in $PICODIR of the PicoProducer config
                controlplots  hists    <- control_histograms  (never null)
                shapes        tuples   <- tuples           null: the same
                fit           shapes   <- shapes           null: the shapes already in Fitter/ (temporary exception)
                python        any names <- any stage       null: no inputs; a mapping names stages, never null
              A slot names a stage that comes earlier in the recipe and makes that kind of data
              (Stage.outputs). A slot may instead name the stage directory of another run (a stage that is
              DONE, with its manifest.json; validation.py checks it, the Framework reads its artifacts):
                shapes: {path: /afs/.../taufw_runs/<run>/stages/shapes}
              (absolute; nothing is expanded; not inside the bundle). A tuples slot may also name tuples made
              outside TauFW:
                tuples: {external: /eos/.../TES_variations/$ERA/$GROUP}
              (an absolute directory pattern with $ERA and $GROUP, the files <sample>_<channel>.root in it).
              A slot may be null (only for old recipes: the module's own default) only if its stage lists it in
              Stage.null_inputs. Nothing is connected implicitly: a stage sees only the artifacts of its inputs.
    order:    the stages run in the order they are written (the user's choice); the only rule is that an input
              names an earlier stage. Any stage may appear any number of times (with its own id), except
              production: at most once (its job files are outside the run, and a run has one pico.config).

run_root is the parent directory of the runs: a run is <run_root>/<name>_<YYYYmmdd-HHMMSS>/. It must be absolute, on
a mounted file system (not a URL), and outside the bundle directory (every run copies its bundle, so it would copy
the earlier runs too; a loose recipe file's directory is not copied). ~ and $VARIABLES are expanded where taufw.py runs (a warning says so; an undefined variable is a
problem). Without run_root (or with run_root: null) the runs go to taufw_runs/ in the directory taufw.py is started
from, with a warning. `taufw.py start --run-root DIR` takes precedence over the recipe.

A recipe is usually the recipe.yml of an analysis bundle (Analyses/<name>/, see bundle.py): Recipe.load() takes
the bundle directory or the file, and the path options of the stages are resolved against that directory.

Every problem of a recipe is collected, not only the first: Recipe.parse() returns them as Issues, and
Recipe.from_dict() / Recipe.load() raise one RecipeError that lists them all, e.g.
    recipe.yml: 2 problems
      stages[0] (production): unknown option 'samplez' (known: ...)
      stages[2] (fit).inputs.shapes: no stage 'histo' in the recipe
validation.py adds the checks of the files a recipe names (for the menu and `taufw.py check`).
A warning is not a problem: the recipe can run. recipe_warnings() lists them (Recipe.warnings for a valid recipe);
`taufw.py check`, `plan`, `start` and the menu show them. Besides the run_root warnings, a bundle file copied from a
template of Configs/ gets a warning while its template has a newer version (configs.copy_warnings).

Inputs:  a recipe file or bundle directory, or a dict (e.g. the copy of the recipe saved in run.json).
Outputs: Recipe and StageSpec records (frozen), Issues. Nothing is written.

Public API:
  Recipe.load(path) / Recipe.from_dict(data, source, bundle_dir) / Recipe.parse(...) / recipe.to_dict()
  recipe_warnings(data, bundle_dir=None) -> [Issue]   what a recipe should change, though it can run (e.g. no
                                     run_root, an old copy of a Configs/ template in the bundle)
  run_root_dir(value)   -> str       run_root with ~ and $VARIABLES expanded (None: not set)
  StageSpec            one stage of the recipe: its type, id, inputs, typed options (Spec), options as written
  Issue                one problem (or warning) of a recipe: where it is and what is wrong
  RecipeError          invalid recipe (its .issues list every problem)
"""
import os, re, copy, posixpath
from dataclasses import dataclass, field, replace
from typing import Optional, Tuple
from TauFW.Framework.bundle import leaves_bundle, is_bundle
from TauFW.Framework.configs import copy_warnings
from TauFW.Framework.defaults import RECIPE_NAME, DEFAULT_RUN_ROOT, default_file_io
from TauFW.Framework.stages import STAGES, ORDER, RETIRED, SpecError, spec_from_dict

__all__ = ['Recipe', 'StageSpec', 'Issue', 'RecipeError', 'recipe_warnings', 'run_root_dir']


# =============================================================================
# ================================= CONSTANTS =================================


TOP_KEYS   = ('name', 'run_root', 'pico', 'stages')      # allowed keys at the top of a recipe
PICO_KEYS  = ('config',)                                 # allowed keys under 'pico:'
STAGE_KEYS = ('stage', 'id', 'description', 'inputs')    # keys of every stage that are not its options
NAMEEXP    = re.compile(r"^[A-Za-z0-9_.-]+$")  # allowed run names, stage ids and input names (directory names)
URLEXP     = re.compile(r"^[A-Za-z][A-Za-z0-9+.-]*://")  # a URL, e.g. root://eosuser.cern.ch//eos/...


# =============================================================================
# ================================== RECORDS ==================================


@dataclass(frozen=True)
class StageSpec:
    """One stage of a recipe.

    stage:       the stage's type, e.g. 'production' or 'python'
    id:          the stage's id in the run (unique; run.json and the run directory use it)
    spec:        the stage's typed options, a Spec dataclass (e.g. ProductionSpec); this is what the stage reads
    options:     the options exactly as written in the recipe (without the keys of STAGE_KEYS); saved to run.json
    inputs:      input slot -> stage id, None, {path: directory} or {external: pattern}, as written;
                 None: `inputs: null`
    description: free text from the recipe ("" if none); shown, never used for anything else
    """
    stage:       str
    id:          str
    spec:        object
    options:     dict = field(default_factory=dict)
    inputs:      Optional[dict] = None
    description: str = ""

    @property
    def connections(self):
        """input slot -> stage id (None: not a stage of this run: null, path or external); {} for `inputs: null`."""
        return {slot: value if isinstance(value, str) else None for slot, value in (self.inputs or {}).items()}

    @property
    def paths(self):
        """input slot -> the directory of {path: <stage directory>} (another run's stage); {} if none."""
        return {slot: value.get('path') for slot, value in (self.inputs or {}).items()
                if isinstance(value, dict) and isinstance(value.get('path'), str)}

    @property
    def external(self):
        """input slot -> the pattern of {external: <pattern>} (data made outside TauFW); {} if none."""
        return {slot: value.get('external') for slot, value in (self.inputs or {}).items()
                if isinstance(value, dict) and isinstance(value.get('external'), str)}


@dataclass(frozen=True)
class Issue:
    """One problem (or warning) of a recipe. where: the key, e.g. "stages[2] (fit).inputs.shapes" ("" for the
    whole file)."""
    where:   str
    message: str

    def __str__(self):
        return "%s: %s" % (self.where, self.message) if self.where else self.message


@dataclass(frozen=True)
class Recipe:
    """A checked recipe.
    pico_config: the PicoProducer configuration as written (None: PicoProducer's default); see pico_config_path.
    bundle_dir:  the directory the path options are resolved against (the bundle; None: none).
    run_root:    the parent directory of the runs as written (None: not set); see run_root_dir.
    warnings:    what the recipe should change, though it can run (recipe_warnings)."""
    name:        str
    stages:      Tuple[StageSpec, ...]
    pico_config: Optional[str] = None
    source:      str = "<recipe>"
    bundle_dir:  Optional[str] = None
    run_root:    Optional[str] = None
    warnings:    Tuple[Issue, ...] = field(default=(), compare=False)

    def stage(self, stage_id):
        """The StageSpec with this id, or None."""
        for stage_spec in self.stages:
            if stage_spec.id == stage_id:
                return stage_spec
        return None

    def first(self, stage_type):
        """The first StageSpec of a stage type (e.g. 'production'), or None."""
        for stage_spec in self.stages:
            if stage_spec.stage == stage_type:
                return stage_spec
        return None

    @property
    def pico_config_path(self):
        """The path of the PicoProducer configuration (relative paths are in the bundle), or None."""
        return _pico_config_path(self.pico_config, self.bundle_dir)

    @property
    def run_root_dir(self):
        """The parent directory of the runs, with ~ and $VARIABLES expanded, or None if the recipe sets none."""
        return run_root_dir(self.run_root)

    # =========================================================================
    # ================================ LOADING ================================

    @classmethod
    def load(cls, path, files=None):
        """Read and check a recipe: a bundle directory (its recipe.yml) or a .yml/.yaml/.json file. The file's
        directory is the bundle directory. files: a TauFW.Utilities FileIO (default: new).
        Raises RecipeError listing every problem, also for a file that cannot be read (Framework BUGS K06)."""
        try:
            data, source, directory = read_recipe(path, files)
        except RecipeError:
            raise
        except Exception as error:  # a missing or unreadable file, a YAML syntax error, ...
            reason = "no such file" if not os.path.exists(path) else str(error)
            raise RecipeError(path, [Issue("", "cannot read the recipe: %s" % (reason))]) from None
        recipe = cls.from_dict(data, source=source, bundle_dir=directory)
        if recipe.pico_config and not os.path.isabs(recipe.pico_config) and leaves_bundle(recipe.pico_config):
            # above the bundle (e.g. ../../PicoProducer/config/config.json): not copied into a run, so made absolute
            recipe = replace(recipe, pico_config=recipe.pico_config_path)
        return recipe

    @classmethod
    def from_dict(cls, data, source="<recipe>", bundle_dir=None):
        """Check a recipe dict and build the Recipe; raises RecipeError listing every problem."""
        recipe, _, issues = cls.parse(data, source, bundle_dir)
        if issues:
            raise RecipeError(source, issues)
        return recipe

    @classmethod
    def parse(cls, data, source="<recipe>", bundle_dir=None):
        """Check a recipe dict without raising: (Recipe or None, [(index, StageSpec)], [Issue]).
        The Recipe is None if there is any issue; the StageSpecs are those of the stages whose options are valid
        (validation.py checks their files even when other stages are wrong)."""
        issues = []
        if not isinstance(data, dict):
            return None, [], [Issue("", "a recipe is a mapping with keys %s" % (', '.join(TOP_KEYS)))]
        _check_keys(data, TOP_KEYS, "", issues)
        name = data.get('name')
        if not isinstance(name, str) or not NAMEEXP.match(name):
            issues.append(Issue('name', "must be a word of letters, digits, '_', '.' or '-' (got %r)" % (name,)))
        run_root = _check_run_root(data.get('run_root'), bundle_dir, issues)
        pico = data.get('pico') or {}
        if not isinstance(pico, dict):
            issues.append(Issue('pico', "must be a mapping, e.g. {config: null}"))
            pico = {}
        _check_keys(pico, PICO_KEYS, "pico", issues)
        stages = data.get('stages')
        if not isinstance(stages, list) or not stages:
            issues.append(Issue('stages', "must be a non-empty list"))
            stages = []
        entries = [_stage_entry(entry, index, bundle_dir, issues) for index, entry in enumerate(stages)]
        _check_graph([e for e in entries if e is not None], issues)
        stage_specs = [(e.index, e.stage_spec) for e in entries if e is not None and e.stage_spec is not None]
        if issues:
            return None, stage_specs, issues
        recipe = cls(name=name, stages=tuple(s for _, s in stage_specs), pico_config=pico.get('config'),
                     source=source, bundle_dir=bundle_dir, run_root=run_root,
                     warnings=tuple(recipe_warnings(data, bundle_dir)))
        return recipe, stage_specs, issues

    def to_dict(self):
        """The recipe as a dict; from_dict(to_dict()) gives the same recipe."""
        stages = []
        for s in self.stages:
            entry = [('stage', s.stage), ('id', s.id)]
            if s.description:
                entry.append(('description', s.description))
            entry.append(('inputs', copy.deepcopy(s.inputs)))
            stages.append(dict(entry + list(copy.deepcopy(s.options).items())))
        top = [('name', self.name)] + ([('run_root', self.run_root)] if self.run_root is not None else [])
        return dict(top + [('pico', {'config': self.pico_config}), ('stages', stages)])


# =============================================================================
# ============================== READING FILES ================================


def read_recipe(path, files=None):
    """(data, source, bundle directory) of a recipe file or bundle directory. source names the file in messages
    (<bundle>/recipe.yml for a bundle). Raises RecipeError for a path that is not a recipe."""
    files = files or default_file_io()
    if os.path.isdir(path):
        path = os.path.join(path, RECIPE_NAME)
    if path.endswith(('.yml', '.yaml')):
        data = files.read_yaml(path)
    elif path.endswith('.json'):
        data = files.read_json(path)
    else:
        raise RecipeError(path, [Issue("", "a recipe must be a bundle directory or a .yml, .yaml or .json file")])
    directory = os.path.dirname(os.path.abspath(path))
    source = os.path.basename(path)
    if source == RECIPE_NAME:  # name the bundle in the messages
        source = "%s/%s" % (os.path.basename(directory), source)
    return data, source, directory


# =============================================================================
# ================================ VALIDATION =================================


@dataclass
class _Entry:
    """What is known of one entry of 'stages' after its own checks (stage_spec is None if its options are bad)."""
    index:      int
    stage:      str
    id:         Optional[str]
    inputs:     Optional[dict]
    where:      str
    stage_spec: Optional[StageSpec] = None


def _stage_entry(entry, index, bundle_dir, issues):
    """Check one entry of the recipe's 'stages' list on its own; None if it is not even a stage."""
    if not isinstance(entry, dict) or 'stage' not in entry:
        issues.append(Issue("stages[%d]" % (index), "must be a mapping with a 'stage' key"))
        return None
    name = entry['stage']
    if name in RETIRED:
        issues.append(Issue("stages[%d]" % (index), "stage %r no longer exists: %s" % (name, RETIRED[name])))
        return None
    if name not in STAGES:
        known = ORDER + tuple(n for n in STAGES if n not in ORDER)
        issues.append(Issue("stages[%d]" % (index), "unknown stage %r (known: %s)" % (name, ', '.join(known))))
        return None
    where = "stages[%d] (%s)" % (index, name)
    stage_id = _check_id(entry, where, issues)
    description = entry.get('description')
    if description is not None and not isinstance(description, str):
        issues.append(Issue(where + ".description", "must be text (got %r)" % (description,)))
    inputs = _check_inputs(entry, name, where, bundle_dir, issues)
    options = {k: v for k, v in entry.items() if k not in STAGE_KEYS}
    result = _Entry(index=index, stage=name, id=stage_id, inputs=inputs, where=where)
    try:
        spec = spec_from_dict(STAGES[name].Spec, options, where)
    except SpecError as err:  # "<where>[.<group>]: <message>"
        location, _, message = str(err).partition(": ")
        issues.append(Issue(location, message) if message else Issue(where, str(err)))
        return result
    if stage_id is not None:
        result.stage_spec = StageSpec(stage=name, id=stage_id, spec=spec, options=copy.deepcopy(options),
                                      inputs=copy.deepcopy(inputs), description=description or "")
    return result


def _check_id(entry, where, issues):
    """The stage's id, or None (with an issue) if it is missing or not allowed."""
    if 'id' not in entry:
        issues.append(Issue(where, "missing 'id' (every stage needs a unique id, e.g. id: %s)" % (entry['stage'])))
        return None
    stage_id = entry['id']
    if not isinstance(stage_id, str) or not NAMEEXP.match(stage_id):
        issues.append(Issue(where + ".id", "must be a word of letters, digits, '_', '.' or '-' (got %r)"
                            % (stage_id,)))
        return None
    if stage_id in ('.', '..'):  # a directory name: <run_dir>/stages/<id>
        issues.append(Issue(where + ".id", "%r is not allowed (it names a directory)" % (stage_id)))
        return None
    return stage_id


def _check_inputs(entry, name, where, bundle_dir, issues):
    """The stage's inputs as written (None for `inputs: null`), checked against the slots of its type.
    Which stages they name is checked by _check_graph; the directory of a {path: ...} by validation.py."""
    slots, nullable = STAGES[name].inputs, STAGES[name].null_inputs
    where = where + ".inputs"
    if 'inputs' not in entry:
        issues.append(Issue(where, "missing (%s)" % (_inputs_hint(name, slots, nullable))))
        return None
    inputs = entry['inputs']
    if inputs is None:
        if slots:  # a built-in stage with slots lists all of them
            issues.append(Issue(where, "%s reads %s: %s" % (name, ', '.join(slots),
                                                            _inputs_hint(name, slots, nullable))))
        return None
    if not isinstance(inputs, dict):
        issues.append(Issue(where, "must be a mapping or null (%s)" % (_inputs_hint(name, slots, nullable))))
        return None
    if not inputs:
        issues.append(Issue(where, "is empty: write inputs: null if the stage reads no other stage's output"))
        return None
    if slots is not None and not slots:
        issues.append(Issue(where, "%s reads no other stage's output: write inputs: null" % (name)))
        return None
    for slot, value in inputs.items():
        if slots is not None and slot not in slots:
            issues.append(Issue("%s.%s" % (where, slot), "unknown input (%s has: %s)" % (name, ', '.join(slots))))
        elif slots is None and not (isinstance(slot, str) and NAMEEXP.match(slot)):
            issues.append(Issue("%s.%s" % (where, slot), "an input name is a word of letters, digits, '_', '.' "
                                                         "or '-'"))
        elif value is None and slots is None:
            issues.append(Issue("%s.%s" % (where, slot), "must name an earlier stage (leave the input out if "
                                                         "it has none)"))
        elif value is None and slot not in nullable:
            issues.append(Issue("%s.%s" % (where, slot), "must name an earlier stage that makes %s (null is not "
                                                         "allowed for this input)" % (slots[slot])))
        elif isinstance(value, dict):
            problem = _mapping_problem(value, slots.get(slot) if slots else None, bundle_dir)
            if problem:
                issues.append(Issue("%s.%s" % (where, slot), problem))
        elif value is not None and not isinstance(value, str):
            issues.append(Issue("%s.%s" % (where, slot), "must be a stage id, {path: <stage directory>} or null "
                                                         "(got %r)" % (value,)))
    for slot in (slots or {}):
        if slot not in inputs:
            issues.append(Issue("%s.%s" % (where, slot), "missing (the id of an earlier stage%s)"
                                % (", or null" if slot in nullable else "")))
    return dict(inputs)


def _inputs_hint(name, slots, nullable):
    if slots is None:
        return ("write inputs: null, or a mapping of names to the ids of earlier stages (or {path: <stage "
                "directory>})")
    if not slots:
        return "write inputs: null"
    return "write inputs: {%s}" % (', '.join("%s: <stage id, {path: <stage directory>}%s%s>"
                                             % (slot, ", {external: <pattern>}" if slots[slot] == 'tuples' else "",
                                                " or null" if slot in nullable else "")
                                             for slot in slots))


def _mapping_problem(value, kind, bundle_dir):
    """What is wrong with an input written as a mapping: {path: <stage directory>} (any slot) or
    {external: <pattern>} (a tuples slot); None: nothing."""
    if set(value) == {'path'}:
        return _path_problem(value['path'], bundle_dir)
    if set(value) == {'external'}:
        return _external_problem(value, kind)
    return ("a mapping is {path: <stage directory>}%s (got keys %s)"
            % (" or {external: <pattern>}" if kind == 'tuples' else "", ', '.join(sorted(map(str, value)))))


def _path_problem(path, bundle_dir):
    """What is wrong with the directory of {path: <stage directory>} (None: nothing). Only the value is checked
    here; the directory and its manifest are checked by validation.py and the Framework (manifest.py)."""
    if not isinstance(path, str) or not path.strip():
        return ("path must be the absolute stage directory of another run, e.g. "
                "/afs/.../taufw_runs/<run>/stages/shapes (got %r)" % (path,))
    if URLEXP.match(path):
        return "path must be a directory on a mounted file system, not a URL (got %s)" % (path)
    if not _is_absolute(path):
        return ("path must be absolute (got %s; relative paths are not allowed, and ~ and $VARIABLES are not "
                "expanded)" % (path))
    if is_bundle(bundle_dir) and _inside(path, bundle_dir):
        return ("%s is inside the bundle %s: an input names another run's stage directory, and data is never "
                "part of a bundle" % (path, bundle_dir))
    return None


def _external_problem(value, kind):
    """What is wrong with an input written as {external: <pattern>} (None: nothing)."""
    if kind != 'tuples':
        return ("{external: ...} is only for a tuples input (controlhists, shapes); name an earlier stage, or "
                "{path: <stage directory>}")
    if set(value) != {'external'}:
        return "a mapping is {external: <absolute pattern>} (got keys %s)" % (', '.join(sorted(map(str, value))))
    pattern = value['external']
    if not isinstance(pattern, str) or not pattern.strip():
        return "external must be an absolute directory pattern, e.g. /eos/.../$ERA/$GROUP (got %r)" % (pattern,)
    if URLEXP.match(pattern):
        return "external must be a directory on a mounted file system, not a URL (got %s)" % (pattern)
    if not _is_absolute(pattern):
        return ("external must be an absolute directory pattern (got %s; ~ and $VARIABLES at the start are not "
                "expanded)" % (pattern))
    return None


def _check_graph(entries, issues):
    """The checks between stages: unique ids, at most one production stage, and inputs that name an earlier stage
    that makes the right kind of data (the only order rule: a stage reads only stages above it)."""
    seen = {}
    for entry in entries:
        if entry.id is None:
            continue
        if entry.id in seen:
            issues.append(Issue(entry.where + ".id", "%r is already the id of stages[%d]"
                                % (entry.id, seen[entry.id].index)))
        else:
            seen[entry.id] = entry
    productions = [e for e in entries if e.stage == 'production']
    for extra in productions[1:]:  # its job files are outside the run and the run has one pico.config (TODO 6)
        issues.append(Issue(extra.where, "a recipe has at most one production stage (put several eras and "
                                         "channels in its lists, or use separate recipes)"))
    for position, entry in enumerate(entries):
        earlier = {e.id: e for e in entries[:position] if e.id is not None}
        slots = STAGES[entry.stage].inputs
        for slot, value in (entry.inputs or {}).items():
            if not isinstance(value, str):  # null, {path: ...} (checked by validation.py), {external: ...}
                continue
            where = "%s.inputs.%s" % (entry.where, slot)
            if value not in earlier:
                if value == entry.id:
                    message = "a stage cannot read its own output"
                elif value in seen:
                    message = "stage %r comes after this one; an input names an earlier stage" % (value)
                else:
                    message = "no stage %r in the recipe" % (value)
                issues.append(Issue(where, message))
                continue
            kind = slots.get(slot) if slots else None
            makes = STAGES[earlier[value].stage].outputs
            if kind is not None and makes is not None and kind not in makes:
                issues.append(Issue(where, "stage %r (%s) makes %s, not %s"
                                    % (value, earlier[value].stage, ', '.join(makes) or 'nothing', kind)))


def _check_keys(data, known, where, issues):
    """An issue for every key that is not in `known`."""
    for key in data:
        if key not in known:
            issues.append(Issue(where, "unknown key %r (known: %s)" % (key, ', '.join(known))))


def _pico_config_path(value, bundle_dir):
    if not value or os.path.isabs(value) or not bundle_dir:
        return value
    return os.path.normpath(os.path.join(bundle_dir, value))


# =============================================================================
# ================================= RUN ROOT ==================================


def run_root_dir(value):
    """run_root with ~ and $VARIABLES expanded (where taufw.py runs), or None if it is not set."""
    if value is None:
        return None
    return os.path.expandvars(os.path.expanduser(value))


def _check_run_root(value, bundle_dir, issues):
    """run_root as written, or None if it is not set (a warning, see recipe_warnings) or not allowed (an issue)."""
    if value is None:
        return None
    if not isinstance(value, str) or not value.strip():
        issues.append(Issue('run_root', "must be an absolute directory, e.g. run_root: "
                                        "/afs/cern.ch/work/u/user/taufw_runs (got %r)" % (value,)))
        return None
    if URLEXP.match(value):
        issues.append(Issue('run_root', "must be a directory on a mounted file system, not a URL (got %s)" % (value)))
        return None
    expanded = run_root_dir(value)
    if '$' in expanded:
        issues.append(Issue('run_root', "%s: undefined environment variable (expanded: %s)" % (value, expanded)))
        return None
    if not _is_absolute(expanded):
        issues.append(Issue('run_root', "must be an absolute path (got %s)" % (value)))
        return None
    if is_bundle(bundle_dir) and _inside(expanded, bundle_dir):  # a bundle is copied whole (bundle.snapshot)
        issues.append(Issue('run_root', "%s is inside the bundle %s: every run copies its bundle, so it would copy "
                                        "the earlier runs too. Choose a directory outside the bundle"
                            % (expanded, bundle_dir)))
        return None
    return value


def recipe_warnings(data, bundle_dir=None):
    """The warnings of a recipe dict: what it should change, though it can run. Not problems: the recipe is valid
    with them (and nothing here is checked twice: a run_root that is a problem gets no warning). With the bundle
    directory, also the bundle files copied from Configs/ templates that have a newer version (configs.py)."""
    warnings = []
    if not isinstance(data, dict):
        return warnings
    value = data.get('run_root')
    stages = data.get('stages') if isinstance(data.get('stages'), list) else []
    production = [entry.get('id', 'production') for entry in stages
                  if isinstance(entry, dict) and entry.get('stage') == 'production']
    if value is None and production:
        warnings.append(Issue('run_root', "not set: the runs go to %s/ in the directory taufw.py is started from, "
                                          "and production stage %r writes its merged tuples into the run "
                                          "directory (often tens of GB). On lxplus that is your AFS space: the home "
                                          "directory holds only a few GB, and a full quota stops the run midway. "
                                          "Set run_root: <absolute directory with enough space> in the recipe "
                                          "(e.g. under /afs/cern.ch/work/), or start with --run-root"
                            % (DEFAULT_RUN_ROOT, production[0])))
    elif value is None:
        warnings.append(Issue('run_root', "not set: the runs go to %s/ in the directory taufw.py is started from. "
                                          "Set run_root: <absolute directory> in the recipe, or start with "
                                          "--run-root" % (DEFAULT_RUN_ROOT)))
    elif isinstance(value, str) and run_root_dir(value) != value and '$' not in run_root_dir(value):
        warnings.append(Issue('run_root', "%s is expanded where taufw.py runs (here: %s); someone else, or another "
                                          "machine, gets another directory" % (value, run_root_dir(value))))
    if is_bundle(bundle_dir):
        warnings.extend(Issue(relative, message) for relative, message in copy_warnings(bundle_dir))
    return warnings


def _is_absolute(path):
    """An absolute path on lxplus (/afs/..., /eos/...) or on this machine. posixpath: on Windows os.path.isabs
    says False for /afs/... (K05)."""
    return posixpath.isabs(path) or os.path.isabs(path)


def _inside(path, directory):
    """True if `path` is `directory` or below it."""
    path, directory = os.path.normcase(os.path.normpath(path)), os.path.normcase(os.path.normpath(directory))
    try:
        return os.path.commonpath([path, directory]) == directory
    except ValueError:  # different drives (Windows)
        return False


# =============================================================================
# ================================== ERRORS ===================================


class RecipeError(ValueError):
    """An invalid recipe. The message names the file and lists every problem; .issues holds them (Issue)."""

    def __init__(self, source, issues):
        self.source = source
        self.issues = tuple(issues)
        if len(self.issues) == 1:
            message = "%s: %s" % (source, self.issues[0])
        else:
            message = "%s: %d problems\n%s" % (source, len(self.issues),
                                               "\n".join("  %s" % (issue) for issue in self.issues))
        super().__init__(message)
