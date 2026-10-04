# Six themes — the generator of this branch's page

`six.py` rebuilds `kansai/index.html` as a prologue and six themes, following the author's plan in
`kansai/SHINGU.md`, from main's page:

```bash
git show origin/main:kansai/index.html > /tmp/main.html
python3 kansai/tools/six/six.py /tmp/main.html kansai/index.html
```

- **Existing blocks keep their text; they only move.** The exceptions are listed in `six.py`, each with an
  `assert`: the cut glance paragraph and its two photographs, the hinge paragraph moved to Theme 4, the
  exposure table split out of the pathways step (3G), and references whose direction the new order reversed
  ("above" → "below").
- **New text** (theme heads, part heads, leads, conclusions, cross-references, placeholders) is in `texts.py`.
- **Placeholders** (`<aside class="todo" data-plan="…">`) mark evidence the plan calls for and the page does
  not hold yet. The QA gate lists them as warnings on a working branch. A deploy run (`QA_DEPLOY=true`, set
  by `deploy.yml`) fails while any remain.
- `blocks.py` finds the elements of an HTML string by balanced tags.

If main's page changes, run the generator again; its `assert`s stop it where the source no longer matches.
Once `kansai/index.html` on this branch has been edited by hand, do not run the generator over it. Port
those edits into `texts.py`, or keep editing the page directly.
