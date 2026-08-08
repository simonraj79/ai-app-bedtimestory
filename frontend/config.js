// Where the FastAPI backend lives.
//
// Auto-detected so nobody has to remember to edit this file before deploying:
// a page served from localhost talks to the local backend, anything else talks
// to production. Editing one line per environment is how BACKEND_URL typos and
// "works locally, broken in production" happen.
//
// The backend sleeps after 15 minutes on Render's free tier, so the first
// request after an idle period can take 30-60 seconds.
const LOCAL_HOSTS = ["localhost", "127.0.0.1"];

const BACKEND_URL = LOCAL_HOSTS.includes(location.hostname)
  ? "http://localhost:8000"
  : "https://ai-app-bedtimestory.onrender.com";

// Every page renders stored text through innerHTML, so this is the escape
// boundary for anything that came out of the database. It lives here, not in
// each page, because a duplicated escape gets fixed in the copy you happened to
// be looking at.
function escapeHtml(s) {
  return s.replace(/[&<>"']/g, c => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", "\"": "&quot;", "'": "&#39;"
  }[c]));
}
