/**
 * ILA Port Manager panel: probe table, reordering, swapping, bit-slicing
 */

import { state } from "./state.js";
import { t } from "./i18n.js";

let activeSliceTarget = null; // { signal, probeIndex }
let draggedProbeIndex = null;

export function initProbesPanel() {
  document.getElementById("btn-add-probe").addEventListener("click", () => {
    state.addProbe(null, 1);
  });

  document.getElementById("btn-clear-probes").addEventListener("click", () => {
    if (confirm("Clear all probes from this ILA?")) {
      state.clearProbes();
    }
  });

  // Swap modal button
  document.getElementById("btn-swap-probes").addEventListener("click", () => {
    openSwapModal();
  });

  document.getElementById("btn-confirm-swap").addEventListener("click", () => {
    const selA = document.getElementById("swap-select-a");
    const selB = document.getElementById("swap-select-b");
    const idxA = parseInt(selA.value, 10);
    const idxB = parseInt(selB.value, 10);
    if (!isNaN(idxA) && !isNaN(idxB) && idxA !== idxB) {
      state.swapProbes(idxA, idxB);
      closeModals();
    }
  });

  // Bit-slice modal apply
  document.getElementById("btn-confirm-slice").addEventListener("click", () => {
    applySliceModal();
  });

  // Close modals
  document.querySelectorAll(".close-modal").forEach((btn) => {
    btn.addEventListener("click", closeModals);
  });

  // Setup table drag over container
  const tableContainer = document.querySelector(".probe-table-container");
  tableContainer.addEventListener("dragover", (e) => {
    e.preventDefault();
  });
  tableContainer.addEventListener("drop", (e) => {
    // If dropped directly on empty space of container (not on a row)
    if (e.target === tableContainer || e.target.tagName === "TBODY") {
      const dataStr = e.dataTransfer.getData("application/json");
      if (dataStr) {
        const item = JSON.parse(dataStr);
        state.addProbe({ signal: item.signal, path: [] }, item.width || 1);
      }
    }
  });
}

