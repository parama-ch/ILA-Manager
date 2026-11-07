/**
 * REST API client for ILA Manager backend
 */

export async function parseHdlFiles({ paths = null, files = null }) {
  const res = await fetch("/api/hdl/parse", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ paths, files }),
  });
  if (!res.ok) throw new Error(await res.text());
  return await res.json();
}

export async function generateCode(ila, signals) {
  const res = await fetch("/api/generate", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ ila, signals }),
  });
  if (!res.ok) throw new Error(await res.text());
  return await res.json();
}

export async function checkDiff(ila, signals) {
  const res = await fetch("/api/diff", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ ila, signals }),
  });
  if (!res.ok) throw new Error(await res.text());
  return await res.json();
}

export async function saveProject(filePath, project, signalsByUnit) {
  const res = await fetch("/api/project/save", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ file_path: filePath, project, signals_by_unit: signalsByUnit }),
  });
  if (!res.ok) throw new Error(await res.text());
  return await res.json();
}

export async function loadProject(filePath) {
  const res = await fetch("/api/project/load", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ file_path: filePath }),
  });
  if (!res.ok) throw new Error(await res.text());
  return await res.json();
}

export async function importHdlInstance(content, isVhdl) {
  const res = await fetch("/api/import/hdl-instance", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ content, is_vhdl: isVhdl }),
  });
  if (!res.ok) throw new Error(await res.text());
  return await res.json();
}

export async function importTcl(content) {
  const res = await fetch("/api/import/tcl", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ content }),
  });
  if (!res.ok) throw new Error(await res.text());
  return await res.json();
}

export async function listDirectory(path = ".") {
  const res = await fetch(`/api/fs/list?path=${encodeURIComponent(path)}`);
  if (!res.ok) throw new Error(await res.text());
  return await res.json();
}
