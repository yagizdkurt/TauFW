"""
    - stage: python
      id: example_script
      inputs: {fit: NAME}
      file: steps/example_python_step.py
      options:
        pois: [tes, tid_SF]
"""
import json
from pathlib import Path

def run(ctx):
    # 1. Receive from framework
    pois = ctx.options.get("pois", ["tes", "tid_SF"])
    fits = ctx.input("fit", kind="fit")
    output = Path(ctx.stage_dir) / "summary.json"

    # 2. Perform analysis-specific work. The Framework doesnt care.
    rows = []
    for fit in fits:
        for value in fit.get("values", []):
            if value["poi"] in pois:
                rows.append({
                    **value,
                    "era": fit["era"],
                    "jet_wp": fit["jet_wp"],
                    "ele_wp": fit["ele_wp"],
                })

    # 3. Write our output into this stage's directory, created by the Framework.
    output.write_text(json.dumps(rows, indent=2) + "\n", encoding="utf-8")
    ctx.log(f"Wrote {len(rows)} fitted values to {output}")

    # 4. Return JSON-compatible metadata so later stages can find the output.
    #    The step runner writes result.json. The Framework waits for the process
    #    to exit successfully before recording the artifacts and continuing.
    return {
        "message": f"Exported {len(rows)} fitted values",
        "artifacts": [{
            "kind": "table",
            "path": str(output),
            "nrows": len(rows),
        }],
    }
