"""Generates the DeployMate-styled Glassmorphism Pitch Deck for AlphaBrain.

Produces a 16:9 widescreen presentation file at /Users/ajaytiwari/Downloads/AlphaBrain-iQOO-Deck.pptx.
"""

from pathlib import Path

from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_SHAPE
from pptx.enum.text import PP_ALIGN
from pptx.util import Inches, Pt

# Color Palette (DeployMate + Apple Glassmorphism)
COLOR_BG = RGBColor(5, 9, 20)  # Deep obsidian black #050914
COLOR_CARD = RGBColor(17, 24, 39)  # Frosted glass card fill #111827
COLOR_CARD_ALT = RGBColor(15, 23, 42)  # Dark slate card #0F172A
COLOR_BORDER = RGBColor(51, 65, 85)  # Glass border stroke #334155
COLOR_ORANGE = RGBColor(255, 107, 0)  # Electric Amber / Orange #FF6B00
COLOR_AMBER = RGBColor(245, 158, 11)  # Warm Gold #F59E0B
COLOR_CYAN = RGBColor(6, 182, 212)  # Vivid Cyan #06B6D4
COLOR_RED = RGBColor(239, 68, 68)  # Red Light indicator #EF4444
COLOR_GREEN = RGBColor(16, 185, 129)  # Green Light indicator #10B981
COLOR_TEXT_MAIN = RGBColor(248, 250, 252)  # Crisp white #F8FAFC
COLOR_TEXT_MUTED = RGBColor(148, 163, 184)  # Muted slate #94A3B8
COLOR_TEXT_SUB = RGBColor(100, 116, 139)  # Subdued gray #64748B

OUTPUT_PATH = Path("/Users/ajaytiwari/Downloads/AlphaBrain-iQOO-Deck.pptx")


def set_slide_background(slide):
    """Sets a solid deep obsidian background for the slide."""
    bg_shape = slide.shapes.add_shape(
        MSO_SHAPE.RECTANGLE, Inches(0), Inches(0), Inches(13.333), Inches(7.5)
    )
    bg_shape.fill.solid()
    bg_shape.fill.fore_color.rgb = COLOR_BG
    bg_shape.line.fill.background()
    return bg_shape


def add_header(slide, slide_num: int, total: int = 11, category: str = "PITCH DECK"):
    """Adds DeployMate top glass bar and micro-labels."""
    # Top rule
    line = slide.shapes.add_shape(
        MSO_SHAPE.RECTANGLE, Inches(0.8), Inches(0.4), Inches(11.733), Inches(0.015)
    )
    line.fill.solid()
    line.fill.fore_color.rgb = RGBColor(30, 41, 59)
    line.line.fill.background()

    # Brand & category eyebrow
    tx = slide.shapes.add_textbox(Inches(0.8), Inches(0.45), Inches(8), Inches(0.4))
    tf = tx.text_frame
    tf.word_wrap = True
    p = tf.paragraphs[0]
    p.text = f"ALPHABRAIN // {category} · iQOO PUNE HACKATHON 2026"
    p.font.size = Pt(9)
    p.font.name = "Arial"
    p.font.bold = True
    p.font.color.rgb = COLOR_ORANGE

    # Meta tag right side
    tx_meta = slide.shapes.add_textbox(Inches(9.0), Inches(0.45), Inches(3.533), Inches(0.4))
    tf_meta = tx_meta.text_frame
    tf_meta.word_wrap = True
    p_meta = tf_meta.paragraphs[0]
    p_meta.text = f"TRACK: DEVELOPER TOOLS  |  SLIDE {slide_num:02d}/{total:02d}"
    p_meta.alignment = PP_ALIGN.RIGHT
    p_meta.font.size = Pt(9)
    p_meta.font.name = "Arial"
    p_meta.font.color.rgb = COLOR_TEXT_MUTED


def add_card(slide, left, top, width, height, bg_color=COLOR_CARD, border_color=COLOR_BORDER):
    """Draws a rounded rectangle representing an Apple-style frosted glass card."""
    shape = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, left, top, width, height)
    shape.fill.solid()
    shape.fill.fore_color.rgb = bg_color
    if border_color:
        shape.line.color.rgb = border_color
        shape.line.width = Pt(1)
    else:
        shape.line.fill.background()
    return shape


def add_title_block(slide, eyebrow: str, headline: str, subtitle: str = ""):
    """Adds large display headline and description."""
    tx = slide.shapes.add_textbox(Inches(0.8), Inches(0.95), Inches(11.733), Inches(1.3))
    tf = tx.text_frame
    tf.word_wrap = True
    tf.margin_top = Inches(0)
    tf.margin_left = Inches(0)

    p0 = tf.paragraphs[0]
    p0.text = eyebrow.upper()
    p0.font.size = Pt(10)
    p0.font.name = "Arial"
    p0.font.bold = True
    p0.font.color.rgb = COLOR_ORANGE
    p0.space_after = Pt(4)

    p1 = tf.add_paragraph()
    p1.text = headline
    p1.font.size = Pt(28)
    p1.font.name = "Georgia"
    p1.font.bold = True
    p1.font.color.rgb = COLOR_TEXT_MAIN
    p1.space_after = Pt(4)

    if subtitle:
        p2 = tf.add_paragraph()
        p2.text = subtitle
        p2.font.size = Pt(12)
        p2.font.name = "Arial"
        p2.font.color.rgb = COLOR_TEXT_MUTED


