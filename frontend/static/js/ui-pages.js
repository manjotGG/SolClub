const SOLCLUB_ROLE_KEY = "solclub_role";
const SOLCLUB_WALLET_KEY = "solclub_wallet";
const AUTH_BASE = "/api/auth";

const $ = (selector, root = document) => root.querySelector(selector);
const $$ = (selector, root = document) => Array.from(root.querySelectorAll(selector));

function pageId() {
  return document.body.dataset.page || "";
}

function normalizeLabel(text) {
  return String(text || "").replace(/\s+/g, " ").trim().toLowerCase();
}

function findClickableLabel(node) {
  return normalizeLabel(node?.textContent || node?.innerText || "");
}

function setLocalSession(role, wallet) {
  if (role) localStorage.setItem(SOLCLUB_ROLE_KEY, role);
  if (wallet) localStorage.setItem(SOLCLUB_WALLET_KEY, wallet);
}

function clearLocalSession() {
  localStorage.removeItem(SOLCLUB_ROLE_KEY);
  localStorage.removeItem(SOLCLUB_WALLET_KEY);
}

async function apiJson(url, options = {}) {
  const response = await fetch(url, {
    ...options,
    credentials: "same-origin",
    headers: {
      "Content-Type": "application/json",
      ...(options.headers || {}),
    },
  });
  const contentType = response.headers.get("content-type") || "";
  const data = contentType.includes("application/json") ? await response.json() : await response.text();
  if (!response.ok) {
    const detail = typeof data === "string" ? data : data.detail || JSON.stringify(data);
    throw new Error(detail || `Request failed (${response.status})`);
  }
  return data;
}

function go(path) {
  window.location.assign(path);
}

function openModal(node) {
  if (!node) return;
  node.classList.remove("hidden");
  node.classList.add("flex");
}

function closeModal(node) {
  if (!node) return;
  node.classList.add("hidden");
  node.classList.remove("flex");
}

function roleDashboardPath(role) {
  return "/dashboard";
}

function preferredRole() {
  const roleField = $("#registerRole");
  const role = normalizeLabel(roleField?.value || "client");
  return role === "merchant" ? "merchant" : "client";
}

function readWalletInput() {
  return String($("#registerWallet")?.value || "").trim();
}

function setWalletInput(wallet) {
  const input = $("#registerWallet");
  if (input && wallet) input.value = wallet;
}

function loginPagePath() {
  return "/login";
}

async function getSession() {
  return await apiJson(`${AUTH_BASE}/session`, { method: "GET" });
}

async function getOnboardingStatus() {
  return await apiJson(`${AUTH_BASE}/onboarding-status`, { method: "GET" });
}

async function startSession(role, walletAddress) {
  const payload = { role, wallet_address: walletAddress || "" };
  const session = await apiJson(`${AUTH_BASE}/session/start`, {
    method: "POST",
    body: JSON.stringify(payload),
  });
  setLocalSession(session.role, session.wallet);
  return session;
}

async function connectWallet(role) {
  const modalWallet = $("#walletConnectAddress");
  const modalRole = $("#walletConnectRole");
  const wallet = String(modalWallet?.value || readWalletInput() || "").trim();
  if (!wallet) {
    if (!modalWallet && !$("#registerWallet")) {
      go("/auth");
      return;
    }
    throw new Error("wallet_address is required");
  }
  const resolvedRole = normalizeLabel(modalRole?.value || role || "client") === "merchant" ? "merchant" : "client";

  const data = await apiJson(`${AUTH_BASE}/wallet/connect`, {
    method: "POST",
    body: JSON.stringify({
      wallet_address: wallet,
      network: "testnet",
      provider: resolvedRole === "merchant" ? "merchant-wallet" : "phantom",
      user_role: resolvedRole,
    }),
  });
  setWalletInput(wallet);
  setLocalSession(data.role || resolvedRole, wallet);
  const status = await getOnboardingStatus();
  closeModal($("#walletConnectModal"));
  go(status.redirect || "/onboarding");
}

