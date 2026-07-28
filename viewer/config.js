// The live viewer talks to a FastAPI backend. Locally, `audit-orchestrator
// serve` hosts both the API and this viewer on one origin, so relative paths
// ("/api/...") just work. Deployed statically (GitHub Pages, at either the
// github.io URL or the anjesh.ai custom domain), the viewer is static-only
// and the API instead runs on Modal, so requests need an absolute base URL.
const LOCAL_HOSTS = new Set(["localhost", "127.0.0.1"]);
window.AUDIT_API_BASE = LOCAL_HOSTS.has(location.hostname)
  ? ""
  : "https://anjeshdubey--audit-orchestrator-serve.modal.run";
