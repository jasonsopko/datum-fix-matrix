# Adding a fix or a column

Everything on the page is computed by `generate.py` from GitHub, so a change here is a change to what it checks, never to the table itself.

- **A new fix:** append an entry to `FIXES`. Give it a `marker` (a regex that only appears in the fixed code, over `src/*.c`, `src/*.h` and `doc/*.md`), or an `exists` path, or a `contains` commit that every fixed build has as an ancestor. Add `prs` with the PR number per column key so an open PR shows as pending rather than missing.
- **A new repository or branch:** append to `COLUMNS`. `main` is the branch people build; `sides` are branches where a fix may sit unmerged.
- **A new package:** append to `PACKAGES` with how to find the ref it builds (a submodule path, a Dockerfile `ARG`, or a branch).

Run `python3 generate.py` locally with `gh` logged in to see the result before opening a PR. The workflow regenerates hourly.
