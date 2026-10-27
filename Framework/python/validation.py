# Author: Yagizhan Dinckurt (October 2026) (yagizdkurt)
"""Recipe validation: every problem of a recipe, before anything runs (the menu, `taufw.py check`).

    check_recipe(path) ─▶ read the file ─┬─ cannot read ─▶ one issue
                                         └─▶ Recipe.parse() ─▶ structure, ids, inputs, order, path rule (recipe.py)
                                                └─▶ files ─▶ pico.config, absolute path options, templates,
                                                             the stage directories of {path: ...} inputs
                                                       ─▶ RecipeCheck(recipe or None, stages, issues, warnings)

What is checked here and what is not:
    checked:      everything Recipe.load() checks (a path option that is not a bundle file, a template, absolute
                  or a channel name is a Recipe error, CL §38; the old module path of a config that became a
                  template too, stages.MOVED_CONFIGS), plus the files the recipe names: pico.config, absolute
                  path options (also ../x above the bundle, made absolute as Recipe.load() does), Configs/
                  templates (`Configs/...`, bundle.py), the directory of an {external: <pattern>} input (its part before the first $KEY), and the stage
                  directory of a {path: <stage directory>} input: it exists, has a manifest of format 2 (its stage
                  is DONE), was not moved or copied, and its stage makes the kind of data the slot takes
                  (manifest.py; the same rule as between the stages of one recipe).
    samples:      the `samples` option (controlhists, shapes) names files of the bundle (copies of the templates in
                  Configs/Histogrammer/samples/), templates (`Configs/...`) or absolute ones; they are read through the
                  Histogrammer API (the format is the Histogrammer's): readable, exactly one per era of the stage.
    not checked:  a channel name (controlhists configs: the Histogrammer's preflight finds its setup), and the
                  environment (CMSSW, ROOT, combine, tuples on disk): they are the machine's state, not the recipe's. The stages' plan
                  notes and preflight report them.

Inputs:  a recipe file or bundle directory.
Outputs: a RecipeCheck. Nothing is written.

Public API:
  check_recipe(path, files=None) -> RecipeCheck
  read_source(stage_spec, slot, path) -> StageDir   the source of a {path: ...} input (raises ManifestError)
  RecipeCheck   name, path, recipe (None if invalid), stages ((stage id, type, description) of every stage whose
                options are valid), issues (Issue), warnings (Issue: the recipe can run with them), ok
"""
import os
from dataclasses import dataclass
from typing import Optional, Tuple

from TauFW.Framework.bundle import path_rows, is_absolute
from TauFW.Framework.user_settings import production_problems
from TauFW.Framework.manifest import read_stage_dir, ManifestError
from TauFW.Framework.stages import STAGES
from TauFW.Framework.stages.local import fixed_directory
from TauFW.Framework.recipe import (Recipe, RecipeError, Issue, read_recipe, recipe_warnings, _external_problem,
                                    _path_problem, _outside_made_absolute)

__all__ = ['check_recipe', 'RecipeCheck', 'read_source']


# =============================================================================
# ================================= PIPELINE ==================================


def check_recipe(path, files=None):
    """Every problem of the recipe at `path` (a bundle directory or a recipe file). Never raises for a bad
    recipe: the problems are the result."""
    try:
        data, source, bundle_dir = read_recipe(path, files)
    except RecipeError as error:
        return RecipeCheck(name=os.path.basename(path), path=path, issues=error.issues)
    except Exception as error:  # unreadable file, YAML syntax error, ...
        return RecipeCheck(name=os.path.basename(path), path=path,
                           issues=(Issue("", "cannot read %s: %s" % (path, error)),))
    recipe, stage_specs, issues = Recipe.parse(_outside_made_absolute(data, bundle_dir), source, bundle_dir)
    pico = data.get('pico') if isinstance(data, dict) else None
    issues = list(issues) + _file_issues(pico.get('config') if isinstance(pico, dict) else None, stage_specs,
                                         bundle_dir)
    if any(stage_spec.stage == 'production' for _, stage_spec in stage_specs):  # its settings (user_settings.py)
        issues.extend(Issue('user config', problem) for problem in production_problems())
    name = data.get('name') if isinstance(data, dict) and isinstance(data.get('name'), str) else source
    return RecipeCheck(name=name, path=path, recipe=None if issues else recipe,
                       stages=tuple((s.id, s.stage, s.description) for _, s in stage_specs),
                       issues=tuple(issues), warnings=tuple(recipe_warnings(data, bundle_dir)))


