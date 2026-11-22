# PR #8668 — running-turn actions and recovery

Captured in Chromium on the real WebUI page with the same synthetic session and controlled HTTP/SSE responses on each revision. No real provider, personal workspace, or mobile hardware was used. The phone context has touch, no hover and a coarse pointer.

| Viewport | Running (before / after) | Sidebar-first recovery (before / after) |
| --- | --- | --- |
| Desktop · 1440×900 | [Before](assets/desktop-busy-before.png) / [After](assets/desktop-busy-after.png) | [Before](assets/desktop-recovered-before.png) / [After](assets/desktop-recovered-after.png) |
| Narrow · 820×900 | [Before](assets/narrow-busy-before.png) / [After](assets/narrow-busy-after.png) | [Before](assets/narrow-recovered-before.png) / [After](assets/narrow-recovered-after.png) |
| Phone · 390×844 | [Before](assets/phone-busy-before.png) / [After](assets/phone-busy-after.png) | [Before](assets/phone-recovered-before.png) / [After](assets/phone-recovered-after.png) |

* Running control: upstream `dc88be5716edaab596f367a22dcb3eaffcc26036`. The current user row could expose an Edit action even though the turn was running.
* Recovery control: previous PR head `eec36b90c43e7e76656a62f20b1ce75a198d034c`. The sidebar reported idle, but equal message counts left the final answer and actions missing.
* Updated PR head: `6e376670c254734f68b56343dd7e43e3a4df4dee`. The first recovered render restores the answer and actions; the delayed reconnect reply does not revive the reconnect status.
* [Phone Edit after tapping the recovered control](assets/phone-editing.png) shows the original question and the new answer.
* [Application error](assets/desktop-apperror.png) shows the previous assistant answer and the separate, specific terminal error.

Run `python tests/browser_8643_busy_message_actions.py --screenshots <dir>` from the code checkout with Playwright and Chromium installed. The probe verifies DOM state and drives real click/tap interactions; the screenshots complement those checks.
