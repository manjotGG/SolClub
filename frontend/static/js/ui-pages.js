const SOLCLUB_ROLE_KEY = "solclub_role";
const SOLCLUB_WALLET_KEY = "solclub_wallet";

const $ = (selector, root = document) => root.querySelector(selector);
const $$ = (selector, root = document) => Array.from(root.querySelectorAll(selector));

function currentRole() {
  return (localStorage.getItem(SOLCLUB_ROLE_KEY) || document.body.dataset.role || "client").toLowerCase();
}

function currentWallet() {
  return (localStorage.getItem(SOLCLUB_WALLET_KEY) || "").trim();
}

function setRole(role) {
  localStorage.setItem(SOLCLUB_ROLE_KEY, role);
}

function setWallet(wallet) {
  localStorage.setItem(SOLCLUB_WALLET_KEY, wallet);
}

async function apiJson(url, options = {}) {
  const response = await fetch(url, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      "x-solclub-role": currentRole(),
      ...(options.headers || {}),
    },
  });

  const contentType = response.headers.get("content-type") || "";
  const data = contentType.includes("application/json") ? await response.json() : await response.text();
  if (!response.ok) {
    const message = typeof data === "string" ? data : data.detail || JSON.stringify(data);
    throw new Error(message);
  }
  return data;
}

function normalizeLabel(text) {
  return String(text || "").replace(/\s+/g, " ").trim().toLowerCase();
}

function findClickableLabel(node) {
  return normalizeLabel(node?.textContent || node?.innerText || "");
}

function go(path) {
  window.location.assign(path);
}

function promptWallet(defaultRole = currentRole()) {
  const fallback = currentWallet();
  const input = window.prompt("Enter your Solana wallet address", fallback || "");
  if (!input) return null;
  const wallet = input.trim();
  if (!wallet) return null;
  setRole(defaultRole);
  setWallet(wallet);
  return wallet;
}

async function connectWallet(role = currentRole()) {
  const wallet = promptWallet(role);
  if (!wallet) return;
  await apiJson("/ui/api/wallet/connect", {
    method: "POST",
    body: JSON.stringify({
      wallet_address: wallet,
      network: "testnet",
      provider: role === "merchant" ? "merchant-wallet" : "phantom",
      user_role: role,
    }),
  });
  if (role === "merchant") {
    go("/ui/merchant");
    return;
  }
  go("/ui/client");
}

async function createWallet() {
  const data = await apiJson("/ui/api/wallet/auto-create", {
    method: "POST",
    body: JSON.stringify({
      network: "testnet",
      provider: "solclub-managed",
      created_by: "proposed-ui",
    }),
  });
  if (data.wallet_address) {
    setRole("client");
    setWallet(data.wallet_address);
  }
  go("/ui/client");
}

async function startGoogleAuth() {
  const data = await apiJson("/ui/api/auth/google/start?role=client");
  if (data.auth_url) {
    window.location.assign(data.auth_url);
  }
}

function downloadText(filename, content, mimeType = "text/plain") {
  const blob = new Blob([content], { type: mimeType });
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = filename;
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
  URL.revokeObjectURL(url);
}

function wireNavLinks() {
  const page = document.body.dataset.page || "";
  const common = {
    dashboard: currentRole() === "merchant" ? "/ui/merchant" : "/ui/client",
    analytics: "/ui/merchant/analytics",
    docs: "/docs",
    logout: "/ui/auth",
    "connect wallet": "/ui/auth",
    rewards: "/ui/client/rewards",
    "nft collection": "/ui/client/nfts",
    transactions: "/ui/client/transactions",
    "loyalty progress": "/ui/client/progress",
    feedback: "/ui/client/feedback",
    "cashback config": "/ui/merchant/cashback",
    franchises: "/ui/merchant/franchises",
    "nft distribution": "/ui/merchant/nfts",
  };

  if (page === "merchant-feedback") {
    common.feedback = "/ui/merchant/feedback";
  }

  $$('a').forEach((anchor) => {
    const label = findClickableLabel(anchor);
    const route = Object.keys(common).find((key) => label === key || label.includes(key));
    if (route && common[route]) {
      anchor.href = common[route];
    }
  });
}

