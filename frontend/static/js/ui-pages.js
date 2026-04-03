const $ = (id) => document.getElementById(id);
const pretty = (v) => JSON.stringify(v, null, 2);

async function getJson(url, options = {}) {
  const res = await fetch(url, options);
  const data = await res.json();
  if (!res.ok) throw new Error(pretty(data));
  return data;
}

function pageId() {
  return document.body.dataset.page || "";
}

function renderTimeline(elId, items, renderItem) {
  const root = $(elId);
  if (!root) return;
  root.innerHTML = "";
  if (!items || items.length === 0) {
    root.innerHTML = '<div class="timeline-item">No records found.</div>';
    return;
  }
  items.forEach((item) => {
    const el = document.createElement("div");
    el.className = "timeline-item";
    el.innerHTML = renderItem(item);
    root.appendChild(el);
  });
}

function parseRarity(v) {
  const text = String(v || "").toLowerCase();
  if (text.includes("legendary")) return "legendary";
  if (text.includes("epic")) return "epic";
  if (text.includes("rare") || text.includes("mystery")) return "rare";
  return "common";
}

function initClientDashboard() {
  const load = async () => {
    const wallet = $("wallet").value.trim();
    const merchantId = Number($("merchantId").value || 1);
    const amount = Number($("amount").value || 0.1);
    if (!wallet) return alert("Enter wallet");

    const snapshot = await getJson(`/ui/api/client/${wallet}/snapshot?merchant_id=${merchantId}`);
    const preview = await getJson(`/ui/api/client/${wallet}/reward-preview?merchant_id=${merchantId}&amount=${amount}`);

    $("tier").textContent = String(snapshot.tier || "-").toUpperCase();
    $("txCount").textContent = String(snapshot.total_transactions || 0);
    $("cashback").textContent = String(snapshot.total_cashback || 0);
    $("nftCount").textContent = String(snapshot.nft_count || 0);

    const txCount = Number(snapshot.total_transactions || 0);
    const pct = Math.min(((txCount % 10) / 10) * 100, 100);
    $("xpProgress").style.width = `${pct}%`;
    $("progressHint").textContent = `Next tier reward: ${preview.reward_tier} at ${(preview.cashback_rate * 100).toFixed(2)}% cashback.`;
    $("streakValue").textContent = String(Math.max(1, txCount));
    $("unlockCard").textContent = `Next payment unlock preview: ${preview.nft_rarity} NFT + ${preview.cashback_amount} SOL cashback.`;
    $("clientOutput").textContent = pretty({ snapshot, preview });
  };

  $("loadClientData")?.addEventListener("click", () => load().catch((e) => alert(e.message)));

  $("autoRefreshMs")?.addEventListener("change", () => {
    const ms = Number($("autoRefreshMs").value || 0);
    if (window.__clientTimer) clearInterval(window.__clientTimer);
    if (ms > 0) {
      window.__clientTimer = setInterval(() => load().catch(() => {}), ms);
    }
  });
}

function initClientRewards() {
  $("loadRewards")?.addEventListener("click", async () => {
    try {
      const wallet = $("wallet").value.trim();
      const merchantId = Number($("merchantId").value || 1);
      const limit = Number($("limit").value || 50);
      if (!wallet) return alert("Enter wallet");
      const data = await getJson(`/ui/api/client/${wallet}/rewards?merchant_id=${merchantId}&limit=${limit}`);
      renderTimeline("rewardsTimeline", data.items || [], (r) => `
        <div><strong>${r.reward_tier || "tier"}</strong> • Cashback ${r.cashback_amount || 0} SOL</div>
        <div class="hint">Tx: ${r.transaction_signature || "-"}</div>
        <div class="hint">At: ${r.created_at || "-"}</div>
      `);
    } catch (e) {
      alert(e.message);
    }
  });
}

function initClientNfts() {
  $("loadNfts")?.addEventListener("click", async () => {
    try {
      const wallet = $("wallet").value.trim();
      if (!wallet) return alert("Enter wallet");
      const rarityFilter = $("rarityFilter").value;
      const data = await getJson(`/ui/api/client/${wallet}/nfts`);
      const items = (data.items || []).filter((n) => {
        if (rarityFilter === "all") return true;
        return parseRarity(n.nft_type) === rarityFilter;
      });
      const root = $("nftGrid");
      root.innerHTML = "";
      items.forEach((n) => {
        const rarity = parseRarity(n.nft_type);
        const card = document.createElement("div");
        card.className = `nft-card ${rarity}`;
        card.innerHTML = `
          <div><strong>${n.nft_type || "NFT"}</strong></div>
          <div class="hint">Owner: ${n.owner || n.wallet_address || "-"}</div>
          <div class="hint">Mint: ${n.mint_address || "-"}</div>
          <div class="hint">At: ${n.minted_at || n.created_at || "-"}</div>
        `;
        root.appendChild(card);
      });
      if (items.length === 0) root.innerHTML = '<div class="timeline-item">No NFTs found.</div>';
    } catch (e) {
      alert(e.message);
    }
  });
}

