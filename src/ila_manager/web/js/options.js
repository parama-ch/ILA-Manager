/**
 * ILA IP Options controller
 */

import { state } from "./state.js";

export function initOptionsPanel() {
  const ilaName = document.getElementById("opt-ila-name");
  const clkSig = document.getElementById("opt-clock-signal");
  const pipeStages = document.getElementById("opt-pipe-stages");
  const dataDepth = document.getElementById("opt-data-depth");
  const muSame = document.getElementById("opt-mu-same");
  const muIndiv = document.getElementById("opt-mu-indiv");

  ilaName.addEventListener("input", (e) => {
    const ila = state.getCurrentIla();
    if (ila) ila.name = e.target.value;
    state.notify();
  });

  clkSig.addEventListener("input", (e) => {
    const ila = state.getCurrentIla();
    if (ila) ila.clock = e.target.value;
    state.notify();
  });

  pipeStages.addEventListener("change", (e) => {
    const ila = state.getCurrentIla();
    if (ila) ila.pipe_stages = parseInt(e.target.value, 10);
    state.notify();
  });

  dataDepth.addEventListener("change", (e) => {
    const ila = state.getCurrentIla();
    if (ila) ila.data_depth = parseInt(e.target.value, 10);
    state.notify();
  });

  muSame.addEventListener("change", () => {
    const ila = state.getCurrentIla();
    if (ila) ila.same_mu = true;
    state.notify();
  });

  muIndiv.addEventListener("change", () => {
    const ila = state.getCurrentIla();
    if (ila) ila.same_mu = false;
    state.notify();
  });
}

export function syncOptionsFromState() {
  const ila = state.getCurrentIla();
  if (!ila) return;

  document.getElementById("opt-ila-name").value = ila.name || "ila_0";
  document.getElementById("opt-clock-signal").value = ila.clock || "clk";
  document.getElementById("opt-pipe-stages").value = (ila.pipe_stages !== undefined ? ila.pipe_stages : 4).toString();
  document.getElementById("opt-data-depth").value = (ila.data_depth || 1024).toString();

  if (ila.same_mu) {
    document.getElementById("opt-mu-same").checked = true;
  } else {
    document.getElementById("opt-mu-indiv").checked = true;
  }
}
