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

async function fetchSolBalance(wallet) {
  try {
    const data = await apiJson(`/ui/api/wallet/${encodeURIComponent(wallet)}/balance`);
    return data.balance_sol || 0;
  } catch { return 0; }
}

async function resolveWallet(session) {
  if (session.wallet) return session.wallet;
  // Session has no wallet — try to resolve from backend wallet list
  try {
    const data = await apiJson(`${AUTH_BASE}/wallet/list`);
    const wallets = data.wallets || [];
    const primary = wallets.find(w => w.is_primary) || wallets[0];
    if (primary && primary.wallet_address) {
      // Re-attach wallet to session cookie
      try {
        await apiJson(`${AUTH_BASE}/wallet/connect`, {
          method: "POST",
          body: JSON.stringify({
            wallet_address: primary.wallet_address,
            network: primary.network || "testnet",
            provider: primary.provider || "resolved",
            user_role: session.role || "client",
          }),
        });
      } catch { /* best effort */ }
      setLocalSession(session.role, primary.wallet_address);
      return primary.wallet_address;
    }
  } catch { /* ignore */ }
  return null;
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
  closeModal($("#walletConnectModal"));

  if (data.linked_to) {
    // Already-onboarded user linked a wallet — stay on current page
    window.location.reload();
  } else {
    const status = await getOnboardingStatus();
    go(status.redirect || "/onboarding");
  }
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

  let redirectUrl = "/onboarding";
  try {
    const status = await getOnboardingStatus();
    redirectUrl = status.redirect || "/onboarding";
  } catch {
    redirectUrl = "/onboarding";
  }

  // Show private key modal — un-dismissible until user acknowledges
  if (data.private_key_base58) {
    showPrivateKeyModal(data.wallet_address, data.private_key_base58, redirectUrl);
  } else {
    go(redirectUrl);
  }
}

function showPrivateKeyModal(walletAddress, privateKey, redirectUrl = "/onboarding") {
  let modal = $("#privateKeyModal");
  if (modal) modal.remove();
  modal = document.createElement("div");
  modal.id = "privateKeyModal";
  modal.className = "fixed inset-0 z-[100] flex items-center justify-center bg-black/80 px-4";
  modal.innerHTML = `
    <div class="w-full max-w-lg rounded-2xl border border-red-500/30 bg-[#0d1320] p-8 shadow-[0_0_60px_rgba(239,68,68,0.15)]">
      <div class="flex items-center gap-3 mb-4">
        <span class="material-symbols-outlined text-red-400 text-3xl" style="font-variation-settings:'FILL' 1">warning</span>
        <h3 class="text-xl font-bold text-red-400" style="font-family:'Space Grotesk',sans-serif">CRITICAL — Save Your Private Key</h3>
      </div>
      <p class="text-sm text-slate-300 mb-4 leading-relaxed">Your managed wallet has been created. <strong class="text-white">This is the ONLY time your private key will be shown.</strong> Copy it now and import it into Phantom or another Solana wallet to make real transactions.</p>
      <div class="mb-3">
        <label class="text-[10px] uppercase tracking-widest text-slate-500 mb-1 block" style="font-family:'JetBrains Mono',monospace">Wallet Address</label>
        <div class="bg-slate-900/80 border border-slate-700 rounded-lg px-4 py-3 text-xs text-cyan-300 break-all" style="font-family:'JetBrains Mono',monospace">${walletAddress}</div>
      </div>
      <div class="mb-4">
        <label class="text-[10px] uppercase tracking-widest text-red-400 mb-1 block" style="font-family:'JetBrains Mono',monospace">Private Key (Base58)</label>
        <div id="pkDisplay" class="bg-red-950/30 border border-red-500/30 rounded-lg px-4 py-3 text-xs text-red-200 break-all select-all cursor-text" style="font-family:'JetBrains Mono',monospace;word-break:break-all">${privateKey}</div>
      </div>
      <div class="flex gap-3 mb-4">
        <button id="copyPkBtn" class="flex-1 rounded-lg bg-slate-800 border border-slate-600 text-white font-bold py-2 text-sm hover:bg-slate-700 transition-colors" type="button">📋 Copy Private Key</button>
      </div>
      <div class="bg-yellow-900/20 border border-yellow-500/20 rounded-lg p-3 mb-4">
        <p class="text-[11px] text-yellow-300" style="font-family:'JetBrains Mono',monospace">⚠ Import this key into Phantom Wallet to sign real Solana transactions. Never share it with anyone.</p>
      </div>
      <button id="ackPkBtn" class="w-full rounded-lg bg-red-600 hover:bg-red-500 text-white font-bold py-3 text-sm transition-colors" type="button" disabled>I've saved my private key (5s)</button>
    </div>
  `;
  document.body.appendChild(modal);

  // Prevent dismissal for 5 seconds
  const ackBtn = $("#ackPkBtn", modal);
  let countdown = 5;
  const timer = setInterval(() => {
    countdown--;
    if (countdown > 0) {
      ackBtn.textContent = `I've saved my private key (${countdown}s)`;
    } else {
      clearInterval(timer);
      ackBtn.disabled = false;
      ackBtn.textContent = "I've saved my private key — Continue";
    }
  }, 1000);

  $("#copyPkBtn", modal)?.addEventListener("click", () => {
    navigator.clipboard.writeText(privateKey).then(() => {
      $("#copyPkBtn", modal).textContent = "✅ Copied!";
    });
  });

  ackBtn?.addEventListener("click", () => {
    modal.remove();
    go(redirectUrl);
  });
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
  showWalletManageModal();
}

