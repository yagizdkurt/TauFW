# Author: Yagizhan Dinckurt (October 2026) (yagizdkurt)
"""Recipe: what a run should do. It is read from a YAML (or JSON) file and checked before anything runs.

    name: mutau_2022_postEE
    pico: {config: null}              # PicoProducer configuration; null -> PicoProducer/config/config.json
    stages:
      - stage: production             # options: see ProductionSpec (stages/production.py)
        eras: [2022_postEE]
        channels: [mutau]
        samples: ["DY*", "TT*"]
      - stage: plots                  # options: see PlotSpec (stages/plots.py); then histograms, fit
        eras: [2022_postEE]
      - stage: python                 # a Python file of the bundle (stages/python_step.py); anywhere, any number
        id: check_yields              # default: the file name without .py
        file: steps/check_yields.py

A recipe is usually the recipe.yml of an analysis bundle (Analyses/<name>/, see bundle.py): Recipe.load() takes
the bundle directory or the file, and the path options of the stages are resolved against that directory.

Each stage has an id: its name for the built-in stages (production, plots, histograms, fit; at most once each and
in that order), and for a python step the `id:` option or the file name. Ids are unique; run.json and the run
directory use them.

An error names the file and the key, e.g. "recipe.yml: stages[0] (production): unknown option 'samplez'".

Inputs:  a recipe file or bundle directory, or a dict (e.g. the copy of the recipe saved in run.json).
Outputs: Recipe and StageSpec records (frozen). Nothing is written.

Public API:
  Recipe.load(path) / Recipe.from_dict(data, source, bundle_dir) / recipe.to_dict()
  StageSpec            one stage of the recipe: its name, id, typed options (Spec) and the options as written
  RecipeError          invalid recipe
"""
import os, re, copy
from dataclasses import dataclass, field, replace
from typing import Optional, Tuple
from TauFW.Framework.bundle import leaves_bundle
from TauFW.Framework.defaults import RECIPE_NAME, default_file_io
from TauFW.Framework.stages import STAGES, ORDER, SpecError, spec_from_dict

__all__ = ['Recipe', 'StageSpec', 'RecipeError']


# =============================================================================
# ================================= CONSTANTS =================================


TOP_KEYS  = ('name', 'pico', 'stages')       # allowed keys at the top of a recipe
PICO_KEYS = ('config',)                      # allowed keys under 'pico:'
NAMEEXP   = re.compile(r"^[A-Za-z0-9_.-]+$")  # allowed run names and stage ids (they become directory names)


# =============================================================================
# ================================== RECORDS ==================================


@dataclass(frozen=True)
class StageSpec:
    """One stage of a recipe.

    stage:   the stage's name, e.g. 'production' or 'python'
    spec:    the stage's typed options, a Spec dataclass (e.g. ProductionSpec); this is what the stage reads
    options: the options exactly as written in the recipe (without 'stage' and 'id'); saved to run.json
    id:      the stage's id in the run (default: the name; for a python step the file name without .py)
    """
    stage:   str
    spec:    object
    options: dict = field(default_factory=dict)
    id:      str = ""

    def __post_init__(self):
        if not self.id:
            object.__setattr__(self, 'id', self.stage)


