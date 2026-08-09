// The usage page's logic, in its own file rather than an inline <script>.
//
// This page is the reason: it renders every user's display name, email, themes
// and question text in front of the owner's token, so it is the one page where
// an unescaped value would leak other people's data rather than the reader's
// own. Escaping is the defence; a CSP without 'unsafe-inline' is the backstop
// under it, and that backstop is only available to a page with no inline
// script at all. See vercel.json, which drops 'unsafe-inline' for /admin.html
// only.
//
// The other three pages still carry inline blocks and still need
// 'unsafe-inline' in the shared policy. Moving them is the same mechanical
// change; it just buys less, because per-user queries mean XSS there reaches
// only the reader's own rows.

const $ = id => document.getElementById(id);
const errEl = $("error"), usageEl = $("usage");

// Every field below came out of the database, so every field goes through
// escapeHtml - counts included, because a count is only a number until the
// day the query returns something else.
function renderUsage(data) {
  $("totals").innerHTML = [
    [data.totals.users, "people"],
    [data.totals.sign_ins, "sign-ins"],
    [data.totals.stories, "stories"],
    [data.totals.questions, "questions"],
  ].map(([n, k]) => `
    <div class="stat">
      <span class="n">${escapeHtml(String(n))}</span>
      <span class="k">${escapeHtml(k)}</span>
    </div>`).join("");

  // name and last_seen_at are the two columns that can legitimately be
  // empty; escapeHtml calls .replace, so a null would throw and take the
  // whole page down rather than leaving one blank cell.
  // Bars are scaled against the busiest day in the window, not a fixed
  // maximum: a quiet fortnight should still show its own shape rather than
  // fourteen invisible slivers.
  const busiest = Math.max(1, ...data.daily.map(d => d.sign_ins + d.stories + d.questions));
  $("daily").innerHTML = data.daily.map(d => {
    const total = d.sign_ins + d.stories + d.questions;
    const pct = Math.round((total / busiest) * 100);
    return `
    <tr${total ? "" : ' class="quiet"'}>
      <td class="when">${escapeHtml(d.day)}</td>
      <td class="num">${escapeHtml(String(d.people))}</td>
      <td class="num">${escapeHtml(String(d.sign_ins))}</td>
      <td class="num">${escapeHtml(String(d.stories))}</td>
      <td class="num">${escapeHtml(String(d.questions))}</td>
      <td class="bar-h"><span class="bar" style="width:${pct}%"></span></td>
    </tr>`;
  }).join("");

  $("users").innerHTML = data.users.map(u => `
    <tr>
      <td>
        <span class="who">${escapeHtml(u.name || "—")}</span>
        <span class="mail">${escapeHtml(u.email)}</span>
        <span class="joined">joined ${escapeHtml(u.created_at)}</span>
      </td>
      <td class="num">${escapeHtml(String(u.sign_ins))}</td>
      <td class="num">${escapeHtml(String(u.stories))}</td>
      <td class="num">${escapeHtml(String(u.questions))}</td>
      <td class="when">${escapeHtml(u.last_seen_at || "—")}</td>
    </tr>`).join("");

  // Genres come from a keyword heuristic over the story text, so this is a
  // rough shape of what gets asked for, not a taxonomy. Rendered before the
  // recent-activity block below, which returns early when it is empty.
  // avg_grade goes through readingBand for the same reason it does on the
  // story page: "3.2" is a number, "easy, about age 8" is an answer.
  const genres = data.genres || [];
  $("genres-section").hidden = !genres.length;
  $("genres").innerHTML = genres.map(g => `
    <tr>
      <td class="genre">${escapeHtml(g.genre || "—")}</td>
      <td class="num">${escapeHtml(String(g.stories))}</td>
      <td class="num">${escapeHtml(typeof g.avg_words === "number" ? String(Math.round(g.avg_words)) : "—")}</td>
      <td>${escapeHtml(readingBand(g.avg_grade))}</td>
    </tr>`).join("");

  const recent = $("recent");
  if (!data.recent.length) {
    recent.innerHTML = '<li class="empty">Nothing yet.</li>';
    return;
  }
  recent.innerHTML = data.recent.map(r => `
    <li>
      <span class="kind">${escapeHtml(r.kind)}</span>
      <span class="detail">${escapeHtml(r.detail)}</span>
      <span class="meta">${escapeHtml(r.email)} · ${escapeHtml(r.created_at)}</span>
    </li>`).join("");
}

async function loadUsage() {
  const headers = authHeaders();
  if (!headers) return;
  errEl.textContent = "";
  try {
    const r = await fetch(`${BACKEND_URL}/admin/usage`, {headers});
    if (r.status === 401) return handleAuthExpired(errEl);
    if (r.status === 403) {
      // Signed in fine, just not the owner. Say that, rather than showing
      // the backend's wording or an empty page that looks broken.
      errEl.textContent = "This page is for the app owner only.";
      return;
    }
    const data = await r.json();
    if (!r.ok) throw new Error(data.detail || "Request failed");
    renderUsage(data);
    usageEl.hidden = false;
  } catch (e) {
    errEl.textContent = e.message === "Failed to fetch"
      ? "Cannot reach the server. If it was asleep, wait a moment and try again."
      : e.message;
  }
}

const hintEl = $("auth-hint"), whoEl = $("auth-who");
const signoutBtn = $("signout"), buttonEl = $("g-signin");

initGoogleAuth({
  buttonEl,
  onSignIn: user => {
    whoEl.textContent = `Signed in as ${user.name || user.email}`;
    whoEl.hidden = false;
    signoutBtn.hidden = false;
    hintEl.hidden = true;
    buttonEl.hidden = true;
    loadUsage();
  },
  onSignOut: () => {
    whoEl.hidden = true;
    signoutBtn.hidden = true;
    hintEl.hidden = false;
    buttonEl.hidden = false;
    // Other people's emails must not stay on screen after sign-out.
    usageEl.hidden = true;
  },
});
signoutBtn.addEventListener("click", signOut);

// The Google library is loaded from here rather than from a <script> tag in the
// HTML, because that tag carried onload="googleLibraryLoaded()" - an inline
// handler, which 'unsafe-inline' is what authorises. Removing the inline blocks
// but leaving the attribute would have left the directive doing exactly the
// same job for one line of HTML.
//
// Assigning .onload as a PROPERTY is not an inline handler and needs no CSP
// permission; only the onload="..." attribute form does.
//
// Ordering is safer than the tag it replaces, rather than merely equivalent:
// initGoogleAuth() above has already set authHandlers by the time this element
// is appended, so the "handlers are in place before the library lands"
// guarantee no longer depends on where the tag sits in <body>.
const gis = document.createElement("script");
gis.src = "https://accounts.google.com/gsi/client";
gis.async = true;
gis.defer = true;
gis.onload = googleLibraryLoaded;
gis.onerror = googleLibraryFailed;
document.body.appendChild(gis);
