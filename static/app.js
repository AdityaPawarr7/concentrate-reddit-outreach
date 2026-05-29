let posts = [];
let selectedIds = new Set();
let activePostId = null;
let activePermalink = "";
let subreddits = [];

const $ = (id) => document.getElementById(id);

async function api(path, opts = {}) {
  const res = await fetch(path, {
    headers: { "Content-Type": "application/json" },
    ...opts,
  });
  if (!res.ok) {
    const err = await res.text();
    throw new Error(err || res.statusText);
  }
  return res.json();
}

function fmtTime(iso) {
  if (!iso) return "";
  return new Date(iso).toLocaleString();
}

function priorityClass(p) {
  return `priority-badge ${p || "low"}`;
}

function renderPosts() {
  const list = $("postList");
  list.innerHTML = "";
  posts.forEach((p) => {
    const li = document.createElement("li");
    li.className = `post-item${activePostId === p.post_id ? " active" : ""}`;
    li.innerHTML = `
      <div class="post-item-head">
        <label><input type="checkbox" data-id="${p.post_id}" ${selectedIds.has(p.post_id) ? "checked" : ""} /> Select</label>
        <span class="score-badge">${p.alignment_score ?? 0}</span>
      </div>
      <div class="post-item-title">${escapeHtml(p.title || "")}</div>
      <div class="post-item-meta">r/${escapeHtml(p.subreddit)} · u/${escapeHtml(p.author)} · ${fmtTime(p.created_utc)}</div>
      <div class="post-item-meta post-item-foot">
        <span class="${priorityClass(p.outreach_priority)}">${p.outreach_priority || "low"}</span>
        ${p.permalink ? `<span class="list-open-hint">Click to view · open on Reddit</span>` : ""}
      </div>
    `;
    li.querySelector("input").addEventListener("click", (e) => {
      e.stopPropagation();
      if (e.target.checked) selectedIds.add(p.post_id);
      else selectedIds.delete(p.post_id);
      updateSelectedCount();
    });
    li.addEventListener("click", () => selectPost(p.post_id));
    list.appendChild(li);
  });
  updateSelectedCount();
}

function escapeHtml(s) {
  return s.replace(/[&<>"']/g, (c) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
  }[c]));
}

function updateSelectedCount() {
  $("selectedCount").textContent = `${selectedIds.size} selected`;
}

async function loadPosts() {
  const sort = $("sortBy").value;
  const priority = $("filterPriority").value;
  posts = await api(`/api/posts?sort=${sort}&priority=${priority}`);
  renderPosts();
  if (activePostId) await selectPost(activePostId, false);
}

