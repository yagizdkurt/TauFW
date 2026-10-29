"""CL §54: the Tab completion of taufw.sh (_taufw_complete) knows exactly the commands, the options and the configs
choices of Framework/scripts/taufw.py (build_parser): a command or option added to one must be added to the other."""
import argparse
import importlib.util
import re
import unittest

import checkout

SCRIPT = checkout.REPO / "taufw.sh"


def _commands():
    """{command: its argparse parser} of taufw.py."""
    spec = importlib.util.spec_from_file_location("taufw_cli", str(checkout.TAUFW_SCRIPT))
    cli = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(cli)
    parser = cli.build_parser()
    return next(action for action in parser._actions if isinstance(action, argparse._SubParsersAction)).choices


class CompletionTests(unittest.TestCase):
    def setUp(self):
        text = SCRIPT.read_text(encoding="utf-8")
        start = text.index("_taufw_complete() {")
        self.body = text[start:text.index("\n}\n", start)]
        self.commands = _commands()

    def test_the_commands(self):
        words = re.search(r"compgen -W '([^']*)'", self.body).group(1).split()
        self.assertEqual(sorted(word for word in words if not word.startswith("-")), sorted(self.commands))

    def test_the_options_of_each_command(self):
        options = dict(re.findall(r"^\s+([a-z]+)\) options='([^']*)' ;;$", self.body, re.M))
        self.assertEqual(sorted(options), sorted(self.commands))
        for name, parser in self.commands.items():
            with self.subTest(command=name):
                expected = {option for action in parser._actions for option in action.option_strings}
                self.assertEqual(set(options[name].split()), expected)

    def test_the_configs_choices(self):
        choices = next(action.choices for action in self.commands["configs"]._actions if action.dest == "action")
        words = re.search(r"configs\) mapfile -t COMPREPLY < <\(compgen -W '([^']*)'", self.body).group(1).split()
        self.assertEqual(sorted(words), sorted(choices))


if __name__ == "__main__":
    unittest.main()
