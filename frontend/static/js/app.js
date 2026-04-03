const byId = (id) => document.getElementById(id);

const state = {
  refreshTimer: null,
};

function pretty(obj) {
  return JSON.stringify(obj, null, 2);
}

async function getJson(url, options = {}) {
  const res = await fetch(url, options);
  let body = null;
  try {
    body = await res.json();
  } catch {
    body = { error: "Invalid JSON response" };
  }
  if (!res.ok) {
    throw new Error(pretty(body));
  }
  return body;
}

function walletValue() {
  return byId("wallet").value.trim();
}

function merchantIdValue() {
  return Number(byId("merchantId").value || 1);
}

function updateKpis(snapshot) {
  byId("kpiTier").textContent = String(snapshot.tier || "-").toUpperCase();
  byId("kpiTx").textContent = String(snapshot.total_transactions || 0);
  byId("kpiCashback").textContent = String(snapshot.total_cashback || 0);
  byId("kpiNft").textContent = String(snapshot.nft_count || 0);

  const milestone = snapshot.next_milestone || {};
  const needed = Number(milestone.transactions_needed || 0);
  const goal = Number(milestone.milestone || 0);
  const done = Math.max(goal - needed, 0);
  const percent = goal > 0 ? Math.min((done / goal) * 100, 100) : 0;

  byId("milestoneBar").style.width = `${percent}%`;
  byId("milestoneText").textContent =
    goal > 0
      ? `${done}/${goal} transactions. Next reward: ${milestone.reward || "N/A"}`
      : "Milestone unavailable";
}

async function loadClientSnapshot() {
  const wallet = walletValue();
  if (!wallet) {
    alert("Enter a wallet address first.");
    return;
  }
  const merchantId = merchantIdValue();
  const out = await getJson(`/api/client/${wallet}/snapshot?merchant_id=${merchantId}`);
  updateKpis(out);
}

async function loadPreview() {
  const wallet = walletValue();
  if (!wallet) {
    alert("Enter a wallet address first.");
    return;
  }
  const merchantId = merchantIdValue();
  const amount = Number(byId("amount").value || 0.01);
  const out = await getJson(`/api/client/${wallet}/reward-preview?merchant_id=${merchantId}&amount=${amount}`);
  byId("previewOut").textContent = pretty(out);
}

async function loadMerchantAnalytics() {
  const merchantId = merchantIdValue();
  const analytics = await getJson(`/api/merchant/${merchantId}/analytics`);
  const nftData = await getJson(`/api/merchant/${merchantId}/nfts?limit=10`);
  byId("merchantOut").textContent = pretty({ analytics, nft_preview: nftData.items || [] });
}

async function connectWallet() {
  const wallet = walletValue();
  if (!wallet) {
    alert("Enter a wallet address first.");
    return;
  }
  const out = await getJson("/api/wallet/connect", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ wallet_address: wallet, network: "testnet", provider: "frontend", user_role: "client" }),
  });
  byId("authOut").textContent = pretty(out);
}

async function autoCreateWallet() {
  const out = await getJson("/api/wallet/auto-create", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ network: "testnet", provider: "solclub-managed", created_by: "frontend-ui" }),
  });
  byId("authOut").textContent = pretty(out);
  if (out.wallet_address) {
    byId("wallet").value = out.wallet_address;
  }
}

async function startGoogleOauth() {
  const out = await getJson("/api/auth/google/start?role=client");
  byId("authOut").textContent = pretty(out);
}

async function sendFeedback() {
  const wallet = walletValue();
  if (!wallet) {
    alert("Enter a wallet address first.");
    return;
  }
  const merchantId = merchantIdValue();
  const rating = Number(byId("rating").value || 5);
  const message = byId("feedback").value;

  const out = await getJson(`/api/client/${wallet}/feedback`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ merchant_id: merchantId, rating, message }),
  });
  byId("feedbackOut").textContent = pretty(out);
}

function resetAutoRefresh() {
  if (state.refreshTimer) {
    clearInterval(state.refreshTimer);
    state.refreshTimer = null;
  }
  const ms = Number(byId("refreshInterval").value || 0);
  if (ms > 0) {
    state.refreshTimer = setInterval(async () => {
      try {
        await Promise.all([loadClientSnapshot(), loadPreview(), loadMerchantAnalytics()]);
      } catch (e) {
        console.warn("Refresh failed", e);
      }
    }, ms);
  }
}

function attachEvents() {
  byId("loadClient").addEventListener("click", () => loadClientSnapshot().catch((e) => alert(e.message)));
  byId("previewReward").addEventListener("click", () => loadPreview().catch((e) => alert(e.message)));
  byId("loadMerchant").addEventListener("click", () => loadMerchantAnalytics().catch((e) => alert(e.message)));
  byId("connectWallet").addEventListener("click", () => connectWallet().catch((e) => alert(e.message)));
  byId("autoCreateWallet").addEventListener("click", () => autoCreateWallet().catch((e) => alert(e.message)));
  byId("googleStart").addEventListener("click", () => startGoogleOauth().catch((e) => alert(e.message)));
  byId("sendFeedback").addEventListener("click", () => sendFeedback().catch((e) => alert(e.message)));
  byId("refreshInterval").addEventListener("change", resetAutoRefresh);
}

attachEvents();
resetAutoRefresh();
