# Rebuild the full HTML deck styled exactly like DeployMate's design system
# Colors: #FFFFFF bg, #0A0A0A text, #E6391E accent
# Fonts: Space Grotesk (display), Inter (body), Fira Code (micro)
# Style: 1px borders, huge/small bimodal typography, no shadows/gradients, asymmetric

slides_data = [
    {
        "type": "title",
        "title": "AlphaBrain",
        "subtitle": "The Autonomous Multi-Agent Developer Cockpit",
        "tag": "iQOO PUNE HACKATHON 2026",
        "body": "A voice-native, hermetically sealed engineering swarm powered by Gemini & Antigravity.",
        "image": "/Users/ajaytiwari/.gemini/antigravity/brain/52fc9ef8-23aa-4045-a4de-2257c2c0a58f/slide1_brain_1788285056050.jpg",
    },
    {
        "type": "content",
        "tag": "02 // HACKATHON CONTEXT",
        "title": "Breaking the Desktop Chain",
        "subtitle": "Why AlphaBrain Fits the iQOO AgentKit Track perfectly",
        "items": [
            {
                "idx": "01",
                "title": "Phone-First UI",
                "body": "100% controlled via real-time voice duplex on the iQOO phone. No laptop keyboard needed.",
            },
            {
                "idx": "02",
                "title": "AgentKit Core",
                "body": "Built entirely around Antigravity orchestrating the LiveKit voice bridge.",
            },
            {
                "idx": "03",
                "title": "Deep QA Gates",
                "body": "Enforces 'Red Light / Green Light' test-driven paradigm before any code merges.",
            },
        ],
        "image": "/Users/ajaytiwari/.gemini/antigravity/brain/52fc9ef8-23aa-4045-a4de-2257c2c0a58f/broken_chain_light_1788284781223.jpg",
    },
    {
        "type": "content",
        "tag": "03 // THE SOLUTION",
        "title": "Meet Your New Lead Engineer",
        "subtitle": "AlphaBrain doesn't just write code — it leads the project.",
        "items": [
            {
                "idx": "01",
                "title": "Voice Driven",
                "body": "Speak naturally to Eva (Gemini Live). She understands context, codebase history, and architecture.",
            },
            {
                "idx": "02",
                "title": "Autonomous Execution",
                "body": "Headless Antigravity workers write code and run tests in the background.",
            },
            {
                "idx": "03",
                "title": "Verifiable Results",
                "body": "No code is blindly merged. Test output, diffs, and staging links for approval.",
            },
        ],
        "image": "/Users/ajaytiwari/.gemini/antigravity/brain/52fc9ef8-23aa-4045-a4de-2257c2c0a58f/slide3_voice_1788285813249.jpg",
    },
    {
        "type": "content",
        "tag": "04 // ARCHITECTURE",
        "title": "System Topology",
        "subtitle": "Three modular components in perfect synchronization.",
        "items": [
            {
                "idx": "01",
                "title": "AlphaMeet",
                "body": "WebRTC LiveKit client on the phone for sub-second latency voice interactions.",
            },
            {
                "idx": "02",
                "title": "AlphaCore",
                "body": "FastAPI orchestration layer managing states, history, and task queues.",
            },
            {
                "idx": "03",
                "title": "AlphaWorker",
                "body": "Background daemon running headless Antigravity in isolated git worktrees.",
            },
        ],
        "image": "/Users/ajaytiwari/.gemini/antigravity/brain/52fc9ef8-23aa-4045-a4de-2257c2c0a58f/slide4_topology_1788285826678.jpg",
    },
    {
        "type": "content",
        "tag": "05 // CAPABILITIES",
        "title": "The Antigravity Engine",
        "subtitle": "Beyond chatbots — true agentic workflows.",
        "items": [
            {
                "idx": "01",
                "title": "Filesystem Access",
                "body": "Agents read, edit, and navigate the entire project directory autonomously.",
            },
            {
                "idx": "02",
                "title": "Subagent Delegation",
                "body": "Complex tasks broken down and delegated to specialized subagents in parallel.",
            },
            {
                "idx": "03",
                "title": "Command Execution",
                "body": "Agents run CLI commands, compile code, and run tests to verify their own work.",
            },
        ],
        "image": "/Users/ajaytiwari/.gemini/antigravity/brain/52fc9ef8-23aa-4045-a4de-2257c2c0a58f/slide5_engine_1788285861175.jpg",
    },
    {
        "type": "content",
        "tag": "06 // QUALITY ASSURANCE",
        "title": "Red Light / Green Light",
        "subtitle": "Deterministic gates ensuring pipeline integrity.",
        "items": [
            {
                "idx": "01",
                "title": "Pre-flight Lints",
                "body": "Code formatted (Ruff) and type-checked (mypy). Failures block the pipeline.",
            },
            {
                "idx": "02",
                "title": "Test Isolation",
                "body": "Every test runs against a fresh, isolated SQLite database. Zero state bleed.",
            },
            {
                "idx": "03",
                "title": "No-Merge Policy",
                "body": "If Red, the agent iteratively debugs until Green. No exceptions.",
            },
        ],
        "image": "/Users/ajaytiwari/.gemini/antigravity/brain/52fc9ef8-23aa-4045-a4de-2257c2c0a58f/slide6_redgreen_1788285873303.jpg",
    },
    {
        "type": "content",
        "tag": "07 // HERMETIC TESTING",
        "title": "Zero Side Effects",
        "subtitle": "Safe, reproducible testing environments.",
        "items": [
            {
                "idx": "01",
                "title": "Git Worktrees",
                "body": "Every task in a temporary worktree. Main repository stays completely untouched.",
            },
            {
                "idx": "02",
                "title": "Contract Mocks",
                "body": "External API calls strictly mocked during tests to guarantee determinism.",
            },
            {
                "idx": "03",
                "title": "506 Tests Passing",
                "body": "AlphaBrain boasts 506 hermetic tests with zero failures. Rock solid.",
            },
        ],
        "image": "/Users/ajaytiwari/.gemini/antigravity/brain/52fc9ef8-23aa-4045-a4de-2257c2c0a58f/data_cube_light_1788284806138.jpg",
    },
    {
        "type": "content",
        "tag": "08 // CI/CD PIPELINE",
        "title": "Continuous Delivery",
        "subtitle": "From voice command to deployed feature.",
        "items": [
            {
                "idx": "01",
                "title": "Voice → Task",
                "body": "Meeting transcript synthesized into a strict JSON implementation plan.",
            },
            {
                "idx": "02",
                "title": "Task → Code",
                "body": "Antigravity executes the plan, writing code and tests in a dedicated branch.",
            },
            {
                "idx": "03",
                "title": "Code → Prod",
                "body": "Upon passing QA gates, staged for one-tap human approval on the phone.",
            },
        ],
        "image": "/Users/ajaytiwari/.gemini/antigravity/brain/52fc9ef8-23aa-4045-a4de-2257c2c0a58f/slide8_pipeline_1788285908076.jpg",
    },
    {
        "type": "content",
        "tag": "09 // LIVE DEMO FLOW",
        "title": "The User Experience",
        "subtitle": "How a developer uses AlphaBrain daily.",
        "items": [
            {
                "idx": "01",
                "title": "Initialize",
                "body": "Open AlphaMeet on phone: 'Hey Eva, let's build the auth module.'",
            },
            {
                "idx": "02",
                "title": "Collaborate",
                "body": "Eva discusses architecture, asks clarifying questions, finalizes the spec.",
            },
            {
                "idx": "03",
                "title": "Execute & Ship",
                "body": "Worker spins up. Live progress on phone as code is written, tested, and staged.",
            },
        ],
        "image": "/Users/ajaytiwari/.gemini/antigravity/brain/52fc9ef8-23aa-4045-a4de-2257c2c0a58f/slide9_phone_1788285919917.jpg",
    },
    {
        "type": "content",
        "tag": "10 // PRODUCT ROADMAP",
        "title": "Scaling the Swarm",
        "subtitle": "The future of autonomous engineering.",
        "items": [
            {
                "idx": "01",
                "title": "Foundation (Current)",
                "body": "Voice cockpit, headless runner, and strict testing gates.",
            },
            {
                "idx": "02",
                "title": "Swarm Logic (Next)",
                "body": "Multi-agent DAG workflows and automated merge conflict arbitration.",
            },
            {
                "idx": "03",
                "title": "Enterprise Ops (Future)",
                "body": "Carrier phone integration, self-healing CI/CD, air-gapped deployments.",
            },
        ],
        "image": "/Users/ajaytiwari/.gemini/antigravity/brain/52fc9ef8-23aa-4045-a4de-2257c2c0a58f/slide10_roadmap_1788285954615.jpg",
    },
    {
        "type": "content",
        "tag": "11 // PROOF OF EXECUTION",
        "title": "Built. Tested. Proven.",
        "subtitle": "Everything is backed by verifiable code.",
        "items": [
            {
                "idx": "01",
                "title": "Source Code",
                "body": "Clean, modular Python — github.com/Ajtiwari26/alphaBrain",
            },
            {
                "idx": "02",
                "title": "Local Quickstart",
                "body": "LiveKit + Uvicorn + pytest. Reproducible in under 60 seconds.",
            },
            {
                "idx": "03",
                "title": "Automated QA",
                "body": "506 passing tests. Zero residual state. 100% pipeline success.",
            },
        ],
        "image": "/Users/ajaytiwari/.gemini/antigravity/brain/52fc9ef8-23aa-4045-a4de-2257c2c0a58f/slide11_terminal_1788285972901.jpg",
    },
]

html = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>AlphaBrain — Pitch Deck</title>
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@400;500;700&family=Inter:wght@300;400;500&family=Fira+Code:wght@400&display=swap" rel="stylesheet">
    <style>
        /* ============================================================
           DeployMate Design System — Adapted for Presentation
           Colors: #FFFFFF bg · #0A0A0A ink · #E6391E accent
           Fonts: Space Grotesk · Inter · Fira Code
           Rules: No shadows. No gradients. No tinted cards.
                  1px borders. Huge or small. Restraint + motion.
        ============================================================ */
        :root {
            --color-bg: #FFFFFF;
            --color-ink: #0A0A0A;
            --color-accent: #E6391E;
            --color-accent-deep: #C90C0F;
            --color-muted: #0A0A0A;
            --border: 1px solid #0A0A0A;
        }

        *, *::before, *::after { margin: 0; padding: 0; box-sizing: border-box; }
        body, html { background: var(--color-bg); font-family: 'Inter', sans-serif; color: var(--color-ink); overflow-x: hidden; }

        /* 16:9 Slide */
        .slide {
            width: 1920px;
            height: 1080px;
            position: relative;
            overflow: hidden;
            background: var(--color-bg);
            page-break-after: always;
            break-after: page;
        }

        /* Two-column layout */
        .slide-inner {
            width: 100%;
            height: 100%;
            display: flex;
            flex-direction: row;
        }

        .col-text {
            flex: 1.15;
            display: flex;
            flex-direction: column;
            justify-content: center;
            padding: 100px 80px 100px 120px;
            position: relative;
        }

        .col-image {
            flex: 0.85;
            display: flex;
            align-items: center;
            justify-content: center;
            padding: 80px;
            position: relative;
        }

        /* Image blending — mix-blend-mode multiply makes white bg transparent */
        .col-image img {
            max-width: 100%;
            max-height: 100%;
            object-fit: contain;
            mix-blend-mode: multiply;
            filter: contrast(1.08) saturate(1.1);
        }

        /* ---- MICRO EYEBROW (Fira Code, uppercase, tracked) ---- */
        .eyebrow {
            font-family: 'Fira Code', monospace;
            font-size: 14px;
            font-weight: 400;
            text-transform: uppercase;
            letter-spacing: 0.15em;
            color: var(--color-accent);
            margin-bottom: 40px;
        }

        /* ---- HUGE DISPLAY (Space Grotesk) ---- */
        .display {
            font-family: 'Space Grotesk', sans-serif;
            font-weight: 700;
            font-size: 100px;
            line-height: 0.95;
            letter-spacing: -0.03em;
            color: var(--color-ink);
            margin-bottom: 30px;
        }

        /* Title slide gets even bigger */
        .title-slide .display {
            font-size: 140px;
        }

        /* ---- SUBTITLE (Inter, light) ---- */
        .sub {
            font-family: 'Inter', sans-serif;
            font-size: 28px;
            font-weight: 300;
            line-height: 1.4;
            color: var(--color-ink);
            max-width: 700px;
            margin-bottom: 60px;
        }

        .sub-small {
            font-size: 20px;
            font-weight: 400;
            color: var(--color-muted);
            opacity: 0.6;
            max-width: 600px;
        }

        /* ---- INDEX LIST (Locomotive-style rows with 1px borders) ---- */
        .index-list {
            border-top: var(--border);
        }

        .index-row {
            display: flex;
            align-items: baseline;
            gap: 30px;
            padding: 28px 0;
            border-bottom: var(--border);
        }

        .index-num {
            font-family: 'Fira Code', monospace;
            font-size: 13px;
            font-weight: 400;
            color: var(--color-accent);
            letter-spacing: 0.1em;
            min-width: 30px;
            flex-shrink: 0;
        }

        .index-title {
            font-family: 'Space Grotesk', sans-serif;
            font-size: 26px;
            font-weight: 700;
            color: var(--color-ink);
            min-width: 260px;
            flex-shrink: 0;
        }

        .index-body {
            font-family: 'Inter', sans-serif;
            font-size: 18px;
            font-weight: 400;
            color: var(--color-ink);
            opacity: 0.55;
            line-height: 1.5;
        }

        /* ---- FOOTER BAR ---- */
        .footer-bar {
            position: absolute;
            bottom: 0;
            left: 0;
            right: 0;
            height: 60px;
            border-top: var(--border);
            display: flex;
            align-items: center;
            justify-content: space-between;
            padding: 0 120px;
        }

        .footer-bar span {
            font-family: 'Fira Code', monospace;
            font-size: 12px;
            font-weight: 400;
            text-transform: uppercase;
            letter-spacing: 0.15em;
            color: var(--color-ink);
            opacity: 0.35;
        }

        /* ---- ACCENT BAR (4px bottom progress bar like DeployMate) ---- */
        .accent-bar {
            position: absolute;
            bottom: 0;
            left: 0;
            height: 4px;
            background: var(--color-accent);
        }

        /* ---- VERTICAL BORDER between columns ---- */
        .col-divider {
            width: 1px;
            background: var(--color-ink);
            opacity: 0.1;
            align-self: stretch;
            margin: 100px 0;
        }

        @media print {
            @page { size: 1920px 1080px; margin: 0; }
            body { -webkit-print-color-adjust: exact; print-color-adjust: exact; }
        }
    </style>