function initClientTransactions() {
  $("loadTx")?.addEventListener("click", async () => {
    try {
      const wallet = $("wallet").value.trim();
      const merchantId = Number($("merchantId").value || 1);
      const limit = Number($("limit").value || 50);
      if (!wallet) return alert("Enter wallet");

      const [txs, rewards] = await Promise.all([
        getJson(`/ui/api/client/${wallet}/transactions?limit=${limit}`),
        getJson(`/ui/api/client/${wallet}/rewards?merchant_id=${merchantId}&limit=${limit}`),
      ]);

      const rewardBySig = {};
      (rewards.items || []).forEach((r) => {
        rewardBySig[r.transaction_signature] = `${r.reward_tier || "Tier"} (${r.cashback_amount || 0} SOL)`;
      });

      const rows = (txs.items || []).map((t) => {
        const reward = rewardBySig[t.signature] || "-";
        return `
          <tr>
            <td>${t.created_at || "-"}</td>
            <td>${t.merchant_id || "-"}</td>
            <td>${t.amount || 0}</td>
            <td>${reward}</td>
            <td>${t.signature || "-"}</td>
          </tr>
        `;
      }).join("");

      $("txTableWrap").innerHTML = `
        <table>
          <thead><tr><th>Date</th><th>Merchant</th><th>Amount</th><th>Reward</th><th>Signature</th></tr></thead>
          <tbody>${rows || '<tr><td colspan="5">No transactions</td></tr>'}</tbody>
        </table>
      `;
    } catch (e) {
      alert(e.message);
    }
  });
}

function initClientProgress() {
  $("loadProgress")?.addEventListener("click", async () => {
    try {
      const wallet = $("wallet").value.trim();
      const merchantId = Number($("merchantId").value || 1);
      if (!wallet) return alert("Enter wallet");
      const data = await getJson(`/ui/api/client/${wallet}/progress?merchant_id=${merchantId}`);
      const tx = Number(data.transactions || 0);
      const pct = Math.min(((tx % 10) / 10) * 100, 100);
      $("ringPct").textContent = `${Math.round(pct)}%`;
      $("progressRing").style.background = `conic-gradient(#22d3ee ${pct}%, rgba(255,255,255,0.12) ${pct}% 100%)`;
      $("progressDetails").innerHTML = `
        <div class="stack-item"><strong>Tier</strong>: ${String(data.tier || "-").toUpperCase()}</div>
        <div class="stack-item"><strong>Transactions</strong>: ${tx}</div>
        <div class="stack-item"><strong>Next Reward Tier</strong>: ${data.next_reward_tier || "-"}</div>
        <div class="stack-item"><strong>Next Cashback Rate</strong>: ${((data.next_cashback_rate || 0) * 100).toFixed(2)}%</div>
      `;
      const tiers = ["bronze", "silver", "gold", "legendary"];
      const current = String(data.tier || "bronze").toLowerCase();
      document.querySelectorAll("#tierLadder .tier-row").forEach((row) => {
        const rowTier = row.textContent.trim().toLowerCase();
        row.classList.toggle("active", tiers.indexOf(rowTier) <= tiers.indexOf(current));
      });
    } catch (e) {
      alert(e.message);
    }
  });
}

function initClientFeedback() {
  $("submitFeedback")?.addEventListener("click", async () => {
    try {
      const wallet = $("wallet").value.trim();
      const merchantId = Number($("merchantId").value || 1);
      const rating = Number($("rating").value || 5);
      const message = $("feedbackMessage").value;
      if (!wallet) return alert("Enter wallet");
      const out = await getJson(`/ui/api/client/${wallet}/feedback`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ merchant_id: merchantId, rating, message }),
      });
      $("feedbackOut").textContent = pretty(out);
    } catch (e) {
      alert(e.message);
    }
  });
}

