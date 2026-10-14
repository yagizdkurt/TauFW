# Committing and maintaining legacy code

Legacy code is retained for a specific reason: reproducing an older result,
understanding a retired workflow, or preserving a useful study. Archiving it
should leave the next developer able to understand that reason without asking
the original author.

This policy describes how to retire code and commit historical scripts. The
[analysis archive](../Legacy/OldAnalysis/README.md) lists archived analysis files;
the [component legacy inventory](Refactor-2025/Legacy.md) lists code remaining
in the component archives. Keep each file's inventory entry in one place.

## Decide what belongs in legacy

A file is a legacy candidate when its campaign has finished and it has no
ongoing role, its workflow has been retired, or a maintained implementation
has replaced it. State which of these applies and what evidence supports it.

Age, personal paths, specialization, and a lack of search results are clues,
not sufficient reasons on their own. A generator analyzer can be reusable; a
script written in 2023 can process 2022 data. A one-shot script and a retired
reusable module can both be archived, but describe them accurately.

Do not archive code that still supports a current result, production channel,
test, documented exercise, or another module unless its consumers are updated
in the same change. If its status is unclear, resolve that with the workflow
owner before declaring it retired. A broken script also needs a retirement
decision; moving it does not fix its defect.

Working analyses belong in [Analyses/](../Analyses/README.md), or their existing
documented workflow. Shared functionality belongs in the maintained component
that owns it. Keep disposable experiments local until there is a reason to
share them. Avoid committing another campaign-specific copy of a shared module
when a configuration or small reusable change would express the difference.

## When to make the decision

Review temporary scripts when a campaign or study ends, when replacing a
workflow, and before merging a change that introduces historical code. Retire
the old implementation alongside its replacement, once its remaining
consumers have been accounted for. Do not leave an unexplained duplicate in an
active directory for a future cleanup.

If a completed one-off study is first being committed for reference, put it
directly in the archive with its context. Do not describe it as previously
maintained or invent an original path it never occupied.

## Where to put it

Independent historical scripts belong directly inside a folder under
`Legacy/OldAnalysis/`, without component or analysis subfolders:

| Scope | Location | Assignment rule |
| --- | --- | --- |
| One data-taking year | `Legacy/OldAnalysis/2022/file.py` | Use input campaigns, era settings, payloads or recorded production commands. |
| Several explicitly identified years | `Legacy/OldAnalysis/2016-2018/file.py` | Use a range that accurately describes the covered years. |
| Multiple campaigns that do not fit a clear range | `Legacy/OldAnalysis/MultiYear/file.py` | List the supported years explicitly in the banner and inventory. |
| No dependence on a data-taking year | `Legacy/OldAnalysis/YearIndependent/file.py` | For theoretical or general studies whose inputs do not require a campaign year. |
| Insufficient campaign evidence | `Legacy/OldAnalysis/UnknownYear/file.py` | Explain what is missing; do not guess from the authoring date or algorithm name. |

Store a file once. A multi-year tool should not be copied into every year
folder. For a filename collision, choose a descriptive name such as
`mutau_cutflow_repair.py`; avoid ambiguous suffixes such as `old2` or `final`.
Keep required configurations alongside the script with descriptive filenames.

Coupled retired workflows belong under the root `Legacy/<Component>/` archive,
preserving their internal script and configuration structure. Python modules,
shared helpers and macros whose package structure matters belong in
`Legacy/<Component>/python/`, preserving their internal package structure. Check the actual
imports before choosing a destination. Do not flatten a package if that breaks
its consumers. Update explicit imports to `Legacy.<Component>.python.*` and
document that the checkout root must be on `PYTHONPATH`. Explain why it stays in the component archive; do not create
another arbitrary archive directory to avoid making this decision.

## What every archived source file must explain

Put a comment banner near the top, preserving the shebang and any Python
encoding declaration. Use `//` comments for C++/ROOT macros and `#` for Python
or shell scripts. Formats that do not allow comments, such as JSON, need the
equivalent explanation in their owning archive documentation.

