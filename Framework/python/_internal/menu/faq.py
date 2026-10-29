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
     "a command's output. Ctrl+C goes back too; the editor asks before discarding changes."),

    ("Recipes",
     "An analysis is a directory in Analyses/ with recipe.yml (the stages "
     "and their options), the config files it uses, and its Python steps. "
     "Select a listed analysis or enter another path (a bundle directory or "
     "a YAML or JSON recipe file). The examples (Analyses/Examples/) have their "
     "own list: [Examples], above Back. Relative paths are resolved from the "
     "directory where you launched taufw.py. A run reads its own copy of "
     "the bundle, made when it starts."),

    ("Starting a run", 
     "Use [Create a new run] at the top of the list to choose an analysis name and create "
     "Analyses/<name>/recipe.yml with an empty pipeline. Esc cancels; existing files are never overwritten. "
     "The new analysis is selected and labelled Draft. A draft cannot start until stages are configured. "
     "E opens the Run editor entry point for the selected analysis (the editor screen is coming next). "
     "Choose a recipe on the left; its pipeline appears on the right as a table: each stage, what it reads "
     "and its description, with the number of errors and warnings above it. The picker needs at least 64 "
     "columns and 12 rows. Select a recipe to open its plan: Overview, Errors and Warnings (when there are "
     "any) and each stage's details (samples and jobs, or commands; F shows the commands in full). "
     "Start run is at the top: red and refused with errors, yellow with warnings. E edits; Esc goes back. "
     "This submits production jobs and creates taufw_runs/<name>_<timestamp>/ "
     "with run.json and run.log. Starting returns after submission."),

    ("Continuing and polling", 
     "Continue loads an existing run.json. At 120 columns and 18 rows or more, the run list stays on the left "
     "and the selected run's actions and saved stages appear on the right. Enter or Tab focuses the actions; "
     "choose one and press Enter to run it. Esc returns to the list. Page Up/Down scrolls details; R reloads "
     "them. In smaller terminals, Enter opens the selected run as before. Discovery and previews load "
     "behind the menu: you can keep moving or leave. Advance "
     "once checks jobs and may resubmit failed chunks or merge output. Keep "
     "checking repeats while the run waits, every 600 seconds by default. "
     "Ctrl+C stops the foreground operation; it does not cancel batch jobs. "
     "Resume using the saved run record."),

    ("Status and run states", 
     "Inspect status shows saved stage states and "
     "live job counts without advancing or saving (taufw.py status; Esc stops "
     "a slow one). At 120 columns and 18 rows or more, the selected run's status appears beside the list "
     "after a short pause. Up/Down changes runs, Page Up/Down scrolls status, and Enter opens it full screen. "
     "A small ASCII decay animates while status is read; you can still move or leave. "
     "R checks again, keeping the previous preview visible while it loads. "
     "NEW means unstarted; RUNNING means work in progress; WAITING means jobs "
     "are submitted or running; DONE means all stages finished; FAILED means "
     "a stage failed; BLOCKED means a requested stage is not implemented. "
     "Inspect also lists the fitted values of a finished fit."),

    ("Retries", 
     "Production waits until pending jobs finish before resubmitting "
     "failed or missing chunks. The recipe's max_tries defaults to three total "
     "submissions, including the first; then the production stage FAILS. "
     "Continue then offers Retry: max_tries more tries for the failed chunks "
     "(3 made, max_tries 3: up to 6); nothing is moved. Other production "
     "failures (no samples, a merged tuple that failed validation) need a new "
     "run. A failed local stage (histograms, "
     "plots, shapes, fit, python step) can run again: fix the cause, then "
     "Continue offers Retry (taufw retry). The finished stages are kept, "
     "the failed attempt is moved to logs/<id>/attempt<N>/, and run.json "
     "records the retry. If the run's bundle copy was edited, every advance "
     "warns once and run.json and the manifests say so (bundle_changed)."),

    ("Stages",
     "Production runs on the batch system through PicoProducer. Plots, "
     "histograms and fit run the Histogrammer and Fitter scripts on this machine "
     "and finish within one Continue, which can take hours for the fit. "
     "A stage that is not ready (no cmsenv, combine missing) stays NEW with "
     "the reason as its message; fix it and Continue. Logs are in the run "
     "directory, one folder per stage. Outputs stay in Histogrammer/ and Fitter/."),

    ("User config",
     "Analyses/UserConfig.yaml holds your own settings: where your runs go "
     "(runs.run_root) and your production settings (EOS output folders, batch "
     "system, queue). TAUFW_USER_CONFIG can name another file. Modify User Config "
     "opens it inside the menu and creates it if missing. F2 saves, Esc goes back, "
     "and Tab inserts two-space indentation. UserConfig.md opens beside it at 110 columns or more. "
     "F5 switches panes, F4 hides/opens the manual; in smaller terminals only the focused pane is shown. "
     "Arrow keys and Page Up/Down move in that pane; each keeps its own position. "
     "The manual is read only. Save errors keep your edits so you "
     "can fix them; leaving asks about unsaved changes. Change production output "
     "folders between runs. Git ignores the default file. Setup or taufw userconfig "
     "also makes it if missing. The recipe wins over it; plan names what came "
     "from it. Until you set reviewed: true, check, plan and start warn in one "
     "line and the menu shows Modify User Config (Please set) in yellow. Scripts read it with TauFW.Utilities.UserConfig."),

    ("CLI equivalents", 
     "taufw plan RECIPE previews; taufw start RECIPE "
     "starts; taufw advance RUN_DIR continues; taufw status RUN_DIR "
     "inspects. taufw userconfig makes or shows your user config. "
     "Add --wait --poll 600 to advance for polling. Use --help for "
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
