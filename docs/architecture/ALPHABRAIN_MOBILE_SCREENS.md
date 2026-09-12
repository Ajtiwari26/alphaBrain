# AlphaBrain Founder Companion — Complete Mobile Screen Specifications

This document catalogs all **14 mobile screens** designed strictly under the **DeployMate Locomotive Design System (`design.md`)**.

- **Interactive High-Fidelity Standalone Viewer**: [`ALPHABRAIN_FOUNDER_SCREENS.html`](file:///Users/ajaytiwari/Desktop/Projects/alphaBrain/docs/architecture/ALPHABRAIN_FOUNDER_SCREENS.html)
- **Standalone Vector Logo SVG**: [`alpha_neural_logo.svg`](file:///Users/ajaytiwari/.gemini/antigravity/brain/5cf515b3-a826-4c67-bdad-c3bb24508fad/alpha_neural_logo.svg)

---

## 14-Screen Design System Overview

![All 14 Screens Overview](/Users/ajaytiwari/.gemini/antigravity/brain/5cf515b3-a826-4c67-bdad-c3bb24508fad/all_wireframes_overview.png)

![Screens 13 and 14](/Users/ajaytiwari/.gemini/antigravity/brain/5cf515b3-a826-4c67-bdad-c3bb24508fad/wireframes_13_14.png)

---

## Screen Specifications

### 01 — Splash Screen
- **Visual Structure**: Minimalist white field (`#FFFFFF`). Centered vector neural Alpha ($\alpha$) SVG.
- **Typography**: Space Grotesk Bold (`AlphaBrain`, letter-spacing: `-0.03em`).
- **Footer**: `POWERED BY` in Fira Code monospace tracked uppercase with the DeployMate neural tree logo.

### 02 — Authentication (Identity)
- **Visual Structure**: `01 — ACCESS` eyebrow tag in `#E6391E`. Huge Space Grotesk `Founder Access` display header.
- **Center**: Crisp geometric FaceID sensor vector framed by a 2px black border.
- **Footer Action**: Full-width row separated by a 1px rule: `Tap to authenticate` with red-orange arrow `↗` (inverts to black on hover).

### 03 — Local Instance Sync (QR Scanner)
- **Visual Structure**: `Connect Instance` title with `CONNECT HARDWARE` eyebrow.
- **Center**: Viewfinder composed exclusively of four `#E6391E` 90-degree corner brackets framing the QR scan zone.
- **Footer**: `MANUAL SYNC_ID` fallback trigger with `ENTER CODE ↗`.

### 04 — Founder Command Center (Dashboard)
- **Visual Structure**: Strict list rows bounded by `1px solid #0A0A0A` divider rules.
- **List Items**:
  - `01  System Live` (with pulsing `#E6391E` live status dot)
  - `02  AI Quotas ↗`
  - `03  Active Projects ↗`
  - `04  Tech Dept ↗`
  - `05  Triage Board ↗`

### 05 — AI Quotas & Telemetry
- **Visual Structure**: Stark data-driven typographic display.
- **Metrics**: Massive `85%` in DeployMate red-orange (`#E6391E`) for Gemini Pro High, huge `42%` in black for Claude Opus.
- **Footer**: Live quota reset countdown: `RESETS: 04H 20M`.

### 06 — Department Configurator
- **Visual Structure**: Structural row list for active company units: `01 // Tech`, `02 // Operations`, `03 // Strategy` with active agent tallies.
- **Action**: Full-width sharp rectangular black block `ADD DEPARTMENT +` (0px border-radius).

### 07 — Agent Communication Hub
- **Visual Structure**: Multi-agent mesh protocol view.
- **Items**: Rows for `Worker AGY-1` (`ACTIVE`), `Research AGY-2` (`IDLE`), and `Reviewer Opus` (`DEBATING`).
- **Actions**: Direct monospace text links: `CHAT`, `CALL`, `VIDEO`.

### 08 — Tech Department Overview
- **Visual Structure**: Three brutalist data quadrants divided by 1px rules.
- **Metrics**: Giant Space Grotesk numerals: `3` (Pending Tasks in `#E6391E`), `2` (Active Worktrees), and `LIVE ↗` Vercel status.

### 09 — GitHub Worktree Manager
- **Visual Structure**: Git branch manager divided by 1px rules.
- **Branches**: `feat/splash-locomotive`, `fix/triage-safety-gate`, and `main`.
- **Details**: Commit hashes in `#E6391E` (`a1b2c3d`, `789e0fa`) and stark black `MERGE` buttons.

### 10 — Triage Task Board
- **Visual Structure**: High-density execution queue with Fira Code Task IDs (`TSK-042`, `TSK-041`, `TSK-040`).
- **Statuses**: `CODING` in `#E6391E`, `IN REVIEW`, and `QUEUED`.

### 11 — Live Task Execution Stream
- **Visual Structure**: Pure white background terminal log with Fira Code monospace stream.
- **Stream Tags**: `[AGENT]` thoughts highlighted in `#E6391E`, system logs in bold black `[SYS]`.
- **Controls**: Sharp rectangular action buttons: `PAUSE` and `INTERRUPT`.

### 12 — Vercel Deployment Console
- **Visual Structure**: Massive Space Grotesk headline `DEPLOYING` in `#E6391E`.
- **Metadata**: Target `PRODUCTION`, commit hash `f891b2c`, build duration `24.2s`.
- **Actions**: `VIEW LIVE ↗` and `ROLLBACK` text links.

### 13 — Project Portfolio
- **Visual Structure**: Clean table grid of active projects: `DeployMate`, `AlphaBrain Core`, and `Agent Mesh`.
- **Metadata**: `LAST UPDATE` timestamps and active red-orange status indicators.

### 14 — Global Settings
- **Visual Structure**: Editorial preference list with brutalist monospace switches.
- **Toggles**: `[ ON ] / OFF` in `#E6391E` for Autonomous Dispatch, Opus Senior Review, and USB Hardware Sync.

---

## Design System Tokens Reference (`design.md`)

```yaml
colors:
  surface: '#ffffff'
  on-surface: '#0a0a0a'
  primary: '#e6391e'
  outline: '#0a0a0a'
typography:
  headline-xl: Space Grotesk Bold (-0.03em letter-spacing)
  body: Inter Regular
  labels/meta: Fira Code Monospace
rounded:
  default: 0px (Zero border-radius)
borders:
  structural: 1px solid #0a0a0a
```
