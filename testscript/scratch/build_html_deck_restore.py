
slides_data = [
    {
        "type": "title",
        "title": "AlphaBrain",
        "subtitle": "The Autonomous Multi-Agent Developer Cockpit",
        "tag": "iQOO PUNE HACKATHON SUBMISSION",
        "body": "A voice-native, hermetically sealed engineering swarm powered by Gemini and Antigravity.",
        "image": "/Users/ajaytiwari/.gemini/antigravity/brain/52fc9ef8-23aa-4045-a4de-2257c2c0a58f/slide1_brain_1788285056050.jpg",
    },
    {
        "type": "content",
        "tag": "02 // THE CONTEXT",
        "title": "Breaking the Desktop Chain",
        "subtitle": "Why AlphaBrain Fits the iQOO AgentKit Track perfectly",
        "cards": [
            {
                "title": "Phone-First UI",
                "body": "100% controlled via a real-time voice duplex interface on the iQOO phone, eliminating the need for a laptop keyboard.",
                "accent": "#E85D04",
            },
            {
                "title": "AgentKit Core",
                "body": "Built entirely around Antigravity (Google's agentic framework) orchestrating the LiveKit voice bridge.",
                "accent": "#0077B6",
            },
            {
                "title": "Deep QA",
                "body": "Enforces a rigid 'Red Light / Green Light' test-driven paradigm before any code is ever merged.",
                "accent": "#2A9D8F",
            },
        ],
        "image": "/Users/ajaytiwari/.gemini/antigravity/brain/52fc9ef8-23aa-4045-a4de-2257c2c0a58f/broken_chain_light_1788284781223.jpg",
    },
    {
        "type": "content",
        "tag": "03 // THE SOLUTION",
        "title": "Meet Your New Lead Engineer",
        "subtitle": "AlphaBrain doesn't just write code; it leads the project.",
        "cards": [
            {
                "title": "Voice Driven",
                "body": "Speak naturally to Eva (the Gemini Live agent). She understands context, codebase history, and complex architectural needs.",
                "accent": "#7209B7",
            },
            {
                "title": "Autonomous Execution",
                "body": "Once you agree on a plan, headless Antigravity workers take over, write the code, and run the tests in the background.",
                "accent": "#E85D04",
            },
            {
                "title": "Verifiable Results",
                "body": "No code is blindly merged. AlphaBrain provides test output, diffs, and staging links for approval.",
                "accent": "#0077B6",
            },
        ],
    },
    {
        "type": "content",
        "tag": "04 // ARCHITECTURE",
        "title": "System Topology",
        "subtitle": "Three modular components working in perfect synchronization.",
        "cards": [
            {
                "title": "AlphaMeet (Frontend)",
                "body": "WebRTC LiveKit client running on the user's phone for sub-second latency voice interactions.",
                "accent": "#2A9D8F",
            },
            {
                "title": "AlphaCore (API)",
                "body": "FastAPI orchestration layer managing states, session history, and task queues via SQLite.",
                "accent": "#7209B7",
            },
            {
                "title": "AlphaWorker (Runner)",
                "body": "Background daemon running the headless Antigravity CLI in isolated git worktrees.",
                "accent": "#E85D04",
            },
        ],
    },
    {
        "type": "content",
        "tag": "05 // AGENT CAPABILITIES",
        "title": "The Antigravity Engine",
        "subtitle": "Moving beyond simple chatbots into true agentic workflows.",
        "cards": [
            {
                "title": "Filesystem Access",
                "body": "Agents can read, edit, and navigate the entire project directory autonomously.",
                "accent": "#0077B6",
            },
            {
                "title": "Subagent Delegation",
                "body": "Complex tasks are broken down and delegated to specialized subagents for parallel execution.",
                "accent": "#2A9D8F",
            },
            {
                "title": "Command Execution",
                "body": "Agents run CLI commands, compile code, and run tests locally to verify their own work.",
                "accent": "#7209B7",
            },
        ],
    },
    {
        "type": "content",
        "tag": "06 // QUALITY ASSURANCE",
        "title": "Red Light / Green Light",
        "subtitle": "Deterministic gates ensuring pipeline integrity.",
        "cards": [
            {
                "title": "Pre-flight Lints",
                "body": "Code is formatted (Ruff) and type-checked (mypy) strictly. Failures block the pipeline immediately.",
                "accent": "#E85D04",
            },
            {
                "title": "Test Isolation",
                "body": "Every unit test runs against a fresh, in-memory or isolated SQLite database to prevent state bleed.",
                "accent": "#0077B6",
            },
            {
                "title": "No-Merge Policy",
                "body": "If the pipeline is Red, the agent is forced to iteratively debug until it goes Green.",
                "accent": "#2A9D8F",
            },
        ],
    },
    {
        "type": "content",
        "tag": "07 // HERMETIC TESTING",
        "title": "Zero Side Effects",
        "subtitle": "Safe, reproducible testing environments.",
        "cards": [
            {
                "title": "Git Worktrees",
                "body": "Every task is executed in a temporary git worktree, keeping the main repository completely untouched.",
                "accent": "#7209B7",
            },
            {
                "title": "Contract Mocks",
                "body": "External API calls (like LLM generations) are strictly mocked during unit tests to guarantee determinism.",
                "accent": "#E85D04",
            },
            {
                "title": "100% Pass Rate",
                "body": "AlphaBrain currently boasts 506 passing tests. The foundation is rock solid.",
                "accent": "#0077B6",
            },
        ],
        "image": "/Users/ajaytiwari/.gemini/antigravity/brain/52fc9ef8-23aa-4045-a4de-2257c2c0a58f/data_cube_light_1788284806138.jpg",
    },
    {
        "type": "content",
        "tag": "08 // CI/CD PIPELINE",
        "title": "Continuous Delivery",
        "subtitle": "From voice command to deployed feature.",
        "cards": [
            {
                "title": "Voice to Task",
                "body": "The meeting transcript is synthesized into a strict JSON implementation plan.",
                "accent": "#2A9D8F",
            },
            {
                "title": "Task to Code",
                "body": "Antigravity executes the JSON plan, writing code and tests in a dedicated branch.",
                "accent": "#7209B7",
            },
            {
                "title": "Code to Prod",
                "body": "Upon passing the QA gates, the feature is staged for one-tap human approval.",
                "accent": "#E85D04",
            },
        ],
    },
    {
        "type": "content",
        "tag": "09 // LIVE DEMO",
        "title": "The User Experience",
        "subtitle": "How a developer uses AlphaBrain daily.",
        "cards": [
            {
                "title": "1. Initialize",
                "body": "User opens the AlphaMeet UI on their phone and says 'Hey Eva, let's build the auth module.'",
                "accent": "#0077B6",
            },
            {
                "title": "2. Collaborate",
                "body": "Eva discusses the architecture, asks clarifying questions, and finalizes the spec.",
                "accent": "#2A9D8F",
            },
            {
                "title": "3. Execute",
                "body": "Eva spins up a worker. The user sees live progress indicators on their phone as code is written and tested.",
                "accent": "#7209B7",
            },
        ],
    },
    {
        "type": "content",
        "tag": "10 // ROADMAP",
        "title": "Scaling the Swarm",
        "subtitle": "The future of autonomous engineering.",
        "cards": [
            {
                "title": "Current: Foundation",
                "body": "Voice cockpit, headless runner, and strict testing gates.",
                "accent": "#E85D04",
            },
            {
                "title": "Next: Swarm Logic",
                "body": "Multi-agent DAG workflows and automated merge conflict arbitration.",
                "accent": "#0077B6",
            },
            {
                "title": "Future: Enterprise Ops",
                "body": "Carrier phone integration, self-healing CI/CD, and air-gapped deployments.",
                "accent": "#2A9D8F",
            },
        ],
    },
    {
        "type": "content",
        "tag": "11 // PROOF OF EXECUTION",
        "title": "Project Verification",
        "subtitle": "Everything is backed by verifiable code.",
        "cards": [
            {
                "title": "Source Code",
                "body": "Clean, modular Python structure available at github.com/Ajtiwari26/alphaBrain",
                "accent": "#7209B7",
            },
            {
                "title": "Local Setup",
                "body": "Easily reproducible locally with LiveKit and Uvicorn. Scripts included.",
                "accent": "#E85D04",
            },
            {
                "title": "Automated QA",
                "body": "Run `pytest` to see the 506 passing tests. Zero residual state.",
                "accent": "#0077B6",
            },
        ],
    },
]

