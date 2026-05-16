// Live alerts WebSocket client

const statusEl = document.getElementById("ws-status");
const feed = document.getElementById("alert-feed");

const wsProto = location.protocol === "https:" ? "wss" : "ws";
const ws = new WebSocket(`${wsProto}://${location.host}/ws/alerts`);

ws.addEventListener("open", () => {
  statusEl.textContent = "Connected. Waiting for events…";
});
ws.addEventListener("close", () => {
  statusEl.textContent = "Disconnected. Reload to reconnect.";
});
ws.addEventListener("error", () => {
  statusEl.textContent = "Connection error.";
});

ws.addEventListener("message", (ev) => {
  let data;
  try { data = JSON.parse(ev.data); } catch { return; }

  if (data.type === "event") {
    const li = document.createElement("li");
    li.className = data.severity;
    li.innerHTML = `
      ${data.frame_url ? `<img src="${data.frame_url}" alt="" />` : ""}
      <div>
        <strong>${escape(data.kind)}</strong> — ${escape(data.description)}<br />
        <small><a href="/videos/${data.video_id}">${escape(data.video_filename)}</a> @ ${data.timestamp_seconds.toFixed(1)}s · score ${data.score.toFixed(2)}</small>
      </div>`;
    feed.prepend(li);
  } else if (data.type === "video_completed") {
    const li = document.createElement("li");
    li.innerHTML = `<div><strong>Completed</strong> — <a href="/videos/${data.video_id}">${escape(data.video_filename)}</a> (${escape(data.status)})</div>`;
    feed.prepend(li);
  }
});

function escape(s) {
  return String(s)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;");
}
