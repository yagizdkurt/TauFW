# Author: Yagizhan Dinckurt (October 2026) (yagizdkurt)
"""Samples: does the production stage make the tuples its readers ask for? Checked before a run starts.

A plots or histograms stage with the `samples` option (sample model files, copies of Configs/Plotter/samples/) says
which samples it reads, per era and channel: MC sample names and one data dataset pattern. A production stage says
which samples it makes (PicoProducer's sample catalogs, filtered as its first submission filters them). When a reader
takes its tuples from a production stage of the same recipe, the two lists are compared:

    sample_issues(recipe, stage_for) ─▶ (problems, warnings)
      problem:  a reader asks for an MC sample production does not make (era, channel), or its data pattern
                matches no sample production makes: `taufw.py plan` shows it, `start` refuses the recipe
      warning:  production makes a sample that no reader asks for (only when every reader of that production
                stage has the `samples` option: a reader without it reads the tables of samples_v15.py)

Readers without the option, readers of {external: ...} or {path: ...} tuples, and recipes without production are not
compared (the preflight of the reader checks that the tuple files exist).

Inputs:  a Recipe and its stages (Framework._stage_for). Reads the sample model files and PicoProducer's catalogs.
Outputs: two lists of Issues (recipe.py). Nothing is written.

Public API:
  sample_issues(recipe, stage_for) -> (problems, warnings)
"""
from fnmatch import fnmatch

from TauFW.Framework.recipe import Issue
from TauFW.Framework.stages import StageContext

__all__ = ['sample_issues']


# =============================================================================
# ================================= PIPELINE ==================================


def sample_issues(recipe, stage_for, maxshow=5):
    """(problems, warnings) of the comparison above; stage_for(stage id) -> the Stage object."""
    kinds = {stage_spec.id: stage_spec.stage for stage_spec in recipe.stages}
    problems, warnings, produced, used, readers = [], [], {}, {}, {}
    for index, stage_spec in enumerate(recipe.stages):
        source = stage_spec.connections.get('tuples')
        if not source or kinds.get(source) != 'production':
            continue
        readers.setdefault(source, []).append(bool(getattr(stage_spec.spec, 'samples', ())))
        if not getattr(stage_spec.spec, 'samples', ()):
            continue
        if source not in produced:
            production = recipe.stage(source)
            produced[source] = set(stage_for(source).produced_samples(production.spec, _context(recipe, source)))
            used[source] = set()
        made = produced[source]
        where = "stages[%d] (%s).samples" % (index, stage_spec.stage)
        requested = stage_for(stage_spec.id).requested_samples(stage_spec.spec, _context(recipe, stage_spec.id))
        for era, channel, names, data in requested:
            missing = [name for name in names if (era, channel, name) not in made]
            used[source].update((era, channel, name) for name in names if (era, channel, name) in made)
            if missing:
                problems.append(Issue(where, "%d MC sample(s) of %s %s are not made by production stage %r: %s"
                                      % (len(missing), era, channel, source, _names(missing, maxshow))))
            matched = [(e, c, name) for e, c, name in made if e == era and c == channel and data and fnmatch(name, data)]
            used[source].update(matched)
            if data and not matched:
                problems.append(Issue(where, "no data sample of %s %s made by production stage %r matches %r"
                                      % (era, channel, source, data)))
    for source, made in sorted(produced.items()):
        if not all(readers[source]):
            continue
        unread = sorted(made - used[source])
        if unread:
            warnings.append(Issue("stages (%s)" % (source), "production stage %r makes %d sample(s) that no reader "
                                  "asks for: %s" % (source, len(unread), _names(["%s %s %s" % row for row in unread],
                                                                                maxshow))))
    return problems, warnings


# =============================================================================
# ================================== HELPERS ==================================


def _context(recipe, stage_id):
    """The context a stage has in a plan (no run yet): its bundle and inputs, no artifacts."""
    stage_spec = recipe.stage(stage_id)
    return StageContext(inputs={slot: value for slot, value in stage_spec.connections.items() if value},
                        external=stage_spec.external, pico_config=recipe.pico_config_path,
                        bundle_dir=recipe.bundle_dir, stage_id=stage_id)


def _names(names, maxshow):
    return ", ".join(names[:maxshow]) + (", ... (%d more)" % (len(names) - maxshow) if len(names) > maxshow else "")
