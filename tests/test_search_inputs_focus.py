from pathlib import Path
import re
import unittest


ROOT = Path(__file__).resolve().parents[1]
WEB_CLIENT = ROOT / "web_client"


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


class SearchInputFocusTests(unittest.TestCase):
    def test_simplified_library_search_does_not_rerender_focused_input(self) -> None:
        source = read(WEB_CLIENT / "views" / "simplified_library.js")

        handler = re.search(r'querySelector\("#simpleLibrarySearch"\).*?addEventListener\("input".*?\n  \}\);', source, re.S)
        self.assertIsNotNone(handler)
        self.assertIn("refreshSimpleLibraryContent", handler.group(0))
        self.assertNotIn("renderSimplifiedLibraryView", handler.group(0))

    def test_developer_library_search_does_not_rerender_focused_input(self) -> None:
        source = read(WEB_CLIENT / "views" / "library.js")

        handler = re.search(r'querySelector\("#librarySearch"\).*?addEventListener\("input".*?\n  \}\);', source, re.S)
        self.assertIsNotNone(handler)
        self.assertIn("refreshLibraryContent", handler.group(0))
        self.assertNotIn("renderLibraryView", handler.group(0))


if __name__ == "__main__":
    unittest.main()