# =============================================================================
# ================================== FILES ====================================


def _file_issues(pico_config, stage_specs, bundle_dir):
    """The files a recipe names that are missing (see the top of this file)."""
    issues = []
    if isinstance(pico_config, str) and pico_config:
        found = pico_config if is_absolute(pico_config) else os.path.join(bundle_dir or "", pico_config)
        if not os.path.isfile(found):
            issues.append(Issue('pico.config', "file not found: %s" % (os.path.normpath(found))))
    for index, stage_spec in stage_specs:
        where = "stages[%d] (%s)" % (index, stage_spec.stage)
        for option, value, resolved, kind in path_rows(stage_spec.spec, bundle_dir):
            if kind == 'absolute' and not os.path.isfile(resolved):
                issues.append(Issue("%s.%s" % (where, option), "file not found: %s" % (resolved)))
            elif kind == 'template' and not os.path.isfile(resolved):
                issues.append(Issue("%s.%s" % (where, option), "no such template: %s" % (resolved)))
        issues.extend(_sample_issues(stage_spec, where, bundle_dir))
        for slot, pattern in stage_spec.external.items():
            if _external_problem({'external': pattern}, 'tuples'):
                continue  # not a valid pattern: Recipe.parse reported it
            if not os.path.isdir(fixed_directory(pattern)):
                issues.append(Issue("%s.inputs.%s" % (where, slot), "tuple directory %s not found (external: %s)"
                                    % (fixed_directory(pattern), pattern)))
        for slot, path in stage_spec.paths.items():
            if _path_problem(path, bundle_dir):
                continue  # not a valid path: Recipe.parse reported it
            problem = source_problem(stage_spec, slot, path)
            if problem:
                issues.append(Issue("%s.inputs.%s" % (where, slot), problem))
    return issues


def _sample_issues(stage_spec, where, bundle_dir):
    """The problems of the sample model files of a stage's `samples` option (read through the Histogrammer API)."""
    files = [resolved for option, _, resolved, kind in path_rows(stage_spec.spec, bundle_dir)
             if option == 'samples' and kind != 'missing']
    if not files or len(files) != len(getattr(stage_spec.spec, 'samples', ())):
        return []  # none, or a file that is not found (a Recipe error)
    from TauFW.Histogrammer.api import ControlHists  # the format of the files is the Histogrammer's
    return [Issue("%s.samples" % (where), problem)
            for problem in ControlHists().samples_problems(files, stage_spec.spec.eras)]


def source_problem(stage_spec, slot, path):
    """What is wrong with the stage directory a {path: ...} input names (None: nothing); see read_source."""
    try:
        read_source(stage_spec, slot, path)
    except ManifestError as error:
        return str(error)
    return None


def read_source(stage_spec, slot, path):
    """The StageDir of the stage directory a {path: ...} input of `stage_spec` names (manifest.read_stage_dir),
    if its stage makes the kind of data the slot takes (a python step, as source or reader, is not checked).
    Raises ManifestError. Used here and by the Framework (plan, advance), so the messages are the same."""
    source = read_stage_dir(path)
    slots = STAGES[stage_spec.stage].inputs
    kind = slots.get(slot) if slots else None
    makes = STAGES[source.stage].outputs if source.stage in STAGES else None
    if kind is not None and makes is not None and kind not in makes:
        raise ManifestError("%s is stage %r (%s) of run %s: it makes %s, not %s"
                            % (path, source.stage_id, source.stage, source.run_id, ', '.join(makes) or 'nothing',
                               kind))
    return source


# =============================================================================
# ================================== RECORDS ==================================


@dataclass(frozen=True)
class RecipeCheck:
    """The result of check_recipe(). recipe: the Recipe if there is no issue, else None.
    warnings: what the recipe should change, though it can run (they never make it not ok)."""
    name:     str
    path:     str
    recipe:   Optional[Recipe] = None
    stages:   Tuple[Tuple[str, str, str], ...] = ()
    issues:   Tuple[Issue, ...] = ()
    warnings: Tuple[Issue, ...] = ()

    @property
    def ok(self):
        return not self.issues
