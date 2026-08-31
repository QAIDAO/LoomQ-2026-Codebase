# LoomQ Lab Web Design

## Inspiration board

- IBM Quantum Composer keeps circuit, code, and result views close enough to explain one another. LoomQ borrows that evidence adjacency, but removes manual gate editing from the first-run path.
- Quirk makes every circuit change immediately legible through rails and probability output. LoomQ keeps the direct circuit-to-distribution relationship, but presents a verified server result rather than a browser toy state.
- Q-CTRL Black Opal treats “no prerequisites” as an interaction requirement, not a slogan. LoomQ therefore starts with ordinary-language experiments and hides QASM until the user asks.
- Azure Quantum learning uses progressive concept steps. LoomQ compresses those steps into four observable stages: understand, compile, verify, run.

## Visual direction

The page is a quiet scientific workbench, not a neon quantum fantasy. A warm paper field (`#f3f0e7`) supports ink-blue text (`#17233a`), a restrained verification blue (`#2859c5`), and amber only for pending states (`#b47720`). Successful proof uses dark teal (`#1f7463`). Hairline borders and a low-contrast grid make the system feel measured without simulating laboratory chrome.

Headings use local editorial serif fallbacks (`Iowan Old Style`, `Noto Serif SC`, `Source Han Serif SC`, Georgia); controls and body copy use Aptos/Segoe UI/Noto Sans SC/Microsoft YaHei. No font, icon, script, or image depends on a CDN. Inline SVG uses rounded current-color strokes.

## Interaction and responsive behavior

- The only primary action is “验证并运行”. Example choices set the prompt; Bell and GHZ are visibly marked as local examples.
- Four pipeline stages begin neutral, become active during the request, then reflect returned evidence. The interface never pre-checks a stage.
- Result bars always have a parallel table, circuit gates have text labels, status has text in addition to color, and every control is keyboard reachable.
- Desktop uses a two-column hero and result grid; below 1024 px the workspace loosens, and below 768 px all columns become one stack with full-width actions.
- Motion is limited to short transform/opacity transitions and is disabled by `prefers-reduced-motion`.