function showWalletManageModal() {
  let modal = $("#walletManageModal");
  if (modal) modal.remove();
  modal = document.createElement("div");
  modal.id = "walletManageModal";
  modal.className = "fixed inset-0 z-[80] flex items-center justify-center bg-black/70 px-4";
  modal.innerHTML = `
    <div class="w-full max-w-md rounded-2xl border border-purple-500/20 bg-[#0d1320] p-6 shadow-[0_0_60px_rgba(168,85,247,0.1)]">
      <div class="flex items-center justify-between mb-5">
        <h3 class="text-lg font-bold" style="font-family:'Space Grotesk',sans-serif">Wallet Manager</h3>
        <button id="closeWalletManage" class="text-slate-400 hover:text-white text-xl" type="button">✕</button>
      </div>
      <p class="text-sm text-slate-400 mb-6">Link an existing Solana wallet or create a new managed one.</p>
      <div class="space-y-3">
        <button id="wmLinkExternal" class="w-full flex items-center gap-4 p-4 rounded-xl border border-purple-500/20 bg-purple-500/5 hover:bg-purple-500/10 transition-colors text-left">
          <span class="material-symbols-outlined text-purple-400 text-2xl">link</span>
          <div>
            <div class="font-bold text-sm">Link Existing Wallet</div>
            <div class="text-[11px] text-slate-500">Paste your Phantom / Solflare address</div>
          </div>
        </button>
        <button id="wmCreateManaged" class="w-full flex items-center gap-4 p-4 rounded-xl border border-cyan-500/20 bg-cyan-500/5 hover:bg-cyan-500/10 transition-colors text-left">
          <span class="material-symbols-outlined text-cyan-400 text-2xl">add_circle</span>
          <div>
            <div class="font-bold text-sm">Create Managed Wallet</div>
            <div class="text-[11px] text-slate-500">Generate a new Solana testnet keypair</div>
          </div>
        </button>
      </div>
    </div>
  `;
  document.body.appendChild(modal);

  $("#closeWalletManage", modal)?.addEventListener("click", () => modal.remove());
  modal.addEventListener("click", (e) => { if (e.target === modal) modal.remove(); });

  $("#wmLinkExternal", modal)?.addEventListener("click", () => {
    modal.remove();
    showLinkWalletModal();
  });
  $("#wmCreateManaged", modal)?.addEventListener("click", () => {
    modal.remove();
    createManagedWallet(localStorage.getItem(SOLCLUB_ROLE_KEY) || "client").catch((e) => alert(e.message));
  });
}

function updateClientLivePanel(snapshot, preview) {
  const panel = getOrCreateLivePanel();
  const displayName = snapshot.username || snapshot.wallet || "-";
  panel.innerHTML = `
    <div class="font-bold tracking-wider uppercase text-xs mb-2">Live Client Data</div>
    <div class="grid grid-cols-2 md:grid-cols-6 gap-3">
      <div><div class="text-[10px] uppercase text-slate-300">Identity</div><div class="font-mono text-xs">${displayName}</div></div>
      <div><div class="text-[10px] uppercase text-slate-300">Tier</div><div class="font-bold">${String(snapshot.tier || "-").toUpperCase()}</div></div>
      <div><div class="text-[10px] uppercase text-slate-300">Transactions</div><div class="font-bold">${snapshot.total_transactions || 0}</div></div>
      <div><div class="text-[10px] uppercase text-slate-300">Spent</div><div class="font-bold">${snapshot.total_spent || 0} SOL</div></div>
      <div><div class="text-[10px] uppercase text-slate-300">Cashback</div><div class="font-bold">${snapshot.total_cashback || 0} SOL</div></div>
      <div><div class="text-[10px] uppercase text-slate-300">Next Reward</div><div class="font-bold">${preview.reward_tier || "-"}</div></div>
    </div>
  `;

  // Hydrate dashboard cards if present
  hydrateDashboardCards(snapshot, preview);
}

