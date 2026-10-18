# Configs: templates for analysis bundles

This directory holds the **config templates** of the TauFW modules: data files that an analysis copies into its
bundle (`Analyses/<name>/`) and edits there. Analysts never edit the modules' own directories; everything an
analysis can change is a copy in its bundle.

```
Configs/
  README.md             this file
  configs.lock          id, version and content hash of every template (written by `taufw.py configs update`)
  <Module>/...          the templates of one module, e.g. Histogrammer/samples/v15_2025.yml
  Histogrammer/samples/ the sample model of each era (histogrammer.samples_v15_<era>)
  Histogrammer/setups/  the channel setups of fillhists.py (histogrammer.setup_<channel>)
  Fitter/tes_id/        the channel configs of the TES + tau ID fit (fitter.tes_id_*, changelog §22): read by
                        createinputsTES.py (Histogrammer) and the fit scripts (Fitter); the keys of each file are
                        grouped under banners by reader, see docs/contracts/tes-shapes.md
```

The config directories inside the modules (`PicoProducer/config/`, ...) are the modules' **internal** settings:
maintainers edit them by hand, users only through the module's own commands (e.g. `pico.py set ...`). Machine and
user settings (batch system, user directories) are internal settings, never templates.

## For analysts

1. List the templates: `taufw.py configs`.
2. Copy the one you need into your bundle, next to `recipe.yml`, and name the copy in the recipe.
3. Edit the values of your copy. Do **not** edit its `taufw_config` header: it says which template and which version
   the copy came from.
4. Or name the template itself in a recipe, as `Configs/<Module>/...` (e.g. `config: Configs/Fitter/tes_id/config_coarse_TT.yml`):
   the stage reads the template where it is (changelog §22). `taufw.py init --from <recipe>` makes copies of the
   templates a recipe names, so a bundle keeps what it ran with.

`taufw.py check`, `plan` and `start` warn when the template of a copy has a newer version than the copy: the
maintainers changed it since you copied it. Compare the two, and take over the changes or keep your copy on purpose
(the warning stays as long as the copy is older).

**Renamed module (October 2026, changelog §21):** the Plotter became the Histogrammer, so `Configs/Plotter/` is now
`Configs/Histogrammer/` and the ids `plotter.samples_*` / `plotter.setup_*` are `histogrammer.samples_*` /
`histogrammer.setup_*` (same values, same versions). A copy made before still works: `check`, `plan` and `start`
compare it with the renamed template and ask you to change the `id` line of its header (only that line). This
compatibility ends at the migration point.

## For maintainers

Every template is a YAML mapping that starts with the header:

```yaml
taufw_config:                     # set by the maintainers: analysts edit the values below, never these lines
  id: histogrammer.samples_v15_2025   # unique, never changes; starts with the module directory (lower case)
  version: 1                      # the content version: raised when a value changes
  schema: 1                       # the format version: which reader of the module understands the file
  description: the samples of the v15 tuples for 2025
```

- Only YAML (`.yml`, `.yaml`) data files: no Python (it would have to be imported), no JSON (`*.json` is ignored by
  git). A template lives in `Configs/<Module>/`, in any subdirectory.
- Write the header as a block (one key per line, as above), so the version can be raised automatically.
- After changing a template, run `taufw.py configs update`. A template whose **values** changed (comments and layout
  do not count) gets `version + 1` in its file, and `configs.lock` is rewritten; commit both. A version raised by hand
  is kept. A new template is locked with its version. Nothing is written while a template has a problem.
- Never lower a version, and never reuse an id. To replace a template, add one with a new id (e.g. a new tuple
  version) and remove the old one; the copies of the old one then get a warning.
- `schema` is the format of the file: raise it when the module's reader changes how it reads the file, not when a
  value changes.

`Tests/Framework/test_configs.py` (run by `python3 Tests/run.py all`; no ROOT, under a second) fails while
`configs.lock` is not up to date, while a template has a problem, and when a module's reader cannot read a template.
