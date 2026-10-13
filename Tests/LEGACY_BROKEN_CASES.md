# Report: legacy and broken cases excluded from normal tests

These two cases are excluded because their existing scripts cannot complete in
the Python 3.9 test environment. The migration preserved their contents; it did
not introduce the defects described below. This report documents the problems
without fixing them.

## Overview

| Case | Classification | First failure in a suitable dependency environment |
| --- | --- | --- |
| `pico.sample` | `broken` | The `print(` call at line 88 has no closing parenthesis outside its comment. |
| `plotter.rdataframe` | `broken` | With PyROOT available, module execution reaches an undefined `kBlue` at line 17. |

The classifications describe these demonstration/test scripts. They do not
establish that the corresponding production classes are broken.

## `pico.sample`: a parenthesis hidden inside a comment

Source: [testSample.py](PicoProducer/testSample.py).

Line 88 reads:

```python
print(">>> Call Sample.getfiles..." # load Sample.files from txt file)
```

Everything after `#` is a comment, including the apparent closing `)`. The
opening `print(` therefore remains unclosed. Python cannot parse the module, so
none of its imports, sample construction, matching checks, or file operations
execute. This is a syntax defect, not a failing `Sample.getfiles()` call.

There is a separate integration constraint beyond the syntax error. Lines
14–35 configure real 2016 CMS datasets with no supplied local storage or file
list. Line 74 calls `sample.writefiles(..., nevts=True)`, which requests file
discovery and per-file event counts. The production
[Sample storage code](../PicoProducer/python/datasets/sample.py) routes discovery
to DAS when no storage source is available (`getfiles()`, lines 224–248).
Consequently, even a syntactically repaired script would not be an isolated,
offline normal test with its current defaults. This dependency is not itself
proof of another runtime defect, and no DAS request was made for this report.

## `plotter.rdataframe`: multiple independent runtime defects

Source: [testRDataFrame.py](Plotter/testRDataFrame.py).

This file parses as Python 3, but its module-level execution fails before
`main()` in an environment with working PyROOT. Line 11 imports only `TNamed`,
`RDataFrame`, and `RDF` from ROOT. Line 17 then evaluates:

```python
lcolors = [kBlue+1, kRed+1, kGreen+1, kMagenta+1]
```

None of those color names is defined in the Python namespace. `import ROOT`
does not make unqualified names such as `kBlue` available. The first lookup
raises `NameError`; the subsequent color names have the same issue.

Correcting the color imports alone would leave these problems:

| Location | Problem | Consequence if reached |
| --- | --- | --- |
| Lines 89, 145–150, 167 | `sampleset_RDF()` expects each input to unpack into `(stitle, fname, weight)`, but `main()` supplies filename strings. CLI `--fnames` also supplies strings. | The default paths raise `ValueError: too many values to unpack (expected 3)` before an RDataFrame is constructed. |
| Lines 103 and 122 | `res_dict` and `sname` are never defined. The loop defines `stitle`, not `sname`. | Histogram bookkeeping cannot proceed; line 103 first fails on `res_dict` if execution reaches it. |
| Lines 108–112 | `xvar` is read before its later assignment; `vfname` and `xexp` are also undefined. The variable loop instead defines `vname` and `vexp`. | Line 108 would raise `UnboundLocalError` for `xvar`; the expression-definition path has further undefined names. |
| Line 115 | `wname` is undefined. A `weight` string exists, but no corresponding `wname` is established. | The histogram booking call cannot execute as written. |
| Line 66 | `plot()` uses `TCanvas` without importing or defining it. | Calling this helper would raise `NameError`. The current `main()` does not call it. |
| Lines 143–150 | Default inputs live under `/scratch/ineuteli/analysis/UL2018`. | These external files are not portable repository fixtures; later execution would require suitable inputs and branches. |

The failures after the color lookup are established by source inspection. They
are masked by the first failure in the unchanged script and were not reproduced
through a full ROOT execution. The separate `plotter.rdataframe_sample` case is
still classified as local; this exclusion concerns `plotter.rdataframe` only.

## Why these are pre-existing, and how the runner handles them

For both files, the current SHA-256 hash after LF/CRLF normalization matches
the corresponding `canonical_sha256` in [migration.json](migration.json).
Their contents also match the original paths in the parent of migration commit
`046367c` (`git show 046367c^:<original-path>`), using the same normalization.
This directly confirms that the listed script defects existed before relocation.

[inventory.json](inventory.json) retains both case IDs and their reasons.
In [run.py](run.py), `select_cases()` maps `normal` to the `local` group and
selects only that group. Explicitly requesting one of these cases through
`normal --case ...` rejects the selection with its classification and reason;
it does not run the script or report a successful test.

## Validation scope

Validation used source inspection, the migration/historical hash
comparisons, and in-memory parsing with Python 3.13.8's
`ast.parse(..., feature_version=(3, 9))`. Parsing reproduced the unclosed parenthesis
(and, before those cases were removed, the two Python 2 print failures), and confirmed that the RDataFrame
file passes syntax parsing. This grammar check is not execution under Python
3.9 or a PyROOT runtime test. No full test suite, ROOT event processing, or
remote dataset access was performed. Only this Markdown report was added.

The Python 2 cases `common.loadingbar` and `common.table` were removed when
`LoadingBar` and `Table` moved to `TauFW.Utilities.CLI` (changelog §15, §17);
unit tests in `Tests/Utilities/test_cli.py` replace them.
