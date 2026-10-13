# Author: Yagizhan Dinckurt (October 2026)
"""Recipe: what a run should do, read from a YAML (or JSON) file and validated before anything runs.

    name: mutau_2022_postEE
    pico: {config: null}              # PicoProducer configuration; null -> PicoProducer/config/config.json
    stages:
      - stage: production             # options: see ProductionSpec (stages/production.py)
        eras: [2022_postEE]
        channels: [mutau]
        samples: ["DY*", "TT*"]
      - stage: histograms             # placeholder: reported NOT_IMPLEMENTED

Validation errors name the file and the key, e.g. "recipe.yml: stages[0] (production): unknown option 'samplez'".

Inputs:  a recipe file, or a dict (e.g. the copy stored in run.json).
Outputs: Recipe and StageSpec records (frozen). Nothing is written.

Public API:
  Recipe.load(path) / Recipe.from_dict(data, source) / recipe.to_dict()
  StageSpec            one stage: name, typed options (spec), raw options
  RecipeError          invalid recipe
"""

# ===== Imports =====
import os, re, copy
from dataclasses import dataclass, field
from typing import Optional, Tuple
from TauFW.Framework.stages import STAGES, ORDER, SpecError, spec_from_dict

__all__ = ['Recipe', 'StageSpec', 'RecipeError']


# ===== Constants =====
TOP_KEYS  = ('name', 'pico', 'stages')
PICO_KEYS = ('config',)
NAMEEXP   = re.compile(r"^[A-Za-z0-9_.-]+$") # run names become directory names


# ===== Records =====

@dataclass(frozen=True)
class StageSpec:
  """One stage of a recipe: its name, its typed options (the stage's Spec) and the options as written."""
  stage:   str
  spec:    object
  options: dict = field(default_factory=dict) # as written, for run.json (do not modify)


@dataclass(frozen=True)
class Recipe:
  """A validated recipe. pico_config: path of the PicoProducer configuration (None: its default)."""
  name:        str
  stages:      Tuple[StageSpec, ...]
  pico_config: Optional[str] = None
  source:      str = "<recipe>"

  def stage(self,name):
    """The StageSpec of a stage, or None."""
    for spec in self.stages:
      if spec.stage==name:
        return spec
    return None

  # ===== Loading =====

  @classmethod
  def load(cls,path,files=None):
    """Read and validate a recipe file (.yml/.yaml or .json). files: a TauFW.Utilities FileIO (default: new)."""
    if files is None:
      from TauFW.Utilities.FIO import FileIO
      files = FileIO()
    if path.endswith(('.yml','.yaml')):
      data = files.read_yaml(path)
    elif path.endswith('.json'):
      data = files.read_json(path)
    else:
      raise RecipeError("%s: recipe must be a .yml, .yaml or .json file"%(path))
    recipe = cls.from_dict(data,source=os.path.basename(path))
    if recipe.pico_config and not os.path.isabs(recipe.pico_config): # relative to the recipe file
      config = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(path)),recipe.pico_config))
      recipe = Recipe(name=recipe.name,stages=recipe.stages,pico_config=config,source=recipe.source)
    return recipe

  @classmethod
  def from_dict(cls,data,source="<recipe>"):
    """Validate a recipe dict; raises RecipeError naming the offending key."""
    where = source
    if not isinstance(data,dict):
      raise RecipeError("%s: a recipe is a mapping with keys %s"%(where,', '.join(TOP_KEYS)))
    _check_keys(data,TOP_KEYS,where)
    name = data.get('name')
    if not isinstance(name,str) or not NAMEEXP.match(name):
      raise RecipeError("%s: 'name' must be a word of letters, digits, '_', '.' or '-' (got %r)"%(where,name))
    pico = data.get('pico') or { }
    if not isinstance(pico,dict):
      raise RecipeError("%s: 'pico' must be a mapping, e.g. {config: null}"%(where))
    _check_keys(pico,PICO_KEYS,where+": pico")
    stages = data.get('stages')
    if not isinstance(stages,list) or not stages:
      raise RecipeError("%s: 'stages' must be a non-empty list"%(where))
    specs = tuple(_stage_spec(entry,i,where) for i, entry in enumerate(stages))
    _check_order(specs,where)
    return cls(name=name,stages=specs,pico_config=pico.get('config'),source=source)

  def to_dict(self):
    """The recipe as a dict (from_dict(to_dict()) gives the same recipe)."""
    return {'name': self.name, 'pico': {'config': self.pico_config},
            'stages': [dict([('stage',s.stage)]+list(copy.deepcopy(s.options).items())) for s in self.stages]}


# ===== Validation =====

def _stage_spec(entry,index,where):
  if not isinstance(entry,dict) or 'stage' not in entry:
    raise RecipeError("%s: stages[%d] must be a mapping with a 'stage' key"%(where,index))
  name = entry['stage']
  if name not in STAGES:
    raise RecipeError("%s: stages[%d]: unknown stage %r (known: %s)"%(where,index,name,', '.join(ORDER)))
  options = {k: v for k, v in entry.items() if k!='stage'}
  try:
    spec = spec_from_dict(STAGES[name].Spec,options,"%s: stages[%d] (%s)"%(where,index,name))
  except SpecError as err:
    raise RecipeError(str(err))
  return StageSpec(stage=name,spec=spec,options=copy.deepcopy(options))


def _check_order(specs,where):
  names = [s.stage for s in specs]
  for name in set(names):
    if names.count(name)>1:
      raise RecipeError("%s: stage %r appears more than once"%(where,name))
  ranks = [ORDER.index(n) for n in names]
  if ranks!=sorted(ranks):
    raise RecipeError("%s: stages must be in the order %s (got %s)"%(where,' -> '.join(ORDER),' -> '.join(names)))


def _check_keys(data,known,where):
  for key in data:
    if key not in known:
      raise RecipeError("%s: unknown key %r (known: %s)"%(where,key,', '.join(known)))


# ===== Errors =====

class RecipeError(ValueError):
  """An invalid recipe; the message names the file and the key."""
