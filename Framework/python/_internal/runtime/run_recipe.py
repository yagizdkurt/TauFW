# Author: Yagizhan Dinckurt (October 2026) (yagizdkurt)
"""The run's own recipe (CL §55): <run_dir>/bundle/recipe.yml, which may be edited between two advances.

    start()    bundle/recipe.yml      the text of the recipe file, comments kept (a Recipe made in code: its dict)
               recipes/recipe_0.yml   the same: the start
    advance()  bundle/recipe.yml ─▶ as run.json "recipe" ─▶ nothing to do
                                 └▶ changed ─▶ the edit rules (edit_problems) ─▶ every check of `taufw check`
                                              (validation.py) and the samples check ─▶ the Framework takes it:
                                              run.json recipe and recipe_changed, recipes/recipe_<N>.yml, the
                                              records of added and removed stages (framework.py)

A problem refuses the advance before any stage moves (RecipeError); the file is left as it is, to be fixed.
Edit rules (user, 2026-10-30): anything may change, except
    - the type of a stage id: a stage of another type needs another id (a renamed id is a removal and an addition);
    - production and every stage before it: they ran first, and production cannot run twice yet (TODO: lift this
      once it can); without production in the run, none can be added. pico.config is production's;
    - name and run_root: the run directory is made.
What a change does to a stage depends on its state: NEW or FAILED, it runs with its new options; DONE, it is kept
and only recorded (recipe_changed `done`: rerun it from there); removed, its logs and output are archived.
The paths of the file are read as at the start: against the run's bundle copy, ../x against the source bundle.

Inputs:  <run_dir>/bundle/recipe.yml and run.json (a RunRecord).
Outputs: write_run_recipe() writes the two files above; the rest only reads.

Public API:
  write_run_recipe(recipe, run_dir, files)    start(): the run's recipe and recipes/recipe_0.yml
  run_recipe_file(run_dir), recipe_copy(run_dir, version)
  read_run_recipe(record, full=True, path=None)   (Recipe or None, issues); (None, ()) without the file (a run
                                              started before CL §55: its run.json recipe is the only one)
  recipe_changes(old, new)                    {stage id: added|removed|changed|moved} of two recipe dicts
  edit_problems(old, new, changes)            the Issues of the edit rules
  pending_change(record)                      what the next advance does with an edited file (taufw status), or None
"""
import json
import os

from TauFW.Framework._internal.defaults import BUNDLE_DIR_NAME, RECIPE_NAME, default_file_io
from TauFW.Framework._internal.recipes.recipe import Recipe, Issue, _outside_made_absolute
from TauFW.Framework._internal.recipes.validation import check_recipe_data

__all__ = ['write_run_recipe', 'run_recipe_file', 'recipe_copy', 'read_run_recipe', 'recipe_changes',
           'edit_problems', 'pending_change', 'changes_text', 'saved_dict', 'RECIPES_DIR_NAME']


# =============================================================================
# ================================= CONSTANTS =================================


RECIPES_DIR_NAME = "recipes"         # <run_dir>/recipes/: a copy of every version of the run's recipe
RECIPE_COPY      = "recipe_%d.yml"   # recipes/recipe_<N>.yml: version N (0: the start)


# =============================================================================
# ================================== FILES ====================================


def run_recipe_file(run_dir):
    """<run_dir>/bundle/recipe.yml: the run's recipe."""
    return os.path.join(run_dir, BUNDLE_DIR_NAME, RECIPE_NAME)


def recipe_copy(run_dir, version):
    """<run_dir>/recipes/recipe_<version>.yml."""
    return os.path.join(run_dir, RECIPES_DIR_NAME, RECIPE_COPY % (version))


def write_run_recipe(recipe, run_dir, files):
    """The run's recipe at start(): a copy of the file the recipe was read from (a loose .json one too: JSON is
    YAML), or for a Recipe made in code its dict; and the same as recipes/recipe_0.yml."""
    target = run_recipe_file(run_dir)
    files.make_directory(os.path.dirname(target))
    files.make_directory(os.path.join(run_dir, RECIPES_DIR_NAME))
    if recipe.path and os.path.isfile(recipe.path):
        files.copy_file(recipe.path, target)
    else:
        files.write_yaml(target, recipe.to_dict())
    files.copy_file(target, recipe_copy(run_dir, 0))


def read_run_recipe(record, full=True, path=None):
    """(Recipe or None, issues) of the run's recipe file. full: every check of `taufw check` (the files it names,
    the stage directories of {path} inputs, ...); otherwise only what Recipe.parse checks (fast: taufw status, and
    whether the file changed at all). (None, ()) if the run has no such file. path: another file read as the run's
    recipe (the editor's draft next to it, the menu)."""
    path = path or run_recipe_file(record.run_dir)
    if not os.path.isfile(path):
        return None, ()
    source = "%s/%s/%s" % (record.run_id, BUNDLE_DIR_NAME, RECIPE_NAME)
    try:
        data = default_file_io().read_yaml(path)
    except Exception as error:  # a YAML syntax error, ...
        return None, (Issue("", "cannot read %s: %s" % (path, error)),)
    bundle_dir = os.path.join(record.run_dir, BUNDLE_DIR_NAME)
    outside = record.bundle.get('source') or bundle_dir  # ../x: as when the run started
    if full:
        check = check_recipe_data(data, source, bundle_dir, path, outside)
        return check.recipe, tuple(check.issues)
    recipe, _, issues = Recipe.parse(_outside_made_absolute(data, outside), source, bundle_dir)
    return recipe, tuple(issues)


