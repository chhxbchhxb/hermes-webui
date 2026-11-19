# PR #7687 — response-first run-detail evidence

Screenshots captured against a local WebUI server on an isolated test
home with one synthetic cron artifact ("Nightly backup sweep", a
writer-framed run document built with the installed Agent's own writer
constants: 30 KB, 381 lines, 366 context lines before `## Response`).
No real user data appears in any image.

| file | state |
|---|---|
| desktop-row-closed.png | job detail, runs list, no run body mounted |
| desktop-collapsed.png | run body collapsed — response-first snippet |
| desktop-expanded.png | expanded — Response block first, context disclosure, "View raw output" |
| desktop-focus-keyboard.png | keyboard focus ring on the context disclosure summary (desktop) |
| desktop-expanded-second-toggle.png | same response-first order after collapse/expand toggled twice |
| narrow-collapsed.png | collapsed at 390 px |
| narrow-expanded.png | expanded at 390 px |
| narrow-focus-keyboard.png | keyboard focus ring on the summary at 390 px |