async function loginWithCredentials() {
  const identifier = String($("#returningIdentifier")?.value || "").trim();
  const password = String($("#returningPassword")?.value || "").trim();
  const role = normalizeLabel($("#returningRole")?.value || "client") === "merchant" ? "merchant" : "client";
  const session = await apiJson(`${AUTH_BASE}/login`, {
    method: "POST",
    body: JSON.stringify({ identifier, password, role }),
  });
  setLocalSession(session.role, session.wallet);
  go(session.redirect || roleDashboardPath(session.role || role));
  return session;
}

async function createManagedWallet(role = "client") {
  const data = await apiJson(`${AUTH_BASE}/wallet/create`, {
    method: "POST",
    body: JSON.stringify({ network: "testnet", provider: "solclub-managed", created_by: "ui-auth", user_role: role }),
  });
  setWalletInput(data.wallet_address);
  setLocalSession(data.role || role, data.wallet_address);
  const status = await getOnboardingStatus();
  go(status.redirect || "/onboarding");
}

async function registerAccount(payload) {
  return await apiJson(`${AUTH_BASE}/onboarding/complete`, {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

function wireRegisterForm() {
  const form = $("#authRegisterForm");
  if (!form) return;
  const statusNode = $("#authRegisterStatus");

  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    const payload = {
      display_name: String($("#registerDisplayName")?.value || "").trim(),
      email: String($("#registerEmail")?.value || "").trim(),
      role: preferredRole(),
      password: String($("#registerPassword")?.value || "").trim(),
      wallet_address: readWalletInput(),
      network: "testnet",
      provider: "manual",
    };

    try {
      if (statusNode) statusNode.textContent = "Creating account...";
      const data = await registerAccount(payload);
      const wallet = data.wallet || payload.wallet_address || "";
      setLocalSession(payload.role, wallet);
      if (statusNode) statusNode.textContent = "Account created and synced with Supabase.";
      go(data.redirect || roleDashboardPath(payload.role));
    } catch (error) {
      if (statusNode) statusNode.textContent = error.message;
      alert(error.message);
    }
  });
}

function wireReturningLogin() {
  const form = $("#returningLoginForm");
  if (!form) return;
  const statusNode = $("#returningLoginStatus");

  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    try {
      if (statusNode) statusNode.textContent = "Signing in...";
      const session = await loginWithCredentials();
      if (statusNode) statusNode.textContent = "Authenticated. Redirecting...";
    } catch (error) {
      if (statusNode) statusNode.textContent = error.message;
      alert(error.message);
    }
  });
}

function setDetailsMode(enabled) {
  const details = $("#detailsPanel");
  const returning = $("#returningLoginForm")?.closest("div");
  if (details) details.classList.toggle("hidden", !enabled);
  if (returning) returning.classList.toggle("hidden", !!enabled);
}

function wireAuthButtons() {
  const connectBtn = $("#btnConnectWallet");
  const googleBtn = $("#btnGoogleSignin");
  const createBtn = $("#btnCreateWallet");
  const loginPageBtn = $("#btnOpenLoginPage");
  const walletModal = $("#walletConnectModal");
  const walletForm = $("#walletConnectForm");
  const closeWalletModal = $("#closeWalletModal");
  const cancelWalletModal = $("#cancelWalletModal");

  connectBtn?.addEventListener("click", (event) => {
    event.preventDefault();
    const modalWallet = $("#walletConnectAddress");
    const modalRole = $("#walletConnectRole");
    if (modalWallet && !modalWallet.value) modalWallet.value = localStorage.getItem(SOLCLUB_WALLET_KEY) || "";
    if (modalRole) modalRole.value = preferredRole();
    openModal(walletModal);
  });

  googleBtn?.addEventListener("click", async (event) => {
    event.preventDefault();
    try {
      const data = await apiJson(`${AUTH_BASE}/google/start?role=${preferredRole()}`);
      if (data.auth_url) window.location.assign(data.auth_url);
    } catch (error) {
      alert(error.message);
    }
  });

  createBtn?.addEventListener("click", (event) => {
    event.preventDefault();
    createManagedWallet(preferredRole()).catch((error) => alert(error.message));
  });

  loginPageBtn?.addEventListener("click", (event) => {
    event.preventDefault();
    go(loginPagePath());
  });

  walletForm?.addEventListener("submit", (event) => {
    event.preventDefault();
    connectWallet(preferredRole()).catch((error) => alert(error.message));
  });

  closeWalletModal?.addEventListener("click", () => closeModal(walletModal));
  cancelWalletModal?.addEventListener("click", () => closeModal(walletModal));
}

