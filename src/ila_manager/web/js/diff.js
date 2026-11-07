/**
 * Diff Review Dialog controller
 */

import { state } from "./state.js";
import { checkDiff } from "./api.js";

let currentDiffItems = [];

export async function runDiffCheck() {
  const ila = state.getCurrentIla();
  const signals = state.getCurrentSignals();
  if (!ila || signals.length === 0) return;

  try {
    const diffs = await checkDiff(ila, signals);
    if (diffs && diffs.length > 0) {
      currentDiffItems = diffs;
      openDiffModal(diffs);
    }
  } catch (e) {
    console.error("Diff check error:", e);
  }
}

export function openDiffModal(diffItems) {
  const modal = document.getElementById("modal-diff");
  const container = document.getElementById("diff-items-container");
  container.innerHTML = "";

  diffItems.forEach((item, idx) => {
    const row = document.createElement("div");
    row.style.background = "var(--bg-card)";
    row.style.border = "1px solid var(--border-color)";
    row.style.borderRadius = "var(--radius-sm)";
    row.style.padding = "10px 14px";
    row.style.display = "flex";
    row.style.flexDirection = "column";
    row.style.gap = "8px";

    const title = document.createElement("div");
    title.style.fontWeight = "600";
    title.style.fontSize = "13px";
    title.style.color = "var(--warning)";
    title.textContent = `[${item.probe_name}] ${item.message}`;
    row.appendChild(title);

    const actionsGroup = document.createElement("div");
    actionsGroup.style.display = "flex";
    actionsGroup.style.gap = "14px";
    actionsGroup.style.fontSize = "12px";

    // Radio options for resolution
    const groupName = `diff_action_${idx}`;

    if (item.allowed_actions.includes("follow_new_width")) {
      actionsGroup.appendChild(
        createRadio(groupName, "follow_new_width", `Update width to ${item.new_width}b`, true)
      );
    }

    if (item.allowed_actions.includes("remap") && item.suggested_signal) {
      actionsGroup.appendChild(
        createRadio(groupName, "remap", `Remap to '${item.suggested_signal}'`, true)
      );
    }

    if (item.allowed_actions.includes("delete")) {
      actionsGroup.appendChild(
        createRadio(groupName, "delete", "Delete probe", false)
      );
    }

    if (item.allowed_actions.includes("keep_old_width") || item.allowed_actions.includes("keep_unmapped")) {
      actionsGroup.appendChild(
        createRadio(groupName, "keep", "Keep probe as unmapped / old", false)
      );
    }

    row.appendChild(actionsGroup);
    container.appendChild(row);
  });

  modal.classList.remove("hidden");
}

function createRadio(name, value, labelText, checked) {
  const label = document.createElement("label");
  label.className = "checkbox-group";
  const radio = document.createElement("input");
  radio.type = "radio";
  radio.name = name;
  radio.value = value;
  radio.checked = checked;
  label.appendChild(radio);
  label.appendChild(document.createTextNode(labelText));
  return label;
}

export function initDiffModal() {
  document.getElementById("btn-apply-diff").addEventListener("click", () => {
    applyDiffResolutions();
  });
}

function applyDiffResolutions() {
  const ila = state.getCurrentIla();
  const toDelete = [];

  currentDiffItems.forEach((item, idx) => {
    const selected = document.querySelector(`input[name="diff_action_${idx}"]:checked`);
    if (!selected) return;

    const action = selected.value;
    const probe = ila.probes[item.probe_index];
    if (!probe) return;

    if (action === "follow_new_width") {
      probe.width = item.new_width;
    } else if (action === "remap" && item.suggested_signal) {
      probe.mapping = { signal: item.suggested_signal, path: [] };
      const newSig = state.getCurrentSignals().find((s) => s.name === item.suggested_signal);
      if (newSig) probe.width = newSig.width || 1;
    } else if (action === "delete") {
      toDelete.push(item.probe_index);
    }
  });

  // Delete in reverse order
  toDelete.sort((a, b) => b - a).forEach((idx) => {
    state.removeProbe(idx);
  });

  state.renumberProbes();
  document.getElementById("modal-diff").classList.add("hidden");
  state.notify();
}