function initMerchantDashboard() {
  let es;
  const load = async () => {
    const merchantId = Number($("merchantId").value || 1);
    const [analytics, nfts] = await Promise.all([
      getJson(`/ui/api/merchant/${merchantId}/analytics`),
      getJson(`/ui/api/merchant/${merchantId}/nfts?limit=20`),
    ]);
    $("mdRevenue").textContent = String(analytics.transaction_volume || 0);
    $("mdCashback").textContent = String(analytics.cashback_volume || 0);
    $("mdUsers").textContent = String(analytics.unique_clients || 0);
    $("mdNfts").textContent = String((nfts.items || []).length);
    $("merchantOutput").textContent = pretty({ analytics, nft_preview: nfts.items || [] });
  };

  $("loadMerchantData")?.addEventListener("click", () => load().catch((e) => alert(e.message)));
  $("autoRefreshMs")?.addEventListener("change", () => {
    if (es) es.close();
    const ms = Number($("autoRefreshMs").value || 0);
    if (ms <= 0) return;
    const merchantId = Number($("merchantId").value || 1);
    es = new EventSource(`/ui/events?channel=merchant&merchant_id=${merchantId}`);
    es.onmessage = (evt) => {
      try {
        const data = JSON.parse(evt.data);
        const a = data.analytics || {};
        const n = data.nfts || [];
        $("mdRevenue").textContent = String(a.transaction_volume || 0);
        $("mdCashback").textContent = String(a.cashback_volume || 0);
        $("mdUsers").textContent = String(a.unique_clients || 0);
        $("mdNfts").textContent = String(n.length);
        $("merchantOutput").textContent = pretty(data);
      } catch {
        // ignore
      }
    };
  });
}

function initMerchantCashback() {
  const renderPreview = () => {
    const pct = Number($("cashbackPct").value || 2);
    const spend = 1;
    $("previewSpend").textContent = spend.toFixed(2);
    $("previewCashback").textContent = ((pct / 100) * spend).toFixed(3);
  };

  $("cashbackPct")?.addEventListener("input", renderPreview);
  renderPreview();

  $("saveCashbackConfig")?.addEventListener("click", async () => {
    try {
      const merchantId = Number($("merchantId").value || 1);
      const body = {
        name: $("merchantName").value,
        cashback_pool_percentage: Number($("cashbackPct").value || 2),
        max_cashback_limit: Number($("maxCashback").value || 0.05),
        weekly_distribution_rules: JSON.parse($("weeklyRules").value || "{}"),
      };
      const out = await getJson(`/ui/api/merchant/${merchantId}/cashback-config`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      $("cashbackConfigOut").textContent = pretty(out);
    } catch (e) {
      alert(e.message);
    }
  });
}

function initMerchantFranchises() {
  const load = async () => {
    const merchantId = Number($("merchantId").value || 1);
    const out = await getJson(`/ui/api/merchant/${merchantId}/franchises`);
    const root = $("franchiseList");
    root.innerHTML = "";
    const items = out.items || [];
    if (items.length === 0) {
      root.innerHTML = '<div class="stack-item">No franchises found.</div>';
      return;
    }
    items.forEach((f) => {
      const node = document.createElement("div");
      node.className = "stack-item";
      node.innerHTML = `<strong>${f.franchise_name || "Franchise"}</strong><div class="hint">${f.location || "-"}</div>`;
      root.appendChild(node);
    });
  };

  $("addFranchise")?.addEventListener("click", async () => {
    try {
      const merchantId = Number($("merchantId").value || 1);
      const franchise_name = $("franchiseName").value.trim();
      const location = $("franchiseLocation").value.trim();
      if (!franchise_name) return alert("Enter franchise name");
      await getJson(`/ui/api/merchant/${merchantId}/franchises`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ franchise_name, location }),
      });
      load();
    } catch (e) {
      alert(e.message);
    }
  });

  $("loadFranchises")?.addEventListener("click", () => load().catch((e) => alert(e.message)));
}

