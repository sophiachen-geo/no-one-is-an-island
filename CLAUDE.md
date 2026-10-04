# Notes for Claude

- **SHINGU.md** means `kansai/SHINGU.md`. It is the author's editorial plan for the Kansai page (`kansai/index.html`):
  the spine of the argument, a prologue plus six themes, and where each piece of existing evidence goes.
  - When the author names it, read it from there.
  - Additions and edits go into that file.
  - "Apply it" means restructuring the page as it says.
  - It is not deployed: the Pages build copies only `index.html`, `kansai/index.html`, `kansai/data`, `kansai/img` and the
    standalone map folders.
- The six-theme version of the page lives on the branch `claude/kansai-six-themes`. It is built from main's page by
  `kansai/tools/six/six.py`, with its new text in `texts.py` (see that folder's README).
  - Placeholders (`.todo`, with the plan's part code) mark evidence still to add.
  - A deploy fails while any remain.
