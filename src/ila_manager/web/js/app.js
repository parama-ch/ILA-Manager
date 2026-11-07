/**
 * Application Entrypoint
 */

import { currentLang, setLanguage } from "./i18n.js";
import { state } from "./state.js";
import { parseHdlFiles, loadProject, saveProject, importHdlInstance, importTcl } from "./api.js";
import { initSignalsPanel, updateUnitSelector, renderSignals } from "./signals.js";
import { initProbesPanel, renderProbes } from "./probes.js";
import { initOptionsPanel, syncOptionsFromState } from "./options.js";
import { initOutputPanel, refreshGeneratedCode, showToast } from "./output.js";
import { initDiffModal, runDiffCheck } from "./diff.js";

document.addEventListener("DOMContentLoaded", async () => {
  // 1. Initialize language (default to browser language or 'en')
  const browserLang = navigator.language.startsWith("th") ? "th" : "en";
  await setLanguage(browserLang);

  // 2. Initialize panels
  initSignalsPanel();
  initProbesPanel();
  initOptionsPanel();
  initOutputPanel();
  initDiffModal();

  // 3. State change subscriber
  state.subscribe(() => {
    renderProbes();
    syncOptionsFromState();
    refreshGeneratedCode();
  });

  // Initial render
  renderProbes();
  syncOptionsFromState();
  refreshGeneratedCode();

  // 4. Header buttons
  // Language toggle
  document.getElementById("btn-lang-toggle").addEventListener("click", async () => {
    const nextLang = currentLang === "en" ? "th" : "en";
    await setLanguage(nextLang);
  });

  // Theme toggle
  document.getElementById("btn-theme-toggle").addEventListener("click", () => {
    const body = document.body;
    const isLight = body.getAttribute("data-theme") === "light";
    body.setAttribute("data-theme", isLight ? "dark" : "light");
  });

  // Save Project
  document.getElementById("btn-save-proj").addEventListener("click", async () => {
    const filePath = prompt("Enter path to save project file (.ilaproj):", "my_ila_project.ilaproj");
    if (!filePath) return;
    try {
      await saveProject(filePath, state.project, state.signalsByUnit);
      showToast(`Saved project: ${filePath}`);
    } catch (e) {
      alert(`Save failed: ${e.message}`);
    }
  });

  // Open Project
  document.getElementById("btn-open-proj").addEventListener("click", async () => {
    const filePath = prompt("Enter path of project file to open:", "my_ila_project.ilaproj");
    if (!filePath) return;
    try {
      const res = await loadProject(filePath);
      state.project = res.project;
      state.currentIlaIndex = 0;

      // Re-parse project sources if available
      if (state.project.source_files && state.project.source_files.length > 0) {
        const parsedRes = await parseHdlFiles({ paths: state.project.source_files });
        state.signalsByUnit = parsedRes.units || {};
        updateUnitSelector();
      }

      state.notify();
      showToast("Project loaded successfully!");

      // Check diff
      await runDiffCheck();
    } catch (e) {
      alert(`Load failed: ${e.message}`);
    }
  });

  // Import Existing ILA
  document.getElementById("btn-import-existing").addEventListener("click", async () => {
    const text = prompt("Paste HDL instantiation or Vivado TCL script to import:");
    if (!text) return;

    if (text.includes("create_ip") || text.includes("set_property") || text.includes("CONFIG.")) {
      try {
        const ila = await importTcl(text);
        state.project.ilas[state.currentIlaIndex] = ila;
        state.notify();
        showToast("Imported ILA from TCL script!");
      } catch (e) {
        alert(`TCL Import failed: ${e.message}`);
      }
    } else {
      const isVhdl = text.includes("entity") || text.includes("port map") || text.includes("<=");
      try {
        const ilas = await importHdlInstance(text, isVhdl);
        if (ilas && ilas.length > 0) {
          state.project.ilas[state.currentIlaIndex] = ilas[0];
          state.notify();
          showToast(`Imported ILA instance '${ilas[0].name}'!`);
        } else {
          alert("No ILA instance found in the provided HDL snippet.");
        }
      } catch (e) {
        alert(`HDL Import failed: ${e.message}`);
      }
    }
  });

  // 5. Drag & Drop File Loader
  setupFileDrop();
});

function setupFileDrop() {
  const dropZone = document.getElementById("hdl-drop-zone");
  const fileInput = document.getElementById("hdl-file-input");

  dropZone.addEventListener("click", () => {
    fileInput.click();
  });

  fileInput.addEventListener("change", (e) => {
    handleLoadedFiles(e.target.files);
  });

  dropZone.addEventListener("dragover", (e) => {
    e.preventDefault();
    dropZone.classList.add("dragover");
  });

  dropZone.addEventListener("dragleave", () => {
    dropZone.classList.remove("dragover");
  });

  dropZone.addEventListener("drop", (e) => {
    e.preventDefault();
    dropZone.classList.remove("dragover");
    if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
      handleLoadedFiles(e.dataTransfer.files);
    }
  });
}

async function handleLoadedFiles(fileList) {
  const fileObjects = [];
  for (const file of fileList) {
    const content = await file.text();
    fileObjects.push({ filename: file.name, content: content });
  }

  try {
    const res = await parseHdlFiles({ files: fileObjects });
    state.signalsByUnit = Object.assign(state.signalsByUnit, res.units || {});
    updateUnitSelector();
    showToast(`Parsed ${fileObjects.length} HDL file(s)!`);
    await runDiffCheck();
  } catch (e) {
    alert(`Failed to parse HDL files: ${e.message}`);
  }
}
