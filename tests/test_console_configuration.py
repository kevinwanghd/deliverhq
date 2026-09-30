import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "skill" / "scripts"


class ConsoleConfigurationTests(unittest.TestCase):
    def test_every_entrypoint_script_references_configure_console(self):
        entrypoints = [
            path
            for path in sorted(SCRIPTS.glob("*.py"))
            if "__main__" in path.read_text(encoding="utf-8")
        ]
        self.assertTrue(entrypoints, "no entrypoint scripts found")

        missing = [
            path.name
            for path in entrypoints
            if "configure_console" not in path.read_text(encoding="utf-8")
        ]

        print(f"checked {len(entrypoints)} entrypoint scripts")
        self.assertEqual(
            missing,
            [],
            "entrypoint scripts missing configure_console: " + ", ".join(missing),
        )


if __name__ == "__main__":
    unittest.main()
