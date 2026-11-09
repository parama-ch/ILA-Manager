/**
 * Central state store for ILA Manager
 */

export const state = {
  project: {
    version: 1,
    source_files: [],
    ilas: [
      {
        name: "ila_0",
        target_file: "",
        target_unit: "",
        clock: "clk",
        pipe_stages: 4, // Default: 4 stages!
        data_depth: 1024,
        same_mu: true,
        same_mu_cnt: 1,
        strg_qual: false,
        ip_dir: null,
        run_ooc_synth: true,
        probes: [],
      },
    ],
  },
  currentIlaIndex: 0,
  signalsByUnit: {},
  currentUnit: "",
  uploadedFiles: [],
  activeTab: "tcl",
  listeners: [],

  subscribe(fn) {
    this.listeners.push(fn);
  },

  notify() {
    for (const fn of this.listeners) {
      fn();
    }
  },

  getCurrentIla() {
    return this.project.ilas[this.currentIlaIndex];
  },

  getCurrentSignals() {
    return this.signalsByUnit[this.currentUnit] || [];
  },

  renumberProbes() {
    const ila = this.getCurrentIla();
    ila.probes.forEach((p, idx) => {
      p.index = idx;
    });
  },

  addProbe(mapping = null, width = 1) {
    const ila = this.getCurrentIla();
    const newIdx = ila.probes.length;
    ila.probes.push({
      index: newIdx,
      mapping: mapping,
      width: width,
      probe_type: "DATA_AND_TRIGGER",
      mu_cnt: ila.same_mu_cnt || 1,
      label: "",
      snapshot: null,
    });
    this.renumberProbes();
    this.notify();
  },

  removeProbe(idx) {
    const ila = this.getCurrentIla();
    if (idx >= 0 && idx < ila.probes.length) {
      ila.probes.splice(idx, 1);
      this.renumberProbes();
      this.notify();
    }
  },

  swapProbes(idxA, idxB) {
    const ila = this.getCurrentIla();
    if (
      idxA >= 0 &&
      idxA < ila.probes.length &&
      idxB >= 0 &&
      idxB < ila.probes.length
    ) {
      const temp = ila.probes[idxA];
      ila.probes[idxA] = ila.probes[idxB];
      ila.probes[idxB] = temp;
      this.renumberProbes();
      this.notify();
      return true;
    }
    return false;
  },

  moveProbe(fromIdx, toIdx) {
    const ila = this.getCurrentIla();
    if (
      fromIdx >= 0 &&
      fromIdx < ila.probes.length &&
      toIdx >= 0 &&
      toIdx < ila.probes.length
    ) {
      const item = ila.probes.splice(fromIdx, 1)[0];
      ila.probes.splice(toIdx, 0, item);
      this.renumberProbes();
      this.notify();
    }
  },

  setProbeMapping(idx, mapping, width) {
    const ila = this.getCurrentIla();
    if (idx >= 0 && idx < ila.probes.length) {
      ila.probes[idx].mapping = mapping;
      if (width !== undefined && width !== null) {
        ila.probes[idx].width = width;
      }
      this.notify();
    }
  },

  clearProbes() {
    const ila = this.getCurrentIla();
    ila.probes = [];
    this.notify();
  },
};
