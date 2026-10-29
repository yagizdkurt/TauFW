"""Create an analysis draft. No menu, terminal, stage execution or run records."""
import json
import os
from pathlib import Path
import tempfile

from TauFW.Framework._internal.defaults import RECIPE_NAME
from TauFW.Framework._internal.recipes.recipe import name_problem


EMPTY_RECIPE = Path(__file__).resolve().parents[1] / "empty_recipe.yml"


def create_analysis(root, name):
    """Create root/name/recipe.yml from the empty template and return the bundle path.

    Never overwrite an existing path. Publish the recipe only after a complete write;
    on failure remove only our temporary file and the newly created directory if empty.
    """
    problem = name_problem(name)
    if problem:
        raise ValueError("Analysis name " + problem)
    if name in (".", "..") or name.endswith("."):
        raise ValueError("Analysis name must not be '.' or '..' or end with a dot.")
    # Quote names such as true or 123 so YAML always reads them as strings.
    content = EMPTY_RECIPE.read_text(encoding="utf-8").format(name=json.dumps(name))
    root = Path(root).resolve()
    root.mkdir(parents=True, exist_ok=True)
    target = root / name
    try:
        target.mkdir()
    except FileExistsError:
        raise FileExistsError("%s already exists. Choose another analysis name." % target) from None
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", newline="\n", dir=target,
                                         prefix=".recipe-", suffix=".tmp", delete=False) as stream:
            temporary = Path(stream.name)
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, target / RECIPE_NAME)
    except BaseException:
        if temporary is not None:
            try:
                temporary.unlink()
            except OSError:
                pass
        try:
            target.rmdir()  # Never remove files another process may have put here.
        except OSError:
            pass
        raise
    return target