# =============================================================================
# ================================== CHANGES ==================================


def saved_dict(recipe):
    """recipe.to_dict() as run.json keeps it (read back from JSON: lists, not tuples), to compare with it."""
    return json.loads(json.dumps(recipe.to_dict()))


def recipe_changes(old, new):
    """{stage id: 'added', 'removed', 'changed' (anything of its entry) or 'moved' (only its place among the
    stages of both)} from one recipe dict to another; the stages of `new` in order, then the removed ones."""
    before = {entry['id']: entry for entry in old['stages']}
    after = {entry['id']: entry for entry in new['stages']}
    kept_before = [stage_id for stage_id in before if stage_id in after]
    kept_after = [stage_id for stage_id in after if stage_id in before]
    changes = {}
    for stage_id, entry in after.items():
        if stage_id not in before:
            changes[stage_id] = 'added'
        elif entry != before[stage_id]:
            changes[stage_id] = 'changed'
        elif kept_before.index(stage_id) != kept_after.index(stage_id):
            changes[stage_id] = 'moved'
    changes.update((stage_id, 'removed') for stage_id in before if stage_id not in after)
    return changes


def changes_text(changes):
    """'fit changed, extra added' (a recipe_changes())."""
    return ", ".join("%s %s" % (stage_id, change) for stage_id, change in changes.items())


def edit_problems(old, new, changes=None):
    """The Issues of the edit rules (see the top of this file) for a change of the run's recipe from `old` to `new`
    (recipe dicts; changes: their recipe_changes())."""
    changes = recipe_changes(old, new) if changes is None else changes
    problems = []
    for key in ('name', 'run_root'):
        if old.get(key) != new.get(key):
            problems.append(Issue(key, "cannot change in a run (it was %r): the run directory is made; start a new "
                                       "run for another one" % (old.get(key),)))
    types = {entry['id']: entry['stage'] for entry in old['stages']}
    for index, entry in enumerate(new['stages']):
        if types.get(entry['id'], entry['stage']) != entry['stage']:
            problems.append(Issue("stages[%d] (%s)" % (index, entry['stage']),
                                  "stage %r is a %s stage in this run: a stage of another type needs another id"
                                  % (entry['id'], types[entry['id']])))
    first = [entry['stage'] for entry in old['stages']].index('production') if any(
        entry['stage'] == 'production' for entry in old['stages']) else None
    if first is None:
        for index, entry in enumerate(new['stages']):
            if entry['stage'] == 'production' and entry['id'] not in types:
                problems.append(Issue("stages[%d] (production)" % (index),
                                      "a run without a production stage cannot get one: start a new run"))
        return problems
    fixed = old['stages'][:first + 1]
    if new['stages'][:first + 1] != fixed:
        ids = [entry['id'] for entry in fixed + new['stages'][:first + 1]]
        touched = {stage_id: changes[stage_id] for stage_id in dict.fromkeys(ids) if stage_id in changes}
        problems.append(Issue("stages", "stage %r (production) and the stages before it cannot change in a run: they "
                                        "ran first, and production cannot run twice yet. Undo: %s"
                              % (fixed[-1]['id'], changes_text(touched) or "the change of their order")))
    if old.get('pico') != new.get('pico'):
        problems.append(Issue("pico.config", "cannot change in a run with a production stage (only production "
                                             "reads it, and it cannot run twice yet): it was %r"
                              % ((old.get('pico') or {}).get('config'),)))
    return problems


def pending_change(record):
    """What the next advance does with the run's recipe file, for `taufw status` (None: it is the run's recipe,
    or there is none): it takes the change, or refuses it (the first problem of the fast checks)."""
    recipe, issues = read_run_recipe(record, full=False)
    if recipe is None and not issues:
        return None
    if issues:
        return "%s was edited and has %d problem(s): the next advance refuses it (%s)" % (
            os.path.join(BUNDLE_DIR_NAME, RECIPE_NAME), len(issues), issues[0])
    new = saved_dict(recipe)
    if new == record.recipe:
        return None
    changes = recipe_changes(record.recipe, new)
    problems = edit_problems(record.recipe, new, changes)
    if problems:
        return "%s was edited: the next advance refuses it (%s)" % (os.path.join(BUNDLE_DIR_NAME, RECIPE_NAME),
                                                                  problems[0])
    return "%s was edited (%s): the next advance takes it" % (os.path.join(BUNDLE_DIR_NAME, RECIPE_NAME),
                                                              changes_text(changes) or "no stage changed")