function initMerchantAnalytics() {
  let es;
  const load = async () => {
    const merchantId = Number($("merchantId").value || 1);
    const out = await getJson(`/ui/api/merchant/${merchantId}/analytics`);
    $("kpiRevenue").textContent = String(out.transaction_volume || 0);
    $("kpiCashback").textContent = String(out.cashback_volume || 0);
    $("kpiUsers").textContent = String(out.unique_clients || 0);
    $("kpiTx").textContent = String(out.transactions_count || 0);
    $("merchantAnalyticsOut").textContent = pretty(out);
  };

  $("loadMerchantAnalytics")?.addEventListener("click", () => load().catch((e) => alert(e.message)));
  $("autoRefreshMs")?.addEventListener("change", () => {
    if (es) es.close();
    const ms = Number($("autoRefreshMs").value || 0);
    if (ms <= 0) return;
    const merchantId = Number($("merchantId").value || 1);
    es = new EventSource(`/ui/events?channel=merchant&merchant_id=${merchantId}`);
    es.onmessage = (evt) => {
      try {
        const data = JSON.parse(evt.data);
        const out = data.analytics || {};
        $("kpiRevenue").textContent = String(out.transaction_volume || 0);
        $("kpiCashback").textContent = String(out.cashback_volume || 0);
        $("kpiUsers").textContent = String(out.unique_clients || 0);
        $("kpiTx").textContent = String(out.transactions_count || 0);
        $("merchantAnalyticsOut").textContent = pretty(data);
      } catch {
        // ignore
      }
    };
  });
}

function initMerchantNfts() {
  $("loadMerchantNfts")?.addEventListener("click", async () => {
    try {
      const merchantId = Number($("merchantId").value || 1);
      const limit = Number($("limit").value || 50);
      const out = await getJson(`/ui/api/merchant/${merchantId}/nfts?limit=${limit}`);
      renderTimeline("merchantNftTimeline", out.items || [], (n) => `
        <div><strong>${n.nft_type || "NFT"}</strong> • ${n.wallet_address || "wallet"}</div>
        <div class="hint">Mint: ${n.mint_address || "-"}</div>
        <div class="hint">At: ${n.created_at || "-"}</div>
      `);
    } catch (e) {
      alert(e.message);
    }
  });
}

function initMerchantFeedback() {
  $("loadMerchantFeedback")?.addEventListener("click", async () => {
    try {
      const merchantId = Number($("merchantId").value || 1);
      const limit = Number($("limit").value || 50);
      const out = await getJson(`/ui/api/merchant/${merchantId}/feedback?limit=${limit}`);
      const root = $("merchantFeedbackList");
      root.innerHTML = "";
      const items = out.items || [];
      if (items.length === 0) {
        root.innerHTML = '<div class="stack-item">No feedback found.</div>';
        return;
      }
      items.forEach((f) => {
        const item = document.createElement("div");
        item.className = "stack-item";
        item.innerHTML = `<strong>Rating ${f.rating || "-"}/5</strong><div class="hint">${f.message || "No comment"}</div><div class="hint">Wallet: ${f.wallet_address || "-"}</div>`;
        root.appendChild(item);
      });
    } catch (e) {
      alert(e.message);
    }
  });
}

function initAuth() {
  const out = $("authOutput");
  $("connectWallet")?.addEventListener("click", async () => {
    try {
      const wallet = $("wallet").value.trim();
      if (!wallet) return alert("Enter wallet");
      const resp = await getJson("/ui/api/wallet/connect", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ wallet_address: wallet, network: "testnet", provider: "ui", user_role: "client" }),
      });
      out.textContent = pretty(resp);
    } catch (e) {
      alert(e.message);
    }
  });

  $("autoCreateWallet")?.addEventListener("click", async () => {
    try {
      const resp = await getJson("/ui/api/wallet/auto-create", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ network: "testnet", provider: "solclub-managed", created_by: "ui-auth" }),
      });
      out.textContent = pretty(resp);
      if (resp.wallet_address) $("wallet").value = resp.wallet_address;
    } catch (e) {
      alert(e.message);
    }
  });

  $("googleStart")?.addEventListener("click", async () => {
    try {
      const role = $("role").value;
      const resp = await getJson(`/ui/api/auth/google/start?role=${encodeURIComponent(role)}`);
      out.textContent = pretty(resp);
      if (resp.auth_url) window.open(resp.auth_url, "_blank", "noopener,noreferrer");
    } catch (e) {
      alert(e.message);
    }
  });
}

(function boot() {
  const p = pageId();
  const map = {
    "client-dashboard": initClientDashboard,
    "client-rewards": initClientRewards,
    "client-nfts": initClientNfts,
    "client-transactions": initClientTransactions,
    "client-progress": initClientProgress,
    "client-feedback": initClientFeedback,
    "merchant-dashboard": initMerchantDashboard,
    "merchant-cashback": initMerchantCashback,
    "merchant-franchises": initMerchantFranchises,
    "merchant-analytics": initMerchantAnalytics,
    "merchant-nfts": initMerchantNfts,
    "merchant-feedback": initMerchantFeedback,
    "auth": initAuth,
  };

  const fn = map[p];
  if (fn) fn();
})();