html_template = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>AlphaBrain Pitch Deck</title>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;600;800&family=Playfair+Display:ital,wght@0,600;1,600&display=swap" rel="stylesheet">
    <style>
        :root {
            --bg-color: #ffffff;
            --text-primary: #111111;
            --text-secondary: #555555;
            --card-bg: rgba(245, 247, 250, 0.6);
            --card-border: rgba(0, 0, 0, 0.06);
            --glass-shadow: 0 10px 40px rgba(0, 0, 0, 0.04);
        }

        body, html { margin: 0; padding: 0; background: var(--bg-color); font-family: 'Inter', sans-serif; color: var(--text-primary); overflow-x: hidden; }

        .slide {
            width: 1920px; height: 1080px; position: relative; overflow: hidden; background: var(--bg-color); display: flex; flex-direction: column; justify-content: center; box-sizing: border-box; page-break-after: always; break-after: page;
        }

        .ambient-blob { position: absolute; border-radius: 50%; filter: blur(120px); z-index: 0; opacity: 0.15; }
        .blob-1 { top: -100px; left: -100px; width: 800px; height: 800px; background: #E85D04; }
        .blob-2 { bottom: -200px; right: -100px; width: 900px; height: 900px; background: #0077B6; }

        .content-wrapper { position: relative; z-index: 10; padding: 100px 140px; height: 100%; display: flex; flex-direction: row; box-sizing: border-box; align-items: center; }
        .text-col { flex: 1; display: flex; flex-direction: column; justify-content: center; }
        .img-col { flex: 1; display: flex; align-items: center; justify-content: center; padding-left: 60px; }
        .img-col img { max-width: 100%; max-height: 800px; object-fit: contain; mix-blend-mode: multiply; filter: contrast(1.05); }

        .tag { font-size: 18px; font-weight: 800; letter-spacing: 3px; color: #555; margin-bottom: 24px; text-transform: uppercase; }
        h1 { font-family: 'Playfair Display', serif; font-size: 110px; font-weight: 600; line-height: 1.1; margin: 0 0 30px 0; color: var(--text-primary); letter-spacing: -2px; }
        h2 { font-family: 'Playfair Display', serif; font-size: 80px; font-weight: 600; line-height: 1.1; margin: 0 0 20px 0; color: var(--text-primary); letter-spacing: -1px; }
        .subtitle { font-size: 32px; font-weight: 300; color: var(--text-secondary); max-width: 1200px; line-height: 1.4; margin-bottom: 80px; }

        .title-slide { flex-direction: row; }
        .title-slide h1 { font-size: 130px; margin-bottom: 30px; }
        .title-slide .subtitle { font-size: 36px; margin-bottom: 0; }
        
        .card-container { display: flex; flex-direction: column; gap: 30px; }
        .glass-card { background: var(--card-bg); backdrop-filter: blur(30px) saturate(150%); -webkit-backdrop-filter: blur(30px) saturate(150%); border: 1px solid var(--card-border); border-radius: 24px; padding: 30px 40px; box-shadow: var(--glass-shadow); position: relative; overflow: hidden; }
        .glass-card::before { content: ''; position: absolute; top: 0; bottom: 0; left: 0; width: 6px; background: var(--accent); }
        .card-title { font-size: 30px; font-weight: 600; margin: 0 0 12px 0; color: var(--text-primary); }
        .card-body { font-size: 20px; line-height: 1.5; color: var(--text-secondary); font-weight: 400; }

        /* Full width cards if no image */
        .no-img .text-col { flex: 1; }
        .no-img .card-container { flex-direction: row; flex-wrap: wrap; }
        .no-img .glass-card { flex: 1; min-width: 30%; }

        .footer-bar { position: absolute; bottom: 60px; left: 140px; right: 140px; display: flex; justify-content: space-between; align-items: center; font-size: 16px; font-weight: 600; color: #999; letter-spacing: 1px; text-transform: uppercase; }
        @media print { @page { size: 1920px 1080px; margin: 0; } body { -webkit-print-color-adjust: exact; print-color-adjust: exact; } }
    </style>
</head>
<body>
"""

for i, slide in enumerate(slides_data):
    has_img = "image" in slide
    html_template += '<div class="slide">'
    html_template += '<div class="ambient-blob blob-1"></div>'
    html_template += '<div class="ambient-blob blob-2"></div>'

    html_template += f'<div class="content-wrapper {"" if has_img else "no-img"}">'

    html_template += '<div class="text-col">'
    if slide["type"] == "title":
        html_template += f"""
            <div class="tag" style="color: #E85D04;">{slide["tag"]}</div>
            <h1>{slide["title"]}</h1>
            <div class="subtitle">{slide["subtitle"]}<br><br><span style="font-size: 24px; color: #888;">{slide["body"]}</span></div>
        """
    else:
        html_template += f"""
            <div class="tag">{slide["tag"]}</div>
            <h2>{slide["title"]}</h2>
            <div class="subtitle">{slide["subtitle"]}</div>
            <div class="card-container">
        """
        for card in slide["cards"]:
            html_template += f"""
                <div class="glass-card" style="--accent: {card["accent"]};">
                    <h3 class="card-title">{card["title"]}</h3>
                    <div class="card-body">{card["body"]}</div>
                </div>
            """
        html_template += "</div>"
    html_template += "</div>"  # end text-col

    if has_img:
        html_template += f"""
        <div class="img-col">
            <img src="file://{slide["image"]}" alt="Slide Visual">
        </div>
        """

    html_template += "</div>"  # end content-wrapper
    html_template += f"""
        <div class="footer-bar">
            <span>AlphaBrain // Autonomous Dev Cockpit</span>
            <span>{i + 1} / {len(slides_data)}</span>
        </div>
    """
    html_template += "</div>"  # end slide

html_template += """
</body>
</html>
"""

with open("testscript/deck_light.html", "w") as f:
    f.write(html_template)
print("Generated testscript/deck_light.html successfully (restored clean layout).")
