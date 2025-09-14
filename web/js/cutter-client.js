const API_BASE = "";

async function api(path, options) {
  const res = await fetch(API_BASE + path, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  if (res.status === 401) throw new Error("unauthorised");
  return await res.json();
}

export async function startCall(number) {
  return api("/v2/auth/call", { method: "POST", body: JSON.stringify({ number }) });
}

export async function verifyName(number, name) {
  return api("/v2/auth/verify-name", { method: "POST", body: JSON.stringify({ number, name }) });
}

export async function sendMessage(session_id, message) {
  return api("/v2/chat/send", { method: "POST", body: JSON.stringify({ session_id, message }) });
}

export async function switchMode(session_id, mode) {
  return api("/v2/session/mode", { method: "POST", body: JSON.stringify({ session_id, mode }) });
}
