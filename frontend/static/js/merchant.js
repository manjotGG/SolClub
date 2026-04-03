const $ = (id) => document.getElementById(id);
const pretty = (o) => JSON.stringify(o, null, 2);
let es = null;

async function fetchJson(url) {
  const res = await fetch(url);
  const data = await res.json();
  if (!res.ok) throw new Error(pretty(data));
  return data;
}

async function loadMerchantData() {
  const merchantId = Number($("merchantId").value || 1);
  const analytics = await fetchJson(`/ui/api/merchant/${merchantId}/analytics`);
  const nfts = await fetchJson(`/ui/api/merchant/${merchantId}/nfts?limit=20`);
  $("merchantOutput").textContent = pretty({ analytics, nfts: nfts.items || [] });
}

function resetSse() {
  if (es) {
    es.close();
    es = null;
  }
  const ms = Number($("autoRefreshMs").value || 0);
  if (ms <= 0) return;

  const merchantId = Number($("merchantId").value || 1);
  es = new EventSource(`/ui/events?channel=merchant&merchant_id=${merchantId}`);
  es.onmessage = (evt) => {
    try {
      const data = JSON.parse(evt.data);
      $("merchantOutput").textContent = pretty(data);
    } catch (e) {
      console.warn("SSE parse error", e);
    }
  };
}

$("loadMerchantData").addEventListener("click", () => loadMerchantData().catch((e) => alert(e.message)));
$("autoRefreshMs").addEventListener("change", resetSse);
$("merchantId").addEventListener("change", resetSse);
