"""Menu help content. Edit the ordered (topic, explanation) pairs here.

Keep explanations aligned with the CLI behavior; rendering lives in _menu.py.
"""

# =============================================================================
# ================================ FAQ TOPICS =================================

FAQ = (
    ("Navigation", 
     "Use Up/Down to move and Enter to select. Esc goes back; "
     "at the main menu it exits. Page Up/Page Down scroll help. After an "
     "operation, press Enter to return. Ctrl+C returns to the menu."),

    ("Recipes",
     "An analysis is a directory in Analyses/ with recipe.yml (the stages "
     "and their options), the config files it uses, and its Python steps. "
     "Select a listed analysis or enter another path (a bundle directory or "
     "a YAML or JSON recipe file). Relative paths are resolved from the "
     "directory where you launched taufw.py. A run reads its own copy of "
     "the bundle, made when it starts."),

    ("Starting a run", 
     "Select a recipe, review its plan, then select Start run. "
     "This submits production jobs and creates taufw_runs/<name>_<timestamp>/ "
     "with run.json and run.log. Starting returns after submission."),

    ("Continuing and polling", 
     "Continue loads an existing run.json. Advance "
     "once checks jobs and may resubmit failed chunks or merge output. Keep "
     "checking repeats while the run waits, every 600 seconds by default. "
     "Ctrl+C stops the foreground operation; it does not cancel batch jobs. "
     "Resume using the saved run record."),

    ("Status and run states", 
     "Inspect status shows saved stage states and "
     "live job counts without advancing or saving. Refresh checks again. "
     "NEW means unstarted; RUNNING means work in progress; WAITING means jobs "
     "are submitted or running; DONE means all stages finished; FAILED means "
     "a stage failed; BLOCKED means a requested stage is not implemented. "
     "Inspect also lists the fitted values of a finished fit."),

    ("Retries", 
     "Production waits until pending jobs finish before resubmitting "
     "failed or missing chunks. The recipe's max_tries defaults to three total "
     "submissions, including the first. FAILED runs are terminal; Continue "
     "does not reset the retry limit."),

    ("Stages",
     "Production runs on the batch system through PicoProducer. Plots, "
     "histograms and fit run the Plotter and Fitter scripts on this machine "
     "and finish within one Continue, which can take hours for the fit. "
     "A stage that is not ready (no cmsenv, combine missing) stays NEW with "
     "the reason as its message; fix it and Continue. Logs are in the run "
     "directory, one folder per stage. Outputs stay in Plotter/ and Fitter/."),

    ("CLI equivalents", 
     "taufw.py plan RECIPE previews; taufw.py start RECIPE "
     "starts; taufw.py advance RUN_DIR continues; taufw.py status RUN_DIR "
     "inspects. Add --wait --poll 600 to advance for polling. Use --help for "
     "command options. pico.py and the other package entry points remain "
     "available independently."),
     
)