async function logout() {
  try {
    await apiJson(`${AUTH_BASE}/logout`, { method: "POST" });
  } finally {
    clearLocalSession();
    go("/auth");
  }
}

function wireNavigation(role) {
  const routeMap = {
    dashboard: role === "merchant" ? "/ui/merchant" : "/ui/client",
    rewards: "/ui/client/rewards",
    transactions: "/ui/client/transactions",
    "nft collection": "/ui/client/nfts",
    "loyalty progress": "/ui/client/progress",
    "cashback config": "/ui/merchant/cashback",
    analytics: "/ui/merchant/analytics",
    franchises: "/ui/merchant/franchises",
    "nft distribution": "/ui/merchant/nfts",
    feedback: role === "merchant" ? "/ui/merchant/feedback" : "/ui/client/feedback",
    docs: "/docs",
    logout: "#logout",
  };

  $$("a").forEach((anchor) => {
    const label = findClickableLabel(anchor);
    const key = Object.keys(routeMap).find((item) => label === item || label.includes(item));
    if (!key) return;
    const route = routeMap[key];
    if (route === "#logout") {
      anchor.href = "#";
      anchor.addEventListener("click", (event) => {
        event.preventDefault();
        logout().catch((error) => alert(error.message));
      });
      return;
    }
    anchor.href = route;
  });
}

function attachSSE(channel, wallet) {
  const params = new URLSearchParams({ channel, merchant_id: "1", amount: "0.1" });
  if (wallet) params.set("wallet", wallet);
  const es = new EventSource(`/ui/events?${params.toString()}`);

  es.onmessage = (event) => {
    try {
      const payload = JSON.parse(event.data || "{}");
      if (payload.snapshot) updateClientLivePanel(payload.snapshot, payload.preview || {});
      if (payload.analytics) updateMerchantLivePanel(payload.analytics, payload.nfts || []);
    } catch {
      // Ignore malformed event payloads
    }
  };
  return es;
}

function getOrCreateLivePanel() {
  let panel = $("#solclubLivePanel");
  if (panel) return panel;
  panel = document.createElement("section");
  panel.id = "solclubLivePanel";
  panel.className = "mb-8 p-4 rounded-2xl border border-cyan-400/20 bg-cyan-500/10 text-sm";
  const main = $("main");
  if (main && main.firstChild) {
    main.insertBefore(panel, main.firstChild);
  } else if (main) {
    main.appendChild(panel);
  } else {
    document.body.prepend(panel);
  }
  return panel;
}

