#!/bin/bash
set -a && source .env.local && set +a
export ALPHA_API_TOKEN=ced2a32dd9a568fa22e606fa48381543
.venv/bin/uvicorn alpha_core.api.app:app --host 127.0.0.1 --port 8000
