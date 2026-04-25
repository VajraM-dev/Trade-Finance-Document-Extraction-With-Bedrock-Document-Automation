import { apiUpload } from "/js/api.js";
import { showToast } from "/js/toast.js";

export function initUpload(rootEl, { onUploaded, maxBatch = 10 } = {}) {
  rootEl.innerHTML = `
    <div id="dropzone"
         class="border-2 border-dashed border-slate-300 rounded-lg p-8 text-center text-slate-500 hover:bg-slate-50 cursor-pointer">
      Drag &amp; drop up to ${maxBatch} files (PDF / PNG / JPG / TIFF) or click to choose
    </div>
    <input type="file" id="fileInput" hidden multiple
           accept="application/pdf,image/png,image/jpeg,image/tiff" />
    <div id="progress" class="text-sm text-slate-600 mt-3"></div>
  `;
  const drop = rootEl.querySelector("#dropzone");
  const input = rootEl.querySelector("#fileInput");
  const progress = rootEl.querySelector("#progress");

  drop.addEventListener("click", () => input.click());
  drop.addEventListener("dragover", (e) => { e.preventDefault(); drop.classList.add("bg-slate-100"); });
  drop.addEventListener("dragleave", () => drop.classList.remove("bg-slate-100"));
  drop.addEventListener("drop", (e) => {
    e.preventDefault();
    drop.classList.remove("bg-slate-100");
    handle([...e.dataTransfer.files]);
  });
  input.addEventListener("change", () => handle([...input.files]));

  async function handle(files) {
    if (files.length === 0) return;
    if (files.length > maxBatch) {
      showToast(`Too many files (max ${maxBatch})`, "error");
      return;
    }
    progress.textContent = `Uploading ${files.length} file(s)…`;
    try {
      const result = await apiUpload("/api/v1/jobs", files);
      progress.textContent = `Queued ${result.jobs.length} job(s).`;
      showToast(`Uploaded ${result.jobs.length} file(s)`, "success");
      onUploaded?.(result.jobs);
    } catch (err) {
      progress.textContent = "";
    }
  }
}