function wireGenericButtons() {
  $$('button').forEach((button) => {
    const label = findClickableLabel(button);

    if (label === "connect wallet") {
      button.addEventListener("click", (event) => {
        event.preventDefault();
        connectWallet(currentRole()).catch((error) => alert(error.message));
      });
      return;
    }

    if (label === "continue with google") {
      button.addEventListener("click", (event) => {
        event.preventDefault();
        startGoogleAuth().catch((error) => alert(error.message));
      });
      return;
    }

    if (label === "create new wallet") {
      button.addEventListener("click", (event) => {
        event.preventDefault();
        createWallet().catch((error) => alert(error.message));
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

    if (label === "generate report") {
      button.addEventListener("click", (event) => {
        event.preventDefault();
        exportMerchantReport().catch((error) => alert(error.message));
      });
      return;
    }

    if (label === "export csv") {
      button.addEventListener("click", (event) => {
        event.preventDefault();
        exportClientTransactionsCsv().catch((error) => alert(error.message));
      });
      return;
    }

    if (label === "claim reward") {
      button.addEventListener("click", (event) => {
        event.preventDefault();
        go("/ui/client/rewards");
      });
      return;
    }

    if (label === "initialize next drop") {
      button.addEventListener("click", (event) => {
        event.preventDefault();
        go("/ui/merchant/nfts");
      });
      return;
    }

    if (label === "load more activity") {
      button.addEventListener("click", (event) => {
        event.preventDefault();
        window.scrollTo({ top: document.body.scrollHeight, behavior: "smooth" });
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

    if (label === "buy now" || label === "bid" || label === "bid now" || label === "unlock" || label === "view" || label === "join elite list") {
      button.addEventListener("click", (event) => {
        event.preventDefault();
        if (!currentWallet()) {
          go("/ui/auth");
          return;
        }
        go("/ui/client/nfts");
      });
      return;
    }

    if (label === "logout") {
      button.addEventListener("click", (event) => {
        event.preventDefault();
        localStorage.removeItem(SOLCLUB_ROLE_KEY);
        localStorage.removeItem(SOLCLUB_WALLET_KEY);
        go("/ui/auth");
      });
    }
  });
}

function wireCashbackConfig() {
  if ((document.body.dataset.page || "") !== "merchant-cashback") return;

  const ranges = $$('input[type="range"]');
  const percentageRange = ranges[0];
  const poolRange = ranges[1];
  const percentageValue = $$('span').find((node) => node.textContent.trim().endsWith('%') && node.className.includes('text-5xl'));
  const poolValue = $$('span').find((node) => node.textContent.includes('SOL') && node.className.includes('text-3xl'));
  const instantRewardValue = $$('span').find((node) => node.textContent.trim().startsWith('+') && node.className.includes('text-tertiary'));

  const updatePreview = () => {
    const percentage = Number(percentageRange?.value || 0);
    const poolCap = Number(poolRange?.value || 0);
    if (percentageValue) percentageValue.textContent = `${percentage.toFixed(1)}%`;
    if (poolValue) poolValue.textContent = `${poolCap.toLocaleString()} SOL`;
    if (instantRewardValue) instantRewardValue.textContent = `+${(percentage * 1.0).toFixed(2)}`;
  };

  percentageRange?.addEventListener("input", updatePreview);
  poolRange?.addEventListener("input", updatePreview);
  updatePreview();
}

async function submitCashbackConfig() {
  const page = document.body.dataset.page || "";
  if (page !== "merchant-cashback") return;
  const ranges = $$('input[type="range"]');
  const percentage = Number(ranges[0]?.value || 2);
  const poolCap = Number(ranges[1]?.value || 2500);
  await apiJson("/ui/api/merchant/1/cashback-config", {
    method: "POST",
    body: JSON.stringify({
      name: "SolClub Merchant",
      cashback_pool_percentage: percentage,
      max_cashback_limit: poolCap,
      weekly_distribution_rules: {
        base_rate: Math.max(0.01, percentage / 100),
        tiers: [
          { min_transactions: 3, rate: Math.max(0.02, percentage / 100) },
          { min_transactions: 5, rate: Math.max(0.03, percentage / 100) },
          { min_transactions: 10, rate: Math.max(0.05, percentage / 100) },
        ],
      },
    }),
  });
  alert("Cashback configuration saved.");
}

async function exportMerchantReport() {
  const role = currentRole() === "merchant" ? "merchant" : "merchant";
  const analytics = await apiJson("/ui/api/merchant/1/analytics", {
    headers: { "x-solclub-role": role },
  });
  downloadText(`solclub-merchant-report-${Date.now()}.json`, JSON.stringify(analytics, null, 2), "application/json");
}

async function exportClientTransactionsCsv() {
  const wallet = currentWallet();
  if (!wallet) {
    go("/ui/auth");
    return;
  }
  const data = await apiJson(`/ui/api/client/${encodeURIComponent(wallet)}/transactions?limit=200`);
  const rows = ["created_at,merchant_id,amount,signature"];
  (data.items || []).forEach((item) => {
    rows.push([
      item.created_at || "",
      item.merchant_id ?? "",
      item.amount ?? "",
      item.signature || "",
    ].map((value) => `"${String(value).replaceAll('"', '""')}"`).join(","));
  });
  downloadText(`solclub-transactions-${Date.now()}.csv`, rows.join("\n"), "text/csv");
}

function wireTabSwitches() {
  if (!document.body.dataset.page || !document.body.dataset.page.startsWith("merchant")) return;
  $$('button').forEach((button) => {
    const label = findClickableLabel(button);
    if (label === "7d" || label === "30d" || label === "all" || label === "day" || label === "week" || label === "month") {
      button.addEventListener("click", () => {
        $$('button').forEach((candidate) => {
          const candidateLabel = findClickableLabel(candidate);
          if (["7d", "30d", "all", "day", "week", "month"].includes(candidateLabel)) {
            candidate.classList.remove("bg-surface-container-high", "text-white", "border-b", "border-primary");
            candidate.classList.add("text-slate-500");
          }
        });
        button.classList.add("bg-surface-container-high", "text-white");
      });
    }
  });
}

function wireClientFab() {
  if ((document.body.dataset.page || "") !== "client-dashboard") return;
  const fab = $$('button').find((button) => findClickableLabel(button) === "mint new assets");
  if (fab) {
    fab.addEventListener("click", (event) => {
      event.preventDefault();
      go("/ui/client/nfts");
    });
  }
}

function wireHeroActions() {
  void document.body.dataset.page;
}

document.addEventListener("DOMContentLoaded", () => {
  wireNavLinks();
  wireGenericButtons();
  wireCashbackConfig();
  wireTabSwitches();
  wireClientFab();
  wireHeroActions();
});