async function selectPost(postId, reloadList = true) {
  activePostId = postId;
  if (reloadList) renderPosts();
  const p = await api(`/api/posts/${postId}?live=true`);
  activePermalink = p.permalink || "";

  $("emptyState").classList.add("hidden");
  $("postDetail").classList.remove("hidden");
  $("detailSubreddit").textContent = `r/${p.subreddit}`;
  $("detailScore").textContent = `Score ${p.alignment_score ?? 0}`;
  $("detailPriority").textContent = p.outreach_priority || "low";
  $("detailPriority").className = priorityClass(p.outreach_priority);
  $("detailTitle").textContent = p.title || "";
  $("detailAuthor").textContent = (p.author || "").replace(/^\/?u\//, "");
  $("detailTime").textContent = fmtTime(p.created_utc);
  renderPostBody(p.body_html, p.selftext_plain || p.selftext);
  $("replyText").value = p.display_reply || "";
  $("detailRationale").textContent = p.rationale || "";
  $("detailPermalink").textContent = activePermalink;
  $("copyStatus").textContent = "";

  $("openRedditBtn").href = activePermalink || "#";
  $("openRedditBtn").style.display = activePermalink ? "inline-flex" : "none";
}

function renderPostBody(bodyHtml, fallbackText) {
  const el = $("detailBody");
  if (bodyHtml) {
    el.innerHTML = bodyHtml;
    return;
  }
  el.textContent = fallbackText || "(No body)";
}

function openActivePostOnReddit() {
  if (!activePermalink) {
    alert("No Reddit link for this post.");
    return;
  }
  window.open(activePermalink, "_blank", "noopener,noreferrer");
}

async function copyReplyToClipboard() {
  const text = $("replyText").value.trim();
  if (!text) {
    $("copyStatus").textContent = "Nothing to copy — add or generate a reply first.";
    return;
  }
  try {
    await navigator.clipboard.writeText(text);
    $("copyStatus").textContent = "Copied! Open the post on Reddit and paste your comment.";
  } catch (_) {
    $("replyText").focus();
    $("replyText").select();
    $("copyStatus").textContent = "Select the text above and copy manually (Cmd+C).";
  }
}

async function loadSettings() {
  const s = await api("/api/settings");
  subreddits = s.subreddits || [];
  $("gradingPrompt").value = s.grading_prompt || "";
  $("commentPrompt").value = s.comment_prompt || "";
  $("autoScrape").checked = String(s.auto_scrape).toLowerCase() === "true";
  $("scrapeInterval").value = s.scrape_interval_minutes || 5;
  renderSubreddits();
}

function renderSubreddits() {
  const ul = $("subredditList");
  ul.innerHTML = "";
  subreddits.forEach((sub, idx) => {
    const li = document.createElement("li");
    li.innerHTML = `<span>r/${escapeHtml(sub)}</span><button class="btn btn-ghost" data-idx="${idx}">Remove</button>`;
    li.querySelector("button").addEventListener("click", () => {
      subreddits.splice(idx, 1);
      renderSubreddits();
    });
    ul.appendChild(li);
  });
}

async function pollStatus() {
  try {
    const s = await api("/api/status");
    $("jobStatus").textContent = s.job?.message || "Idle";
  } catch (_) {}
}

function bindEvents() {
  $("sortBy").addEventListener("change", loadPosts);
  $("filterPriority").addEventListener("change", loadPosts);

  $("selectAll").addEventListener("change", (e) => {
    if (e.target.checked) posts.forEach((p) => selectedIds.add(p.post_id));
    else selectedIds.clear();
    renderPosts();
  });

  $("themeToggle").addEventListener("click", () => {
    const html = document.documentElement;
    const next = html.getAttribute("data-theme") === "dark" ? "light" : "dark";
    html.setAttribute("data-theme", next);
    localStorage.setItem("theme", next);
    $("themeToggle").textContent = next === "dark" ? "Light mode" : "Dark mode";
  });

  $("runScraperBtn").addEventListener("click", async () => {
    await api("/api/run/scraper", { method: "POST", body: "{}" });
    setTimeout(loadPosts, 1500);
  });

  $("runGraderAllBtn").addEventListener("click", async () => {
    await api("/api/run/grader", { method: "POST", body: "{}" });
    setTimeout(loadPosts, 2000);
  });

  $("runGraderSelectedBtn").addEventListener("click", async () => {
    const ids = [...selectedIds];
    if (!ids.length) return alert("Select at least one post.");
    await api("/api/run/grader", { method: "POST", body: JSON.stringify({ post_ids: ids }) });
    setTimeout(loadPosts, 2000);
  });

  $("saveReplyBtn").addEventListener("click", async () => {
    if (!activePostId) return;
    await api(`/api/posts/${activePostId}/reply`, {
      method: "PATCH",
      body: JSON.stringify({ edited_reply: $("replyText").value }),
    });
    $("copyStatus").textContent = "Draft saved.";
  });

  $("copyReplyBtn").addEventListener("click", copyReplyToClipboard);
  $("openRedditBtn2").addEventListener("click", openActivePostOnReddit);

  $("regenerateBtn").addEventListener("click", async () => {
    if (!activePostId) return;
    const r = await api(`/api/posts/${activePostId}/regenerate-comment`, { method: "POST" });
    $("replyText").value = r.reply || "";
    $("copyStatus").textContent = "";
  });

  $("addSubBtn").addEventListener("click", () => {
    const val = $("newSubreddit").value.trim().replace(/^r\//, "");
    if (val && !subreddits.includes(val)) subreddits.push(val);
    $("newSubreddit").value = "";
    renderSubreddits();
  });

  $("saveSubsBtn").addEventListener("click", async () => {
    await api("/api/subreddits", { method: "PUT", body: JSON.stringify({ subreddits }) });
    alert("Subreddits saved.");
  });

  $("saveGradingPromptBtn").addEventListener("click", async () => {
    await api("/api/settings", {
      method: "PUT",
      body: JSON.stringify({ grading_prompt: $("gradingPrompt").value }),
    });
    alert("Grading prompt saved for next run.");
  });

  $("saveCommentPromptBtn").addEventListener("click", async () => {
    await api("/api/settings", {
      method: "PUT",
      body: JSON.stringify({ comment_prompt: $("commentPrompt").value }),
    });
    alert("Comment prompt saved.");
  });

  $("autoScrape").addEventListener("change", async (e) => {
    await api("/api/settings", {
      method: "PUT",
      body: JSON.stringify({
        auto_scrape: e.target.checked,
        scrape_interval_minutes: Number($("scrapeInterval").value || 5),
      }),
    });
  });

  $("scrapeInterval").addEventListener("change", async () => {
    await api("/api/settings", {
      method: "PUT",
      body: JSON.stringify({
        auto_scrape: $("autoScrape").checked,
        scrape_interval_minutes: Number($("scrapeInterval").value || 5),
      }),
    });
  });
}

async function init() {
  const savedTheme = localStorage.getItem("theme") || "light";
  document.documentElement.setAttribute("data-theme", savedTheme);
  $("themeToggle").textContent = savedTheme === "dark" ? "Light mode" : "Dark mode";
  bindEvents();
  await loadSettings();
  await loadPosts();
  setInterval(pollStatus, 3000);
  setInterval(loadPosts, 15000);
}

init();
