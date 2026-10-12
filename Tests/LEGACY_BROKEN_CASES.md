# Report: legacy and broken cases excluded from normal tests

These four cases are excluded because their existing scripts cannot complete in
the Python 3.9 test environment. The migration preserved their contents; it did
not introduce the defects described below. This report documents the problems
without fixing them.

## Overview

| Case | Classification | First failure in a suitable dependency environment |
| --- | --- | --- |
| `common.table` | `legacy` | Python 3 cannot parse the Python 2 `print` statement at line 20. |
| `common.loadingbar` | `legacy` | Python 3 cannot parse the Python 2 `print` statement at line 18. |
| `pico.sample` | `broken` | The `print(` call at line 88 has no closing parenthesis outside its comment. |
| `plotter.rdataframe` | `broken` | With PyROOT available, module execution reaches an undefined `kBlue` at line 17. |

The classifications describe these demonstration/test scripts. They do not
establish that the corresponding production classes are broken.

## `common.table`: an incomplete Python 3 conversion

Source: [testTable.py](common/testTable.py).

Line 20 contains:

```python
print ">>> Table from hist"
```

This is a Python 2 print statement, which is invalid Python 3 syntax. The parser
rejects the whole file before imports, argument parsing, or any table code runs.
The same syntax appears at lines 28, 39, 51, 62, and 75. Other statements already
use `print(...)`, so the conversion is incomplete rather than absent.

There is also a later Python 2 compatibility problem: `printhist()` calls
`xrange(nevts)` at line 16 without defining or importing `xrange`. If the print
syntax were corrected, this would raise `NameError` when that function runs
under Python 3. The script also requires PyROOT for its histogram example.

The immediate exclusion is caused by the script's syntax, not by a demonstrated
failure of the production `Table` implementation.

## `common.loadingbar`: Python 2 print statements

Source: [testLoadingBar.py](common/testLoadingBar.py).

The first invalid statement is at line 18:

```python
print ">>> Done with first loading bar."
```

Additional Python 2 print statements occur at lines 44, 60, and 71. Python 3
rejects the entire file during parsing, before the `LoadingBar` import or any
progress-bar loop executes. These statements must all be considered in any
future Python 3 conversion; changing only the first would expose the next syntax
error.

This is a legacy script compatibility issue. Its current failure provides no
evidence that the production `LoadingBar` class itself fails.

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

For all four files, the current SHA-256 hash after LF/CRLF normalization matches
the corresponding `canonical_sha256` in [migration.json](migration.json).
Their contents also match the original paths in the parent of migration commit
`046367c` (`git show 046367c^:<original-path>`), using the same normalization.
This directly confirms that the listed script defects existed before relocation.

[inventory.json](inventory.json) retains all four case IDs and their reasons.
In [run.py](run.py), `select_cases()` maps `normal` to the `local` group and
selects only that group. Explicitly requesting one of these cases through
`normal --case ...` rejects the selection with its classification and reason;
it does not run the script or report a successful test.

## Validation scope

Validation used source inspection, the four migration/historical hash
comparisons, and in-memory parsing with Python 3.13.8's
`ast.parse(..., feature_version=(3, 9))`. Parsing reproduced the two Python 2
print failures and the unclosed parenthesis, and confirmed that the RDataFrame
file passes syntax parsing. This grammar check is not execution under Python
3.9 or a PyROOT runtime test. No full test suite, ROOT event processing, or
remote dataset access was performed. Only this Markdown report was added.
