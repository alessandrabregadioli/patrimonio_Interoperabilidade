# Design QA

## Evidence

- Dashboard source: `design-references/dashboard-target.png` (1487 × 1058 px).
- Dashboard implementation: `design-references/dashboard-implementation.png` (1440 × 1024 px).
- Patrimônios source: `design-references/patrimonios-target.png` (1487 × 1058 px).
- Patrimônios implementation: `design-references/patrimonios-implementation.png` (1440 × 1024 px).
- Integrações source: `design-references/integracoes-target.png` (1487 × 1058 px).
- Integrações implementation: `design-references/integracoes-implementation.png` (1425 × 1013 px; viewport content excludes the 15 px vertical scrollbar).
- Responsive implementation: `design-references/mobile-implementation.png` (375 × 812 px content in a 390 × 844 browser viewport).
- Intended desktop CSS viewport: 1440 × 1024, device scale factor 1.
- State: administrador autenticado; banco inicial com dois patrimônios e nenhuma importação realizada.

The generated sources use the same 1.405 aspect ratio as the desktop implementation but were emitted at 1487 × 1058. They were visually normalized to the implementation viewport before comparison. The Integrações capture uses the available content width after the vertical scrollbar.

## Full-view comparison

The three source designs and their corresponding browser-rendered implementations were opened together and compared in the same review input. The implementation deliberately combines the three selected directions into one consistent product shell:

- Dashboard uses the operations-command-center hierarchy and integration flow.
- Patrimônios uses the search-first inventory workspace and compact data table.
- Integrações uses the three-step workflow, file drop area, live API routes, exports and audit history.

The shared dark forest sidebar, Manrope typography, Tabler icon family, status colors and component spacing are intentional cross-screen unification. Differences in activity/history content reflect the real empty database state; the mock data was not fabricated in production screens.

## Focused-region comparison

- Header and navigation: hierarchy, active state, icon sizing and brand block are consistent across all routes.
- Integration flow: stage spacing, connectors, semantic status and primary action match the reference intent.
- Tables and filters: header weight, row rhythm, status chips, actions and search/filter controls remain readable at desktop width.
- Upload and API panels: the real CSV/JSON/ZIP contract and actual application endpoints replace fictional mock endpoints.
- Mobile shell: menu opens and closes correctly, the flow becomes vertical, the primary action remains visible and tables stay horizontally scrollable.

## Required fidelity surfaces

- Fonts and typography: passed. Self-hosted Manrope Variable is used from weight 200–800; headings, body copy, labels and numeric values preserve a clear hierarchy without remote-font dependency.
- Spacing and layout rhythm: passed. Major section proportions, alignment, dividers, radii and table rhythm match the selected references. No persistent control is clipped.
- Colors and visual tokens: passed. Deep forest, eucalyptus green, warm canvas, semantic mint/amber/red and neutral dividers are consistently tokenized in `static/style.css`.
- Image and asset quality: passed. The interface has no raster illustration requirement; every UI icon comes from the locally hosted MIT-licensed Tabler webfont. No emoji, custom SVG or CSS-drawn replacement is used.
- Copy and content: passed. All visible text is in Brazilian Portuguese and describes the real Vendas → Patrimônio → RH/Colaborador behavior.

## Comparison history

1. Initial review found a P2 table issue on Dashboard: codes such as `PAT-002` wrapped in the first column.
   - Fix: set an 84 px minimum width and `white-space: nowrap` for the code column.
   - Post-fix evidence: `dashboard-implementation.png` shows both codes on one line.
2. Initial review found a P2 density issue on Integrações: the upload panel height pushed the audit history too far below the 1024 px viewport.
   - Fix: reduced the drop-zone height and internal vertical spacing while preserving the primary action and help text.
   - Post-fix evidence: `integracoes-implementation.png` shows the complete panels, export actions, audit header and table header in the primary viewport.
3. Initial review found a P3 icon issue in the RH export action.
   - Fix: replaced the unavailable glyph with Tabler `user-share`.
   - Post-fix evidence: the RH export action now has a visible, consistent icon.

## Interaction and runtime checks

- Login completed successfully.
- Dashboard, Patrimônios and Integrações navigation completed successfully.
- Inventory status filtering returned the expected one-row result.
- Responsive sidebar opened at mobile width and exposed every navigation item.
- Ten authenticated HTML routes rendered with status 200.
- Public Patrimônio and RH integration APIs returned status 200.
- Browser console warnings/errors checked: none.

## Findings

No actionable P0, P1 or P2 findings remain. Differences from the source mock data and navigation shell are intentional product constraints documented above.

## Follow-up polish

- P3: Add server-side pagination when the inventory grows beyond a few hundred rows.

final result: passed
