/**
 * Signal Explorer panel: search, filter, drill-down tree, and drag source
 */

import { state } from "./state.js";
import { openSliceModal } from "./probes.js";

let currentFilter = "all";
let searchQuery = "";

export function initSignalsPanel() {
  const searchInput = document.getElementById("signal-search");
  searchInput.addEventListener("input", (e) => {
    searchQuery = e.target.value.toLowerCase();
    renderSignals();
  });

  const filterBtns = document.querySelectorAll(".filter-btn");
  filterBtns.forEach((btn) => {
    btn.addEventListener("click", () => {
      filterBtns.forEach((b) => b.classList.remove("active"));
      btn.classList.add("active");
      currentFilter = btn.dataset.filter;
      renderSignals();
    });
  });

  const unitSelect = document.getElementById("select-target-unit");
  unitSelect.addEventListener("change", (e) => {
    state.currentUnit = e.target.value;
    const ila = state.getCurrentIla();
    if (ila) ila.target_unit = state.currentUnit;
    renderSignals();
    state.notify();
  });
}

export function updateUnitSelector() {
  const unitSelect = document.getElementById("select-target-unit");
  unitSelect.innerHTML = "";

  const units = Object.keys(state.signalsByUnit);
  if (units.length === 0) {
    unitSelect.innerHTML = '<option value="">-- No HDL loaded --</option>';
    state.currentUnit = "";
    renderSignals();
    return;
  }

  units.forEach((u) => {
    const opt = document.createElement("option");
    opt.value = u;
    opt.textContent = u;
    if (u === state.currentUnit || !state.currentUnit) {
      opt.selected = true;
      state.currentUnit = u;
    }
    unitSelect.appendChild(opt);
  });

  const ila = state.getCurrentIla();
  if (ila) ila.target_unit = state.currentUnit;
  renderSignals();
}

export function renderSignals() {
  const container = document.getElementById("signal-list-container");
  container.innerHTML = "";

  const signals = state.getCurrentSignals();
  const filtered = signals.filter((sig) => {
    // Filter by type
    if (currentFilter === "ports" && !sig.kind.startsWith("port")) return false;
    if (currentFilter === "signals" && sig.kind !== "signal") return false;

    // Filter by search query
    if (searchQuery) {
      return sig.name.toLowerCase().includes(searchQuery);
    }
    return true;
  });

  if (filtered.length === 0) {
    container.innerHTML = '<div style="font-size: 12px; color: var(--text-muted); text-align: center; padding: 20px;">No signals match filter</div>';
    return;
  }

  filtered.forEach((sig) => {
    const item = document.createElement("div");
    item.className = "signal-item";
    item.draggable = true;

    // Drag start
    item.addEventListener("dragstart", (e) => {
      e.dataTransfer.setData(
        "application/json",
        JSON.stringify({
          signal: sig.name,
          width: sig.width || 1,
          type: sig.type,
        })
      );
      e.dataTransfer.effectAllowed = "copy";
    });

    const info = document.createElement("div");
    info.className = "signal-info";

    // Kind badge
    const badge = document.createElement("span");
    badge.className = `badge badge-${sig.kind.replace("port_", "")}`;
    badge.textContent = sig.kind.replace("port_", "");
    info.appendChild(badge);

    // Name
    const nameEl = document.createElement("span");
    nameEl.className = "signal-name";
    nameEl.textContent = sig.name;
    nameEl.title = `${sig.name}: ${sig.summary || ""}`;
    info.appendChild(nameEl);

    // Width badge
    const wBadge = document.createElement("span");
    wBadge.className = "badge badge-width";
    wBadge.textContent = `${sig.width || 1}b`;
    info.appendChild(wBadge);

    // Actions
    const actions = document.createElement("div");
    actions.style.display = "flex";
    actions.style.gap = "4px";

    // Slice / Tree config button if vector/array/record
    const canSlice =
      sig.type &&
      (sig.type.kind === "vector" ||
        sig.type.kind === "array" ||
        sig.type.kind === "record");

    if (canSlice) {
      const sliceBtn = document.createElement("button");
      sliceBtn.className = "icon-btn";
      sliceBtn.innerHTML = "✂";
      sliceBtn.title = "Configure bit-slice or array index";
      sliceBtn.addEventListener("click", () => {
        openSliceModal(sig);
      });
      actions.appendChild(sliceBtn);
    }

    // Append button (+)
    const addBtn = document.createElement("button");
    addBtn.className = "icon-btn";
    addBtn.innerHTML = "+";
    addBtn.title = "Append to ILA";
    addBtn.addEventListener("click", () => {
      state.addProbe({ signal: sig.name, path: [] }, sig.width || 1);
    });
    actions.appendChild(addBtn);

    item.appendChild(info);
    item.appendChild(actions);
    container.appendChild(item);
  });
}
