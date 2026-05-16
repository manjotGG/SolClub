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
    navBtn.textContent = snapshot.wallet.slice(0, 4) + "..." + snapshot.wallet.slice(-4);
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
    if (session.wallet) {
      await hydrateClientPages(session.wallet);
      attachSSE("client", session.wallet);
      loadWalletList();
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
    if (!["landing", "auth", "auth-login", "onboarding"].includes(pageId())) {
      go("/auth");
    }
  });
});