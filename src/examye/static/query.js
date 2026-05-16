// Investigation query

const form = document.getElementById("query-form");
const result = document.getElementById("query-result");

form?.addEventListener("submit", async (ev) => {
  ev.preventDefault();
  const question = document.getElementById("question").value.trim();
  const videoId = document.getElementById("video-id").value;
  if (!question) return;
  result.innerHTML = `<p class="muted">Searching…</p>`;
  const payload = { question, top_k: 6 };
  if (videoId) payload.video_id = parseInt(videoId, 10);

  try {
    const res = await fetch("/api/query", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    if (!res.ok) {
      result.innerHTML = `<p class="error">Query failed: ${await res.text()}</p>`;
      return;
    }
    const data = await res.json();
    const evHtml = (data.evidence || [])
      .map(
        (e) =>
          `<li>[E${e.event_id}] <a href="/videos/${e.video_id}">video #${e.video_id}</a> @ ${e.timestamp_seconds.toFixed(1)}s — ${escape(e.description)} <em>(score ${e.score.toFixed(2)})</em></li>`
      )
      .join("");
    result.innerHTML = `
      <h3>Answer <small class="muted">(source: ${data.source})</small></h3>
      <div class="answer">${escape(data.answer)}</div>
      ${evHtml ? `<div class="evidence"><h4>Evidence</h4><ul>${evHtml}</ul></div>` : ""}
    `;
  } catch (err) {
    result.innerHTML = `<p class="error">Query failed: ${err}</p>`;
  }
});

function escape(s) {
  return String(s)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;");
}