function hydrateDashboardCards(snapshot, preview) {
  const el = (id) => document.getElementById(id);
  const username = snapshot.username || snapshot.wallet || "Agent";
  if (el("dashUsername")) el("dashUsername").textContent = username;
  if (el("dashTier")) el("dashTier").textContent = String(snapshot.tier || "Bronze").toUpperCase();
  if (el("dashTotalCashback")) el("dashTotalCashback").textContent = snapshot.total_cashback || "0";
  if (el("dashNftCount")) el("dashNftCount").textContent = `${snapshot.nft_count || 0} Collected`;
  if (el("dashTxCount")) el("dashTxCount").textContent = `${snapshot.total_transactions || 0} Txns`;
  if (el("dashXp")) el("dashXp").textContent = `XP: ${(snapshot.total_transactions || 0) * 10}`;
  if (el("dashCashbackCard")) el("dashCashbackCard").textContent = `${snapshot.total_cashback || 0} SOL`;
  if (el("dashSpentCard")) el("dashSpentCard").textContent = `${snapshot.total_spent || 0} SOL`;
  if (el("dashBadgeCard")) el("dashBadgeCard").textContent = `${snapshot.nft_count || 0} NFTs`;

  // Render activity list with real transaction data
  const actList = el("dashActivityList");
  if (actList && snapshot.recent_transactions && snapshot.recent_transactions.length) {
    actList.innerHTML = snapshot.recent_transactions.slice(0, 5).map((tx) => {
      const date = tx.created_at ? new Date(tx.created_at).toLocaleString() : "-";
      const sig = tx.signature ? tx.signature.slice(0, 12) + "..." : "-";
      return `
        <div class="bg-[#171b27] hover:bg-[#1b1f2b] p-4 rounded-2xl flex items-center justify-between transition-colors">
          <div class="flex items-center gap-4 md:gap-6">
            <div class="w-10 h-10 md:w-12 md:h-12 bg-slate-900 rounded-xl flex items-center justify-center border border-white/5">
              <span class="material-symbols-outlined text-cyan-400">shopping_cart</span>
            </div>
            <div>
              <p class="font-headline font-bold text-on-background text-sm">${sig}</p>
              <p class="text-xs text-slate-500">${date}</p>
            </div>
          </div>
          <div class="text-right">
            <p class="font-headline font-bold text-cyan-400">${tx.amount || 0} SOL</p>
            <p class="text-[10px] text-slate-500 uppercase">Merchant #${tx.merchant_id || 1}</p>
          </div>
        </div>
      `;
    }).join("");
  } else if (actList) {
    actList.innerHTML = `
      <div class="bg-[#171b27] p-6 rounded-2xl text-center">
        <span class="material-symbols-outlined text-slate-600 text-4xl mb-2 block">receipt_long</span>
        <p class="text-slate-500 text-sm">No transactions yet. Make your first purchase to see activity here.</p>
      </div>
    `;
  }

  // Update nav button text if wallet is connected
  const navBtn = el("navConnectWallet");
  if (navBtn && snapshot.wallet) {
    // Show "Wallet 1 · X.XX SOL" instead of raw address
    fetchSolBalance(snapshot.wallet).then(balance => {
      navBtn.textContent = `Wallet 1 \u00B7 ${balance} SOL`;
    });
  }
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
  hydrateMerchantAnalytics(analytics);

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

function hydrateMerchantAnalytics(analytics) {
  const el = (id) => document.getElementById(id);
  // Total Transactions
  if (el("analyticsTxCount")) {
    el("analyticsTxCount").innerHTML = `${(analytics.transactions_count || 0).toLocaleString()} <span class="text-sm font-body font-normal text-tertiary">${analytics.unique_clients || 0} clients</span>`;
  }
  // Rewards Issued (cashback volume)
  if (el("analyticsRewardsIssued")) {
    el("analyticsRewardsIssued").innerHTML = `${analytics.cashback_volume || 0} <span class="text-xs text-slate-400 uppercase tracking-tighter">SOL</span>`;
  }
  // User Retention Rate (unique clients as % — use ratio of clients with >1 tx)
  if (el("analyticsRetention")) {
    const pct = analytics.unique_clients && analytics.transactions_count
      ? Math.min(100, Math.round((analytics.unique_clients / Math.max(analytics.transactions_count, 1)) * 100))
      : 0;
    el("analyticsRetention").textContent = `${pct}%`;
  }
  // Live Transactions list
  const txList = el("analyticsLiveTxList");
  if (txList && analytics.recent_transactions && analytics.recent_transactions.length) {
    txList.innerHTML = analytics.recent_transactions.map(tx => {
      const wallet = tx.wallet_address || "-";
      const shortWallet = wallet.length > 12 ? wallet.slice(0, 6) + "\u2026" + wallet.slice(-4) : wallet;
      const ago = tx.created_at ? timeAgo(tx.created_at) : "-";
      return `
        <div class="flex items-center justify-between group cursor-pointer">
          <div class="flex items-center gap-4">
            <div class="w-10 h-10 rounded-full bg-[#313441] flex items-center justify-center">
              <span class="material-symbols-outlined text-tertiary text-sm">arrow_downward</span>
            </div>
            <div>
              <p class="text-sm font-bold text-white">${shortWallet}</p>
              <p class="text-[10px] text-slate-500 uppercase">${ago}</p>
            </div>
          </div>
          <div class="text-right">
            <p class="text-sm font-headline font-bold text-tertiary">+${tx.amount || 0} SOL</p>
            <p class="text-[10px] text-slate-500 uppercase">Confirmed</p>
          </div>
        </div>
      `;
    }).join("");
  } else if (txList) {
    txList.innerHTML = `<div class="text-center text-slate-500 text-sm py-4">No transactions yet</div>`;
  }
  // Bar chart — populate proportionally from recent transactions
  const barChart = el("analyticsBarChart");
  if (barChart && analytics.recent_transactions) {
    const txs = analytics.recent_transactions;
    const maxAmt = Math.max(...txs.map(t => t.amount || 0), 0.01);
    const bars = txs.map((tx, i) => {
      const pct = Math.max(10, Math.round(((tx.amount || 0) / maxAmt) * 100));
      const isMax = (tx.amount || 0) === maxAmt;
      return `<div class="w-full ${isMax ? 'bg-[#b76dff]' : 'bg-[#171b27] hover:bg-[#b76dff]/40'} rounded-t-lg transition-all cursor-pointer relative group" style="height:${pct}%">
        <div class="absolute -top-10 left-1/2 -translate-x-1/2 bg-[#353945] px-2 py-1 rounded text-[10px] opacity-0 group-hover:opacity-100 transition-opacity whitespace-nowrap">${tx.amount || 0} SOL</div>
      </div>`;
    }).join("");
    // Pad to 10 bars if fewer
    const padded = bars + Array(Math.max(0, 10 - txs.length)).fill('<div class="w-full bg-[#171b27] rounded-t-lg" style="height:5%"></div>').join("");
    barChart.innerHTML = padded;
  }
}

function timeAgo(dateStr) {
  try {
    const diff = Date.now() - new Date(dateStr).getTime();
    const mins = Math.floor(diff / 60000);
    if (mins < 1) return "just now";
    if (mins < 60) return `${mins} min ago`;
    const hrs = Math.floor(mins / 60);
    if (hrs < 24) return `${hrs} hr ago`;
    const days = Math.floor(hrs / 24);
    return `${days}d ago`;
  } catch { return "-"; }
}

function wireCommonButtons(session) {
  $$('button').forEach((button) => {
    if (button.type === "submit") return;
    const label = findClickableLabel(button);

    if (label.includes("connect wallet")) {
      button.addEventListener("click", (event) => {
        event.preventDefault();
        if (session && session.authenticated) {
          showWalletManageModal();
        } else {
          go("/auth");
        }
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

    if (label.includes("link wallet") || label.includes("link real wallet")) {
      button.addEventListener("click", (event) => {
        event.preventDefault();
        showLinkWalletModal();
      });
      return;
    }
  });
}

function showLinkWalletModal() {
  let modal = $("#linkWalletModal");
  if (modal) modal.remove();
  modal = document.createElement("div");
  modal.id = "linkWalletModal";
  modal.className = "fixed inset-0 z-[90] flex items-center justify-center bg-black/70 px-4";
  modal.innerHTML = `
    <div class="w-full max-w-md rounded-2xl border border-purple-500/20 bg-[#0d1320] p-6">
      <div class="flex items-center justify-between mb-4">
        <h3 class="text-lg font-bold" style="font-family:'Space Grotesk',sans-serif">Link Real Solana Wallet</h3>
        <button id="closeLinkWallet" class="text-slate-400 hover:text-white" type="button">✕</button>
      </div>
      <p class="text-sm text-slate-400 mb-4">Paste your real Solana wallet address (mainnet) to link it to your SolClub account for real transactions.</p>
      <form id="linkWalletForm">
        <div class="mb-3">
          <label class="text-[10px] uppercase tracking-widest text-slate-500 mb-1 block" style="font-family:'JetBrains Mono',monospace">Wallet Address</label>
          <input id="linkWalletAddress" class="w-full bg-slate-900/80 border border-slate-600 rounded-lg px-4 py-3 text-sm text-white" style="font-family:'JetBrains Mono',monospace" placeholder="Your Solana wallet address..." required />
        </div>
        <div class="mb-4">
          <label class="text-[10px] uppercase tracking-widest text-slate-500 mb-1 block" style="font-family:'JetBrains Mono',monospace">Network</label>
          <select id="linkWalletNetwork" class="w-full bg-slate-900/80 border border-slate-600 rounded-lg px-4 py-3 text-sm text-white">
            <option value="mainnet-beta">Mainnet</option>
            <option value="testnet">Testnet</option>
            <option value="devnet">Devnet</option>
          </select>
        </div>
        <p id="linkWalletStatus" class="text-xs text-slate-500 mb-3" style="font-family:'JetBrains Mono',monospace"></p>
        <div class="flex gap-3">
          <button type="submit" class="flex-1 rounded-lg bg-purple-600 hover:bg-purple-500 text-white font-bold py-2 text-sm transition-colors">Link Wallet</button>
          <button type="button" id="cancelLinkWallet" class="rounded-lg border border-slate-600 px-4 py-2 text-sm text-slate-300 hover:text-white transition-colors">Cancel</button>
        </div>
      </form>
    </div>
  `;
  document.body.appendChild(modal);

  $("#closeLinkWallet", modal)?.addEventListener("click", () => modal.remove());
  $("#cancelLinkWallet", modal)?.addEventListener("click", () => modal.remove());

  $("#linkWalletForm", modal)?.addEventListener("submit", async (e) => {
    e.preventDefault();
    const addr = $("#linkWalletAddress", modal)?.value?.trim();
    const network = $("#linkWalletNetwork", modal)?.value || "mainnet-beta";
    const status = $("#linkWalletStatus", modal);
    if (!addr) return;
    try {
      if (status) status.textContent = "Linking...";
      await apiJson(`${AUTH_BASE}/wallet/link`, {
        method: "POST",
        body: JSON.stringify({ wallet_address: addr, network }),
      });
      if (status) status.textContent = "✅ Wallet linked successfully!";
      setTimeout(() => { modal.remove(); loadWalletList(); }, 1500);
    } catch (err) {
      if (status) status.textContent = err.message;
    }
  });
}

async function loadWalletList() {
  try {
    const data = await apiJson(`${AUTH_BASE}/wallet/list`);
    renderWalletList(data.wallets || []);
  } catch { /* ignore */ }
}

function renderWalletList(wallets) {
  let container = $("#walletListPanel");
  if (!container) {
    container = document.createElement("section");
    container.id = "walletListPanel";
    container.className = "mb-6 p-4 rounded-2xl border border-purple-400/20 bg-purple-500/5 text-sm";
    const livePanel = $("#solclubLivePanel");
    if (livePanel && livePanel.parentNode) {
      livePanel.parentNode.insertBefore(container, livePanel.nextSibling);
    } else {
      const main = $("main");
      if (main) main.prepend(container);
    }
  }
  if (!wallets.length) {
    container.innerHTML = `
      <div class="flex items-center justify-between">
        <div class="font-bold tracking-wider uppercase text-xs">Linked Wallets</div>
        <button id="btnLinkRealWallet" class="text-xs text-purple-400 hover:text-purple-300 font-bold uppercase tracking-wider">+ Link Real Wallet</button>
      </div>
      <p class="text-xs text-slate-500 mt-2">No wallets linked yet. Link a real Solana wallet to make on-chain transactions.</p>
    `;
  } else {
    const rows = wallets.map(w => `
      <div class="flex items-center justify-between py-2 border-b border-white/5 last:border-0">
        <div>
          <span class="font-mono text-xs">${w.wallet_address || "-"}</span>
          <span class="ml-2 text-[9px] uppercase px-2 py-0.5 rounded ${w.managed_wallet ? 'bg-cyan-500/10 text-cyan-400' : 'bg-purple-500/10 text-purple-400'}">${w.managed_wallet ? 'Managed' : 'External'}</span>
          <span class="ml-1 text-[9px] uppercase px-2 py-0.5 rounded bg-slate-700 text-slate-300">${w.network || 'testnet'}</span>
          ${w.is_primary ? '<span class="ml-1 text-[9px] uppercase px-2 py-0.5 rounded bg-green-500/10 text-green-400">Primary</span>' : ''}
        </div>
      </div>
    `).join("");
    container.innerHTML = `
      <div class="flex items-center justify-between mb-2">
        <div class="font-bold tracking-wider uppercase text-xs">Linked Wallets (${wallets.length})</div>
        <button id="btnLinkRealWallet" class="text-xs text-purple-400 hover:text-purple-300 font-bold uppercase tracking-wider">+ Link Real Wallet</button>
      </div>
      ${rows}
    `;
  }
  $("#btnLinkRealWallet", container)?.addEventListener("click", (e) => {
    e.preventDefault();
    showLinkWalletModal();
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

// ─── Payment Page ─────────────────────────────────────────────────────────────
function wirePayPage(session) {
  const tabScan   = $("#tabScan");
  const tabManual = $("#tabManual");
  const scanSec   = $("#scanSection");
  const manualSec = $("#manualSection");
  const confirmSec= $("#payConfirm");
  const reviewBtn = $("#btnReviewPay");
  const confirmBtn= $("#btnConfirmPay");
  const payStatus = $("#payStatus");
  let currentPayload = null;

  function setTab(mode) {
    if (mode === "scan") {
      tabScan.className   = tabScan.className.replace("text-slate-500", "text-cyan-400").replace("hover:text-slate-300","") + " bg-cyan-500/20 border border-cyan-500/30";
      tabManual.className = "flex-1 py-3 rounded-lg text-sm font-headline font-bold uppercase tracking-wider transition-all text-slate-500 hover:text-slate-300";
      scanSec.classList.remove("hidden");
      manualSec.classList.add("hidden");
      confirmSec.classList.add("hidden");
      reviewBtn.classList.remove("hidden");
      startCamera();
    } else {
      tabManual.className = tabManual.className.replace("text-slate-500","text-cyan-400").replace("hover:text-slate-300","") + " bg-cyan-500/20 border border-cyan-500/30";
      tabScan.className   = "flex-1 py-3 rounded-lg text-sm font-headline font-bold uppercase tracking-wider transition-all text-slate-500 hover:text-slate-300";
      scanSec.classList.add("hidden");
      manualSec.classList.remove("hidden");
      confirmSec.classList.add("hidden");
      reviewBtn.classList.remove("hidden");
      stopCamera();
    }
  }

  tabScan?.addEventListener("click",   () => setTab("scan"));
  tabManual?.addEventListener("click", () => setTab("manual"));

  // Camera QR scanning
  let stream = null;
  async function startCamera() {
    const video = $("#qrVideo");
    const errDiv = $("#cameraError");
    if (!video) return;
    try {
      stream = await navigator.mediaDevices.getUserMedia({ video: { facingMode: "environment" } });
      video.srcObject = stream;
      if (errDiv) errDiv.classList.add("hidden");
      scanQRFrames(video);
    } catch {
      if (errDiv) errDiv.classList.remove("hidden");
    }
  }
  function stopCamera() {
    if (stream) { stream.getTracks().forEach(t => t.stop()); stream = null; }
  }

  function scanQRFrames(video) {
    if (!stream) return;
    // Use BarcodeDetector if available (Chrome, Android)
    if ("BarcodeDetector" in window) {
      const detector = new BarcodeDetector({ formats: ["qr_code"] });
      const frame = async () => {
        if (!stream) return;
        try {
          const codes = await detector.detect(video);
          if (codes.length > 0) { onQRDetected(codes[0].rawValue); return; }
        } catch {}
        requestAnimationFrame(frame);
      };
      requestAnimationFrame(frame);
    }
  }

  function onQRDetected(data) {
    stopCamera();
    // Parse solana:<address>?amount=<n>&reference=<ref>&label=<label>
    try {
      let addr = data, amount = 0, ref = "", label = "";
      if (data.startsWith("solana:")) {
        const url = new URL(data.replace("solana:", "solana://x/").replace("solana://x/",""));
        addr   = data.split("?")[0].replace("solana:","");
        amount = parseFloat(url.searchParams.get("amount") || "0");
        ref    = url.searchParams.get("reference") || "";
        label  = url.searchParams.get("label") || "";
      }
      showPayConfirm(addr, amount, ref);
    } catch {
      showPayConfirm(data, 0, "");
    }
  }

  function showPayConfirm(addr, amount, ref) {
    currentPayload = { merchant_wallet: addr, amount, reference: ref };
    const short = addr.length > 20 ? addr.slice(0, 8) + "…" + addr.slice(-6) : addr;
    const el = id => document.getElementById(id);
    if (el("confirmAddr"))   el("confirmAddr").textContent   = short;
    if (el("confirmAmount")) el("confirmAmount").textContent = `${amount || "?"} SOL`;
    if (ref && el("confirmRef")) { el("confirmRef").textContent = ref; el("confirmRefRow").classList.remove("hidden"); }
    confirmSec.classList.remove("hidden");
    reviewBtn.classList.add("hidden");
    manualSec.classList.add("hidden");
    scanSec.classList.add("hidden");
  }

  // Manual review
  reviewBtn?.addEventListener("click", () => {
    const addr   = $("#payAddress")?.value?.trim();
    const amount = parseFloat($("#payAmount")?.value || "0");
    if (!addr) { alert("Please enter a wallet address."); return; }
    if (amount <= 0) { alert("Please enter a valid amount greater than 0."); return; }
    showPayConfirm(addr, amount, "");
  });

  // Confirm & send
  confirmBtn?.addEventListener("click", async () => {
    if (!currentPayload) return;
    if (!session.wallet) { alert("Connect a wallet first to make payments."); return; }
    confirmBtn.disabled = true;
    confirmBtn.textContent = "Sending…";
    if (payStatus) payStatus.textContent = "";
    const resultDiv = $("#payResult");
    const onChainDiv = $("#payResultOnChain");
    const solanaPayDiv = $("#payResultSolanaPay");
    const cashbackDiv = $("#payResultCashback");
    try {
      const res = await apiJson(`${AUTH_BASE}/payment/send`, {
        method: "POST",
        body: JSON.stringify(currentPayload),
      });

      if (res.solana_pay_url) {
        // External wallet — show Solana Pay link
        if (payStatus) {
          payStatus.className = "text-center text-xs mt-3 font-['JetBrains_Mono'] text-purple-400";
          payStatus.textContent = "Open the payment link in your Solana wallet.";
        }
        if (resultDiv) resultDiv.classList.remove("hidden");
        if (solanaPayDiv) {
          solanaPayDiv.classList.remove("hidden");
          const link = $("#paySolanaPayLink");
          if (link) { link.href = res.solana_pay_url; }
        }
        if (onChainDiv) onChainDiv.classList.add("hidden");
        if (cashbackDiv) cashbackDiv.classList.add("hidden");
        confirmBtn.textContent = "Awaiting Wallet Approval";
      } else {
        // Managed or fallback — show result
        if (payStatus) {
          payStatus.className = "text-center text-xs mt-3 font-['JetBrains_Mono'] text-tertiary";
          payStatus.textContent = res.on_chain
            ? `✅ On-chain transaction confirmed!`
            : `✅ Payment recorded. Cashback: ${res.cashback} SOL · Tier: ${res.tier}`;
        }
        if (resultDiv) resultDiv.classList.remove("hidden");
        if (solanaPayDiv) solanaPayDiv.classList.add("hidden");
        if (res.on_chain && res.signature) {
          if (onChainDiv) onChainDiv.classList.remove("hidden");
          const explorerLink = $("#payExplorerLink");
          const network = "testnet";
          const explorerUrl = `https://explorer.solana.com/tx/${res.signature}?cluster=${network}`;
          if (explorerLink) { explorerLink.href = explorerUrl; explorerLink.textContent = res.signature; }
        } else {
          if (onChainDiv) onChainDiv.classList.add("hidden");
        }
        if (res.cashback && res.cashback > 0) {
          if (cashbackDiv) cashbackDiv.classList.remove("hidden");
          const cashbackAmt = $("#payResultCashbackAmt");
          if (cashbackAmt) cashbackAmt.textContent = `${res.cashback} SOL`;
        } else {
          if (cashbackDiv) cashbackDiv.classList.add("hidden");
        }
        confirmBtn.textContent = "Payment Sent ✓";
      }
    } catch (err) {
      if (payStatus) {
        payStatus.className = "text-center text-xs mt-3 font-['JetBrains_Mono'] text-red-400";
        payStatus.textContent = err.message;
      }
      confirmBtn.disabled = false;
      confirmBtn.textContent = "Confirm & Send";
    }
  });

  // New Payment button
  $("#btnNewPayment")?.addEventListener("click", () => {
    currentPayload = null;
    confirmSec.classList.add("hidden");
    const resultDiv = $("#payResult");
    if (resultDiv) resultDiv.classList.add("hidden");
    scanSec.classList.remove("hidden");
    reviewBtn.classList.remove("hidden");
    if (payStatus) payStatus.textContent = "";
    confirmBtn.disabled = false;
    confirmBtn.innerHTML = `<span class="material-symbols-outlined align-middle mr-2 text-base">send</span>Confirm & Send`;
    if ($("#payAddress")) $("#payAddress").value = "";
    if ($("#payAmount")) $("#payAmount").value = "";
    if ($("#payNote")) $("#payNote").value = "";
    setTab("scan");
  });

  // Default to scan tab
  setTab("scan");
}

// ─── Notifications ─────────────────────────────────────────────────────────────
function wireNotifications(session) {
  const btn = $("#btnNotifications");
  if (!btn) return;
  let panel = null;

  btn.addEventListener("click", async (e) => {
    e.stopPropagation();
    if (panel) { panel.remove(); panel = null; return; }

    panel = document.createElement("div");
    panel.id = "notifPanel";
    panel.className = "fixed top-16 right-4 md:right-8 z-[90] w-80 max-w-[calc(100vw-2rem)] bg-[#0d1320] border border-white/10 rounded-2xl shadow-[0_0_40px_rgba(0,0,0,0.6)] overflow-hidden";
    panel.innerHTML = `
      <div class="px-5 py-4 border-b border-white/5 flex items-center justify-between">
        <span class="font-headline font-bold text-sm">Notifications</span>
        <span id="notifClear" class="text-[10px] text-cyan-400 cursor-pointer uppercase tracking-wider hover:text-cyan-300">Clear all</span>
      </div>
      <div id="notifList" class="max-h-72 overflow-y-auto divide-y divide-white/5">
        <div class="flex items-center justify-center py-8 text-slate-600 text-sm">Loading…</div>
      </div>
    `;
    document.body.appendChild(panel);
    document.addEventListener("click", () => { panel?.remove(); panel = null; }, { once: true });
    $("#notifClear", panel)?.addEventListener("click", () => { panel.remove(); panel = null; });

    try {
      const wallet = session.wallet || "";
      if (!wallet) throw new Error("no wallet");
      const [txData, rewData] = await Promise.all([
        apiJson(`/ui/api/client/${encodeURIComponent(wallet)}/transactions?limit=5`),
        apiJson(`/ui/api/client/${encodeURIComponent(wallet)}/rewards?merchant_id=1&limit=5`),
      ]);
      const items = [
        ...(txData.items || []).map(tx => ({ icon: "payments", color: "text-cyan-400", text: `Payment: ${tx.amount} SOL`, sub: tx.created_at ? new Date(tx.created_at).toLocaleDateString() : "" })),
        ...(rewData.items || []).map(r => ({ icon: "card_giftcard", color: "text-tertiary", text: `Cashback: ${r.cashback_amount} SOL (${r.reward_tier})`, sub: r.created_at ? new Date(r.created_at).toLocaleDateString() : "" })),
      ].sort((a, b) => (b.sub > a.sub ? 1 : -1)).slice(0, 8);

      const list = $("#notifList", panel);
      if (list) {
        list.innerHTML = items.length ? items.map(it => `
          <div class="flex items-center gap-3 px-5 py-3 hover:bg-white/5 transition-colors">
            <span class="material-symbols-outlined ${it.color} text-xl" style="font-variation-settings:'FILL' 1">${it.icon}</span>
            <div class="flex-1 min-w-0">
              <div class="text-xs font-headline font-bold truncate">${it.text}</div>
              <div class="text-[10px] text-slate-600">${it.sub}</div>
            </div>
          </div>
        `).join("") : `<div class="flex items-center justify-center py-8 text-slate-600 text-sm">No notifications yet</div>`;
      }
    } catch {
      const list = $("#notifList", panel);
      if (list) list.innerHTML = `<div class="flex items-center justify-center py-8 text-slate-600 text-sm">No notifications yet</div>`;
    }
  });
}

// ─── Settings Modal ─────────────────────────────────────────────────────────────
function wireSettings(session) {
  const btn = $("#btnSettings");
  if (!btn) return;

  btn.addEventListener("click", async (e) => {
    e.preventDefault();
    let modal = $("#settingsModal");
    if (modal) { modal.remove(); return; }

    modal = document.createElement("div");
    modal.id = "settingsModal";
    modal.className = "fixed inset-0 z-[85] flex items-center justify-center bg-black/70 px-4";
    modal.innerHTML = `
      <div class="w-full max-w-md rounded-2xl border border-white/10 bg-[#0d1320] overflow-hidden shadow-[0_0_60px_rgba(0,0,0,0.8)]">
        <div class="flex items-center justify-between px-6 py-5 border-b border-white/5">
          <h3 class="font-headline font-bold text-lg">Settings</h3>
          <button id="closeSettings" class="material-symbols-outlined text-slate-400 hover:text-white text-2xl">close</button>
        </div>
        <div class="px-6 py-5 space-y-5">
          <div>
            <div class="text-[10px] uppercase tracking-widest text-slate-500 mb-2 font-['JetBrains_Mono']">Account</div>
            <div class="space-y-2">
              <div class="flex items-center justify-between bg-slate-900/50 rounded-xl px-4 py-3">
                <span class="text-sm text-slate-400">Username</span>
                <span id="settingUsername" class="text-sm font-headline font-bold text-primary">${session.username || "—"}</span>
              </div>
              <div class="flex items-center justify-between bg-slate-900/50 rounded-xl px-4 py-3">
                <span class="text-sm text-slate-400">Role</span>
                <span class="text-sm font-headline font-bold uppercase text-secondary">${session.role || "client"}</span>
              </div>
              <div class="flex items-center justify-between bg-slate-900/50 rounded-xl px-4 py-3">
                <span class="text-sm text-slate-400">Wallet</span>
                <span class="text-xs font-['JetBrains_Mono'] text-slate-300">${session.wallet ? session.wallet.slice(0,8)+"…"+session.wallet.slice(-6) : "None"}</span>
              </div>
            </div>
          </div>
          <div>
            <div class="text-[10px] uppercase tracking-widest text-slate-500 mb-2 font-['JetBrains_Mono']">Wallet</div>
            <button id="settingsManageWallet" class="w-full flex items-center gap-3 bg-slate-900/50 rounded-xl px-4 py-3 hover:bg-slate-800/60 transition-colors text-left">
              <span class="material-symbols-outlined text-purple-400">account_balance_wallet</span>
              <span class="text-sm font-headline font-bold">Manage Wallets</span>
              <span class="material-symbols-outlined text-slate-600 ml-auto">chevron_right</span>
            </button>
          </div>
          <div class="pt-2 border-t border-white/5">
            <button id="settingsLogout" class="w-full flex items-center gap-3 bg-red-950/30 border border-red-500/20 rounded-xl px-4 py-3 hover:bg-red-900/30 transition-colors text-left">
              <span class="material-symbols-outlined text-red-400">logout</span>
              <span class="text-sm font-headline font-bold text-red-400">Sign Out</span>
            </button>
          </div>
        </div>
      </div>
    `;
    document.body.appendChild(modal);
    modal.addEventListener("click", ev => { if (ev.target === modal) modal.remove(); });
    $("#closeSettings", modal)?.addEventListener("click", () => modal.remove());
    $("#settingsManageWallet", modal)?.addEventListener("click", () => { modal.remove(); showWalletManageModal(); });
    $("#settingsLogout", modal)?.addEventListener("click", () => logout().catch(err => alert(err.message)));

    // Fetch real username if empty
    if (!session.username) {
      try {
        const obs = await getOnboardingStatus();
        const u = obs.username || "";
        const el = $("#settingUsername", modal);
        if (el && u) el.textContent = u;
      } catch {}
    }
  });
}

// ─── Merchant Receive Page ─────────────────────────────────────────────────────
function wireMerchantReceive(session) {
  const staticBtn  = $("#btnStaticQR");
  const curtain    = $("#staticQRCurtain");
  const closeBtn   = $("#closeStaticQR");
  const genBtn     = $("#btnGenerateQR");
  const newQRBtn   = $("#btnNewQR");
  const copyBtn    = $("#btnCopyPayLink");
  const dynSection = $("#dynamicQRSection");
  let lastPayLink  = "";

  // Load static QR on curtain open
  async function loadStaticQR() {
    try {
      const info = await apiJson(`${AUTH_BASE}/merchant/wallet-info`);
      const addr = info.wallet || session.wallet || "";
      const addrEl = $("#staticWalletAddr");
      if (addrEl) addrEl.textContent = addr;
      const canvas = $("#staticQRCanvas");
      if (canvas && addr && window.QRCode) {
        const ctx = canvas.getContext("2d");
        ctx.clearRect(0, 0, canvas.width, canvas.height);
        QRCode.toCanvas(canvas, `solana:${addr}`, { width: 250, margin: 2, color: { dark: "#000000", light: "#ffffff" } });
      }
    } catch (err) {
      console.warn("Static QR load failed:", err.message);
    }
  }

  // Static QR curtain
  staticBtn?.addEventListener("click", async () => {
    curtain.classList.add("open");
    await loadStaticQR();
  });
  closeBtn?.addEventListener("click", () => curtain.classList.remove("open"));

  // Dynamic QR generation
  genBtn?.addEventListener("click", async () => {
    const amount = parseFloat($("#reqAmount")?.value || "0");
    const label  = ($("#reqLabel")?.value || "SolClub Payment").trim();
    if (amount <= 0) { alert("Enter a valid amount."); return; }
    genBtn.disabled = true;
    genBtn.textContent = "Generating…";
    try {
      const merchantWallet = session.wallet || "";
      const res = await apiJson(`${AUTH_BASE}/payment/create`, {
        method: "POST",
        body: JSON.stringify({ amount, label, merchant_wallet: merchantWallet }),
      });
      // Solana Pay URL: solana:<address>?amount=<n>&reference=<ref>&label=<label>
      const solanaPayUrl = `solana:${merchantWallet}?amount=${amount}&reference=${res.reference}&label=${encodeURIComponent(label)}`;
      lastPayLink = solanaPayUrl;
      const canvas = $("#dynamicQRCanvas");
      if (canvas && window.QRCode) {
        const ctx = canvas.getContext("2d");
        ctx.clearRect(0, 0, canvas.width, canvas.height);
        QRCode.toCanvas(canvas, solanaPayUrl, { width: 220, margin: 2, color: { dark: "#000000", light: "#ffffff" } });
      }
      const amtLabel = $("#dynAmountLabel");
      const refLabel = $("#dynRefLabel");
      if (amtLabel) amtLabel.textContent = `${amount} SOL — ${label}`;
      if (refLabel) refLabel.textContent  = `REF: ${res.reference}`;
      dynSection.classList.remove("hidden");
    } catch (err) {
      alert(err.message);
    } finally {
      genBtn.disabled = false;
      genBtn.innerHTML = `<span class="material-symbols-outlined align-middle mr-2 text-base">qr_code_2</span>Generate Payment QR`;
    }
  });

  newQRBtn?.addEventListener("click", () => {
    dynSection.classList.add("hidden");
    if ($("#reqAmount")) $("#reqAmount").value = "";
    if ($("#reqLabel"))  $("#reqLabel").value  = "";
  });

  copyBtn?.addEventListener("click", () => {
    navigator.clipboard.writeText(lastPayLink).then(() => {
      copyBtn.textContent = "✅ Copied!";
      setTimeout(() => { copyBtn.innerHTML = `<span class="material-symbols-outlined align-middle mr-1 text-base">content_copy</span>Copy Link`; }, 2000);
    });
  });
}

async function bootstrap() {
  const page = pageId();

  if (!page || page === "landing") {
    return;
  }

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

  // Mobile sidebar toggle
  const menuBtn = $("#mobileMenuBtn");
  const sidebar = $("#sidebar");
  const overlay = $("#sidebarOverlay");
  if (menuBtn && sidebar) {
    menuBtn.addEventListener("click", () => {
      sidebar.classList.toggle("-translate-x-full");
      if (overlay) overlay.classList.toggle("hidden");
    });
    if (overlay) overlay.addEventListener("click", () => {
      sidebar.classList.add("-translate-x-full");
      overlay.classList.add("hidden");
    });
  }

  // Nav connect wallet button
  const navConnBtn = $("#navConnectWallet");
  if (navConnBtn) {
    navConnBtn.addEventListener("click", (e) => {
      e.preventDefault();
      showWalletManageModal();
    });
  }

  if (page.startsWith("client")) {
    // Immediately set username from session/onboarding-status (fixes "..." bug)
    try {
      const obs = await getOnboardingStatus();
      const u = obs.username || obs.user_ref || "";
      if (u && document.getElementById("dashUsername")) document.getElementById("dashUsername").textContent = u;
      if (session.wallet) {
        const nb = document.getElementById("navConnectWallet");
        if (nb) {
          fetchSolBalance(session.wallet).then(balance => {
            nb.textContent = `Wallet 1 \u00B7 ${balance} SOL`;
          });
        }
      }
    } catch {}

    if (session.wallet) {
      await hydrateClientPages(session.wallet);
      attachSSE("client", session.wallet);
      loadWalletList();
    } else {
      // Try to resolve wallet from backend
      const resolvedWallet = await resolveWallet(session);
      if (resolvedWallet) {
        session.wallet = resolvedWallet;
        await hydrateClientPages(resolvedWallet);
        attachSSE("client", resolvedWallet);
        loadWalletList();
      } else if (page === "client-dashboard") {
        showSoftWalletPrompt();
      }
    }

    // FAB payment button
    const fab = $("#fabPayment");
    if (fab) fab.addEventListener("click", (e) => { e.preventDefault(); go("/ui/client/pay"); });

    // Wire pay page
    if (page === "client-pay") wirePayPage(session);

    // Notifications bell
    wireNotifications(session);

    // Settings
    wireSettings(session);
  } else if (page.startsWith("merchant")) {
    await hydrateMerchantPages();
    attachSSE("merchant", session.wallet || "");
    if (page === "merchant-receive") wireMerchantReceive(session);
  }
}

document.addEventListener("DOMContentLoaded", () => {
  bootstrap().catch((error) => {
    console.error(error);
    alert(error.message || "UI bootstrap failed.");
    if (!["landing", "auth", "auth-login", "onboarding"].includes(pageId())) {
      go("/auth");
    }
  });
});