Use this pattern, replacing the example details with evidence about the file:

```python
# =============================================================================
# LEGACY CODE - POSTPROCESSING
# Original location: PicoProducer/scripts/campaign_cutflow_repair.py
# Data-taking year: 2022
# Year basis: Default era and input directory select 2022_postEE.
# Purpose: Repair cutflow totals in existing campaign pico files.
# Why legacy: The fixed campaign repair is complete; no ongoing workflow uses it.
# Status: Reference material; review dependencies and input paths before reuse.
# =============================================================================
```

Choose a useful type: `ANALYSIS`, `PLOTTING`, `CORRECTION`, `POSTPROCESSING`,
`POSTFIT`, `DIAGNOSTICS`, or another precise description. Include a
`Previous archive:` line if the file has already moved through a legacy area.
For a file first committed in the archive, say that it was created there and
record its campaign origin instead of claiming a nonexistent earlier location.

Name the replacement when there is one. Record the required working directory,
environment, external inputs and known defects in the owning archive README.
For data repair tools, explain what they modify and how to verify the result.
Include an owner or contact and retirement date in the README entry so later
developers know who can answer questions about the archived workflow.

## How to prepare the change and commit

1. **Establish the purpose and retirement reason.** Read the script, its
   configuration and its callers. Identify the data year separately from its
   creation date and record any uncertainty.
2. **Check dependencies in both directions.** Search filenames and module
   names with `rg`, including relevant ignored local configurations. Inspect
   imports, channel loaders, shell commands, ROOT macro loading, tests and
   documentation. Check sibling imports, `__file__`, working-directory paths,
   configuration lookup and external payload paths. Distinguish executable
   callers from comments and similarly named functions. Record any external
   consumers you know about; a repository search cannot rule those out.
3. **Move and explain the file.** Use `git mv` for tracked files, add the
   banner, and preserve its implementation. If restoring or fixing behavior
   is also necessary, describe that separately so the reviewer can distinguish
   a relocation from a functional change.
4. **Update the owning inventory and consumers.** Add one entry with its
   purpose, year evidence, retirement reason, owner, date and replacement.
   Remove the old inventory entry, update links and commands, and remove empty
   directories. Do not leave copies or stale registrations behind.
5. **Validate only what the change needs.** For a comment-only Python move,
   compare the code before and after and check parsing. Check affected imports
   or path resolution when necessary, plus documentation links and
   `git diff --check`. Run a small relevant test if behavior changed. Do not run
   a data-writing repair merely to test its relocation. Report existing
   failures and checks you could not perform; do not claim the archive runs
   when only static checks were done.
6. **Review the staged changes before committing.** Stage the moves, banners
   and related documentation together. Inspect `git diff --cached` and
   `git diff --cached --check`. Exclude generated caches, logs, ROOT outputs,
   plots, private credentials and unrelated local changes. Include source,
   small required configurations and enough input provenance to understand
   the study. Avoid indiscriminate `git add .`.

Use a commit message that names the retired workflow, for example:
`Archive completed 2022 cutflow repair`. Its description should explain why it
is retired, its old and new locations, affected consumers, any behavior changes,
and the validation performed. A reviewer should be able to assess the change
without reconstructing the author's chat history.

## Being a responsible developer

Own the lifecycle of code you introduce. Make its purpose, inputs, outputs and
maintenance status clear while the context is still fresh. Before handing over
a result, reconcile the repository with the workflow actually used: retain the
needed source and configuration, document external input versions, and retire
temporary steps that have served their purpose.

Prefer honest uncertainty to an invented year or unsupported claim that a
file is unused. Leave enough evidence for another developer to reproduce or
evaluate the work. Keep the archive discoverable without letting maintained
workflows silently depend on it.

If archived code becomes useful again, restore it to an appropriate maintained
location, review its dependencies and scientific assumptions, add focused
validation, and update its documentation and inventory. Remove or revise the
legacy banner as part of that change. Do not maintain two competing copies.
