"""Python step of the tes_id_2025 analysis: one table of the fitted values of every working point.

Recipe (recipe.yml):

    - stage: python
      id: fit_summary
      inputs: {fit: fit}
      file: steps/fit_summary.py
      options: {pois: [tes, tid_SF]}

Inputs:  fit: the artifacts of the stage connected to the `fit` input: {kind: 'fit', era, jet_wp, ele_wp,
         values: [{region, poi, value, low, high}], corrections: [paths]} per point, and with the fit's summary step
         {kind: 'corrections', era, path, combined} per era.
Outputs: <run_dir>/stages/fit_summary/summary.txt (the table, then the correction files the fit wrote) and
         summary.json (the rows), and one 'table' artifact.
"""
import json
import os


def run(ctx):
    """Collect the fitted values of the chosen parameters (options.pois) and write them as a table, followed by the
    correction files of the fit (the results to copy to their final place: the Framework does not)."""
    pois = ctx.options.get('pois') or ['tes', 'tid_SF']
    fits = ctx.input('fit', kind='fit')
    rows = [dict(value, era=fit['era'], jet_wp=fit['jet_wp'], ele_wp=fit['ele_wp'])
            for fit in fits for value in fit.get('values', [])
            if value['poi'] in pois]
    if not rows:
        ctx.log("no fitted values found (did the fit stage run its fit step?)")
    files = [path for fit in fits for path in fit.get('corrections', [])] + \
        [artifact['path'] for artifact in ctx.input('fit', kind='corrections')]
    table = os.path.join(ctx.stage_dir, 'summary.txt')
    with open(table, 'w') as stream:
        stream.write(_table(rows))
        stream.write(_files(files))
    with open(os.path.join(ctx.stage_dir, 'summary.json'), 'w') as stream:
        json.dump(rows, stream, indent=2)
    ctx.log("wrote %s" % (table))
    points = {(row['era'], row['jet_wp'], row['ele_wp']) for row in rows}
    return {'message': "%d value(s) of %d working point(s)" % (len(rows), len(points)),
            'artifacts': [{'kind': 'table', 'path': table, 'nrows': len(rows)}]}


def _table(rows):
    """A fixed-width text table: era, working points, region, parameter, value and 1-sigma interval."""
    lines = ["%-8s %-8s %-8s %-16s %-7s %9s  %s" % ("era", "jet WP", "ele WP", "region", "poi", "value",
                                                    "1 sigma")]
    for row in sorted(rows, key=lambda r: (r['era'], r['jet_wp'], r['ele_wp'], r['region'], r['poi'])):
        interval = ("[%.4f, %.4f]" % (row['low'], row['high'])
                    if row.get('low') is not None and row.get('high') is not None else "-")
        lines.append("%-8s %-8s %-8s %-16s %-7s %9.4f  %s" % (row['era'], row['jet_wp'], row['ele_wp'],
                                                             row['region'], row['poi'], row['value'], interval))
    return "\n".join(lines) + "\n"


def _files(paths):
    """The correction files, each with whether it exists (a missing one: its fit step did not run, or failed)."""
    if not paths:
        return "\nCorrection files: none (the fit ran without its corrections and summary steps)\n"
    return "\nCorrection files:\n" + "".join("  %s%s\n" % (path, "" if os.path.isfile(path) else "  (missing)")
                                             for path in paths)
