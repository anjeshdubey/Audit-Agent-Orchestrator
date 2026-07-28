"""Modal deployment for the Audit Orchestrator live-demo API.

Wraps `audit_orchestrator.server:app` (the same FastAPI app the README's
`audit-orchestrator serve` runs locally) as a Modal ASGI web endpoint.

Pinned to exactly one container: run state (`RUNS`, `_active_run_id` in
server.py) lives in a process-global dict, so a second container would
silently split traffic across two independent engagements and corrupt
whichever one a browser is watching.

Deploy:
    modal deploy modal_app.py

Provider keys are read from the Modal Secret "audit-orchestrator-secrets"
(see README) -- never baked into the image or committed to the repo.
"""

import modal

app = modal.App("audit-orchestrator")

image = (
    modal.Image.debian_slim(python_version="3.11")
    .pip_install(
        "instructor>=1.6",
        "pydantic>=2.7",
        "pyyaml>=6.0",
        "python-dotenv>=1.0",
        "fastapi>=0.115",
        "uvicorn[standard]>=0.30",
        "langgraph>=0.2",
        "groq>=0.11",
        "google-genai>=0.3",
        "openai>=1.40",
        "anthropic>=0.40",
    )
    .env({"PYTHONPATH": "/root/app/src"})
    .add_local_dir("src", remote_path="/root/app/src")
    .add_local_dir("sample", remote_path="/root/app/sample")
    .add_local_dir("viewer", remote_path="/root/app/viewer")
)


@app.function(
    image=image,
    secrets=[modal.Secret.from_name("audit-orchestrator-secrets")],
    max_containers=1,
    timeout=30 * 60,
)
@modal.concurrent(max_inputs=20)
@modal.asgi_app()
def serve():
    from audit_orchestrator.server import app as fastapi_app

    return fastapi_app