function showSoftWalletPrompt() {
  let modal = $("#softWalletPrompt");
  if (!modal) {
    modal = document.createElement("div");
    modal.id = "softWalletPrompt";
    modal.className = "fixed inset-0 z-40 flex items-center justify-center bg-black/60 px-4";
    modal.innerHTML = `
      <div class="w-full max-w-md rounded-2xl border border-white/10 bg-[#1b1f2b] p-6">
        <div class="flex items-center justify-between mb-3">
          <h3 class="text-xl font-bold">Connect your wallet</h3>
          <button id="softWalletCloseX" class="text-slate-300" type="button">X</button>
        </div>
        <p class="text-sm text-slate-300 mb-4">Unlock full features by connecting your wallet.</p>
        <div class="flex gap-3">
          <button id="softWalletConnect" class="flex-1 rounded-lg bg-cyan-400 text-cyan-950 font-bold py-2" type="button">Connect Wallet</button>
          <button id="softWalletLater" class="rounded-lg border border-slate-500 px-4" type="button">Maybe later</button>
        </div>
      </div>
    `;
    document.body.appendChild(modal);

    $("#softWalletCloseX", modal)?.addEventListener("click", () => closeModal(modal));
    $("#softWalletLater", modal)?.addEventListener("click", () => closeModal(modal));
    $("#softWalletConnect", modal)?.addEventListener("click", () => {
      closeModal(modal);
      go("/auth");
    });
  }
  openModal(modal);
}

function updateClientLivePanel(snapshot, preview) {
  const panel = getOrCreateLivePanel();
  panel.innerHTML = `
    <div class="font-bold tracking-wider uppercase text-xs mb-2">Live Client Data</div>
    <div class="grid grid-cols-2 md:grid-cols-6 gap-3">
      <div><div class="text-[10px] uppercase text-slate-300">Wallet</div><div class="font-mono text-xs">${snapshot.wallet || "-"}</div></div>
      <div><div class="text-[10px] uppercase text-slate-300">Tier</div><div class="font-bold">${String(snapshot.tier || "-").toUpperCase()}</div></div>
      <div><div class="text-[10px] uppercase text-slate-300">Transactions</div><div class="font-bold">${snapshot.total_transactions || 0}</div></div>
      <div><div class="text-[10px] uppercase text-slate-300">Spent</div><div class="font-bold">${snapshot.total_spent || 0} SOL</div></div>
      <div><div class="text-[10px] uppercase text-slate-300">Cashback</div><div class="font-bold">${snapshot.total_cashback || 0} SOL</div></div>
      <div><div class="text-[10px] uppercase text-slate-300">Next Reward</div><div class="font-bold">${preview.reward_tier || "-"}</div></div>
    </div>
  `;
}

function updateMerchantLivePanel(analytics, nfts) {
  const panel = getOrCreateLivePanel();
  panel.innerHTML = `
    <div class="font-bold tracking-wider uppercase text-xs mb-2">Live Merchant Data</div>
    <div class="grid grid-cols-2 md:grid-cols-5 gap-3">
      <div><div class="text-[10px] uppercase text-slate-300">Tx Volume</div><div class="font-bold">${analytics.transaction_volume || 0}</div></div>
      <div><div class="text-[10px] uppercase text-slate-300">Cashback Volume</div><div class="font-bold">${analytics.cashback_volume || 0}</div></div>
      <div><div class="text-[10px] uppercase text-slate-300">Unique Clients</div><div class="font-bold">${analytics.unique_clients || 0}</div></div>
      <div><div class="text-[10px] uppercase text-slate-300">NFT Events</div><div class="font-bold">${(nfts || []).length}</div></div>
      <div><div class="text-[10px] uppercase text-slate-300">Updated</div><div class="font-bold">now</div></div>
    </div>
  `;
}

function renderClientTransactions(items) {
  const container = $$("section").find((section) => section.querySelector(".space-y-3"));
  if (!container) return;
  const list = container.querySelector(".space-y-3");
  if (!list) return;
  const rows = (items || []).slice(0, 8).map((tx) => `
    <div class="group glass-panel rounded-2xl p-4 border-l-4 border-cyan-400/50">
      <div class="grid grid-cols-1 md:grid-cols-4 gap-2 text-sm">
        <div><div class="text-[10px] uppercase text-slate-400">Date</div><div>${tx.created_at || "-"}</div></div>
        <div><div class="text-[10px] uppercase text-slate-400">Merchant</div><div>${tx.merchant_id || "-"}</div></div>
        <div><div class="text-[10px] uppercase text-slate-400">Amount</div><div>${tx.amount || 0} SOL</div></div>
        <div><div class="text-[10px] uppercase text-slate-400">Signature</div><div class="font-mono text-xs">${tx.signature || "-"}</div></div>
      </div>
    </div>
  `).join("");
  list.innerHTML = rows || '<div class="glass-panel rounded-2xl p-4">No transaction data available.</div>';
}