@dataclass(frozen=True)
class Recipe:
    """A checked recipe.
    pico_config: the PicoProducer configuration as written (None: PicoProducer's default); see pico_config_path.
    bundle_dir:  the directory the path options are resolved against (the bundle; None: none)."""
    name:        str
    stages:      Tuple[StageSpec, ...]
    pico_config: Optional[str] = None
    source:      str = "<recipe>"
    bundle_dir:  Optional[str] = None

    def stage(self, stage_id):
        """The StageSpec with this id (for a built-in stage: its name), or None."""
        for stage_spec in self.stages:
            if stage_spec.id == stage_id:
                return stage_spec
        return None

    @property
    def pico_config_path(self):
        """The path of the PicoProducer configuration (relative paths are in the bundle), or None."""
        if not self.pico_config or os.path.isabs(self.pico_config) or not self.bundle_dir:
            return self.pico_config
        return os.path.normpath(os.path.join(self.bundle_dir, self.pico_config))

    # =========================================================================
    # ================================ LOADING ================================

    @classmethod
    def load(cls, path, files=None):
        """Read and check a recipe: a bundle directory (its recipe.yml) or a .yml/.yaml/.json file. The file's
        directory is the bundle directory. files: a TauFW.Utilities FileIO (default: new)."""
        files = files or default_file_io()
        if os.path.isdir(path):
            path = os.path.join(path, RECIPE_NAME)
        if path.endswith(('.yml', '.yaml')):
            data = files.read_yaml(path)
        elif path.endswith('.json'):
            data = files.read_json(path)
        else:
            raise RecipeError("%s: recipe must be a bundle directory or a .yml, .yaml or .json file" % (path))
        directory = os.path.dirname(os.path.abspath(path))
        source = os.path.basename(path)
        if source == RECIPE_NAME:  # name the bundle in the messages
            source = "%s/%s" % (os.path.basename(directory), source)
        recipe = cls.from_dict(data, source=source, bundle_dir=directory)
        if recipe.pico_config and not os.path.isabs(recipe.pico_config) and leaves_bundle(recipe.pico_config):
            # above the bundle (e.g. ../../PicoProducer/config/config.json): not copied into a run, so made absolute
            recipe = replace(recipe, pico_config=recipe.pico_config_path)
        return recipe

    @classmethod
    def from_dict(cls, data, source="<recipe>", bundle_dir=None):
        """Check a recipe dict and build the Recipe; raises RecipeError naming the wrong key."""
        where = source
        if not isinstance(data, dict):
            raise RecipeError("%s: a recipe is a mapping with keys %s" % (where, ', '.join(TOP_KEYS)))
        _check_keys(data, TOP_KEYS, where)
        name = data.get('name')
        if not isinstance(name, str) or not NAMEEXP.match(name):
            raise RecipeError("%s: 'name' must be a word of letters, digits, '_', '.' or '-' (got %r)" % (where, name))
        pico = data.get('pico') or {}
        if not isinstance(pico, dict):
            raise RecipeError("%s: 'pico' must be a mapping, e.g. {config: null}" % (where))
        _check_keys(pico, PICO_KEYS, where + ": pico")
        stages = data.get('stages')
        if not isinstance(stages, list) or not stages:
            raise RecipeError("%s: 'stages' must be a non-empty list" % (where))
        stage_specs = tuple(_stage_spec(entry, i, where) for i, entry in enumerate(stages))
        _check_order(stage_specs, where)
        return cls(name=name, stages=stage_specs, pico_config=pico.get('config'), source=source,
                   bundle_dir=bundle_dir)

    def to_dict(self):
        """The recipe as a dict; from_dict(to_dict()) gives the same recipe. An id is written only if it is not
        the stage's default id."""
        stages = []
        for s in self.stages:
            entry = [('stage', s.stage)]
            if s.id != STAGES[s.stage].default_id(s.spec):
                entry.append(('id', s.id))
            stages.append(dict(entry + list(copy.deepcopy(s.options).items())))
        return {'name': self.name, 'pico': {'config': self.pico_config}, 'stages': stages}


# =============================================================================
# ================================ VALIDATION =================================


def _stage_spec(entry, index, where):
    """The StageSpec of one entry of the recipe's 'stages' list."""
    if not isinstance(entry, dict) or 'stage' not in entry:
        raise RecipeError("%s: stages[%d] must be a mapping with a 'stage' key" % (where, index))
    name = entry['stage']
    if name not in STAGES:
        known = ORDER + tuple(n for n in STAGES if n not in ORDER)
        raise RecipeError("%s: stages[%d]: unknown stage %r (known: %s)" % (where, index, name, ', '.join(known)))
    where = "%s: stages[%d] (%s)" % (where, index, name)
    options = {k: v for k, v in entry.items() if k not in ('stage', 'id')}
    try:
        spec = spec_from_dict(STAGES[name].Spec, options, where)
    except SpecError as err:
        raise RecipeError(str(err))
    stage_id = entry.get('id') or STAGES[name].default_id(spec)
    if not isinstance(stage_id, str) or not NAMEEXP.match(stage_id):
        raise RecipeError("%s: 'id' must be a word of letters, digits, '_', '.' or '-' (got %r)" % (where, stage_id))
    if name in ORDER and stage_id != name:
        raise RecipeError("%s: a %s stage cannot have another id (got %r)" % (where, name, stage_id))
    if name not in ORDER and stage_id in STAGES:
        raise RecipeError("%s: id %r is the name of a stage; give the step its own 'id'" % (where, stage_id))
    return StageSpec(stage=name, spec=spec, options=copy.deepcopy(options), id=stage_id)


def _check_order(stage_specs, where):
    """Each id at most once; the built-in stages in the order of ORDER (production before histograms before fit).
    Python steps may be anywhere."""
    ids = [s.id for s in stage_specs]
    for stage_id in dict.fromkeys(ids):
        if ids.count(stage_id) > 1:
            raise RecipeError("%s: stage id %r appears more than once (give each python step its own 'id')"
                              % (where, stage_id))
    names = [s.stage for s in stage_specs if s.stage in ORDER]
    ranks = [ORDER.index(n) for n in names]
    if ranks != sorted(ranks):
        raise RecipeError("%s: stages must be in the order %s (got %s)" % (
            where, ' -> '.join(ORDER), ' -> '.join(names)))


def _check_keys(data, known, where):
    """Reject keys that are not in `known`."""
    for key in data:
        if key not in known:
            raise RecipeError("%s: unknown key %r (known: %s)" % (where, key, ', '.join(known)))


# =============================================================================
# ================================== ERRORS ===================================


class RecipeError(ValueError):
    """An invalid recipe; the message names the file and the key."""
