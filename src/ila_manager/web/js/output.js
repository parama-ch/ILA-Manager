/**
 * Live Output Code Generator & Viewer
 */

import { state } from "./state.js";
import { generateCode } from "./api.js";

let generatedOutput = {
  tcl: "",
  vhdl: "",
  verilog: "",
};

export function initOutputPanel() {
  const tabBtns = document.querySelectorAll(".tab-btn");
  tabBtns.forEach((btn) => {
    btn.addEventListener("click", () => {
      tabBtns.forEach((b) => b.classList.remove("active"));
      btn.classList.add("active");
      state.activeTab = btn.dataset.tab;
      renderActiveTabCode();
    });
  });

  document.getElementById("btn-copy-code").addEventListener("click", () => {
    const code = getActiveCode();
    if (code) {
      navigator.clipboard.writeText(code).then(() => {
        showToast("Copied to clipboard!");
      });
    }
  });

  document.getElementById("btn-download-code").addEventListener("click", () => {
    downloadActiveCode();
  });
}

export async function refreshGeneratedCode() {
  const ila = state.getCurrentIla();
  if (!ila) return;

  const signals = state.getCurrentSignals();
  try {
    const res = await generateCode(ila, signals);
    generatedOutput = res;
    renderActiveTabCode();
  } catch (e) {
    console.error("Failed to generate code:", e);
  }
}

function getActiveCode() {
  if (state.activeTab === "tcl") return generatedOutput.tcl;
  if (state.activeTab === "vhdl") return generatedOutput.vhdl;
  if (state.activeTab === "verilog") return generatedOutput.verilog;
  return "";
}

function renderActiveTabCode() {
  const codeEl = document.getElementById("code-output");
  codeEl.textContent = getActiveCode() || "# No code generated yet.";
}

function downloadActiveCode() {
  const code = getActiveCode();
  if (!code) return;

  const ila = state.getCurrentIla();
  const baseName = ila ? ila.name : "ila_0";

  let ext = "tcl";
  if (state.activeTab === "vhdl") ext = "vhd";
  if (state.activeTab === "verilog") ext = "v";

  const filename = `${baseName}.${ext}`;
  const blob = new Blob([code], { type: "text/plain;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
}

export function showToast(message, duration = 2500) {
  const toast = document.getElementById("toast-msg");
  toast.textContent = message;
  toast.classList.remove("hidden");
  setTimeout(() => {
    toast.classList.add("hidden");
  }, duration);
}
