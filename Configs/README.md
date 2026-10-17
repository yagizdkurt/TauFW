# Configs: templates for analysis bundles

This directory holds the **config templates** of the TauFW modules: data files that an analysis copies into its
bundle (`Analyses/<name>/`) and edits there. Analysts never edit the modules' own directories; everything an
analysis can change is a copy in its bundle.

```
Configs/
  README.md             this file
  configs.lock          id, version and content hash of every template (written by `taufw.py configs update`)
  <Module>/...          the templates of one module, e.g. Plotter/samples/v15_2025.yml
```

The config directories inside the modules (`PicoProducer/config/`, ...) are the modules' **internal** settings:
maintainers edit them by hand, users only through the module's own commands (e.g. `pico.py set ...`). Machine and
user settings (batch system, user directories) are internal settings, never templates.

## For analysts

1. List the templates: `taufw.py configs`.
2. Copy the one you need into your bundle, next to `recipe.yml`, and name the copy in the recipe.
3. Edit the values of your copy. Do **not** edit its `taufw_config` header: it says which template and which version
   the copy came from.

`taufw.py check`, `plan` and `start` warn when the template of a copy has a newer version than the copy: the
maintainers changed it since you copied it. Compare the two, and take over the changes or keep your copy on purpose
(the warning stays as long as the copy is older).

## For maintainers

Every template is a YAML mapping that starts with the header:

```yaml
taufw_config:                     # set by the maintainers: analysts edit the values below, never these lines
  id: plotter.samples_v15_2025    # unique, never changes; starts with the module directory (Plotter -> plotter)
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
