// Dashboard: upload + delete

const form = document.getElementById("upload-form");
const status = document.getElementById("upload-status");

form?.addEventListener("submit", async (ev) => {
  ev.preventDefault();
  const file = document.getElementById("file").files[0];
  if (!file) return;
  status.textContent = `Uploading ${file.name}…`;
  const fd = new FormData();
  fd.append("file", file);
  try {
    const res = await fetch("/api/videos", { method: "POST", body: fd });
    if (!res.ok) {
      const text = await res.text();
      status.textContent = `Upload failed: ${text}`;
      return;
    }
    const video = await res.json();
    status.textContent = `Uploaded as video #${video.id}. Pipeline running… refreshing…`;
    setTimeout(() => location.reload(), 1200);
  } catch (err) {
    status.textContent = `Upload failed: ${err}`;
  }
});

document.querySelectorAll("[data-delete]").forEach((btn) => {
  btn.addEventListener("click", async () => {
    const id = btn.getAttribute("data-delete");
    if (!confirm(`Delete video #${id}?`)) return;
    const res = await fetch(`/api/videos/${id}`, { method: "DELETE" });
    if (res.ok) location.reload();
  });
});
