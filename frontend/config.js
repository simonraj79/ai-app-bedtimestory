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

// --- Reading stats: presentation only ---------------------------------------
//
// story.html and admin.html both put reading numbers in front of a person, so
// the wording lives here. Two pages quietly disagreeing about what "grade 3.2"
// means is exactly what a duplicated helper produces.

// A Flesch-Kincaid grade is a US school year. Outside the US it means nothing,
// and inside it "grade 3.2" is still a number rather than something a parent
// can act on. The band says what to expect; the age is the part someone already
// knows about their own child.
//
// The age is DERIVED, not measured: US grade + 5 is the conventional rough
// conversion, and the formula behind the grade counts syllables and sentence
// length - not whether a child follows the story. It is a hint, which is why
// the wording has to keep sounding like one ("about age 8", never "age 8").
function readingBand(gradeLevel) {
  // Number(null) is 0, which would come back "very easy" - an invented answer
  // for a story that was never measured. Reject the empty cases first.
  if (gradeLevel === null || gradeLevel === undefined) return "—";
  const grade = Number(gradeLevel);
  if (!Number.isFinite(grade)) return "—";

  // Short sentences and short words can score below grade 1, and the formula
  // genuinely goes negative; the floor stops that reading as "about age 2".
  const age = Math.max(5, Math.round(grade) + 5);

  // "to read alone" is load-bearing, not padding. STORY_SYSTEM_PROMPT asks for
  // words a five-year-old understands, and these stories still score around
  // grade 3-4 - because the formula counts syllables and sentence length, not
  // whether a child follows the story. A parent of a four-year-old reading
  // "about age 9" on tonight's story would reasonably think it was wrong for
  // them. It is the age a child could read it THEMSELVES; being read to has no
  // such floor. The band word is the part worth comparing between stories.
  if (grade <= 1) return `very easy · age ${age} to read alone`;
  if (grade <= 3) return `easy · age ${age} to read alone`;
  if (grade <= 5) return `medium · age ${age} to read alone`;
  if (grade <= 7) return `harder · age ${age} to read alone`;
  return `hard · age ${age} to read alone`;
}

// Minutes and seconds, because "93 seconds" makes the reader do the division.
// The caller must say what the time is FOR: this is read-ALOUD time at about
// 130 words a minute, which is roughly half silent reading speed.
function readingTime(seconds) {
  if (seconds === null || seconds === undefined) return "—";
  const total = Math.round(Number(seconds));
  if (!Number.isFinite(total)) return "—";
  if (total < 60) return `${total} s`;
  const minutes = Math.floor(total / 60);
  const rest = total % 60;
  // Past ten minutes the seconds are noise and the string gets long enough to
  // wrap a stat tile onto two lines, leaving it taller than the ones beside it.
  // "1 min 18 s" is a story; "17 min" is a lifetime total, and nobody needs the
  // 47 seconds.
  if (total >= 600) return `${Math.round(total / 60)} min`;
  return rest ? `${minutes} min ${rest} s` : `${minutes} min`;
}

// --- Google sign-in ---------------------------------------------------------
//
// The OAuth client ID is PUBLIC BY DESIGN. It names the app to Google and rides
// along in every sign-in request the browser makes, so it is not a credential
// and cannot be kept private. The thing that must never appear in frontend/ is
// the client *secret* - and this flow has none: the browser is handed a signed
// ID token directly, and the backend checks that signature against Google's
// public keys. That is how "nothing secret may ever live in frontend/" survives
// bolting sign-in onto a static site.
const GOOGLE_CLIENT_ID =
  "722888382160-s5gggbictm3ehmgpu926m2u6ur55pb1r.apps.googleusercontent.com";

// sessionStorage, not localStorage: this is a bearer token, and a phone handed
// to somebody else should not still be signed in after the tab is closed.
const TOKEN_KEY = "googleIdToken";

// Google ID tokens last about an hour. Treating the last minute as already gone
// stops a request leaving with a token that expires while it is in flight.
const TOKEN_EXPIRY_SKEW_SECONDS = 60;

// Set by initGoogleAuth() before the Google library loads, read once it lands.
let authHandlers = null;

// The middle segment of a JWT is base64url-encoded JSON.
//
// Reading it here is safe for DISPLAY ONLY. Nothing is verified: a JWT payload
// is just text, and anyone can hand this page one that claims to be anybody.
// The only authority on who the caller is, is the backend's signature check
// against Google's public keys. Never branch on this for permission - not even
// "is this the owner?" - or the admin page becomes a text field.
function decodeJwtPayload(token) {
  try {
    const b64 = token.split(".")[1].replace(/-/g, "+").replace(/_/g, "/");
    const bytes = Uint8Array.from(atob(b64), c => c.charCodeAt(0));
    return JSON.parse(new TextDecoder().decode(bytes));
  } catch {
    return null;
  }
}