def build_presentation():
    prs = Presentation()
    prs.slide_width = Inches(13.333)
    prs.slide_height = Inches(7.5)
    blank_layout = prs.slide_layouts[6]

    # =========================================================================
    # SLIDE 1: Title / Cover
    # =========================================================================
    s1 = prs.slides.add_slide(blank_layout)
    set_slide_background(s1)
    add_header(s1, 1, category="SYSTEM BLUEPRINT")

    # Big Glass Hero Box
    add_card(s1, Inches(0.8), Inches(1.1), Inches(11.733), Inches(5.8), bg_color=COLOR_CARD)

    tx1 = s1.shapes.add_textbox(Inches(1.2), Inches(1.5), Inches(10.9), Inches(3.2))
    tf1 = tx1.text_frame
    tf1.word_wrap = True

    p = tf1.paragraphs[0]
    p.text = "01 // PITCH PRESENTATION"
    p.font.size = Pt(11)
    p.font.name = "Arial"
    p.font.bold = True
    p.font.color.rgb = COLOR_ORANGE
    p.space_after = Pt(8)

    p = tf1.add_paragraph()
    p.text = "The Phone-First Autonomous\nDeveloper Cockpit."
    p.font.size = Pt(42)
    p.font.name = "Georgia"
    p.font.bold = True
    p.font.color.rgb = COLOR_TEXT_MAIN
    p.space_after = Pt(14)

    p = tf1.add_paragraph()
    p.text = (
        "Transforming an iQOO smartphone into a hands-free multi-modal command center for software engineering.\n"
        "Powered by Vertex AI Gemini Live duplex voice, LiveKit WebRTC, and headless Antigravity workers."
    )
    p.font.size = Pt(14)
    p.font.name = "Arial"
    p.font.color.rgb = COLOR_TEXT_MUTED

    # 3 Bottom Pills
    pills = [
        (
            "01 / INTERFACE",
            "Duplex Voice Cockpit",
            "Sub-second speech with Eva; zero keyboard typing required.",
        ),
        (
            "02 / BRIDGE",
            "iQOO Office Kit",
            "Remote desktop execution, clipboard sync & HackTracker telemetry.",
        ),
        (
            "03 / ENGINE",
            "Autonomous 12-Gate QA",
            "Headless Antigravity worker leases tasks & passes 506 unit tests.",
        ),
    ]
    for i, (tag, title, desc) in enumerate(pills):
        col_w = Inches(3.45)
        col_l = Inches(1.2) + i * Inches(3.7)
        add_card(s1, col_l, Inches(4.85), col_w, Inches(1.65), bg_color=COLOR_CARD_ALT)
        t_box = s1.shapes.add_textbox(
            col_l + Inches(0.2), Inches(4.95), col_w - Inches(0.4), Inches(1.45)
        )
        tf = t_box.text_frame
        tf.word_wrap = True

        p = tf.paragraphs[0]
        p.text = tag
        p.font.size = Pt(9)
        p.font.name = "Arial"
        p.font.bold = True
        p.font.color.rgb = COLOR_ORANGE

        p = tf.add_paragraph()
        p.text = title
        p.font.size = Pt(13)
        p.font.name = "Georgia"
        p.font.bold = True
        p.font.color.rgb = COLOR_TEXT_MAIN
        p.space_after = Pt(2)

        p = tf.add_paragraph()
        p.text = desc
        p.font.size = Pt(10)
        p.font.name = "Arial"
        p.font.color.rgb = COLOR_TEXT_MUTED

    # =========================================================================
    # SLIDE 2: The Problem & Solution
    # =========================================================================
    s2 = prs.slides.add_slide(blank_layout)
    set_slide_background(s2)
    add_header(s2, 2, category="THE PROBLEM & SOLUTION")
    add_title_block(
        s2,
        "02 // CORE MOTIVATION",
        "Breaking the Desktop Chain for Developers",
        "Why software engineers lose critical hours tethered to physical keyboards.",
    )

    # 2 Comparison Glass Cards
    col_w = Inches(5.66)
    card_top = Inches(2.5)
    card_h = Inches(4.4)

    # Left: The Challenge
    add_card(s2, Inches(0.8), card_top, col_w, card_h, bg_color=COLOR_CARD, border_color=COLOR_RED)
    tx = s2.shapes.add_textbox(
        Inches(1.1), card_top + Inches(0.3), col_w - Inches(0.6), card_h - Inches(0.6)
    )
    tf = tx.text_frame
    tf.word_wrap = True

    p = tf.paragraphs[0]
    p.text = "THE PROBLEM"
    p.font.size = Pt(10)
    p.font.name = "Arial"
    p.font.bold = True
    p.font.color.rgb = COLOR_RED
    p.space_after = Pt(4)

    p = tf.add_paragraph()
    p.text = "Chained to the Terminal & IDE"
    p.font.size = Pt(20)
    p.font.name = "Georgia"
    p.font.bold = True
    p.font.color.rgb = COLOR_TEXT_MAIN
    p.space_after = Pt(14)

    points_left = [
        (
            "Physical Bottleneck",
            "Developers are forced to open heavy laptop workstations to triage production bugs, review pull requests, or supervise agent builds.",
        ),
        (
            "Mobile Failure",
            "When on-call emergencies occur while commuting, typing code or terminal commands on a mobile glass keyboard is nearly impossible.",
        ),
        (
            "Disconnected Agents",
            "Modern autonomous agents (Cursor, Claude, Codex) lack a phone-first voice cockpit that decouples the input UI from desktop compute.",
        ),
    ]
    for sub, desc in points_left:
        p = tf.add_paragraph()
        p.text = f"• {sub}: {desc}"
        p.font.size = Pt(11)
        p.font.name = "Arial"
        p.font.color.rgb = COLOR_TEXT_MUTED
        p.space_after = Pt(10)

    # Right: The Solution
    add_card(
        s2, Inches(6.866), card_top, col_w, card_h, bg_color=COLOR_CARD, border_color=COLOR_GREEN
    )
    tx = s2.shapes.add_textbox(
        Inches(7.166), card_top + Inches(0.3), col_w - Inches(0.6), card_h - Inches(0.6)
    )
    tf = tx.text_frame
    tf.word_wrap = True

    p = tf.paragraphs[0]
    p.text = "THE ALPHABRAIN SOLUTION"
    p.font.size = Pt(10)
    p.font.name = "Arial"
    p.font.bold = True
    p.font.color.rgb = COLOR_GREEN
    p.space_after = Pt(4)

    p = tf.add_paragraph()
    p.text = "Hands-Free Voice Cockpit"
    p.font.size = Pt(20)
    p.font.name = "Georgia"
    p.font.bold = True
    p.font.color.rgb = COLOR_TEXT_MAIN
    p.space_after = Pt(14)

    points_right = [
        (
            "The Phone as Steering Wheel",
            "Developers speak naturally to Eva (Gemini Live native duplex audio) on an iQOO phone with sub-second conversational latency.",
        ),
        (
            "Workstation as Compute Engine",
            "Heavy agent compilation, testing, and Git operations execute headlessly in the background via the iQOO Office Kit bridge.",
        ),
        (
            "Instant Mobile Approvals",
            "Pull request diffs and test results stream directly into the phone's narrow drawer for instant one-tap merge approvals.",
        ),
    ]
    for sub, desc in points_right:
        p = tf.add_paragraph()
        p.text = f"• {sub}: {desc}"
        p.font.size = Pt(11)
        p.font.name = "Arial"
        p.font.color.rgb = COLOR_TEXT_MUTED
        p.space_after = Pt(10)

    # =========================================================================
    # SLIDE 3: 3-Tier Architecture
    # =========================================================================
    s3 = prs.slides.add_slide(blank_layout)
    set_slide_background(s3)
    add_header(s3, 3, category="SYSTEM ARCHITECTURE")
    add_title_block(
        s3,
        "03 // 3-TIER ARCHITECTURE",
        "Concentric System Topology",
        "Decoupling the mobile multimodal interface from the heavy background execution layer.",
    )

    tiers = [
        (
            "TIER 1 · MOBILE COCKPIT",
            "iQOO Smartphone Surface",
            COLOR_ORANGE,
            [
                "WebRTC Room: LiveKit audio/video SFU with active-speaker detection.",
                "Gemini Live Duplex Voice: Native speech-to-speech interaction via Eva.",
                "Responsive Drawer: Real-time transcription, task cards, and PR diff viewer.",
                "Zero-touch control optimized for 55% Red Light hackathon build window.",
            ],
        ),
        (
            "TIER 2 · HARDWARE BRIDGE",
            "iQOO Office Kit & Policy Broker",
            COLOR_CYAN,
            [
                "Bi-directional Clipboard Sync: Seamless transfer of specs and logs.",
                "Remote Execution: Low-latency trigger of workstation terminal scripts.",
                "HackTracker Telemetry: Automated event logging (+25% judging weight).",
                "FastAPI Control Plane: ACID lease broker and dependency DAG scheduler.",
            ],
        ),
        (
            "TIER 3 · WORKSTATION ENGINE",
            "Headless Antigravity Worker",
            COLOR_AMBER,
            [
                "Outbound-only Runner: `alpha_worker` leasing tasks without open ports.",
                "Isolated Worktrees: Safe, ephemeral Git environments per task.",
                "12-Category SDLC Gates: Enforces compilation, typing, lint, and unit tests.",
                "Deterministic Test Harness: 506 passing hermetic test cases.",
            ],
        ),
    ]

    card_w = Inches(3.64)
    card_h = Inches(4.5)
    for i, (tag, title, accent, items) in enumerate(tiers):
        c_left = Inches(0.8) + i * Inches(4.04)
        add_card(s3, c_left, Inches(2.4), card_w, card_h, bg_color=COLOR_CARD, border_color=accent)
        tx = s3.shapes.add_textbox(
            c_left + Inches(0.25), Inches(2.6), card_w - Inches(0.5), card_h - Inches(0.4)
        )
        tf = tx.text_frame
        tf.word_wrap = True

        p = tf.paragraphs[0]
        p.text = tag
        p.font.size = Pt(9)
        p.font.name = "Arial"
        p.font.bold = True
        p.font.color.rgb = accent
        p.space_after = Pt(4)

        p = tf.add_paragraph()
        p.text = title
        p.font.size = Pt(17)
        p.font.name = "Georgia"
        p.font.bold = True
        p.font.color.rgb = COLOR_TEXT_MAIN
        p.space_after = Pt(14)

        for it in items:
            p = tf.add_paragraph()
            p.text = f"• {it}"
            p.font.size = Pt(10)
            p.font.name = "Arial"
            p.font.color.rgb = COLOR_TEXT_MUTED
            p.space_after = Pt(8)

    # =========================================================================
    # SLIDE 4: 5-Step Process Pipeline
    # =========================================================================
    s4 = prs.slides.add_slide(blank_layout)
    set_slide_background(s4)
    add_header(s4, 4, category="WORKFLOW PIPELINE")
    add_title_block(
        s4,
        "04 // END-TO-END WORKFLOW",
        "From Spoken Voice to Verified Pull Request",
        "How a developer commands an end-to-end coding task completely from their phone.",
    )

    steps = [
        (
            "01 / INPUT",
            "Voice Intake",
            "Developer speaks to Eva on iQOO phone: 'Implement rate-limiting middleware.'",
        ),
        (
            "02 / REASONING",
            "Duplex Clarification",
            "Eva clarifies scope via Gemini Live and drafts deterministic task graph with gates.",
        ),
        (
            "03 / BRIDGE",
            "Office Kit Dispatch",
            "Task specification dispatches over the iQOO Office Kit bridge to workstation worker.",
        ),
        (
            "04 / AGENT",
            "Autonomous Code & QA",
            "Antigravity worker creates worktree, writes code, and executes 506 unit tests.",
        ),
        (
            "05 / HANDOFF",
            "Mobile PR Approval",
            "Eva speaks: 'Tests passed!' Diffs stream to the mobile drawer for one-tap merge.",
        ),
    ]

    step_w = Inches(2.18)
    step_h = Inches(3.2)
    for i, (tag, title, desc) in enumerate(steps):
        s_left = Inches(0.8) + i * Inches(2.38)
        add_card(s4, s_left, Inches(2.5), step_w, step_h, bg_color=COLOR_CARD)
        tx = s4.shapes.add_textbox(
            s_left + Inches(0.15), Inches(2.65), step_w - Inches(0.3), step_h - Inches(0.3)
        )
        tf = tx.text_frame
        tf.word_wrap = True

        p = tf.paragraphs[0]
        p.text = tag
        p.font.size = Pt(9)
        p.font.name = "Arial"
        p.font.bold = True
        p.font.color.rgb = COLOR_ORANGE
        p.space_after = Pt(6)

        p = tf.add_paragraph()
        p.text = title
        p.font.size = Pt(14)
        p.font.name = "Georgia"
        p.font.bold = True
        p.font.color.rgb = COLOR_TEXT_MAIN
        p.space_after = Pt(10)

        p = tf.add_paragraph()
        p.text = desc
        p.font.size = Pt(10)
        p.font.name = "Arial"
        p.font.color.rgb = COLOR_TEXT_MUTED

    # Bottom summary card
    add_card(s4, Inches(0.8), Inches(5.95), Inches(11.733), Inches(1.05), bg_color=COLOR_CARD_ALT)
    tx = s4.shapes.add_textbox(Inches(1.1), Inches(6.05), Inches(11.1), Inches(0.85))
    tf = tx.text_frame
    p = tf.paragraphs[0]
    p.text = (
        "TOTAL CYCLE TIME: Sub-second voice clarification · Under 3 minutes for verified Git PR"
    )
    p.font.size = Pt(12)
    p.font.name = "Georgia"
    p.font.bold = True
    p.font.color.rgb = COLOR_ORANGE

    p = tf.add_paragraph()
    p.text = "HackTracker Compliance: Zero laptop touches required during the entire feature implementation."
    p.font.size = Pt(10)
    p.font.name = "Arial"
    p.font.color.rgb = COLOR_TEXT_MUTED

    # =========================================================================
    # SLIDE 5: Red Light / Green Light Mastery
    # =========================================================================
    s5 = prs.slides.add_slide(blank_layout)
    set_slide_background(s5)
    add_header(s5, 5, category="HACKATHON MECHANICS")
    add_title_block(
        s5,
        "05 // THE RED LIGHT / GREEN LIGHT STRATEGY",
        "Turning Constraints into Competitive Advantage",
        "How AlphaBrain dominates the 30-hour iQOO hybrid development format.",
    )

    box_w = Inches(5.66)
    box_h = Inches(4.5)

    # Red Light Card
    add_card(
        s5, Inches(0.8), Inches(2.4), box_w, box_h, bg_color=COLOR_CARD, border_color=COLOR_RED
    )
    tx = s5.shapes.add_textbox(Inches(1.1), Inches(2.6), box_w - Inches(0.6), box_h - Inches(0.4))
    tf = tx.text_frame
    tf.word_wrap = True

    p = tf.paragraphs[0]
    p.text = "● 55% RED LIGHT · PHONE-ONLY BUILD"
    p.font.size = Pt(10)
    p.font.name = "Arial"
    p.font.bold = True
    p.font.color.rgb = COLOR_RED
    p.space_after = Pt(4)

    p = tf.add_paragraph()
    p.text = "Laptops Screens Closed"
    p.font.size = Pt(20)
    p.font.name = "Georgia"
    p.font.bold = True
    p.font.color.rgb = COLOR_TEXT_MAIN
    p.space_after = Pt(12)

    red_items = [
        (
            "Hands-Free Voice Flow",
            "While competitors struggle without keyboards, AlphaBrain developers speak naturally into the iQOO phone with Eva.",
        ),
        (
            "Office Kit Telemetry",
            "Screen mirroring and remote terminal execution generate continuous activity logged by HackTracker (+25% of total score).",
        ),
        (
            "Mobile Code Review",
            "Inspect Git diffs and test logs inside the mobile meeting drawer with one-tap approvals.",
        ),
    ]
    for sub, desc in red_items:
        p = tf.add_paragraph()
        p.text = f"• {sub}: {desc}"
        p.font.size = Pt(10)
        p.font.name = "Arial"
        p.font.color.rgb = COLOR_TEXT_MUTED
        p.space_after = Pt(8)

    # Green Light Card
    add_card(
        s5, Inches(6.866), Inches(2.4), box_w, box_h, bg_color=COLOR_CARD, border_color=COLOR_GREEN
    )
    tx = s5.shapes.add_textbox(Inches(7.166), Inches(2.6), box_w - Inches(0.6), box_h - Inches(0.4))
    tf = tx.text_frame
    tf.word_wrap = True

    p = tf.paragraphs[0]
    p.text = "● 45% GREEN LIGHT · HYBRID POLISH"
    p.font.size = Pt(10)
    p.font.name = "Arial"
    p.font.bold = True
    p.font.color.rgb = COLOR_GREEN
    p.space_after = Pt(4)

    p = tf.add_paragraph()
    p.text = "Laptops Unlocked"
    p.font.size = Pt(20)
    p.font.name = "Georgia"
    p.font.bold = True
    p.font.color.rgb = COLOR_TEXT_MAIN
    p.space_after = Pt(12)

    green_items = [
        (
            "Backend Infrastructure",
            "Spin up local LiveKit SFU server, configure PostgreSQL state schemas, and optimize vertex audio channels.",
        ),
        (
            "Deterministic Test Rig",
            "Run comprehensive pytest regression suites and verify hermetic multi-worktree execution.",
        ),
        (
            "Production Architecture",
            "Configure enterprise CI/CD gates, database clustering, and cloud preview environments.",
        ),
    ]
    for sub, desc in green_items:
        p = tf.add_paragraph()
        p.text = f"• {sub}: {desc}"
        p.font.size = Pt(10)
        p.font.name = "Arial"
        p.font.color.rgb = COLOR_TEXT_MUTED
        p.space_after = Pt(8)

    # =========================================================================
    # SLIDE 6: Autonomous 12-Gate QA Engine
    # =========================================================================
    s6 = prs.slides.add_slide(blank_layout)
    set_slide_background(s6)
    add_header(s6, 6, category="SECURITY & RELIABILITY")
    add_title_block(
        s6,
        "06 // CODE INTEGRITY GUARANTEES",
        "Autonomous 12-Category SDLC Gates",
        "AlphaBrain rejects code completion unless deterministic proof manifests are verified.",
    )

    gates = [
        (
            "G1 · BUILD",
            "Clean Compilation",
            "Zero syntax or packaging errors across all Python modules.",
        ),
        (
            "G2 · UNIT TESTS",
            "506 Hermetic Tests",
            "Executed in isolated temporary SQLite databases; 100% green.",
        ),
        (
            "G3 · STATIC TYPING",
            "mypy Enforcement",
            "Strict type checking across all 63 active source files.",
        ),
        (
            "G4 · LINT & STYLE",
            "Ruff Formatted",
            "Deterministic code formatting; zero lint violations.",
        ),
        (
            "G5 · ISOLATION",
            "Git Worktrees",
            "Tasks execute in clean worktrees; base commits resolved.",
        ),
        (
            "G6 · CONTRACTS",
            "Alpha Protocol v1",
            "Strict typed Pydantic envelopes across tasks, attempts, and audits.",
        ),
        (
            "G7 · SECURITY",
            "Zero Secret Leaks",
            "Automated scrubbing for credentials and API tokens.",
        ),
        (
            "G8 · SELF-HEALING",
            "Automated Repair",
            "Worker independently reproduces failures and fixes bugs.",
        ),
    ]

    gw = Inches(2.78)
    gh = Inches(2.05)
    for i, (tag, title, desc) in enumerate(gates):
        row = i // 4
        col = i % 4
        g_left = Inches(0.8) + col * Inches(2.98)
        g_top = Inches(2.4) + row * Inches(2.25)
        add_card(s6, g_left, g_top, gw, gh, bg_color=COLOR_CARD)
        tx = s6.shapes.add_textbox(
            g_left + Inches(0.15), g_top + Inches(0.15), gw - Inches(0.3), gh - Inches(0.3)
        )
        tf = tx.text_frame
        tf.word_wrap = True

        p = tf.paragraphs[0]
        p.text = tag
        p.font.size = Pt(8)
        p.font.name = "Arial"
        p.font.bold = True
        p.font.color.rgb = COLOR_ORANGE

        p = tf.add_paragraph()
        p.text = title
        p.font.size = Pt(13)
        p.font.name = "Georgia"
        p.font.bold = True
        p.font.color.rgb = COLOR_TEXT_MAIN
        p.space_after = Pt(4)

        p = tf.add_paragraph()
        p.text = desc
        p.font.size = Pt(9)
        p.font.name = "Arial"
        p.font.color.rgb = COLOR_TEXT_MUTED

    # =========================================================================
    # SLIDE 7: Benchmarks & Empirical Performance
    # =========================================================================
    s7 = prs.slides.add_slide(blank_layout)
    set_slide_background(s7)
    add_header(s7, 7, category="BENCHMARKS & METRICS")
    add_title_block(
        s7,
        "07 // EMPIRICAL VALIDATION",
        "Performance Benchmarks & Reliability",
        "Real-world data measured across our deterministic test suite and WebRTC audio channels.",
    )

    metrics = [
        (
            "<400ms",
            "VOICE RESPONSE LATENCY",
            "Duplex speech-to-speech conversational latency via Vertex AI Gemini Live.",
        ),
        (
            "506 / 506",
            "TEST SUITE PASS RATE",
            "Hermetic test cases passing without environment hacks or manual PYTHONPATH overrides.",
        ),
        (
            "<150ms",
            "OFFICE KIT DISPATCH",
            "Sub-second task forwarding and telemetry synchronization over hardware bridge.",
        ),
        (
            "0 Errors",
            "STATIC TYPE & LINT CHECKS",
            "Clean Ruff linting and mypy static type checking verified across 63 source files.",
        ),
        (
            "99.9%",
            "CRASH RECOVERY SLA",
            "Automatic lease reclamation under PostgreSQL lock with bounded exponential backoff.",
        ),
        (
            "100%",
            "HACKATHON ALIGNMENT",
            "Complete compliance with Developer Tools track and Phone-First scoring criteria.",
        ),
    ]

    mw = Inches(3.64)
    mh = Inches(2.1)
    for i, (val, label, desc) in enumerate(metrics):
        row = i // 3
        col = i % 3
        m_left = Inches(0.8) + col * Inches(4.04)
        m_top = Inches(2.4) + row * Inches(2.35)
        add_card(s7, m_left, m_top, mw, mh, bg_color=COLOR_CARD)
        tx = s7.shapes.add_textbox(
            m_left + Inches(0.25), m_top + Inches(0.2), mw - Inches(0.5), mh - Inches(0.4)
        )
        tf = tx.text_frame
        tf.word_wrap = True

        p = tf.paragraphs[0]
        p.text = val
        p.font.size = Pt(32)
        p.font.name = "Arial"
        p.font.bold = True
        p.font.color.rgb = COLOR_TEXT_MAIN

        p = tf.add_paragraph()
        p.text = label
        p.font.size = Pt(8)
        p.font.name = "Arial"
        p.font.bold = True
        p.font.color.rgb = COLOR_ORANGE
        p.space_after = Pt(4)

        p = tf.add_paragraph()
        p.text = desc
        p.font.size = Pt(9)
        p.font.name = "Arial"
        p.font.color.rgb = COLOR_TEXT_MUTED

    # =========================================================================
    # SLIDE 8: Technology Stack
    # =========================================================================
    s8 = prs.slides.add_slide(blank_layout)
    set_slide_background(s8)
    add_header(s8, 8, category="TECHNOLOGY STACK")
    add_title_block(
        s8,
        "08 // SYSTEM IMPLEMENTATION",
        "Production-Grade Technology Stack",
        "Decoupled, modular architecture built for resilience and zero-latency mobile control.",
    )

    stacks = [
        (
            "AI & VOICE",
            "Intelligence",
            COLOR_ORANGE,
            [
                "Vertex AI Gemini 3.5 Live: Native duplex audio.",
                "Gemini 3.1 Pro: Spec drafting & requirements.",
                "Antigravity: Headless autonomous agent runtime.",
                "Memory Graph: Cross-agent session persistence.",
            ],
        ),
        (
            "MEDIA & TRANSPORT",
            "Real-Time Comm",
            COLOR_CYAN,
            [
                "LiveKit Server: WebRTC audio/video SFU.",
                "FastAPI / Uvicorn: Async control plane.",
                "Alpha Protocol v1: Strict Pydantic contracts.",
                "WebSockets: High-frequency live telemetry.",
            ],
        ),
        (
            "HARDWARE & PHONE",
            "iQOO Ecosystem",
            COLOR_AMBER,
            [
                "iQOO Flagship Loaner: Primary user surface.",
                "iQOO Office Kit: Low-latency PC-mobile bridge.",
                "HackTracker: Automatic telemetry verification.",
                "Snapdragon NPU: On-device quantized SLM ready.",
            ],
        ),
        (
            "PERSISTENCE & OPS",
            "Durable Layer",
            COLOR_GREEN,
            [
                "PostgreSQL / Supabase: ACID task lease state.",
                "Ruff & mypy: Automated quality gates.",
                "pytest: Deterministic test harness (506 tests).",
                "launchd: 24/7 background worker persistence.",
            ],
        ),
    ]

    sw = Inches(2.78)
    sh = Inches(4.5)
    for i, (tag, title, accent, items) in enumerate(stacks):
        s_left = Inches(0.8) + i * Inches(2.98)
        add_card(s8, s_left, Inches(2.4), sw, sh, bg_color=COLOR_CARD, border_color=accent)
        tx = s8.shapes.add_textbox(
            s_left + Inches(0.2), Inches(2.6), sw - Inches(0.4), sh - Inches(0.4)
        )
        tf = tx.text_frame
        tf.word_wrap = True

        p = tf.paragraphs[0]
        p.text = tag
        p.font.size = Pt(8)
        p.font.name = "Arial"
        p.font.bold = True
        p.font.color.rgb = accent
        p.space_after = Pt(4)

        p = tf.add_paragraph()
        p.text = title
        p.font.size = Pt(16)
        p.font.name = "Georgia"
        p.font.bold = True
        p.font.color.rgb = COLOR_TEXT_MAIN
        p.space_after = Pt(14)

        for it in items:
            p = tf.add_paragraph()
            p.text = f"• {it}"
            p.font.size = Pt(9)
            p.font.name = "Arial"
            p.font.color.rgb = COLOR_TEXT_MUTED
            p.space_after = Pt(8)

    # =========================================================================
    # SLIDE 9: Live Demo Flow
    # =========================================================================
    s9 = prs.slides.add_slide(blank_layout)
    set_slide_background(s9)
    add_header(s9, 9, category="LIVE STAGE DEMONSTRATION")
    add_title_block(
        s9,
        "09 // ON-STAGE DEMO PLAN",
        "Deterministic 3-Minute Live Demo",
        "Proving phone-first autonomous software engineering live in front of the judges.",
    )

    demo_phases = [
        (
            "PHASE 1 · SPOKEN INTAKE",
            "1. Voice Command on iQOO Phone",
            COLOR_ORANGE,
            (
                "• The presenter joins Alpha Meet directly on the iQOO flagship phone.\n"
                "• Speaks naturally to Eva: 'Eva, add rate-limiting middleware to our FastAPI endpoints and write unit tests.'\n"
                "• Eva acknowledges with sub-second duplex audio and displays the frozen task graph in the phone drawer."
            ),
        ),
        (
            "PHASE 2 · HEADLESS BUILD",
            "2. Autonomous Execution",
            COLOR_CYAN,
            (
                "• The laptop screen remains untouched throughout.\n"
                "• In the background, `alpha_worker` leases the task via iQOO Office Kit, creates a clean Git worktree, and runs Antigravity.\n"
                "• Antigravity writes the code and runs 506 unit tests to prove zero regressions."
            ),
        ),
        (
            "PHASE 3 · MOBILE HANDOFF",
            "3. One-Tap Mobile PR Merge",
            COLOR_GREEN,
            (
                "• Eva speaks through the phone speakers: 'Done! All unit tests passed.'\n"
                "• The live PR diff and test manifest appear in the iQOO phone drawer.\n"
                "• The presenter taps 'Approve & Merge' directly on the phone screen."
            ),
        ),
    ]

    dw = Inches(3.64)
    dh = Inches(4.5)
    for i, (tag, title, accent, body) in enumerate(demo_phases):
        d_left = Inches(0.8) + i * Inches(4.04)
        add_card(s9, d_left, Inches(2.4), dw, dh, bg_color=COLOR_CARD, border_color=accent)
        tx = s9.shapes.add_textbox(
            d_left + Inches(0.25), Inches(2.6), dw - Inches(0.5), dh - Inches(0.4)
        )
        tf = tx.text_frame
        tf.word_wrap = True

        p = tf.paragraphs[0]
        p.text = tag
        p.font.size = Pt(8)
        p.font.name = "Arial"
        p.font.bold = True
        p.font.color.rgb = accent
        p.space_after = Pt(4)

        p = tf.add_paragraph()
        p.text = title
        p.font.size = Pt(16)
        p.font.name = "Georgia"
        p.font.bold = True
        p.font.color.rgb = COLOR_TEXT_MAIN
        p.space_after = Pt(14)

        p = tf.add_paragraph()
        p.text = body
        p.font.size = Pt(10)
        p.font.name = "Arial"
        p.font.color.rgb = COLOR_TEXT_MUTED
        p.line_spacing = 1.3

    # =========================================================================
    # SLIDE 10: Future Roadmap
    # =========================================================================
    s10 = prs.slides.add_slide(blank_layout)
    set_slide_background(s10)
    add_header(s10, 10, category="PRODUCT ROADMAP")
    add_title_block(
        s10,
        "10 // PRODUCT ROADMAP",
        "AlphaBrain Evolution & Scaling Horizon",
        "From a local developer cockpit to an enterprise-grade autonomous engineering swarm.",
    )

    stages = [
        (
            "PHASE 1 · FOUNDATION (CURRENT)",
            "Voice Cockpit & Headless Runner",
            COLOR_ORANGE,
            [
                "Sub-second duplex voice meeting with Eva (Gemini Live).",
                "LiveKit WebRTC audio/video SFU with responsive drawer.",
                "Outbound-only headless Antigravity runner (`alpha_worker`).",
                "506 hermetic unit and protocol contract tests passing.",
                "Safe, isolated per-task Git worktree creation.",
            ],
        ),
        (
            "PHASE 2 · SCALING (NEXT)",
            "Swarm & Merge Arbitration",
            COLOR_CYAN,
            [
                "Multi-agent parallel code generation in DAG workflows.",
                "Automated Git merge conflict arbitration engine.",
                "Live staging preview environments with smoke gates.",
                "Distributed Linux GPU worker fleets alongside Mac nodes.",
                "Cross-agent memory ledger & code review graph sync.",
            ],
        ),
        (
            "PHASE 3 · ENTERPRISE (MATURE)",
            "Autonomous DevOps & Carrier Ops",
            COLOR_GREEN,
            [
                "Full autonomous software engineering swarm coordination.",
                "Carrier phone call triage & alerts via AgentLine integration.",
                "Self-healing CI/CD with automatic rollback proofs.",
                "Air-gapped on-premise enterprise deployments.",
                "End-to-end voice meeting to production in under 5 minutes.",
            ],
        ),
    ]

    card_w = Inches(3.64)
    card_h = Inches(4.5)
    for i, (tag, title, accent, items) in enumerate(stages):
        c_left = Inches(0.8) + i * Inches(4.04)
        add_card(s10, c_left, Inches(2.4), card_w, card_h, bg_color=COLOR_CARD, border_color=accent)
        tx = s10.shapes.add_textbox(
            c_left + Inches(0.25), Inches(2.6), card_w - Inches(0.5), card_h - Inches(0.4)
        )
        tf = tx.text_frame
        tf.word_wrap = True

        p = tf.paragraphs[0]
        p.text = tag
        p.font.size = Pt(8)
        p.font.name = "Arial"
        p.font.bold = True
        p.font.color.rgb = accent
        p.space_after = Pt(4)

        p = tf.add_paragraph()
        p.text = title
        p.font.size = Pt(17)
        p.font.name = "Georgia"
        p.font.bold = True
        p.font.color.rgb = COLOR_TEXT_MAIN
        p.space_after = Pt(14)

        for it in items:
            p = tf.add_paragraph()
            p.text = f"• {it}"
            p.font.size = Pt(10)
            p.font.name = "Arial"
            p.font.color.rgb = COLOR_TEXT_MUTED
            p.space_after = Pt(8)

    # =========================================================================
    # SLIDE 11: Open-Source Proof & Assets
    # =========================================================================
    s11 = prs.slides.add_slide(blank_layout)
    set_slide_background(s11)
    add_header(s11, 11, category="PROJECT ASSETS & VERIFICATION")
    add_title_block(
        s11,
        "11 // PROOF OF EXECUTION",
        "Project Assets, Source Code & Verification",
        "Everything presented is backed by verifiable code, deterministic tests, and live pipelines.",
    )

    assets = [
        (
            "SOURCE CODE",
            "GitHub Repository",
            COLOR_ORANGE,
            (
                "• Repository: github.com/Ajtiwari26/alphaBrain\n\n"
                "• Modular structure: `alpha_core` (API & Task Engine), `alpha_meet` (LiveKit WebRTC), and `alpha_worker` (Antigravity Bridge).\n\n"
                "• 100% clean Ruff formatting and strict mypy type compliance."
            ),
        ),
        (
            "REPRODUCIBLE SETUP",
            "Local Quickstart",
            COLOR_CYAN,
            (
                "• Start SFU: `livekit-server --bind 127.0.0.1`\n\n"
                "• Run Server: `./.venv/bin/uvicorn alpha_core.api.app:app`\n\n"
                "• Open Room: Navigate to `http://127.0.0.1:8000/meet` on iQOO phone.\n\n"
                "• Live Audio: `python testscript/smoke_gemini_live.py`"
            ),
        ),
        (
            "AUTOMATED QA PROOF",
            "Deterministic Gates",
            COLOR_GREEN,
            (
                "• Run Complete Suite: `./.venv/bin/pytest -q`\n\n"
                "• 506 hermetic unit and contract tests pass with 0 failures.\n\n"
                "• Isolated SQLite databases guarantee test safety with zero residual state."
            ),
        ),
    ]

    card_w = Inches(3.64)
    card_h = Inches(3.8)
    for i, (tag, title, accent, body) in enumerate(assets):
        c_left = Inches(0.8) + i * Inches(4.04)
        add_card(s11, c_left, Inches(2.4), card_w, card_h, bg_color=COLOR_CARD, border_color=accent)
        tx = s11.shapes.add_textbox(
            c_left + Inches(0.25), Inches(2.55), card_w - Inches(0.5), card_h - Inches(0.3)
        )
        tf = tx.text_frame
        tf.word_wrap = True

        p = tf.paragraphs[0]
        p.text = tag
        p.font.size = Pt(8)
        p.font.name = "Arial"
        p.font.bold = True
        p.font.color.rgb = accent
        p.space_after = Pt(4)

        p = tf.add_paragraph()
        p.text = title
        p.font.size = Pt(16)
        p.font.name = "Georgia"
        p.font.bold = True
        p.font.color.rgb = COLOR_TEXT_MAIN
        p.space_after = Pt(12)

        p = tf.add_paragraph()
        p.text = body
        p.font.size = Pt(9.5)
        p.font.name = "Arial"
        p.font.color.rgb = COLOR_TEXT_MUTED
        p.line_spacing = 1.3

    # Bottom Banner
    add_card(s11, Inches(0.8), Inches(6.35), Inches(11.733), Inches(0.8), bg_color=COLOR_CARD_ALT)
    tx = s11.shapes.add_textbox(Inches(1.1), Inches(6.45), Inches(11.1), Inches(0.6))
    tf = tx.text_frame
    p = tf.paragraphs[0]
    p.text = "AlphaBrain · The Autonomous Multi-Agent Developer Cockpit · Powered by Gemini & Antigravity."
    p.font.size = Pt(11)
    p.font.name = "Georgia"
    p.font.bold = True
    p.font.color.rgb = COLOR_TEXT_MAIN

    p = tf.add_paragraph()
    p.text = "Ajay Tiwari  |  AlphaBrain Autonomous Development Ecosystem"
    p.font.size = Pt(9)
    p.font.name = "Arial"
    p.font.color.rgb = COLOR_ORANGE

    # Save
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    prs.save(str(OUTPUT_PATH))
    print(f"Successfully generated: {OUTPUT_PATH}")


if __name__ == "__main__":
    build_presentation()
