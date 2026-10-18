#! /usr/bin/env python3
"""Export the samples of Histogrammer/config/samples_v15.py to the templates Configs/Histogrammer/samples/v15_<era>.yml.

Nothing is typed by hand: the old getsampleset() runs with the recorder (recorder.py, stub utils module, no ROOT) and
the files are written from the calls it makes. For every era:
  - with join=[] and split=[] and sentinel extra weights: the MC table, which rows take dyweight/ttweight, the
    stitching and the era's extra joins (every join after the DY join)
  - with the defaults: the extra weight values
  - one channel per channel kind: the data dataset pattern and the MC weight (a kind whose call raises in the old
    code, e.g. tautau in 2526, is left out: the model then raises too)
Each file is read back with TauFW.Histogrammer.sample.model.load_sample_model and compared value by value (types
included) before it is written; test_sample_model.py then compares every call of the old and the new function.

  python3 Tests/Histogrammer/sample_model/export.py [--outdir DIR] [--era ERA ...]
"""
import json
import os
import sys
from argparse import ArgumentParser

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import checkout
import recorder
from TauFW.Histogrammer.sample.model import load_sample_model, KEYS

OUTDIR = checkout.REPO / "Configs" / "Histogrammer" / "samples"
SENTINELS = {'dyweight': "@dyweight@", 'ttweight': "@ttweight@"}
DATA_CHANNELS = (('tautau', 'tautau'), ('muon', 'mutau'), ('electron', 'etau'), ('emu', 'emu'))
WEIGHT_CHANNELS = (('semileptonic', 'mutau'), ('ditau', 'tautau'), ('other', 'mumu'))


def export(era, function, targets):
    """The model dict of one era, from the calls of the old function."""
    calls = recorder.record(function, targets, 'mumu', era, join=[], split=[], table=False, **SENTINELS)
    _check(calls, 'mumu', era)
    assert calls[0][:2] == ['setera', [era]] and list(calls[0][2]) == ['cme'], calls[0]
    cme, core = calls[0][2]['cme'], calls[1]
    defaults = _extraweights(function, targets, era)
    rows = []
    for row in core[1][1]:
        group, name, title, xsec = row[:4]
        entry = {'group': group, 'name': name, 'title': title, 'xsec': xsec}
        if len(row) == 5:
            assert list(row[4]) == ['extraweight'], row
            matches = [key for key, sentinel in SENTINELS.items() if row[4]['extraweight'] == sentinel]
            assert len(matches) == 1, row
            entry['extraweight'] = matches[0]
        rows.append(entry)
    stitch, join = [], []
    rest = calls[2:]
    while rest and rest[0][0] == 'SampleSet.stitch':
        (_, (pattern,), options), rest = rest[0], rest[1:]
        assert sorted(options) == ['cme', 'incl', 'name'] and options['cme'] == cme, options
        stitch.append({'pattern': pattern, 'incl': options['incl'], 'name': options['name']})
    assert rest and rest[0] == ['SampleSet.join', ['DY'], {'name': 'DY'}], rest[:1]
    for _, patterns, options in rest[1:]:
        assert _ == 'SampleSet.join' and list(options) == ['name'], (_, options)
        join.append({'patterns': patterns, 'name': options['name']})
    data, weights = {}, {}
    for kind, channel in DATA_CHANNELS:
        found = _core(function, targets, channel, era)
        if found:
            data[kind] = found[1][0][1]
    for kind, channel in WEIGHT_CHANNELS:
        found = _core(function, targets, channel, era)
        if found:
            weights[kind] = found[2]['weight']
    return {'era': era, 'cme': cme, 'extraweights': defaults, 'mc': rows, 'data': data, 'weights': weights,
            'stitch': stitch, 'join': join}


def _extraweights(function, targets, era):
    """The default values of the extra weights: what the rows that take them get without an override."""
    calls = recorder.record(function, targets, 'mumu', era, join=[], split=[], table=False)
    marked = recorder.record(function, targets, 'mumu', era, join=[], split=[], table=False, **SENTINELS)
    values = {}
    for row, mark in zip(calls[1][1][1], marked[1][1][1]):
        for key, sentinel in SENTINELS.items():
            if len(mark) == 5 and mark[4]['extraweight'] == sentinel:
                assert values.setdefault(key, row[4]['extraweight']) == row[4]['extraweight'], (key, row)
    assert sorted(values) == sorted(SENTINELS), values
    return values


