const el = (id) => document.getElementById(id);
const pretty = (o) => JSON.stringify(o, null, 2);

async function postJson(url, body) {
  const res = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  const data = await res.json();
  if (!res.ok) throw new Error(pretty(data));
  return data;
}

async function getJson(url) {
  const res = await fetch(url);
  const data = await res.json();
  if (!res.ok) throw new Error(pretty(data));
  return data;
}

function wallet() {
  return el("wallet").value.trim();
}

el("connectWallet").addEventListener("click", async () => {
  try {
    const out = await postJson("/ui/api/wallet/connect", {
      wallet_address: wallet(),
      network: "testnet",
      provider: "ui",
      user_role: "client",
    });
    el("authOutput").textContent = pretty(out);
  } catch (e) {
    alert(e.message);
  }
});

el("autoCreateWallet").addEventListener("click", async () => {
  try {
    const out = await postJson("/ui/api/wallet/auto-create", {
      network: "testnet",
      provider: "solclub-managed",
      created_by: "ui-auth-page",
    });
    el("authOutput").textContent = pretty(out);
    if (out.wallet_address) el("wallet").value = out.wallet_address;
  } catch (e) {
    alert(e.message);
  }
});

el("googleStart").addEventListener("click", async () => {
  try {
    const role = el("role").value;
    const out = await getJson(`/ui/api/auth/google/start?role=${encodeURIComponent(role)}`);
    el("authOutput").textContent = pretty(out);
    if (out.auth_url) window.open(out.auth_url, "_blank", "noopener,noreferrer");
  } catch (e) {
    alert(e.message);
  }
});