function renderClientRewards(items) {
  if (!["client-rewards", "client-feedback"].includes(pageId())) return;
  const rightGrid = $$(".grid").find((grid) => grid.className.includes("col-span-9") || grid.className.includes("col-span-2"));
  if (!rightGrid) return;
  const rewards = (items || []).slice(0, 6).map((reward) => `
    <div class="glass-panel rounded-xl p-4 border border-cyan-400/20">
      <div class="text-[10px] uppercase text-slate-400">${reward.created_at || "-"}</div>
      <div class="text-lg font-bold">${reward.reward_tier || "tier"}</div>
      <div class="text-sm">Cashback: ${reward.cashback_amount || 0} SOL</div>
      <div class="text-xs font-mono text-slate-400 mt-1">${reward.transaction_signature || "-"}</div>
    </div>
  `).join("");
  if (rewards) rightGrid.innerHTML = rewards;
}

function renderClientNfts(items) {
  if (pageId() !== "client-nfts") return;
  const grid = $$(".grid").find((node) => node.className.includes("xl:grid-cols-4"));
  if (!grid) return;
  const cards = (items || []).slice(0, 8).map((nft, index) => `
    <div class="glass-card rounded-2xl p-4 border border-purple-300/20">
      <div class="text-[10px] uppercase text-slate-400">NFT ${index + 1}</div>
      <div class="font-bold mt-1">${nft.nft_type || "Mystery NFT"}</div>
      <div class="text-xs font-mono text-slate-400 mt-2">${nft.mint_address || nft.token_id || "pending"}</div>
      <div class="text-xs text-slate-300 mt-2">Minted: ${nft.minted_at || nft.created_at || "-"}</div>
    </div>
  `).join("");
  if (cards) grid.innerHTML = cards;
}

function updateCashbackFormFromServer(profile) {
  if (pageId() !== "merchant-cashback") return;
  const ranges = $$("input[type='range']");
  const percentageRange = ranges[0];
  const poolRange = ranges[1];
  if (percentageRange) percentageRange.value = String(profile.cashback_pool_percentage || 2);
  if (poolRange) poolRange.value = String(profile.max_cashback_limit || 2500);
}

async function submitCashbackConfig() {
  if (pageId() !== "merchant-cashback") return;
  const ranges = $$("input[type='range']");
  const percentage = Number(ranges[0]?.value || 2);
  const pool = Number(ranges[1]?.value || 2500);
  await apiJson("/ui/api/merchant/1/cashback-config", {
    method: "POST",
    body: JSON.stringify({
      name: "SolClub Merchant",
      cashback_pool_percentage: percentage,
      max_cashback_limit: pool,
      weekly_distribution_rules: {
        base_rate: Math.max(0.01, percentage / 100),
        tiers: [{ min_transactions: 3, rate: Math.max(0.02, percentage / 100) }],
      },
    }),
  });
  alert("Cashback config saved to backend.");
}

