// Per-video page: suspicious filter + regenerate

const suspOnly = document.getElementById("susp-only");
suspOnly?.addEventListener("change", () => {
  const threshold = 0.55;
  document.querySelectorAll(".frame").forEach((el) => {
    const s = parseFloat(el.dataset.suspicion || "0");
    el.style.display = !suspOnly.checked || s >= threshold ? "" : "none";
  });
});

document.querySelectorAll("[data-regenerate]").forEach((btn) => {
  btn.addEventListener("click", async () => {
    const id = btn.getAttribute("data-regenerate");
    btn.disabled = true;
    btn.textContent = "Regenerating…";
    const res = await fetch(`/api/videos/${id}/summary`, { method: "POST" });
    if (res.ok) location.reload();
    else {
      btn.textContent = "Failed — retry";
      btn.disabled = false;
    }
  });
});