def _core(function, targets, channel, era):
    """The core getsampleset call of a channel (None if the old function raised before it)."""
    calls = recorder.record(function, targets, channel, era, join=[], split=[], table=False)
    found = [call for call in calls if call[0] == 'getsampleset']
    return found[0] if found else None


def _check(calls, channel, era):
    if not calls or calls[-1][0] == 'raised':
        raise RuntimeError("samples_v15.getsampleset(%r, %r) failed: %s" % (channel, era, calls[-1:]))


# =============================================================================
# ================================== WRITING ==================================


def write(model, outdir):
    """Write the template of one era and check that it reads back to the same values."""
    era = model['era']
    path = os.path.join(str(outdir), "v15_%s.yml" % (era))
    lines = [
        "taufw_config:                     # set by the maintainers: analysts edit the values below, never these lines",
        "  id: histogrammer.samples_v15_%s" % (era.lower()),
        "  version: 1",
        "  schema: 1",
        "  description: samples of the v15 pico tuples for %s (MC table, data, MC weights, stitching)" % (era),
        "# The samples Histogrammer/config/samples_v15.py getsampleset() uses for era %s, exported by" % (era),
        "# Tests/Histogrammer/sample_model/export.py. Format: Histogrammer/python/sample/model.py. "
        "The cross sections are the",
        "# values samples_v15.py computed (cross section times k-factor).",
        "era: %s" % (_text(era)),
        "cme: %r" % (model['cme']),
        "extraweights: {%s}   # defaults; plot/shape scripts may override them by name" % (
            ", ".join("%s: %s" % (key, _text(value)) for key, value in sorted(model['extraweights'].items()))),
        "mc:",
    ]
    for row in model['mc']:
        fields = ["group: %s" % (_text(row['group'])), "name: %s" % (_text(row['name'])),
                  "title: %s" % (_text(row['title'])), "xsec: %r" % (row['xsec'])]
        if 'extraweight' in row:
            fields.append("extraweight: %s" % (row['extraweight']))
        lines.append("  - {%s}" % (", ".join(fields)))
    lines.append("data:                             # dataset pattern by channel kind (tautau, muon, electron, emu)")
    lines.extend("  %s: %s" % (kind, _text(value)) for kind, value in model['data'].items())
    lines.append("weights:                          # MC weight by channel kind (semileptonic, ditau, other)")
    lines.extend("  %s: %s" % (kind, _text(value)) for kind, value in model['weights'].items())
    lines.append("stitch:%s" % ("" if model['stitch'] else " []"))
    lines.extend("  - {pattern: %s, incl: %s, name: %s}" % (_text(s['pattern']), _text(s['incl']), _text(s['name']))
                 for s in model['stitch'])
    lines.append("join:%s" % ("" if model['join'] else " []"))
    lines.extend("  - {patterns: [%s], name: %s}" % (", ".join(_text(p) for p in j['patterns']), _text(j['name']))
                 for j in model['join'])
    text = "\n".join(lines) + "\n"
    os.makedirs(str(outdir), exist_ok=True)
    with open(path, 'w', newline='\n') as stream:
        stream.write(text)
    _compare(path, model)
    return path


def _compare(path, model):
    """The file must read back to exactly the exported values (types too: 6744.0 stays a float)."""
    loaded = load_sample_model(path)
    for key in KEYS:
        value = getattr(loaded, key)
        expected = model[key]
        if isinstance(value, tuple):
            value = list(value)
        if json.dumps(value, sort_keys=True) != json.dumps(expected, sort_keys=True) or \
           _types(value) != _types(expected):
            raise RuntimeError("%s: %s does not read back as exported:\n%r\n%r" % (path, key, value, expected))


def _types(value):
    if isinstance(value, dict):
        return {key: _types(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_types(item) for item in value]
    return type(value).__name__


def _text(value):
    """A YAML double-quoted text (JSON strings are valid YAML)."""
    return json.dumps(value)


def main(argv=None):
    parser = ArgumentParser(description="Export samples_v15.py to Configs/Histogrammer/samples/v15_<era>.yml")
    parser.add_argument('--outdir', default=str(OUTDIR), help="default: %(default)s")
    parser.add_argument('--era', dest='eras', nargs='+', default=list(recorder.ERAS), help="default: every era")
    args = parser.parse_args(argv)
    with recorder.stub_utils():
        old = recorder.load_samples_v15()
        targets = recorder.old_targets(old)
        for era in args.eras:
            print(write(export(era, old.getsampleset, targets), args.outdir))
    return 0


if __name__ == "__main__":
    sys.exit(main())