export function renderProbes() {
  const tbody = document.getElementById("probes-table-body");
  tbody.innerHTML = "";

  const ila = state.getCurrentIla();
  if (!ila || ila.probes.length === 0) {
    tbody.innerHTML = `<tr><td colspan="6" style="text-align: center; color: var(--text-muted); padding: 30px;">
      No probes configured. Drag signals here or click <b>+ Add Probe</b>.
    </td></tr>`;
    return;
  }

  ila.probes.forEach((probe, idx) => {
    const tr = document.createElement("tr");
    tr.className = `probe-row ${!probe.mapping ? "unmapped" : ""}`;
    tr.draggable = true;

    // Probe Row Drag & Drop (reorder or swap)
    tr.addEventListener("dragstart", (e) => {
      draggedProbeIndex = idx;
      e.dataTransfer.setData("text/plain", idx.toString());
      e.dataTransfer.effectAllowed = "move";
    });

    tr.addEventListener("dragover", (e) => {
      e.preventDefault();
      tr.classList.add("drag-over");
    });

    tr.addEventListener("dragleave", () => {
      tr.classList.remove("drag-over");
    });

    tr.addEventListener("drop", (e) => {
      e.preventDefault();
      tr.classList.remove("drag-over");

      // Check if drop comes from signal list
      const sigData = e.dataTransfer.getData("application/json");
      if (sigData) {
        const item = JSON.parse(sigData);
        if (probe.mapping && probe.mapping.signal) {
          if (!confirm(`Replace probe${idx} mapping (${probe.mapping.signal}) with ${item.signal}?`)) {
            return;
          }
        }
        state.setProbeMapping(idx, { signal: item.signal, path: [] }, item.width || 1);
        return;
      }

      // Drop from another probe row (reorder or swap)
      if (draggedProbeIndex !== null && draggedProbeIndex !== idx) {
        if (e.altKey) {
          // Alt+Drop = SWAP
          state.swapProbes(draggedProbeIndex, idx);
        } else {
          // Normal Drop = REORDER
          state.moveProbe(draggedProbeIndex, idx);
        }
        draggedProbeIndex = null;
      }
    });

    // 1. Index cell with drag handle
    const tdIdx = document.createElement("td");
    tdIdx.className = "probe-idx";
    tdIdx.innerHTML = `<span class="drag-handle" title="Drag to reorder (Hold Alt to swap)">⋮⋮</span> probe${idx}`;
    tr.appendChild(tdIdx);

    // 2. Mapping cell
    const tdMap = document.createElement("td");
    if (probe.mapping) {
      const mapSpan = document.createElement("span");
      mapSpan.className = "probe-mapping-expr";
      mapSpan.textContent = formatMappingString(probe.mapping);
      mapSpan.title = "Click to edit bit range / slice";
      mapSpan.addEventListener("click", () => {
        const sig = state.getCurrentSignals().find((s) => s.name === probe.mapping.signal);
        openSliceModal(sig || { name: probe.mapping.signal, width: probe.width, type: null }, idx);
      });
      tdMap.appendChild(mapSpan);
    } else {
      tdMap.innerHTML = `<span style="color: var(--text-muted); font-style: italic;">&lt;unmapped&gt;</span>`;
    }
    tr.appendChild(tdMap);

    // 3. Width cell
    const tdWidth = document.createElement("td");
    const widthInput = document.createElement("input");
    widthInput.type = "number";
    widthInput.min = "1";
    widthInput.max = "4096";
    widthInput.value = probe.width || 1;
    widthInput.style.width = "55px";
    widthInput.addEventListener("change", (e) => {
      const val = parseInt(e.target.value, 10);
      if (!isNaN(val) && val >= 1) {
        probe.width = val;
        state.notify();
      }
    });
    tdWidth.appendChild(widthInput);
    tr.appendChild(tdWidth);

    // 4. Type cell
    const tdType = document.createElement("td");
    const typeSelect = document.createElement("select");
    typeSelect.style.width = "100%";
    typeSelect.innerHTML = `
      <option value="DATA_AND_TRIGGER" ${probe.probe_type === "DATA_AND_TRIGGER" ? "selected" : ""}>Data & Trigger</option>
      <option value="DATA" ${probe.probe_type === "DATA" ? "selected" : ""}>Data Only</option>
      <option value="TRIGGER" ${probe.probe_type === "TRIGGER" ? "selected" : ""}>Trigger Only</option>
    `;
    typeSelect.addEventListener("change", (e) => {
      probe.probe_type = e.target.value;
      state.notify();
    });
    tdType.appendChild(typeSelect);
    tr.appendChild(tdType);

    // 5. MU count cell
    const tdMu = document.createElement("td");
    const muInput = document.createElement("input");
    muInput.type = "number";
    muInput.min = "1";
    muInput.max = "16";
    muInput.value = probe.mu_cnt || 1;
    muInput.style.width = "45px";
    muInput.disabled = ila.same_mu; // Disabled if same_mu is active
    muInput.addEventListener("change", (e) => {
      const val = parseInt(e.target.value, 10);
      if (!isNaN(val) && val >= 1) {
        probe.mu_cnt = val;
        state.notify();
      }
    });
    tdMu.appendChild(muInput);
    tr.appendChild(tdMu);

    // 6. Action buttons cell
    const tdActions = document.createElement("td");
    tdActions.className = "probe-actions";

    // Move Up
    const upBtn = document.createElement("button");
    upBtn.className = "icon-btn";
    upBtn.innerHTML = "↑";
    upBtn.title = "Move Up";
    upBtn.disabled = idx === 0;
    upBtn.addEventListener("click", () => state.moveProbe(idx, idx - 1));
    tdActions.appendChild(upBtn);

    // Move Down
    const downBtn = document.createElement("button");
    downBtn.className = "icon-btn";
    downBtn.innerHTML = "↓";
    downBtn.title = "Move Down";
    downBtn.disabled = idx === ila.probes.length - 1;
    downBtn.addEventListener("click", () => state.moveProbe(idx, idx + 1));
    tdActions.appendChild(downBtn);

    // Swap with next
    const swapBtn = document.createElement("button");
    swapBtn.className = "icon-btn";
    swapBtn.innerHTML = "⇄";
    swapBtn.title = "Swap with another probe";
    swapBtn.addEventListener("click", () => openSwapModal(idx));
    tdActions.appendChild(swapBtn);

    // Delete
    const delBtn = document.createElement("button");
    delBtn.className = "icon-btn";
    delBtn.innerHTML = "🗑";
    delBtn.title = "Delete probe";
    delBtn.addEventListener("click", () => state.removeProbe(idx));
    tdActions.appendChild(delBtn);

    tr.appendChild(tdActions);
    tbody.appendChild(tr);
  });
}

function formatMappingString(mapping) {
  if (!mapping) return "<unmapped>";
  let str = mapping.signal;
  for (const step of mapping.path || []) {
    if (step.step === "index") str += `(${step.index})`;
    if (step.step === "field") str += `.${step.field}`;
    if (step.step === "range") {
      const dir = step.ascending ? "to" : "downto";
      str += `(${step.left} ${dir} ${step.right})`;
    }
    if (step.step === "bit") str += `(${step.bit})`;
  }
  return str;
}

