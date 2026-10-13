# Plotter bug register

Defects found while connecting the Plotter to the TauFW Framework (Part G, October 2026, branch `Refactor-2025`).
Same policy as [PicoProducer/docs/BUGS.md](../../PicoProducer/docs/BUGS.md): bugs on the path the Framework runs are
fixed with `# BUGS <ID>` comments at the changed lines; others are registered only.

**Severity:** **crash** (raises on a reachable path), **wrong** (silently wrong), **latent** (nothing reaches it).

| ID | Location | Symptom | Severity | Fix | Output impact |
|---|---|---|---|---|---|
| L01 | `plot.py` `plot` (variable lists) | `idDeepTau2018v2p5VSVjet_2` and `idDeepTau2018v2p5VSVSe_2` are not branches of the pico tuples, but are plotted for every channel (also mumu), and the tau-channel list has `VSVSe` instead of `VSe` | wrong | Part G: the two all-channel entries are removed (the tau-channel list has the tau ID variables), `VSVSe` -> `VSe` | the two broken plots are gone; tau channels get a correct `idDeepTau2018v2p5VSe_2_zoom` plot |
| L02 | `config/samples_v15.py:285` (`getsampleset`) vs `python/sample/utils.py:29` (`_getsampleset`) | the file-name pattern is passed as `fname=`, but the generic builder reads `file=`; so `samples.filename` in the Fitter configs and `fname` in `plot.py` are ignored and the default `$PICODIR/$SAMPLE_$CHANNEL$TAG.root` is always used | latent | registered only: every caller uses the default pattern today. A fix must also stop `file=` from reaching the `MC(...)` keyword arguments, so it needs a test with tuples | |
