# Web QA — five responsive viewports

> Captured 2026-08-22 against the local LoomQ web server with real browser automation. This is post-acceptance supplemental UX evidence; it does not alter Issue #61's archived commit.

## Exercise

At each relevant viewport, the browser loaded the first-run screen. Result viewports used the visible **第一次实验** shortcut followed by **运行实验**. The local `spinq_taurus_simulator` Bell run returned 1024 shots: `00=512`, `11=512`.

| Viewport | Captured state | Result | Overflow / clipping | Notes |
|---|---|---|---|---|
| 1440×900 | First screen + keyboard focus | PASS | None / 0 controls | Chinese hero and controls readable; Tab visibly focuses the skip link. |
| 1366×768 | Measurement-result area | PASS | None / 0 controls | 00/11 bars and table readable. |
| 1280×720 | Boundary/explanation route | PASS | None / 0 controls | Result and scientific boundary copy remain visible. |
| 390×844 | Mobile first screen | PASS | None / 0 controls | Controls stack without button clipping; Chinese wraps within the card. |
| 375×812 | Mobile measurement-result area | PASS | None / 0 controls | Results, verification rows, and explanatory copy retain one-column readability. |

## Persistent captures

- `files/web-qa/desktop-1440-first-run.png`
- `files/web-qa/desktop-1366-result.png`
- `files/web-qa/desktop-1280-boundary.png`
- `files/web-qa/mobile-390-first-run.png`
- `files/web-qa/mobile-375-result.png`

No visible responsive defect was found. No UI code was changed.