export function openSwapModal(preselectA = 0) {
  const modal = document.getElementById("modal-swap");
  const selA = document.getElementById("swap-select-a");
  const selB = document.getElementById("swap-select-b");
  selA.innerHTML = "";
  selB.innerHTML = "";

  const ila = state.getCurrentIla();
  ila.probes.forEach((p, i) => {
    const text = `probe${i}: ${p.mapping ? p.mapping.signal : "<unmapped>"}`;
    const optA = document.createElement("option");
    optA.value = i;
    optA.textContent = text;
    if (i === preselectA) optA.selected = true;
    selA.appendChild(optA);

    const optB = document.createElement("option");
    optB.value = i;
    optB.textContent = text;
    if (i === (preselectA + 1) % ila.probes.length) optB.selected = true;
    selB.appendChild(optB);
  });

  modal.classList.remove("hidden");
}

export function openSliceModal(signal, probeIndex = null) {
  activeSliceTarget = { signal, probeIndex };
  const modal = document.getElementById("modal-slice");
  const info = document.getElementById("slice-signal-info");
  const grpArr = document.getElementById("group-array-idx");
  const grpRec = document.getElementById("group-record-field");
  const grpRange = document.getElementById("group-bit-range");

  info.textContent = `${signal.name} (${signal.type ? signal.type.kind : "signal"})`;

  // Array index field
  const isArr = signal.type && signal.type.kind === "array";
  grpArr.style.display = isArr ? "flex" : "none";

  // Record fields
  const isRec = signal.type && signal.type.kind === "record";
  grpRec.style.display = isRec ? "flex" : "none";
  const selField = document.getElementById("slice-select-field");
  selField.innerHTML = "";
  if (isRec && signal.type.fields) {
    Object.keys(signal.type.fields).forEach((fn) => {
      const opt = document.createElement("option");
      opt.value = fn;
      opt.textContent = `${fn} (${signal.type.fields[fn].kind})`;
      selField.appendChild(opt);
    });
  }

  // Bit range
  const isVec = signal.type && (signal.type.kind === "vector" || signal.type.kind === "array");
  grpRange.style.display = isVec ? "flex" : "none";

  modal.classList.remove("hidden");
}

function applySliceModal() {
  if (!activeSliceTarget || !activeSliceTarget.signal) return;
  const sig = activeSliceTarget.signal;
  const path = [];
  let computedW = sig.width || 1;

  // Array index
  const idxInput = document.getElementById("slice-input-idx");
  if (idxInput.offsetParent !== null && idxInput.value !== "") {
    path.push({ step: "index", index: parseInt(idxInput.value, 10) });
  }

  // Record field
  const selField = document.getElementById("slice-select-field");
  if (selField.offsetParent !== null && selField.value) {
    path.push({ step: "field", field: selField.value });
  }

  // Bit range (e.g. 15 downto 8 or 7:0)
  const rangeInput = document.getElementById("slice-input-range");
  if (rangeInput.offsetParent !== null && rangeInput.value.trim()) {
    const raw = rangeInput.value.trim();
    const mDownto = raw.match(/(\d+)\s+downto\s+(\d+)/i);
    const mTo = raw.match(/(\d+)\s+to\s+(\d+)/i);
    const mColon = raw.match(/\[?\s*(\d+)\s*:\s*(\d+)\s*\]?/);

    if (mDownto) {
      const l = parseInt(mDownto.group(1), 10);
      const r = parseInt(mDownto.group(2), 10);
      path.push({ step: "range", left: l, right: r, ascending: false });
      computedW = Math.abs(l - r) + 1;
    } else if (mTo) {
      const l = parseInt(mTo.group(1), 10);
      const r = parseInt(mTo.group(2), 10);
      path.push({ step: "range", left: l, right: r, ascending: true });
      computedW = Math.abs(l - r) + 1;
    } else if (mColon) {
      const l = parseInt(mColon[1], 10);
      const r = parseInt(mColon[2], 10);
      path.push({ step: "range", left: l, right: r, ascending: l < r });
      computedW = Math.abs(l - r) + 1;
    } else if (/^\d+$/.test(raw)) {
      const bitVal = parseInt(raw, 10);
      path.push({ step: "bit", bit: bitVal });
      computedW = 1;
    }
  }

  const mapping = { signal: sig.name, path: path };

  if (activeSliceTarget.probeIndex !== null) {
    state.setProbeMapping(activeSliceTarget.probeIndex, mapping, computedW);
  } else {
    state.addProbe(mapping, computedW);
  }

  closeModals();
}

export function closeModals() {
  document.querySelectorAll(".modal-overlay").forEach((m) => {
    m.classList.add("hidden");
  });
  activeSliceTarget = null;
}