</head>
<body>
"""

total = len(slides_data)

for i, slide in enumerate(slides_data):
    progress_pct = ((i + 1) / total) * 100

    html += '<div class="slide">'
    html += f'<div class="slide-inner {"title-slide" if slide["type"] == "title" else ""}">'

    # Text column
    html += '<div class="col-text">'
    html += f'<div class="eyebrow">{slide["tag"]}</div>'
    html += f'<div class="display">{slide["title"]}</div>'
    html += f'<div class="sub">{slide["subtitle"]}</div>'

    if slide["type"] == "title":
        html += f'<div class="sub-small">{slide["body"]}</div>'
    else:
        html += '<div class="index-list">'
        for item in slide["items"]:
            html += f"""<div class="index-row">
                <span class="index-num">{item["idx"]}</span>
                <span class="index-title">{item["title"]}</span>
                <span class="index-body">{item["body"]}</span>
            </div>"""
        html += "</div>"

    html += "</div>"  # col-text

    # Vertical divider
    html += '<div class="col-divider"></div>'

    # Image column
    if "image" in slide:
        html += f'<div class="col-image"><img src="file://{slide["image"]}" alt="{slide["title"]}"></div>'

    html += "</div>"  # slide-inner

    # Footer
    html += f"""<div class="footer-bar">
        <span>AlphaBrain · Autonomous Dev Cockpit</span>
        <span>{str(i + 1).zfill(2)} / {str(total).zfill(2)}</span>
    </div>"""

    # Accent progress bar
    html += f'<div class="accent-bar" style="width: {progress_pct}%;"></div>'

    html += "</div>"  # slide

html += "</body></html>"

with open("testscript/deck_light.html", "w") as f:
    f.write(html)
print("SUCCESS: DeployMate-styled deck generated with all 11 images.")