async function exportClientTransactionsCsv(wallet) {
  const data = await apiJson(`/ui/api/client/${encodeURIComponent(wallet)}/transactions?limit=200`);
  const rows = ["created_at,merchant_id,amount,signature"];
  (data.items || []).forEach((item) => {
    const row = [item.created_at || "", item.merchant_id ?? "", item.amount ?? "", item.signature || ""]
      .map((value) => `"${String(value).replaceAll('"', '""')}"`)
      .join(",");
    rows.push(row);
  });
  const blob = new Blob([rows.join("\n")], { type: "text/csv" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = `solclub-transactions-${Date.now()}.csv`;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}

async function exportMerchantReport() {
  const analytics = await apiJson("/ui/api/merchant/1/analytics");
  const blob = new Blob([JSON.stringify(analytics, null, 2)], { type: "application/json" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = `solclub-merchant-report-${Date.now()}.json`;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}

async function hydrateClientPages(wallet) {
  const [snapshot, rewards, txs, nfts, progress] = await Promise.all([
    apiJson(`/ui/api/client/${encodeURIComponent(wallet)}/snapshot?merchant_id=1`),
    apiJson(`/ui/api/client/${encodeURIComponent(wallet)}/rewards?merchant_id=1&limit=30`),
    apiJson(`/ui/api/client/${encodeURIComponent(wallet)}/transactions?limit=30`),
    apiJson(`/ui/api/client/${encodeURIComponent(wallet)}/nfts`),
    apiJson(`/ui/api/client/${encodeURIComponent(wallet)}/progress?merchant_id=1`),
  ]);

  const preview = await apiJson(`/ui/api/client/${encodeURIComponent(wallet)}/reward-preview?merchant_id=1&amount=0.1`);
  updateClientLivePanel(snapshot, preview);
  renderClientTransactions(txs.items || []);
  renderClientRewards(rewards.items || []);
  renderClientNfts(nfts.items || []);

  if (pageId() === "client-progress") {
    const pctText = $$("p").find((node) => node.textContent.trim().endsWith("%") && node.className.includes("text-5xl"));
    const txsCount = Number(progress.transactions || 0);
    const pct = Math.max(0, Math.min(100, Math.round(((txsCount % 10) / 10) * 100)));
    if (pctText) pctText.textContent = `${pct}%`;
  }
}

async function hydrateMerchantPages() {
  const [analytics, nfts, feedback, cashback] = await Promise.all([
    apiJson("/ui/api/merchant/1/analytics"),
    apiJson("/ui/api/merchant/1/nfts?limit=20"),
    apiJson("/ui/api/merchant/1/feedback?limit=20"),
    apiJson("/ui/api/merchant/1/cashback-config"),
  ]);
  updateMerchantLivePanel(analytics, nfts.items || []);
  updateCashbackFormFromServer(cashback);

  if (pageId() === "merchant-feedback") {
    const tableBody = $("tbody");
    if (tableBody) {
      tableBody.innerHTML = (feedback.items || []).map((item) => `
        <tr class="border-b border-white/5">
          <td class="py-3">${item.wallet_address || item.wallet || "-"}</td>
          <td class="py-3">${item.rating || "-"}</td>
          <td class="py-3">${item.message || "-"}</td>
          <td class="py-3">${item.created_at || "-"}</td>
        </tr>
      `).join("") || '<tr><td class="py-3" colspan="4">No feedback entries.</td></tr>';
    }
  }
}

function wireCommonButtons(session) {
  $$('button').forEach((button) => {
    if (button.type === "submit") return;
    const label = findClickableLabel(button);

    if (label.includes("connect wallet")) {
      button.addEventListener("click", (event) => {
        event.preventDefault();
        const resolvedRole = preferredRole();
        connectWallet(resolvedRole).catch((error) => alert(error.message));
      });
      return;
    }

    if (label.includes("create new wallet")) {
      button.addEventListener("click", (event) => {
        event.preventDefault();
        createManagedWallet(preferredRole()).catch((error) => alert(error.message));
      });
      return;
    }

    if (label.includes("continue with google")) {
      button.addEventListener("click", async (event) => {
        event.preventDefault();
        try {
          const data = await apiJson(`${AUTH_BASE}/google/start?role=${preferredRole()}`);
          if (data.auth_url) window.location.assign(data.auth_url);
        } catch (error) {
          alert(error.message);
        }
      });
      return;
    }

    if (label === "logout") {
      button.addEventListener("click", (event) => {
        event.preventDefault();
        logout().catch((error) => alert(error.message));
      });
      return;
    }

    if (label === "sign & commit") {
      button.addEventListener("click", (event) => {
        event.preventDefault();
        submitCashbackConfig().catch((error) => alert(error.message));
      });
      return;
    }

    if (label === "export csv") {
      button.addEventListener("click", (event) => {
        event.preventDefault();
        if (!session.wallet) {
          alert("No wallet found in authenticated session.");
          return;
        }
        exportClientTransactionsCsv(session.wallet).catch((error) => alert(error.message));
      });
      return;
    }

    if (label === "generate report") {
      button.addEventListener("click", (event) => {
        event.preventDefault();
        exportMerchantReport().catch((error) => alert(error.message));
      });
      return;
    }

    if (label === "view full ledger") {
      button.addEventListener("click", (event) => {
        event.preventDefault();
        go("/ui/client/transactions");
      });
      return;
    }

    if (label === "mint new assets") {
      button.addEventListener("click", (event) => {
        event.preventDefault();
        go("/ui/client/nfts");
      });
      return;
    }
  });
}

function wirePortal(session) {
  if (pageId() !== "role-gateway") return;
  const roleNode = $("#sessionRole");
  const walletNode = $("#sessionWallet");
  const clientBtn = $("#enterClient");
  const merchantBtn = $("#enterMerchant");
  const logoutBtn = $("#logoutBtn");

  if (roleNode) roleNode.textContent = `Role: ${session.role || "unknown"}`;
  if (walletNode) walletNode.textContent = `Wallet: ${session.wallet || "not attached"}`;

  clientBtn?.addEventListener("click", async () => {
    await startSession("client", session.wallet || "");
    go("/ui/client");
  });

  merchantBtn?.addEventListener("click", async () => {
    await startSession("merchant", session.wallet || "");
    go("/ui/merchant");
  });

  logoutBtn?.addEventListener("click", async () => {
    await logout();
  });
}

async function bootstrap() {
  const page = pageId();

  if (page === "auth") {
    wireAuthButtons();
    const session = await getSession();
    if (session.authenticated) {
      const status = await getOnboardingStatus();
      go(status.redirect || "/dashboard");
    }
    return;
  }

  if (page === "auth-login") {
    wireAuthButtons();
    wireReturningLogin();
    const session = await getSession();
    if (!session.authenticated) return;
    const status = await getOnboardingStatus();
    go(status.redirect || "/dashboard");
    return;
  }

  if (page === "onboarding") {
    wireRegisterForm();
    const session = await getSession();
    if (!session.authenticated) {
      go("/auth");
      return;
    }

    const status = await getOnboardingStatus();
    if (!status.requires_details) {
      go(status.redirect || "/dashboard");
      return;
    }

    const walletInput = $("#registerWallet");
    if (walletInput && status.wallet) walletInput.value = status.wallet;
    const roleInput = $("#registerRole");
    if (roleInput && status.role) roleInput.value = status.role;
    const emailInput = $("#registerEmail");
    if (emailInput && status.user_ref) emailInput.value = status.user_ref;
    return;
  }

  const session = await getSession();
  if (!session.authenticated) {
    go("/auth?required=login");
    return;
  }
  setLocalSession(session.role, session.wallet);

  if (page === "role-gateway") {
    go(roleDashboardPath(session.role));
    return;
  }

  wireNavigation(session.role);
  wireCommonButtons(session);
  wirePortal(session);

  if (page.startsWith("client")) {
    if (session.wallet) {
      await hydrateClientPages(session.wallet);
      attachSSE("client", session.wallet);
    } else if (page === "client-dashboard") {
      showSoftWalletPrompt();
    }
  } else if (page.startsWith("merchant")) {
    await hydrateMerchantPages();
    attachSSE("merchant", session.wallet || "");
  }
}

document.addEventListener("DOMContentLoaded", () => {
  bootstrap().catch((error) => {
    console.error(error);
    alert(error.message || "UI bootstrap failed.");
    if (!["auth", "auth-login", "onboarding"].includes(pageId())) {
      go("/auth");
    }
  });
});