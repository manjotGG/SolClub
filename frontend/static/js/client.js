const qs = (id) => document.getElementById(id);
const pretty = (o) => JSON.stringify(o, null, 2);
let timer = null;
let es = null;

async function fetchJson(url, options = {}) {
  const res = await fetch(url, options);
  const data = await res.json();
  if (!res.ok) throw new Error(pretty(data));
  return data;
}

function readInputs() {
  return {
    wallet: qs("wallet").value.trim(),
    merchantId: Number(qs("merchantId").value || 1),
    amount: Number(qs("amount").value || 0.1),
  };
}

function hydrate(snapshot, preview) {
  qs("tier").textContent = String(snapshot.tier || "-").toUpperCase();
  qs("txCount").textContent = String(snapshot.total_transactions || 0);
  qs("cashback").textContent = String(snapshot.total_cashback || 0);
  qs("nftCount").textContent = String(snapshot.nft_count || 0);
  qs("clientOutput").textContent = pretty({ snapshot, preview });
}

async function loadClientData() {
  const { wallet, merchantId, amount } = readInputs();
  if (!wallet) {
    alert("Enter wallet address");
    return;
  }
  const snapshot = await fetchJson(`/ui/api/client/${wallet}/snapshot?merchant_id=${merchantId}`);
  const preview = await fetchJson(`/ui/api/client/${wallet}/reward-preview?merchant_id=${merchantId}&amount=${amount}`);
  hydrate(snapshot, preview);
}

function resetRefresh() {
  if (timer) {
    clearInterval(timer);
    timer = null;
  }
  if (es) {
    es.close();
    es = null;
  }

  const ms = Number(qs("autoRefreshMs").value || 0);
  if (ms <= 0) return;

  const { wallet, merchantId, amount } = readInputs();
  if (!wallet) return;

  es = new EventSource(`/ui/events?channel=client&wallet=${encodeURIComponent(wallet)}&merchant_id=${merchantId}&amount=${amount}`);
  es.onmessage = (evt) => {
    try {
      const data = JSON.parse(evt.data);
      if (data.snapshot && data.preview) hydrate(data.snapshot, data.preview);
    } catch (e) {
      console.warn("SSE parse error", e);
    }
  };
  es.onerror = () => {
    if (es) es.close();
    timer = setTimeout(() => resetRefresh(), ms);
  };
}

qs("loadClientData").addEventListener("click", () => loadClientData().catch((e) => alert(e.message)));
qs("autoRefreshMs").addEventListener("change", resetRefresh);
["wallet", "merchantId", "amount"].forEach((id) => qs(id).addEventListener("change", resetRefresh));
