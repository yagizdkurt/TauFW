# Author: Yagizhan Dinckurt (October 2026) (yagizdkurt)
"""Menu help content. Edit the ordered (topic, explanation) pairs here.

Keep explanations aligned with the CLI behavior; rendering lives in _menu.py.
"""

# =============================================================================
# ================================ FAQ TOPICS =================================

FAQ = (
    ("Navigation", 
     "Use Up/Down to move and Enter to select. Esc goes back; "
     "at the main menu it exits. Page Up/Page Down scroll help, the pipeline or "
     "a command's output. Ctrl+C returns to the menu."),

    ("Recipes",
     "An analysis is a directory in Analyses/ with recipe.yml (the stages "
     "and their options), the config files it uses, and its Python steps. "
     "Select a listed analysis or enter another path (a bundle directory or "
     "a YAML or JSON recipe file). Relative paths are resolved from the "
     "directory where you launched taufw.py. A run reads its own copy of "
     "the bundle, made when it starts."),

    ("Starting a run", 
     "Choose a recipe in the left table; its pipeline appears on the right, "
     "with stages running from top to bottom. The picker needs at least 64 columns "
     "and 12 rows. Select a recipe to prepare its read-only plan and review the "
     "pipeline and planning notes. View detailed plan shows the output of "
     "taufw.py plan; Esc returns to the review. Select Start run to launch. "
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
     "live job counts without advancing or saving (taufw.py status; Esc stops "
     "a slow one). R checks again. "
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
     "histograms and fit run the Histogrammer and Fitter scripts on this machine "
     "and finish within one Continue, which can take hours for the fit. "
     "A stage that is not ready (no cmsenv, combine missing) stays NEW with "
     "the reason as its message; fix it and Continue. Logs are in the run "
     "directory, one folder per stage. Outputs stay in Histogrammer/ and Fitter/."),

    ("CLI equivalents", 
     "taufw.py plan RECIPE previews; taufw.py start RECIPE "
     "starts; taufw.py advance RUN_DIR continues; taufw.py status RUN_DIR "
     "inspects. Add --wait --poll 600 to advance for polling. Use --help for "
     "command options. pico.py and the other package entry points remain "
     "available independently."),

    ("Grid Certificate",
     "The main menu checks your existing grid proxy without asking for a password. "
     "A tick means it is valid; Warning: Proxy Failed! means it is missing, expired, "
     "or VOMS tools are unavailable. Select Grid Certificate to create or renew your "
     "CMS proxy with voms-proxy-init -voms cms: type your grid certificate password "
     "in the panel (shown as *; it goes to voms-proxy-init only and is kept nowhere) "
     "and press Enter. The result is shown in the panel. The tick follows the proxy: "
     "renewed or destroyed in another terminal, the next draw shows it."),

    ("Tests",
     "Open Tests from the main menu to run all automated tests, unit/harness "
     "suites, normal cases, or BBB regression checks. Choose tests uses Space "
     "to toggle checkboxes; move to Run and press Enter. Review the selected "
     "tests before Run; Esc returns without running. Page Up/Down scroll details. "
     "Tests use quiet output, with P/F/S statuses, failure tails and log paths. "
     "Normal PASS means the script exited successfully; SKIP means a missing "
     "dependency. BBB compares exact data/schema against saved expectations "
     "and requires Linux Python 3.9 with the matching ROOT environment and a "
     "baseline lock. Full testing needs the documented CMSSW/ROOT stack. "
     "Check environment only warns about Python package origins; it does not "
     "repair the environment. S or Ctrl+C asks, then stops the test run; while it "
     "stops, K kills it at once. "
     "Integration tests and baseline creation/replacement remain explicit CLI "
     "operations. The menu itself requires an interactive Linux terminal and "
     "working Framework imports. A test run goes on behind the menu: Esc leaves "
     "its screen, the main menu shows its state and Tests opens it again."),
     
)