// The stored token, or null. Expiry is checked here rather than at each call
// site so a stale token can never reach a fetch.
function getToken() {
  const token = sessionStorage.getItem(TOKEN_KEY);
  if (!token) return null;

  const payload = decodeJwtPayload(token);
  if (!payload || payload.exp - TOKEN_EXPIRY_SKEW_SECONDS <= Date.now() / 1000) {
    sessionStorage.removeItem(TOKEN_KEY);
    return null;
  }
  return token;
}

// Who the browser believes is signed in - for greeting them, nothing more.
// See decodeJwtPayload: this is unverified.
function currentUser() {
  const token = getToken();
  const payload = token && decodeJwtPayload(token);
  if (!payload) return null;
  return {email: payload.email, name: payload.name, picture: payload.picture};
}

// Headers for an authenticated call, or null when signed out. Callers check for
// null rather than sending a header-less request the backend will 401 anyway.
function authHeaders() {
  const token = getToken();
  if (!token) return null;
  return {"Content-Type": "application/json", "Authorization": `Bearer ${token}`};
}

function handleGoogleCredential(response) {
  sessionStorage.setItem(TOKEN_KEY, response.credential);
  const user = currentUser();
  // An unreadable credential leaves the page signed out rather than half in,
  // where the UI says "signed in" and every request comes back 401.
  if (user) authHandlers.onSignIn(user);
}

function signOut() {
  sessionStorage.removeItem(TOKEN_KEY);
  // Without this, One Tap signs the same person straight back in and "sign out"
  // looks like it did nothing.
  if (window.google) google.accounts.id.disableAutoSelect();
  authHandlers.onSignOut();
  renderGoogleButton();
}

// Called again after sign-out, not only on load: on load the signed-in UI has
// already hidden the container, and Google sizes the button when it draws it.
function renderGoogleButton() {
  if (!window.google || !authHandlers) return;
  google.accounts.id.renderButton(authHandlers.buttonEl, {
    type: "standard",
    theme: "filled_black",
    size: "large",
    shape: "pill",
    text: "signin_with",
    width: "240",
  });
}

function initGoogleAuth({onSignIn, onSignOut, buttonEl}) {
  authHandlers = {onSignIn, onSignOut, buttonEl};

  // Restore before the Google library loads. A reload inside the hour must not
  // blank the page while a script downloads from another origin.
  const user = currentUser();
  if (user) onSignIn(user);
  else onSignOut();

  if (window.google) googleLibraryLoaded();
}

// The Google <script> tag carries onload="googleLibraryLoaded()" and is the last
// element in <body>, after the page's own script - so the handlers are always in
// place by the time the library lands, whatever order async loading picks.
function googleLibraryLoaded() {
  if (!authHandlers) return;

  google.accounts.id.initialize({
    client_id: GOOGLE_CLIENT_ID,
    callback: handleGoogleCredential,
  });
  renderGoogleButton();

  // Deliberately NO google.accounts.id.prompt() here.
  //
  // One Tap is a prompt, not a sign-in: dismissing it leaves you signed out, so
  // it reappeared on the next page and read as being asked to sign in twice.
  // Alongside the button it also put two ways to sign in on one screen.
  //
  // It is the fragile half of GIS as well - it needs FedCM, third-party cookie
  // permission and no content blocker in the way, which is why it worked on
  // some machines and silently did nothing on others. The rendered button
  // depends on none of that. One affordance, everywhere, or none.
  //
  // `auto_select` went with it: it only ever applied to One Tap, so keeping it
  // would be a flag that does nothing.
}

// accounts.google.com is blocked by some content blockers and networks. Without
// this the page sits there with a dead button and no explanation at all.
function googleLibraryFailed() {
  if (!authHandlers) return;
  authHandlers.buttonEl.textContent =
    "Google sign-in could not load. Check your connection, or a content blocker.";
}

// A 401 means the backend rejected the token - expired, or revoked elsewhere.
// Say that plainly and put the Google button back; a raw error reads as a broken
// app, and leaving the signed-in UI up means every retry fails the same way.
function handleAuthExpired(errorEl) {
  signOut();
  errorEl.textContent = "Your sign-in expired. Sign in with Google again to continue.";
}
