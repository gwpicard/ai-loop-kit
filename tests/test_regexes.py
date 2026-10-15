"""Compile every module-level regular expression in the kit."""
from __future__ import annotations

import importlib.util
import re
import sys
import unittest
import warnings
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
KIT = ROOT / "kit"
SCRIPTS = KIT / "scripts"
sys.path.insert(0, str(SCRIPTS))


class ModuleRegexTest(unittest.TestCase):
    def test_every_module_level_regex_compiles(self):
        for index, path in enumerate(sorted(KIT.rglob("*.py"))):
            name = f"_kit_regex_check_{index}_{path.stem.replace('-', '_')}"
            spec = importlib.util.spec_from_file_location(name, path)
            self.assertIsNotNone(spec, path)
            self.assertIsNotNone(spec.loader, path)
            module = importlib.util.module_from_spec(spec)
            with self.subTest(module=path.relative_to(ROOT)):
                sys.modules[name] = module
                try:
                    with warnings.catch_warnings():
                        warnings.simplefilter("error", DeprecationWarning)
                        spec.loader.exec_module(module)
                        for regex_name, value in vars(module).items():
                            if isinstance(value, re.Pattern):
                                with self.subTest(regex=regex_name):
                                    re.compile(value.pattern, value.flags)
                finally:
                    sys.modules.pop(name, None)


if __name__ == "__main__":
    unittest.main()
