const state = {
  activeView: "command",
  health: null,
  privateRuntime: null,
  nativeSupervisor: null,
  risk: null,
  performance: null,
  equityCurve: null,
  strategies: [],
  strategyConfigs: [],
  strategyFactoryReadiness: null,
  researchCandidates: [],
  researchObservations: [],
  researchEvidence: null,
  researchReadinessQueue: null,
  researchMktIntakeReadiness: null,
  researchMktRunbook: null,
  researchMktImport: null,
  selectedResearchCandidateId: null,
  analyst: null,
  broker: null,
  sandboxProfileStatus: null,
  operatorProfileStatus: null,
  operatorProfileTemplate: null,
  operatorProfilePreflight: null,
  operatorProfileValidatedInput: null,
  operatorProfileInitialized: false,
  deployment: null,
  activationAttempt: null,
  brokerStatementPreflight: null,
  strategyEvidenceReviews: [],
  backtestStrategySetup: null,
  backtestWindowPlan: null,
  backtestCsvFileName: null,
  backtestOhlcvPreflight: null,
  backtestDatasets: [],
  backtestReferenceReplay: null,
  backtestReferenceRuns: [],
  backtestReferenceValidationPreflight: null,
  backtestReferenceValidations: [],
  backtestParityExportManifest: null,
  backtestParityPreflight: null,
  backtestParityRuns: [],
  backtestPaperEligibility: null,
  backtestPreflight: null,
  backtestProtocols: [],
  backtestRunManifest: null,
  backtestRunPackage: null,
  backtestReports: [],
  predictionSummary: null,
  predictionDemoReadiness: null,
  predictionDemoProgress: null,
  predictionDemoRunbook: null,
  predictionDemoLedger: null,
  predictionDemoCampaigns: null,
  predictionDemoBatches: null,
  predictionDemoBatchPreflight: null,
  predictionDemoBatch: null,
  predictionDemoMktDbCampaignPreflight: null,
  predictionDemoMktDbCampaignManifest: null,
  predictionDemoMktDbCampaign: null,
  predictionContractCsvPreflight: null,
  predictionContractMktDonorReadiness: null,
  predictionContractMktDonorRunbook: null,
  predictionContractMktDonorBootstrap: null,
  predictionContractMktDonorLaunchPreflight: null,
  predictionContractMktDonorCollectionStatus: null,
  predictionContractMktRuntimeSafety: null,
  predictionContractMktDbDiscovery: null,
  predictionContractMktDbReadiness: null,
  predictionContractMktDbInventory: null,
  predictionContractMktDbPreflight: null,
  predictionDemoMktDbCampaignReadiness: null,
  predictionContracts: [],
  predictionIntents: [],
  predictionOrders: [],
  predictionPositions: [],
  predictionEvidence: [],
  paperEvidenceCollection: null,
  paperEvidencePreflight: null,
  paperEvidenceImports: [],
  signalContract: null,
  signalRunbook: null,
  signalAlertSetup: null,
  signalVerification: null,
  signalPreflight: null,
  signals: [],
  trades: [],
  events: [],
  lastRefreshedAt: null,
  refreshFailures: [],
};

const pendingUiActions = new WeakSet();
const scheduleRefresh = AurexTransport.serialQueue();
let nativeReadSequence = 0;
let nativePollTimer = null;

const TRADINGVIEW_PAIRED_EXPORT_ATTESTATION = [
  "I attest that the selected TradingView chart CSV and Strategy Tester CSV",
  "were exported from the same run without changing the Pine source, inputs,",
  "Strategy Properties, symbol, timeframe, date range, costs, or order settings.",
].join(" ");

const viewDefinitions = {
  command: {
    title: "Command Center",
    eyebrow: "Operating state",
    context: "Portfolio state and market posture",
  },
  signals: {
    title: "Signals",
    eyebrow: "Signal intake",
    context: "Validated strategy events and rejection reasons",
  },
  trades: {
    title: "Paper Trades",
    eyebrow: "Execution ledger",
    context: "Open and closed paper positions",
  },
  performance: {
    title: "Performance",
    eyebrow: "Portfolio analytics",
    context: "Realized outcomes and drawdown",
  },
  strategies: {
    title: "Strategies",
    eyebrow: "Research portfolio",
    context: "Strategy state, scope, and evidence",
  },
  analyst: {
    title: "Analyst",
    eyebrow: "Advisory layer",
    context: "Evidence-based warnings and review notes",
  },
  backtests: {
    title: "Backtests",
    eyebrow: "Historical evidence",
    context: "TradingView imports and acceptance gates",
  },
  prediction: {
    title: "Prediction Markets",
    eyebrow: "Paper-only market lab",
    context: "Binary contract snapshots, paper fills, settlements, and evidence",
  },
  risk: {
    title: "Risk Controls",
    eyebrow: "Capital protection",
    context: "Current limits and emergency state",
  },
  broker: {
    title: "Broker Readiness",
    eyebrow: "Execution boundary",
    context: "Connection and reconciliation controls",
  },
  operator: {
    title: "Operator Profile",
    eyebrow: "Research boundary",
    context: "Venue, access, capital, loss, product, and data constraints",
  },
  deployment: {
    title: "Deployment",
    eyebrow: "Live locked",
    context: "Evidence gates, approvals, and activation audit",
  },
  evidence: {
    title: "Paper Evidence",
    eyebrow: "Forward validation",
    context: "Imported trades, coverage, and integrity",
  },
  events: {
    title: "System Events",
    eyebrow: "Audit trail",
    context: "Recent operational and control-plane events",
  },
};

const dashboardResources = [
  ["health", "/health"],
  ["privateRuntime", "/system/private-runtime"],
  ["risk", "/risk/status"],
  ["performance", "/performance/summary"],
  ["equityCurve", "/performance/equity-curve?limit=80"],
  ["strategies", "/strategies/comparison", (value) => value.strategies || []],
  ["strategyConfigs", "/strategies"],
  ["strategyFactoryReadiness", "/system/readiness"],
  ["researchCandidates", "/strategies/research-candidates"],
  ["researchReadinessQueue", "/strategies/research-candidates/readiness-queue"],
  ["researchObservations", "/strategies/research-candidates/observations?limit=20"],
  ["analyst", "/analyst/summary"],
  ["broker", "/broker/readiness"],
  ["sandboxProfileStatus", "/sandbox-profile/status"],
  ["binanceTestnetStatus", "/broker/binance-testnet/status"],
  ["operatorProfileStatus", "/operator-profile/status"],
  ["operatorProfileTemplate", "/operator-profile/template"],
  ["deployment", "/live/deployment"],
  ["strategyEvidenceReviews", "/live/deployment/evidence-reviews"],
  ["backtestProtocols", "/backtests/protocols?limit=20"],
  ["backtestDatasets", "/backtests/ohlcv/datasets?limit=10"],
  ["backtestReferenceRuns", "/backtests/reference-replay/runs?limit=10"],
  [
    "backtestReferenceValidations",
    "/backtests/reference-replay/validations?limit=10",
  ],
  ["backtestReports", "/backtests/reports?limit=10"],
  ["backtestParityRuns", "/backtests/parity/runs?limit=10"],
  ["predictionSummary", "/prediction-market/summary"],
  ["predictionDemoReadiness", "/prediction-market/paper/demo-readiness"],
  ["predictionDemoProgress", "/prediction-market/paper/demo-progress"],
  ["predictionDemoRunbook", "/prediction-market/paper/demo-runbook"],
  ["predictionDemoLedger", "/prediction-market/paper/demo-ledger?limit=20"],
  ["predictionDemoCampaigns", "/prediction-market/paper/demo-campaigns?limit=10"],
  ["predictionDemoBatches", "/prediction-market/paper/demo-batches?limit=10"],
  ["predictionContracts", "/prediction-market/contracts"],
  ["predictionIntents", "/prediction-market/paper/order-intents"],
  ["predictionOrders", "/prediction-market/paper/orders"],
  ["predictionPositions", "/prediction-market/paper/positions"],
  ["predictionEvidence", "/prediction-market/evidence?limit=12"],
  ["paperEvidenceCollection", "/paper/evidence/collection-status"],
  ["paperEvidenceImports", "/paper/evidence/imports?limit=10"],
  ["signals", "/signals?limit=25"],
  ["trades", "/trades?limit=25"],
  ["events", "/system/events?limit=30"],
];

const money = new Intl.NumberFormat("en-US", {
  style: "currency",
  currency: "USD",
  maximumFractionDigits: 2,
});

const percent = new Intl.NumberFormat("en-US", {
  style: "percent",
  maximumFractionDigits: 2,
});

function text(id, value) {
  const element = document.getElementById(id);
  if (element) element.textContent = value;
}

function setPath(id, value) {
  const element = document.getElementById(id);
  if (element) element.setAttribute("d", value);
}

function className(id, value) {
  const element = document.getElementById(id);
  if (element) element.className = value;
}

function setDisabled(id, disabled) {
  const element = document.getElementById(id);
  if (element) element.disabled = disabled;
}

function revealActiveNavItem(button) {
  const nav = button?.closest(".nav-list");
  if (!nav || nav.scrollWidth <= nav.clientWidth) return;
  const centeredLeft = button.offsetLeft - ((nav.clientWidth - button.offsetWidth) / 2);
  nav.scrollTo({ left: Math.max(0, centeredLeft), behavior: "auto" });
}

function activateView(view, { updateHistory = true, focus = false } = {}) {
  const nextView = viewDefinitions[view] ? view : "command";
  state.activeView = nextView;
  let activeButton = null;

  document.querySelectorAll("[data-dashboard-view]").forEach((element) => {
    const active = element.dataset.dashboardView === nextView;
    element.classList.toggle("is-active", active);
    element.hidden = !active;
  });

  document.querySelectorAll("[data-view-target]").forEach((button) => {
    const active = button.dataset.viewTarget === nextView;
    button.classList.toggle("is-active", active);
    if (active) {
      activeButton = button;
      button.setAttribute("aria-current", "page");
      if (focus) button.focus();
    } else {
      button.removeAttribute("aria-current");
    }
  });
  revealActiveNavItem(activeButton);

  const definition = viewDefinitions[nextView];
  text("view-title", definition.title);
  text("view-eyebrow", definition.eyebrow);
  text("view-context", definition.context);
  document.title = `${definition.title} / Aurex`;

  if (updateHistory && window.location.hash !== `#${nextView}`) {
    window.history.pushState({ view: nextView }, "", `#${nextView}`);
  }
  window.scrollTo({ top: 0, behavior: "auto" });
}

function initializeNavigation() {
  const nav = document.querySelector(".nav-list");
  if (!nav) return;

  nav.addEventListener("click", (event) => {
    const button = event.target.closest("[data-view-target]");
    if (!button) return;
    activateView(button.dataset.viewTarget);
  });

  nav.addEventListener("keydown", (event) => {
    const button = event.target.closest("[data-view-target]");
    if (!button || !["ArrowUp", "ArrowDown", "ArrowLeft", "ArrowRight", "Home", "End"].includes(event.key)) {
      return;
    }
    event.preventDefault();
    const buttons = [...nav.querySelectorAll("[data-view-target]")];
    const currentIndex = buttons.indexOf(button);
    const previous = event.key === "ArrowUp" || event.key === "ArrowLeft";
    const nextIndex = event.key === "Home"
      ? 0
      : event.key === "End"
        ? buttons.length - 1
        : (currentIndex + (previous ? -1 : 1) + buttons.length) % buttons.length;
    activateView(buttons[nextIndex].dataset.viewTarget, { focus: true });
  });

  window.addEventListener("popstate", () => {
    activateView(window.location.hash.slice(1), { updateHistory: false });
  });

  activateView(window.location.hash.slice(1), { updateHistory: false });
}

function showNotification(message, { tone = "info", title = "Aurex", duration } = {}) {
  const region = document.getElementById("notification-region");
  if (!region) return;

  const notification = document.createElement("div");
  notification.className = `notification notification-${tone}`;
  const content = document.createElement("div");
  const heading = document.createElement("strong");
  const body = document.createElement("span");
  const close = document.createElement("button");
  heading.textContent = title;
  body.textContent = message;
  close.type = "button";
  close.className = "notification-close";
  close.setAttribute("aria-label", "Dismiss notification");
  close.textContent = "\u00d7";
  content.append(heading, body);
  notification.append(content, close);
  region.appendChild(notification);

  const dismiss = () => {
    notification.classList.add("is-leaving");
    window.setTimeout(() => notification.remove(), 180);
  };
  close.addEventListener("click", dismiss);
  window.setTimeout(dismiss, duration ?? (tone === "error" ? 9000 : 5000));
}

async function runUiAction(button, action, successMessage) {
  if (!button || button.disabled || pendingUiActions.has(button)) return;
  pendingUiActions.add(button);
  button.classList.add("is-loading");
  button.setAttribute("aria-busy", "true");
  try {
    const result = await action();
    if (successMessage) {
      const outcome = typeof successMessage === "function"
        ? successMessage(result)
        : successMessage;
      if (typeof outcome === "string") {
        showNotification(outcome, { tone: "success", title: "Complete" });
      } else if (outcome?.message) {
        showNotification(outcome.message, {
          tone: outcome.tone || "success",
          title: outcome.title || "Complete",
        });
      }
    }
    return result;
  } catch (error) {
    showNotification(error.message || "The operation failed.", {
      tone: "error",
      title: "Action failed",
    });
    return undefined;
  } finally {
    pendingUiActions.delete(button);
    button.classList.remove("is-loading");
    button.removeAttribute("aria-busy");
  }
}

function bindAction(id, action, successMessage) {
  const button = document.getElementById(id);
  button?.addEventListener("click", () => {
    runUiAction(button, action, successMessage);
  });
}

async function copyTextToClipboard(value) {
  if (!value) {
    throw new Error("No text is available to copy.");
  }
  if (navigator.clipboard?.writeText) {
    await navigator.clipboard.writeText(value);
    return;
  }
  const textarea = document.createElement("textarea");
  textarea.value = value;
  textarea.setAttribute("readonly", "");
  textarea.style.position = "fixed";
  textarea.style.top = "-9999px";
  document.body.appendChild(textarea);
  textarea.select();
  const copied = document.execCommand("copy");
  textarea.remove();
  if (!copied) {
    throw new Error("Clipboard copy is unavailable in this browser.");
  }
}

function currentPredictionMktDonorLaunchCommand() {
  const preflightCommand = state.predictionContractMktDonorLaunchPreflight?.launch_command || "";
  if (preflightCommand) return preflightCommand;
  const hints = state.predictionContractMktDonorCollectionStatus?.command_hints || [];
  const collectionCommand = hints.find((hint) => hint.label === "Start MKT with Aurex demo userData")?.command || "";
  if (collectionCommand) return collectionCommand;
  const bootstrapHints = state.predictionContractMktDonorBootstrap?.command_hints || [];
  return bootstrapHints.find((hint) => hint.label === "Start MKT with Aurex demo userData")?.command || "";
}

function updatePredictionMktDonorLaunchCommandButton() {
  setDisabled(
    "prediction-mkt-donor-copy-launch-command-button",
    !currentPredictionMktDonorLaunchCommand(),
  );
}

async function copyPredictionMktDonorLaunchCommand() {
  await copyTextToClipboard(currentPredictionMktDonorLaunchCommand());
}

async function api(path, options = {}) {
  return AurexTransport.requestJson(path, options);
}

function refresh(options = {}) {
  // A post-mutation refresh must run after any older in-flight reads, not reuse them.
  return scheduleRefresh(() => refreshDashboard(options));
}

async function refreshDashboard({ announce = false } = {}) {
  text("last-sync-state", "Refreshing");
  const results = await AurexTransport.settleResources(dashboardResources, async (path) => {
    try {
      return await api(path);
    } catch (error) {
      if (path === "/system/private-runtime" && error.status === 404) {
        return { status: "UNGUARDED_RUNTIME" };
      }
      throw error;
    }
  });
  const failures = [];

  results.forEach((result, index) => {
    const [key, path, normalize = (value) => value] = dashboardResources[index];
    if (result.status === "fulfilled") {
      state[key] = normalize(result.value);
      return;
    }
    if (["health", "privateRuntime", "risk", "strategyFactoryReadiness", "broker", "deployment"].includes(key)) {
      state[key] = null;
    } else if (["strategyConfigs", "strategies"].includes(key)) {
      state[key] = [];
    }
    failures.push({ path, message: result.reason?.message || "Request failed" });
  });

  await refreshNativeSupervisor(failures);
  await refreshQualifiedStrategyResources(failures);
  await refreshResearchEvidence(failures);
  await refreshCoreRunManifest(failures);

  state.lastRefreshedAt = new Date();
  state.refreshFailures = failures;
  render();
  renderSyncState();

  if (failures.length === dashboardResources.length) {
    throw new Error("Aurex is unreachable. No dashboard source responded.");
  }
  if (failures.length) {
    showNotification(
      `${failures.length} data source${failures.length === 1 ? " is" : "s are"} unavailable. Last received data may be stale.`,
      { tone: "warning", title: "Partial refresh" },
    );
  } else if (announce) {
    showNotification("All dashboard sources are current.", {
      tone: "success",
      title: "Refresh complete",
    });
  }
}

function qualifiedStrategyContext() {
  if (!state.strategyFactoryReadiness?.source_integrity_verified) return null;
  return state.strategyConfigs.find(
    (strategy) =>
      strategy.lifecycle_status === "ACTIVE"
      && strategy.enable_eligible === true,
  ) || null;
}

async function refreshQualifiedStrategyResources(failures = []) {
  const strategy = qualifiedStrategyContext()?.strategy || null;
  if (!strategy) {
    state.backtestStrategySetup = null;
    state.backtestPaperEligibility = null;
    state.signalContract = null;
    state.signalRunbook = null;
    state.signalAlertSetup = null;
    state.signalVerification = null;
    return;
  }

  const plan = state.deployment?.plan || {};
  const symbol = (plan.symbols || ["BTCUSDT"])[0] || "BTCUSDT";
  const timeframe = plan.timeframe || "15m";
  const encodedStrategy = encodeURIComponent(strategy);
  const encodedSymbol = encodeURIComponent(symbol);
  const resources = [
    [
      "backtestStrategySetup",
      `/backtests/strategy-setup?strategy=${encodedStrategy}&symbol=${encodedSymbol}&timeframe=${encodeURIComponent(timeframe)}&venue=BINANCE`,
    ],
    [
      "backtestPaperEligibility",
      `/backtests/paper-eligibility?strategy=${encodedStrategy}&symbol=${encodedSymbol}`,
    ],
    ["signalContract", `/signals/contract?strategy=${encodedStrategy}&symbol=${encodedSymbol}`],
    ["signalRunbook", `/signals/tradingview-runbook?strategy=${encodedStrategy}&symbol=${encodedSymbol}`],
    ["signalAlertSetup", `/signals/tradingview-alert-setup?strategy=${encodedStrategy}&symbol=${encodedSymbol}`],
    ["signalVerification", `/signals/tradingview-verification?strategy=${encodedStrategy}&symbol=${encodedSymbol}`],
  ];
  const results = await AurexTransport.settleResources(resources, api);
  results.forEach((result, index) => {
    const [key, path] = resources[index];
    if (result.status === "fulfilled") {
      state[key] = result.value;
      return;
    }
    state[key] = null;
    failures.push({ path, message: result.reason?.message || "Request failed" });
  });
}

async function refreshResearchEvidence(failures = []) {
  const candidate = ensureSelectedResearchCandidate();
  if (!candidate?.id) {
    state.researchEvidence = null;
    return;
  }
  const path = `/strategies/research-candidates/${encodeURIComponent(candidate.id)}/evidence?observation_limit=12&backtest_limit=8`;
  try {
    state.researchEvidence = await api(path);
  } catch (error) {
    state.researchEvidence = null;
    failures.push({ path, message: error.message || "Request failed" });
  }
}

async function refreshCoreRunManifest(failures = []) {
  const protocol = currentCoreBacktestProtocol();
  if (!protocol) {
    state.backtestRunManifest = null;
    return;
  }
  const path = `/backtests/protocols/${encodeURIComponent(protocol.id)}/run-manifest`;
  try {
    state.backtestRunManifest = await api(path);
  } catch (error) {
    state.backtestRunManifest = null;
    failures.push({ path, message: error.message || "Request failed" });
  }
}

function ensureSelectedResearchCandidate() {
  if (!state.researchCandidates.length) {
    state.selectedResearchCandidateId = null;
    return null;
  }
  const selected = state.researchCandidates.find(
    (candidate) => candidate.id === state.selectedResearchCandidateId,
  );
  if (selected) return selected;
  const latest = state.researchCandidates[0];
  state.selectedResearchCandidateId = latest.id;
  return latest;
}

function render() {
  renderHealth();
  renderPrivateRuntime();
  renderNativeSupervisor();
  renderNavigationCounts();
  renderMarketPreview();
  renderCommandEvidencePath();
  renderRisk();
  renderPerformance();
  renderStrategies();
  renderAnalyst();
  renderBroker();
  renderOperatorProfile();
  renderDeployment();
  renderBrokerStatementPreflight();
  renderBacktestSetup();
  renderBacktestWindowPlan();
  renderBacktestOhlcv();
  renderBacktestReferenceReplay();
  renderBacktestParity();
  renderBacktestProtocols();
  renderBacktestPreflight();
  renderBacktestReports();
  renderPredictionMarkets();
  renderPaperEvidenceCollection();
  renderPaperEvidencePreflight();
  renderPaperEvidenceImports();
  renderSignals();
  renderTrades();
  renderEvents();
}

function renderNavigationCounts() {
  text("nav-signals-count", String(state.signals.length));
  text("nav-trades-count", String(state.trades.length));
  text("nav-backtests-count", String(state.backtestReports.length));
  text("nav-prediction-count", String(state.predictionSummary?.orders || 0));
  text("nav-evidence-count", String(state.paperEvidenceImports.length));
  text("nav-events-count", String(state.events.length));
}

function renderHealth() {
  const service = state.health?.service || "Aurex";
  const environment = state.health?.environment || "local";
  const authority = state.health?.live_trading_enabled
    ? "live enabled"
    : state.strategyFactoryReadiness?.paper_operation_ready
      ? "paper authorized"
      : "research only";
  const healthFailed = state.refreshFailures.some((failure) => failure.path === "/health");
  const online = Boolean(state.health) && !healthFailed;
  text("health-mode", online ? `${service} online` : "Connection degraded");
  text("health-state", `${environment} / ${authority}`);
  className(
    "health-indicator",
    `presence-dot ${online ? "is-online" : "is-offline"}`,
  );
}

function renderPrivateRuntime() {
  const runtime = state.privateRuntime;
  const ready = runtime?.status === "PRIVATE_CONFIG_READY";
  text("runtime-service", ready ? "Private / loopback only" : runtime?.status === "UNGUARDED_RUNTIME" ? "Legacy service / unguarded" : "Unavailable");
  className("runtime-state", `status-pill ${ready ? "status-ok" : "status-warn"}`);
  text("runtime-state", ready ? "SERVICE READY" : "NOT VERIFIED");
  text("runtime-instance", runtime?.instance_id ? shortHash(runtime.instance_id) : "Not verified");
  text("runtime-schema", runtime?.database_revisions?.join(", ") || "Not verified");
  text("runtime-acceptance", runtime?.operational_acceptance === false ? "Not accepted" : "Not verified");
}

async function refreshNativeSupervisor(failures = []) {
  window.clearTimeout(nativePollTimer);
  const sequence = ++nativeReadSequence;
  const configured = state.nativeSupervisor?.configured || state.privateRuntime?.native_supervisor_configured;
  try {
    const value = await api("/system/native-supervisor");
    if (sequence !== nativeReadSequence) return;
    state.nativeSupervisor = value;
  } catch (error) {
    if (sequence !== nativeReadSequence) return;
    state.nativeSupervisor = null;
    if (error.status !== 404) failures.push({ path: "/system/native-supervisor", message: error.message });
  }
  renderNativeSupervisor();
  if (configured || state.nativeSupervisor?.configured) {
    nativePollTimer = window.setTimeout(() => {
      if (!document.hidden) refreshNativeSupervisor();
      else nativePollTimer = window.setTimeout(() => refreshNativeSupervisor(), 15000);
    }, 5000);
  }
}

function renderNativeSupervisor() {
  const native = state.nativeSupervisor;
  const sameInstance = native?.instance_id === state.privateRuntime?.instance_id;
  text("runtime-supervisor", native?.state || "Unknown");
  text("native-mode", native?.mode || "Not configured");
  text("native-run", native?.run_id ? shortHash(native.run_id) : "No owned run");
  text("native-process", native ? native.process_alive ? "Owned process alive / feed unverified" : "No live owned process / external unknown" : "Unknown");
  text("native-reason", native?.reason || "Status unavailable");
  text("native-journal", native?.control_journal_failed ? "Control journal failed / restart blocked" : native?.journal_verified ? "Terminal journal verified / not qualification" : "Not verified");
  text("native-limits", native?.configured ? `${native.max_run_seconds}s / ${native.max_processed_bars} bars` : "Not configured");
  text("native-start-button", native?.run_id ? "Restart supervisor" : "Start supervisor");
  setDisabled("native-start-button", !(sameInstance && state.privateRuntime?.status === "PRIVATE_CONFIG_READY" && native?.can_start === true));
  setDisabled("native-stop-button", native?.can_stop !== true);
}

async function controlNativeSupervisor(action) {
  const native = state.nativeSupervisor;
  if (!native?.instance_id) throw new Error("Supervisor status unavailable.");
  const payload = {
    expected_instance_id: native.instance_id,
    expected_run_id: native.run_id,
    request_id: crypto.randomUUID().replaceAll("-", ""),
  };
  try {
    await api(`/system/native-supervisor/${action}`, {
      method: "POST", timeoutMs: 45000, headers: { "X-Aurex-Instance": native.instance_id },
      body: JSON.stringify(payload),
    });
  } finally {
    await refreshNativeSupervisor();
  }
}

function renderSyncState() {
  const refreshedAt = state.lastRefreshedAt;
  if (!refreshedAt) {
    text("last-sync-state", "Not synced");
    return;
  }
  const time = refreshedAt.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
  const failures = state.refreshFailures.length;
  text("last-sync-state", failures ? `${failures} degraded / ${time}` : `Synced ${time}`);
  className("last-sync-state", `sync-state ${failures ? "is-degraded" : "is-current"}`);
}

function renderMarketPreview() {
  const deployment = state.deployment || {};
  const plan = deployment.plan || {};
  const qualifiedStrategy = qualifiedStrategyContext();
  const symbol = (plan.symbols || ["BTCUSDT"])[0] || "BTCUSDT";
  const risk = !state.risk ? "Risk state unknown" : qualifiedStrategy
    ? qualifiedStrategy.risk_per_trade === null
      ? "Risk not set"
      : `${percent.format(Number(qualifiedStrategy.risk_per_trade))} risk`
    : state.risk.kill_switch_enabled ? "Entries blocked" : "Risk limits configured";
  const mode = deployment.live_trading_enabled
    ? "Live enabled"
    : state.strategyFactoryReadiness?.paper_operation_ready
      ? "Paper authorized"
      : "Research only";
  const strategy = qualifiedStrategy?.strategy || "No qualified strategy";
  const points = state.equityCurve?.points || [];
  const failed = state.refreshFailures.some((failure) => failure.path.startsWith("/performance/equity-curve"));
  const hasCurve = !failed && points.length >= 2 && points.every((point) => Number.isFinite(Number(point.equity)));
  const linePath = hasCurve ? equityCurvePath(points) : "";

  text("preview-symbol-pill", symbol);
  text("preview-risk-pill", risk);
  text("preview-strategy-pill", strategy.replaceAll("_", " "));
  text("preview-mode-pill", mode);
  text("preview-chart-symbol", "Paper equity");
  text("preview-risk-label", "USD");
  text(
    "preview-chart-title",
    hasCurve
      ? `${state.equityCurve.point_count} equity points / ${money.format(Number(state.equityCurve.latest_equity || 0))}`
      : failed ? "Equity unavailable" : "No equity history",
  );
  setPath("preview-line-main", linePath);
  setPath("preview-line-shadow", linePath);
  const empty = document.getElementById("preview-chart-empty");
  if (empty) empty.hidden = hasCurve;
  text("preview-chart-empty", failed ? "Equity data unavailable" : "No recorded equity history");
}

function renderCommandEvidencePath() {
  const readiness = state.strategyFactoryReadiness || null;
  const gates = new Map(
    (readiness?.gate_results || []).map((gate) => [gate.gate_id, gate]),
  );
  const signalGate = gates.get("AUTHENTICATED_SIGNAL_DELIVERY");
  const sandboxGate = gates.get("EXCHANGE_SANDBOX_QUALIFICATION");
  const liveEnabled = Boolean(
    state.health?.live_trading_enabled || state.broker?.live_trading_enabled,
  );
  const steps = [
    {
      label: "Factory contract",
      passed: Boolean(readiness?.source_integrity_verified),
      evidence: readiness
        ? `${readiness.source_integrity_verified ? "PASS" : "BLOCKED"} / ${shortHash(readiness.contract_evidence_hash)}`
        : "NOT_CHECKED",
      nextAction: "Restore the hash-bound strategy-factory contract and source integrity.",
    },
    {
      label: "Research gates",
      passed: Boolean(readiness?.strategy_research_ready),
      evidence: readiness
        ? `${readiness.passed_gate_count}/${readiness.passed_gate_count + readiness.partial_gate_count + readiness.failed_gate_count} pass / ${readiness.research_blocking_gate_ids.length} research blockers`
        : "NOT_CHECKED",
      nextAction: "Close every research-required platform gate before mechanism design.",
    },
    {
      label: "Qualified strategy",
      passed: Number(readiness?.qualified_strategy_count || 0) > 0,
      evidence: readiness
        ? `${readiness.qualified_strategy_count} qualified / ${readiness.enable_eligible_strategy_count} enable-eligible`
        : "NOT_CHECKED",
      nextAction: readiness?.next_action || "Freeze a new economic-mechanism charter.",
    },
    {
      label: "Accepted backtest",
      passed: Boolean(readiness?.paper_operation_ready),
      evidence: readiness?.paper_operation_ready ? "PASS" : "NO QUALIFIED EVIDENCE",
      nextAction: "A candidate must pass development, validation, and holdout gates first.",
    },
    {
      label: "External signal",
      passed: signalGate?.status === "PASS",
      evidence: signalGate?.status || "NOT_CHECKED",
      nextAction: "Complete one genuine authenticated external TradingView delivery proof.",
    },
    {
      label: "Paper evidence",
      passed: Boolean(readiness?.paper_operation_ready),
      evidence: readiness?.paper_operation_ready ? "PASS" : "NOT AUTHORIZED",
      nextAction: "Forward paper evidence starts only after a strategy qualifies historically.",
    },
    {
      label: "Broker sandbox",
      passed: sandboxGate?.status === "PASS",
      evidence: sandboxGate?.status || "NOT_CHECKED",
      nextAction: "Sandbox capability exists; strategy order authority remains locked.",
    },
  ];
  const currentIndex = steps.findIndex((step) => !step.passed);
  const completed = steps.filter((step) => step.passed).length;
  const current = currentIndex >= 0 ? steps[currentIndex] : null;
  const status = readiness?.status || "READINESS_UNAVAILABLE";

  text("command-evidence-path-state", status);
  className(
    "command-evidence-path-state",
    `status-pill ${readiness?.strategy_research_ready ? "status-ok" : "status-warn"}`,
  );
  text(
    "command-evidence-current",
    current ? `${currentIndex + 1}. ${current.label} / ${current.evidence}` : "All displayed gates passed",
  );
  text("command-evidence-pine", steps[0].evidence);
  text("command-evidence-protocol", steps[1].evidence);
  text("command-evidence-manifest", steps[2].evidence);
  text("command-evidence-backtest", steps[3].evidence);
  text("command-evidence-signal", steps[4].evidence);
  text("command-evidence-paper", steps[5].evidence);
  text("command-evidence-broker", steps[6].evidence);
  text(
    "command-evidence-progress",
    `${completed} of ${steps.length} displayed checks; not production acceptance`,
  );
  text(
    "command-evidence-live",
    liveEnabled ? "UNSAFE / live enabled" : "LOCKED / no execution authority",
  );
  text(
    "command-evidence-next",
    current?.nextAction || readiness?.next_action || "Review canonical readiness evidence.",
  );
}

function currentCoreBacktestProtocol() {
  const setup = state.backtestStrategySetup;
  if (!setup) return null;
  return (state.backtestProtocols || []).find(
    (protocol) =>
      protocol.status === "REGISTERED" &&
      protocol.strategy === setup.strategy &&
      protocol.strategy_version === setup.strategy_version &&
      protocol.timeframe === setup.timeframe &&
      (protocol.symbols || []).includes(setup.symbol),
  ) || null;
}

function renderRisk() {
  const risk = state.risk;
  setDisabled("reset-kill-switch-button", !risk || !risk.kill_switch_enabled);
  if (!risk) {
    ["metric-equity", "metric-open-positions", "metric-kill-switch", "risk-mode", "risk-per-trade", "max-daily-loss", "max-weekly-loss", "minimum-rr"].forEach((id) => text(id, "Unknown"));
    className("risk-mode", "status-pill status-warn");
    return;
  }
  text("metric-equity", money.format(Number(risk.current_equity || 0)));
  text("metric-open-positions", String(risk.open_positions ?? 0));
  text("metric-kill-switch", risk.kill_switch_enabled ? "Enabled" : "Disabled");
  text("risk-mode", risk.kill_switch_enabled ? "Blocked" : "Paper");
  className("risk-mode", `status-pill ${risk.kill_switch_enabled ? "status-danger" : "status-ok"}`);
  text("risk-per-trade", percent.format(Number(risk.risk_per_trade || 0)));
  text("max-daily-loss", percent.format(Number(risk.max_daily_loss || 0)));
  text("max-weekly-loss", percent.format(Number(risk.max_weekly_loss || 0)));
  text(
    "minimum-rr",
    risk.minimum_reward_risk === undefined ? "--" : `${Number(risk.minimum_reward_risk).toFixed(2)}R`,
  );
}

function renderPerformance() {
  const perf = state.performance;
  if (!perf) return;
  text("metric-net-pl", money.format(Number(perf.total_net_pl || 0)));
  text("performance-trades", `${perf.total_trades || 0} closed`);
  text("win-rate", percent.format(Number(perf.win_rate || 0)));
  text("expectancy", money.format(Number(perf.expectancy || 0)));
  text(
    "profit-factor",
    perf.profit_factor === null ? "No losses" : Number(perf.profit_factor).toFixed(2),
  );
  text("max-drawdown", money.format(Number(perf.max_drawdown || 0)));
}

function renderStrategies() {
  text(
    "strategies-count",
    `${state.strategies.length} tracked / ${state.researchCandidates.length} research`,
  );
  text("research-candidate-state", `${state.researchCandidates.length} candidates`);
  renderMktResearchIntakeReadiness();
  renderMktResearchRunbook();
  renderMktResearchImport();
  const body = document.getElementById("strategies-body");
  if (body) {
    body.innerHTML = "";
    if (!state.strategies.length) {
      body.appendChild(emptyRow(10, "No strategies configured yet"));
    } else {
      const configs = new Map(
        state.strategyConfigs.map((config) => [config.strategy, config]),
      );
      state.strategies.forEach((comparison) => {
        const strategy = { ...comparison, ...(configs.get(comparison.strategy) || {}) };
        const row = document.createElement("tr");
        const lifecycle = strategy.lifecycle_status || "UNREGISTERED";
        const lifecycleClass = lifecycle === "ACTIVE" ? "status-ok" : "status-warn";
        const stateLabel = strategy.is_enabled ? "Enabled" : "Disabled";
        const stateClass = strategy.is_enabled ? "status-ok" : "status-danger";
        const enableAllowed = Boolean(
          configs.get(comparison.strategy)?.enable_eligible
          && state.strategyFactoryReadiness?.source_integrity_verified
          && state.risk && !state.risk.kill_switch_enabled,
        );
        const action = strategy.is_enabled ? "Disable" : enableAllowed ? "Enable" : "Locked";
        const actionDisabled = !strategy.is_enabled && !enableAllowed;
        const risk = strategy.risk_per_trade === null ? "--" : percent.format(Number(strategy.risk_per_trade));
        const minRr =
          strategy.minimum_reward_risk === null
            ? "--"
            : `${Number(strategy.minimum_reward_risk).toFixed(2)}R`;
        row.innerHTML = `
          <td><strong>${escapeHtml(strategy.display_name)}</strong><span>${escapeHtml(strategy.strategy)}</span></td>
          <td><span class="status-pill ${lifecycleClass}" title="${escapeHtml(strategy.lifecycle_reason || "")}">${escapeHtml(lifecycle)}</span></td>
          <td><span class="status-pill ${stateClass}">${stateLabel}</span></td>
          <td>${escapeHtml((strategy.allowed_regimes || []).join(", "))}</td>
          <td>${risk}</td>
          <td>${minRr}</td>
          <td>${strategy.open_trades || 0}</td>
          <td>${strategy.closed_trades || 0}</td>
          <td>${money.format(Number(strategy.total_net_pl || 0))}</td>
          <td><button class="compact" type="button" data-strategy="${escapeHtml(strategy.strategy)}" data-enabled="${strategy.is_enabled}" title="${escapeHtml(strategy.lifecycle_reason || "")}" ${actionDisabled ? "disabled" : ""}>${action}</button></td>
        `;
        body.appendChild(row);
      });
    }
  }
  renderResearchCandidates();
}

function renderResearchCandidates() {
  const body = document.getElementById("research-candidates-body");
  if (!body) return;
  body.innerHTML = "";
  if (!state.researchCandidates.length) {
    renderResearchGate(null);
    renderResearchReadinessQueue();
    renderResearchEvidence();
    body.appendChild(emptyRow(7, "No research candidates recorded yet"));
    return;
  }

  const selected = ensureSelectedResearchCandidate();
  syncResearchCandidateInputs(selected);
  renderResearchGate(selected);
  renderResearchReadinessQueue();
  renderResearchEvidence();

  state.researchCandidates.forEach((candidate) => {
    const row = document.createElement("tr");
    if (candidate.id === state.selectedResearchCandidateId) {
      row.className = "is-selected";
    }
    const importQuality =
      candidate.normalized_payload?.source_quality_status ||
      candidate.normalized_payload?.import_quality_status ||
      "No import quality";
    row.innerHTML = `
      <td>${formatDate(candidate.last_seen_at)}</td>
      <td><strong>${escapeHtml(candidate.display_name)}</strong><span>${escapeHtml(candidate.strategy)} / ${escapeHtml(candidate.candidate_key)}</span></td>
      <td>${statusBadge(candidate.status)}</td>
      <td>${statusBadge(candidate.trade_eligible ? "ELIGIBLE" : "RESEARCH_ONLY")}</td>
      <td>${candidate.observation_count || 0}</td>
      <td>${escapeHtml(String(candidate.eligibility_reason || "").replaceAll("_", " "))}<span>${escapeHtml(importQuality)}</span></td>
      <td><button class="compact" type="button" data-research-candidate-id="${escapeHtml(candidate.id)}">Inspect</button></td>
    `;
    body.appendChild(row);
  });
}

function renderResearchReadinessQueue() {
  const body = document.getElementById("research-readiness-body");
  if (!body) return;
  body.innerHTML = "";
  const queue = state.researchReadinessQueue || {};
  const items = queue.items || [];
  const summary = queue.summary || {};
  text("research-readiness-state", `${items.length} queued`);
  className("research-readiness-state", `status-pill ${items.length ? "status-ok" : "status-warn"}`);
  text("research-readiness-paper", `${summary.paper_research_eligible || 0} paper-only`);
  text("research-readiness-blocked", `${summary.gate_blocked || 0} blocked`);
  text("research-readiness-ready", `${summary.ready_for_research_gate || 0} ready`);
  text("research-readiness-next", summary.top_next_action || "--");

  if (!items.length) {
    body.appendChild(emptyRow(7, "No research candidates in the readiness queue"));
    return;
  }

  items.forEach((item) => {
    const row = document.createElement("tr");
    if (item.candidate_id === state.selectedResearchCandidateId) {
      row.className = "is-selected";
    }
    const profitFactor = item.oos_profit_factor_infinite
      ? "No losses"
      : formatRatio(item.oos_profit_factor);
    row.innerHTML = `
      <td>${item.rank}</td>
      <td><strong>${escapeHtml(item.display_name)}</strong><span>${escapeHtml(item.strategy)} / ${escapeHtml(item.candidate_key)}</span></td>
      <td>${statusBadge(item.readiness_state)}</td>
      <td>${item.resolved_observation_count || 0}/${item.observation_count || 0} resolved / ${item.total_trades || 0} trades<span>${escapeHtml(item.regime_coverage || "No regime gate yet")} / ${escapeHtml(item.regime_diagnostics || "No regime diagnostics yet")} / ${escapeHtml(item.variant_pressure || "No variant gate yet")} / ${escapeHtml(item.variant_diagnostics || "No variant diagnostics yet")} / ${escapeHtml(item.statistical_significance || "No significance gate yet")}</span></td>
      <td>${item.oos_trades || 0} trades / ${money.format(Number(item.oos_expectancy || 0))} exp / PF ${profitFactor}<span>DD ${money.format(Number(item.oos_max_drawdown || 0))}</span></td>
      <td>${escapeHtml(item.next_action || "--")}</td>
      <td><button class="compact" type="button" data-research-candidate-id="${escapeHtml(item.candidate_id)}">Inspect</button></td>
    `;
    body.appendChild(row);
  });
}

function renderMktResearchIntakeReadiness() {
  const report = state.researchMktIntakeReadiness || null;
  if (!report) {
    text("research-mkt-intake-readiness-state", "NOT_CHECKED");
    className("research-mkt-intake-readiness-state", "status-pill status-warn");
    text(
      "research-mkt-intake-readiness-next",
      "Run MKT readiness before importing donor research.",
    );
    text("research-mkt-intake-db-freshness", "--");
    className("research-mkt-intake-db-freshness", "status-pill status-warn");
    text("research-mkt-log-activity", "--");
    className("research-mkt-log-activity", "status-pill status-warn");
    text("research-mkt-collection-health", "--");
    className("research-mkt-collection-health", "status-pill status-warn");
    text("research-mkt-intake-start-command", "--");
    return;
  }

  const status = report.status || "UNKNOWN";
  const statusClass = status === "RESEARCH_INTAKE_READY_FOR_BACKTEST_IMPORT"
    ? "status-ok"
    : status === "RESEARCH_INTAKE_READY_FOR_RESEARCH_IMPORT"
      ? "status-warn"
      : "status-danger";
  text("research-mkt-intake-readiness-state", status);
  className("research-mkt-intake-readiness-state", `status-pill ${statusClass}`);
  text(
    "research-mkt-intake-readiness-next",
    report.next_action || "Review MKT research intake readiness.",
  );
  const freshness = report.db_freshness_status || "UNKNOWN";
  const freshnessClass = freshness === "RESEARCH_DB_RECENT"
    ? "status-ok"
    : freshness === "RESEARCH_DB_STALE"
      ? "status-danger"
      : "status-warn";
  text(
    "research-mkt-intake-db-freshness",
    `${freshness} / ${report.db_file_size_bytes ?? "--"} B / ${formatDate(report.db_modified_at)}`,
  );
  className("research-mkt-intake-db-freshness", `status-pill ${freshnessClass}`);
  const activity = report.collection_activity_status || "UNKNOWN";
  const activityClass = activity === "RESEARCH_COLLECTION_DB_RECENT"
    || activity === "RESEARCH_COLLECTION_LOG_RECENT"
    || activity === "RESEARCH_COLLECTION_STARTING"
    ? "status-warn"
    : activity === "RESEARCH_COLLECTION_INACTIVE"
      ? "status-danger"
      : "status-warn";
  text(
    "research-mkt-log-activity",
    `${activity} / log mod ${formatDate(report.latest_log_modified_at)}`,
  );
  className("research-mkt-log-activity", `status-pill ${activityClass}`);
  const collectionHealth = report.collection_health || {};
  const healthStatus = collectionHealth.status || "UNKNOWN";
  const healthClass = healthStatus === "COLLECTION_HEALTH_BACKTEST_DEPTH_READY"
    ? "status-ok"
    : healthStatus === "COLLECTION_HEALTH_SAMPLE_READY"
      || healthStatus === "COLLECTION_HEALTH_COLLECTING"
      || healthStatus === "COLLECTION_HEALTH_UNRESOLVED_ONLY"
      ? "status-warn"
      : "status-danger";
  text(
    "research-mkt-collection-health",
    `${healthStatus} / ${Number(collectionHealth.backtest_depth_progress_pct || 0).toFixed(2)}% depth`,
  );
  className("research-mkt-collection-health", `status-pill ${healthClass}`);
  const startCommand = (report.command_hints || []).find((hint) =>
    String(hint.label || "").toLowerCase().includes("start mkt"),
  );
  text("research-mkt-intake-start-command", startCommand?.command || "--");
}

function renderMktResearchRunbook() {
  const report = state.researchMktRunbook || null;
  const body = document.getElementById("research-mkt-runbook-body");
  if (!report) {
    text("research-mkt-runbook-state", "NOT_RUN");
    text("research-mkt-runbook-current-step", "--");
    text("research-mkt-runbook-current-command", "--");
    text("research-mkt-runbook-progress", "--");
    text("research-mkt-runbook-badge", "NOT_RUN");
    className("research-mkt-runbook-badge", "status-pill status-warn");
    text(
      "research-mkt-runbook-next",
      "Build the MKT research runbook before importing donor research.",
    );
    if (body) {
      body.innerHTML = "";
      body.appendChild(emptyRow(5, "Build the MKT research runbook to see ordered steps"));
    }
    return;
  }

  const status = report.status || "UNKNOWN";
  const statusClass = status === "RUNBOOK_READY_FOR_BACKTEST_GATE"
    ? "status-ok"
    : status === "RUNBOOK_READY_FOR_RESEARCH_IMPORT"
      || status === "RUNBOOK_COLLECTION_ACTIVE"
      ? "status-warn"
      : "status-danger";
  text("research-mkt-runbook-state", status);
  const currentStep = report.current_step || null;
  text(
    "research-mkt-runbook-current-step",
    currentStep
      ? `${currentStep.rank}. ${currentStep.label} / ${currentStep.status}`
      : "--",
  );
  text("research-mkt-runbook-current-command", report.current_command || "--");
  text(
    "research-mkt-runbook-progress",
    `${report.completed_step_count || 0}/${report.total_step_count || 0} / ${Number(report.progress_pct || 0).toFixed(2)}%`,
  );
  text("research-mkt-runbook-badge", status);
  className("research-mkt-runbook-badge", `status-pill ${statusClass}`);
  text("research-mkt-runbook-next", report.next_action || "Review MKT research runbook.");
  if (!body) return;
  body.innerHTML = "";
  const steps = report.steps || [];
  if (!steps.length) {
    body.appendChild(emptyRow(5, "No runbook steps available"));
    return;
  }
  steps.forEach((step) => {
    const row = document.createElement("tr");
    row.innerHTML = `
      <td>${step.rank}. <strong>${escapeHtml(step.label)}</strong><span>${escapeHtml(step.key)}</span></td>
      <td>${statusBadge(step.status)}</td>
      <td>${escapeHtml(step.evidence || "--")}</td>
      <td>${step.writes_research_ledger ? statusBadge("LEDGER_WRITE") : "Read-only"}</td>
      <td>${escapeHtml(step.next_action || "--")}</td>
    `;
    body.appendChild(row);
  });
}

function renderMktResearchImport() {
  const report = state.researchMktImport || null;
  const body = document.getElementById("research-mkt-import-quality-body");
  if (!report) {
    text("research-mkt-import-state", "NOT_RUN");
    className("research-mkt-import-state", "status-pill status-warn");
    text("research-mkt-import-rows", "--");
    text("research-mkt-import-depth", "--");
    text("research-mkt-import-mutation", "--");
    text("research-mkt-import-next", "Run MKT preflight after selecting a donor DB.");
    if (body) {
      body.innerHTML = "";
      body.appendChild(emptyRow(7, "Run MKT import to inspect source quality"));
    }
    return;
  }

  const status = report.quality_status || "UNKNOWN";
  const statusClass = status === "IMPORT_BACKTEST_CANDIDATE"
    ? "status-ok"
    : ["IMPORT_SPARSE_RESOLVED_SAMPLE", "IMPORT_UNRESOLVED_ONLY"].includes(status)
      ? "status-warn"
      : "status-danger";
  text("research-mkt-import-state", status);
  className("research-mkt-import-state", `status-pill ${statusClass}`);
  const mode = report.preflight_only ? "preflight" : "import";
  text(
    "research-mkt-import-rows",
    `${report.processed_observations || 0} ${mode} row(s) / ${report.skipped_rows || 0} skipped`,
  );
  text(
    "research-mkt-import-depth",
    `${report.resolved_observations || 0} resolved / ${report.unresolved_observations || 0} unresolved`,
  );
  text(
    "research-mkt-import-mutation",
    report.mutates_research_ledger ? "writes research ledger" : "read-only preflight",
  );
  text("research-mkt-import-next", report.next_action || "Review MKT research import quality.");

  if (!body) return;
  body.innerHTML = "";
  const quality = report.source_quality || [];
  if (!quality.length) {
    body.appendChild(emptyRow(7, "No MKT source quality details returned"));
    return;
  }

  quality.forEach((item) => {
    const row = document.createElement("tr");
    row.innerHTML = `
      <td><strong>${escapeHtml(item.source || "--")}</strong></td>
      <td>${escapeHtml(item.table || "--")}</td>
      <td>${mktImportSourceStatusBadge(item.status || "UNKNOWN")}</td>
      <td>${item.resolved_observations || 0}</td>
      <td>${item.unresolved_observations || 0}</td>
      <td>${item.resolved_observations || 0}/${item.target_resolved_observations || 100}</td>
      <td>${escapeHtml(item.next_action || "--")}</td>
    `;
    body.appendChild(row);
  });
}

function mktImportSourceStatusBadge(status) {
  const normalized = String(status || "UNKNOWN");
  const statusClass = normalized === "SOURCE_BACKTEST_CANDIDATE"
    ? "status-ok"
    : ["SOURCE_SPARSE_RESOLVED_SAMPLE", "SOURCE_UNRESOLVED_ONLY"].includes(normalized)
      ? "status-warn"
      : "status-danger";
  return `<span class="status-pill ${statusClass}">${escapeHtml(normalized)}</span>`;
}

function renderResearchGate(candidate) {
  const report = latestResearchBacktest(candidate);
  if (!report) {
    text("research-gate-state", "NO_BACKTEST");
    className("research-gate-state", "status-pill status-warn");
    text("research-gate-decision", "Not evaluated");
    text("research-gate-blocker", "Run the research gate before paper eligibility");
    text("research-gate-oos", "--");
    text("research-gate-drawdown", "--");
    text("research-gate-regime", "--");
    text("research-gate-variants", "--");
    text("research-gate-significance", "--");
    return;
  }

  const metrics = report.metrics || {};
  const requirements = report.requirements || {};
  const oos = metrics.out_of_sample || {};
  const regime = metrics.regime_breakdown || {};
  const regimeDiagnostics = metrics.regime_diagnostics || {};
  const variants = metrics.multiple_testing || {};
  const variantDiagnostics = metrics.variant_diagnostics || {};
  const significance = metrics.statistical_significance || {};
  const accepted = Boolean(report.accepted);
  const stateLabel = accepted ? "PAPER_ELIGIBLE" : "BLOCKED";
  text("research-gate-state", stateLabel);
  className("research-gate-state", `status-pill ${accepted ? "status-ok" : "status-danger"}`);
  text("research-gate-decision", `${report.decision || "--"} / ${metrics.total_trades || 0} trades`);
  text("research-gate-blocker", researchGateBlocker(report));
  text("research-gate-oos", researchGateOosSummary(oos));
  text("research-gate-drawdown", researchGateDrawdownSummary(oos, requirements));
  text("research-gate-regime", researchGateRegimeSummary(regime, requirements, regimeDiagnostics));
  text("research-gate-variants", researchGateVariantSummary(variants, variantDiagnostics));
  text("research-gate-significance", researchGateSignificanceSummary(significance));
}

function latestResearchBacktest(candidate) {
  return candidate?.normalized_payload?.latest_research_backtest || null;
}

function syncResearchCandidateInputs(candidate) {
  if (!candidate) return;
  setInput("research-candidate-key", candidate.candidate_key);
  setInput("research-strategy", candidate.strategy);
  setInput("research-display-name", candidate.display_name);
  setInput("research-hypothesis", candidate.hypothesis);
}

function researchGateBlocker(report) {
  const reasons = report.reasons || [];
  if (!reasons.length) return "Accepted for paper research only";
  return String(reasons[0]).replaceAll("_", " ");
}

function researchGateOosSummary(oos) {
  const trades = oos.total_trades || 0;
  const expectancy = money.format(Number(oos.expectancy || 0));
  const profitFactor = oos.profit_factor_infinite ? "No losses" : formatRatio(oos.profit_factor);
  return `${trades} trades / ${expectancy} exp / PF ${profitFactor}`;
}

function researchGateDrawdownSummary(oos, requirements) {
  const drawdown = money.format(Number(oos.max_drawdown || 0));
  const limit = money.format(Number(requirements.maximum_oos_drawdown || 0));
  return `${drawdown} / ${limit}`;
}

function researchGateRegimeSummary(regime, requirements, diagnostics = {}) {
  const eligible = regime.eligible_group_count || 0;
  const passed = regime.passed_group_count || 0;
  const missing = regime.missing_regime_count || 0;
  const required = requirements.minimum_regime_groups || 0;
  const diagnosticStatus = diagnostics.status ? ` / ${diagnostics.status}` : "";
  const thin = diagnostics.thin_group_count || 0;
  const weak = diagnostics.weak_group_count || 0;
  return `${passed}/${eligible} pass / ${required} required / ${missing} unknown${diagnosticStatus} / ${thin} thin / ${weak} weak`;
}

function researchGateVariantSummary(variants, diagnostics = {}) {
  const effective = variants.effective_tested_variant_count || 0;
  const maximum = variants.maximum_tested_variants || 0;
  const adjusted = formatRatio(variants.adjusted_minimum_oos_profit_factor);
  const diagnosticStatus = diagnostics.status ? ` / ${diagnostics.status}` : "";
  const thin = diagnostics.thin_group_count || 0;
  const weak = diagnostics.weak_group_count || 0;
  return `${effective}/${maximum} variants / adjusted PF ${adjusted}${diagnosticStatus} / ${thin} thin / ${weak} weak`;
}

function researchGateSignificanceSummary(significance) {
  if (!significance || !significance.method) return "--";
  const state = significance.passed ? "PASS" : "BLOCK";
  const wins = significance.wins || 0;
  const trades = significance.oos_trades || 0;
  const adjusted = formatRatio(significance.adjusted_p_value);
  const limit = formatRatio(significance.maximum_p_value);
  return `${state} / ${wins}/${trades} OOS wins / p ${adjusted} <= ${limit}`;
}

function renderResearchEvidence() {
  const evidence = state.researchEvidence;
  const runsBody = document.getElementById("research-backtest-runs-body");
  const observationsBody = document.getElementById("research-observation-evidence-body");
  if (!runsBody || !observationsBody) return;
  runsBody.innerHTML = "";
  observationsBody.innerHTML = "";

  if (!evidence) {
    text("research-evidence-state", "NO_CANDIDATE");
    className("research-evidence-state", "status-pill status-warn");
    text("research-evidence-resolution", "--");
    text("research-evidence-history", "--");
    text("research-evidence-hash", "--");
    text("research-evidence-candidate", "--");
    runsBody.appendChild(emptyRow(6, "No research gate history yet"));
    observationsBody.appendChild(emptyRow(6, "No candidate observations selected"));
    return;
  }

  const candidate = evidence.candidate || {};
  const summary = evidence.evidence_summary || {};
  const latest = evidence.latest_backtest || null;
  text("research-evidence-state", latest ? (latest.accepted ? "PASS_HISTORY" : "BLOCKED_HISTORY") : "NO_BACKTEST");
  className(
    "research-evidence-state",
    `status-pill ${latest?.accepted ? "status-ok" : "status-warn"}`,
  );
  text(
    "research-evidence-resolution",
    `${summary.resolved_observation_count || 0}/${summary.observation_count || 0} resolved`,
  );
  text(
    "research-evidence-history",
    `${summary.accepted_backtest_run_count || 0}/${summary.backtest_run_count || 0} accepted runs`,
  );
  text("research-evidence-hash", shortHash(summary.latest_backtest_hash));
  text("research-evidence-candidate", candidate.display_name || candidate.candidate_key || "--");

  const runs = evidence.backtest_runs || [];
  if (!runs.length) {
    runsBody.appendChild(emptyRow(6, "Run the research gate to create backtest evidence"));
  } else {
    runs.forEach((run) => {
      const metrics = run.metrics || {};
      const oos = metrics.out_of_sample || {};
      const reasons = run.reasons || [];
      const row = document.createElement("tr");
      row.innerHTML = `
        <td>${formatDate(run.reviewed_at)}</td>
        <td>${statusBadge(run.accepted ? "ACCEPTED" : "BLOCKED")}<span>${escapeHtml(run.decision || "--")}</span></td>
        <td>${metrics.total_trades || 0}</td>
        <td>${oos.total_trades || 0} / PF ${formatRatio(oos.profit_factor)} / EXP ${money.format(Number(oos.expectancy || 0))}<span>${researchGateSignificanceSummary(metrics.statistical_significance || {})}</span></td>
        <td>${escapeHtml(String(reasons[0] || "accepted_for_paper_only").replaceAll("_", " "))}</td>
        <td>${escapeHtml(shortHash(run.evidence_hash))}</td>
      `;
      runsBody.appendChild(row);
    });
  }

  const observations = evidence.observations || [];
  if (!observations.length) {
    observationsBody.appendChild(emptyRow(6, "No candidate observations recorded yet"));
  } else {
    observations.forEach((observation) => {
      const row = document.createElement("tr");
      row.innerHTML = `
        <td>${formatDate(observation.observed_at)}</td>
        <td>${escapeHtml(observation.observation_type || "--")}</td>
        <td>${escapeHtml(observation.symbol || observation.contract_ticker || "--")}</td>
        <td>${escapeHtml(observation.side || "--")}</td>
        <td>${observation.resolved_at ? statusBadge("RESOLVED") : statusBadge("UNRESOLVED")}</td>
        <td>${escapeHtml(shortHash(observation.evidence_hash))}</td>
      `;
      observationsBody.appendChild(row);
    });
  }
}

function renderAnalyst() {
  const analyst = state.analyst;
  if (!analyst) return;
  text("analyst-state", analyst.advisory_only ? "Advisory" : "Blocked");
  className("analyst-state", `status-pill ${analyst.advisory_only ? "status-ok" : "status-danger"}`);
  text("analyst-closed-trades", String(analyst.closed_trades || 0));
  text("analyst-note-count", String(analyst.note_count || 0));
  text("analyst-warning-count", String(analyst.warning_count || 0));
  text("analyst-critical-count", String(analyst.critical_count || 0));
  text("analyst-headline", analyst.headline || "--");

  const list = document.getElementById("analyst-notes-list");
  if (!list) return;
  list.innerHTML = "";
  const notes = analyst.latest_notes || [];
  if (!notes.length) {
    const item = document.createElement("li");
    item.className = "empty-state";
    item.textContent = "No analyst notes yet";
    list.appendChild(item);
    return;
  }

  notes.forEach((note) => {
    const item = document.createElement("li");
    item.innerHTML = `
      <strong>${statusBadge(note.severity)} ${escapeHtml(note.title)}</strong>
      <time>${formatDate(note.generated_at)} / ${escapeHtml(note.note_type)}</time>
      <span>${escapeHtml(note.summary)}</span>
    `;
    list.appendChild(item);
  });
}

function renderBroker() {
  const broker = state.broker;
  if (!broker) return;
  const connection = broker.sandbox_connection || {};
  const ready = broker.ready_for_live && !broker.live_trading_enabled;
  text("broker-state", ready ? "Ready" : "Blocked");
  className("broker-state", `status-pill ${ready ? "status-ok" : "status-warn"}`);
  text("broker-environment", connection.environment || "--");
  text("broker-live-enabled", broker.live_trading_enabled ? "Yes" : "No");
  text("broker-connection-status", connection.status || "--");
  text("broker-reconciliation", broker.latest_reconciliation?.status || "NOT_RUN");
  text("broker-summary", broker.summary || "--");

  const list = document.getElementById("broker-checks-list");
  if (!list) return;
  list.innerHTML = "";
  const checks = broker.checks || [];
  if (!checks.length) {
    const item = document.createElement("li");
    item.className = "empty-state";
    item.textContent = "No readiness checks yet";
    list.appendChild(item);
    return;
  }

  checks.forEach((check) => {
    const item = document.createElement("li");
    item.innerHTML = `
      <strong>${statusBadge(check.status)} ${escapeHtml(check.name)}</strong>
      <time>${formatDate(check.last_checked_at)} / ${escapeHtml(check.check_key)}</time>
      <span>${escapeHtml(check.notes || "")}</span>
    `;
    list.appendChild(item);
  });
}

function initializeOperatorProfileForm() {
  if (state.operatorProfileInitialized || !state.operatorProfileTemplate) return;
  const attestedAt = document.getElementById("operator-profile-attested-at");
  if (attestedAt) {
    attestedAt.value =
      state.operatorProfileTemplate.input_template?.attested_at
      || new Date().toISOString();
  }
  state.operatorProfileInitialized = true;
}

function renderOperatorProfile() {
  initializeOperatorProfileForm();
  const sandbox = state.sandboxProfileStatus || {};
  const testnet = state.binanceTestnetStatus || {};
  const sandboxStatus = sandbox.workflow_status || "INPUT_REQUIRED";
  const sandboxVerified = sandboxStatus === "FROZEN_VERIFIED";
  const sandboxInvalid = sandboxStatus === "FROZEN_INVALID";
  text("sandbox-profile-state", String(sandboxStatus).replaceAll("_", " "));
  className(
    "sandbox-profile-state",
    `status-pill ${
      sandboxVerified ? "status-ok" : sandboxInvalid ? "status-danger" : "status-warn"
    }`,
  );
  text(
    "sandbox-profile-artifact",
    sandbox.artifact_exists
      ? `${sandbox.artifact_verified ? "VERIFIED" : "INVALID"} / ${shortHash(
        sandbox.profile_evidence_hash,
      )}`
      : `ABSENT / ${
        sandbox.artifact_path
        || "data/evidence/binance_spot_testnet_sandbox_profile_v1.json"
      }`,
  );
  text(
    "sandbox-profile-gates",
    `${sandbox.passed_gate_count ?? 0}/${sandbox.total_gate_count ?? 9}`,
  );
  text(
    "sandbox-profile-adapter-authority",
    sandbox.sandbox_adapter_implementation_authorized ? "AUTHORIZED" : "BLOCKED",
  );
  text(
    "sandbox-connectivity-public",
    testnet.public_connectivity_verified ? "VERIFIED" : "NOT VERIFIED",
  );
  text(
    "sandbox-connectivity-auth",
    testnet.authenticated_account_read_verified ? "VERIFIED" : "NOT VERIFIED",
  );
  text(
    "sandbox-connectivity-test-order",
    testnet.signed_test_order_verified ? "VERIFIED" : "NOT VERIFIED",
  );
  text(
    "sandbox-connectivity-cancel",
    testnet.virtual_cancel_lifecycle_verified ? "VERIFIED" : "NOT VERIFIED",
  );
  text(
    "sandbox-connectivity-reconciliation",
    testnet.order_reconciliation_verified ? "VERIFIED" : "NOT VERIFIED",
  );
  text(
    "sandbox-fill-contract",
    testnet.fill_fee_contract_frozen
      ? `FROZEN / ${shortHash(testnet.fill_fee_contract_sha256)}`
      : "NOT FROZEN",
  );
  text(
    "sandbox-fill-reconciliation",
    testnet.fill_fee_reconciliation_verified
      ? "VERIFIED"
      : testnet.fill_fee_campaign_recorded
        ? "FAILED OR INVALID"
        : "NOT RUN",
  );
  text(
    "sandbox-stream-contract",
    testnet.user_stream_contract_frozen
      ? `FROZEN / ${shortHash(testnet.user_stream_contract_sha256)}`
      : "NOT FROZEN",
  );
  text(
    "sandbox-stream-reconciliation",
    testnet.user_stream_reconciliation_verified
      ? "VERIFIED"
      : testnet.user_stream_campaign_recorded
        ? "FAILED OR INVALID"
        : "NOT RUN",
  );
  text(
    "sandbox-restart-contract",
    testnet.restart_soak_contract_frozen
      ? `FROZEN / ${shortHash(testnet.restart_soak_contract_sha256)}`
      : "NOT FROZEN",
  );
  text(
    "sandbox-restart-reconciliation",
    testnet.restart_soak_reconciliation_verified
      ? "VERIFIED"
      : testnet.restart_soak_campaign_recorded
        ? "FAILED OR INVALID"
        : "NOT RUN",
  );
  text(
    "sandbox-profile-order-authority",
    sandbox.testnet_virtual_order_entry_authorized ? "AUTHORIZED" : "BLOCKED",
  );
  text(
    "sandbox-profile-qualification",
    testnet.sandbox_qualified ? "QUALIFIED" : "NOT QUALIFIED",
  );
  text(
    "sandbox-profile-live-authority",
    sandbox.creates_live_eligibility || sandbox.real_capital_authorized
      ? "POLICY ERROR"
      : "DISABLED",
  );
  text(
    "sandbox-profile-next",
    testnet.next_action
      || (
        sandboxVerified
          ? "Configure local Testnet credentials and qualify the adapter"
          : "Freeze and independently verify the sandbox profile"
      ),
  );
  const artifact = state.operatorProfileStatus || {};
  const preflight = state.operatorProfilePreflight;
  const workflowStatus = preflight?.status || artifact.workflow_status || "INPUT_REQUIRED";
  const passing = workflowStatus === "PASS" || workflowStatus === "FROZEN_VERIFIED";
  const failing = workflowStatus === "BLOCKED" || workflowStatus === "FROZEN_INVALID";
  text("operator-profile-state", String(workflowStatus).replaceAll("_", " "));
  className(
    "operator-profile-state",
    `status-pill ${passing ? "status-ok" : failing ? "status-danger" : "status-warn"}`,
  );
  text(
    "operator-profile-artifact",
    artifact.artifact_exists
      ? `${artifact.artifact_verified ? "VERIFIED" : "INVALID"} / ${shortHash(artifact.profile_evidence_hash)}`
      : `ABSENT / ${artifact.artifact_path || "data/evidence/post_v4_operator_access_profile_v1.json"}`,
  );
  text(
    "operator-profile-decision",
    String(preflight?.decision || artifact.decision || "INPUT REQUIRED").replaceAll(
      "_",
      " ",
    ),
  );
  const passedGates = preflight?.passed_gate_count ?? artifact.passed_gate_count ?? 0;
  const totalGates = preflight?.total_gate_count ?? artifact.total_gate_count ?? 9;
  text("operator-profile-gates", `${passedGates}/${totalGates}`);
  text(
    "operator-profile-total-risk",
    preflight ? percent.format(Number(preflight.maximum_total_loss_ratio || 0)) : "--",
  );
  text(
    "operator-profile-daily-risk",
    preflight ? percent.format(Number(preflight.maximum_daily_loss_ratio || 0)) : "--",
  );
  text(
    "operator-profile-trade-risk",
    preflight ? percent.format(Number(preflight.maximum_per_trade_loss_ratio || 0)) : "--",
  );
  text(
    "operator-profile-milestone-ratio",
    preflight
      ? percent.format(Number(preflight.first_profit_milestone_to_capital_ratio || 0))
      : "--",
  );
  const charterDesign = Boolean(
    preflight?.successor_charter_design_authorized
    || artifact.successor_charter_design_authorized,
  );
  text(
    "operator-profile-authority",
    charterDesign
      ? "SUCCESSOR CHARTER DESIGN ONLY / no execution"
      : "NO TRADING AUTHORITY",
  );
  const nextActions = {
    INPUT_REQUIRED: "Supply operator facts",
    CORRECT_OPERATOR_INPUT: "Correct failed gates",
    RUN_INDEPENDENT_CLI_FREEZE: "Download input and run independent CLI freeze",
    AUDIT_EXISTING_FROZEN_PROFILE: "Audit the existing frozen profile",
  };
  text(
    "operator-profile-next",
    nextActions[preflight?.next_action || workflowStatus] || "Independent review required",
  );
  text(
    "operator-profile-note",
    "NO CREDENTIALS / PREFLIGHT WRITES NOTHING / PASS AUTHORIZES CHARTER DESIGN ONLY",
  );

  const readyToExport = Boolean(
    preflight?.status === "PASS"
    && !preflight?.frozen_artifact_exists
    && state.operatorProfileValidatedInput,
  );
  setDisabled("operator-profile-download-button", !readyToExport);
  setDisabled("operator-profile-copy-freeze-button", !readyToExport);

  const list = document.getElementById("operator-profile-gate-list");
  if (!list) return;
  list.innerHTML = "";
  const gates = preflight?.gate_results
    || (state.operatorProfileTemplate?.gate_ids || []).map((gateId) => ({
      gate_id: gateId,
      status: "PENDING",
      reason: "Awaiting credential-free operator input and no-write preflight.",
    }));
  gates.forEach((gate) => {
    const item = document.createElement("li");
    const gateStatus = String(gate.status || "PENDING").toLowerCase();
    item.className = `is-${gateStatus}`;
    item.innerHTML = `
      <strong>${escapeHtml(String(gate.gate_id || "--").replaceAll("_", " "))}</strong>
      <span>${escapeHtml(gate.reason || "--")}</span>
    `;
    list.appendChild(item);
  });
}

function renderDeployment() {
  const deployment = state.deployment;
  if (!deployment) return;
  const plan = deployment.plan || {};
  text("deployment-state", deployment.status || "--");
  className("deployment-state", `status-pill ${deployment.activation_allowed ? "status-ok" : "status-warn"}`);
  text("deployment-live-enabled", deployment.live_trading_enabled ? "Yes" : "No");
  text("deployment-strategy", plan.strategy || "--");
  text("deployment-symbols", (plan.symbols || []).join(", ") || "--");
  text("deployment-risk", plan.risk_per_trade === undefined ? "--" : percent.format(Number(plan.risk_per_trade)));
  text("deployment-target", money.format(Number(plan.target_net_profit || 100)));
  text("deployment-approvals", approvalCount(plan.approval_snapshot || {}));
  text("deployment-activation-audit", activationAuditSummary(state.activationAttempt));
  text("deployment-live-adapter", liveExecutionAdapterSummary(deployment));
  text("deployment-mkt-credentials", mktDonorCredentialBoundarySummary(deployment));
  text("deployment-backtest-evidence", backtestEvidence(deployment));
  text("deployment-paper-evidence", deployment.latest_paper_evidence?.status || "NOT_RUN");
  text("deployment-paper-freshness", paperEvidenceFreshness(deployment));
  text("deployment-paper-progress", paperEvidenceProgress(deployment.latest_paper_evidence));
  text("deployment-paper-scope", paperEvidenceScope(deployment.latest_paper_evidence));
  text("deployment-paper-coverage", paperEvidenceCoverage(deployment.latest_paper_evidence));
  text("deployment-paper-integrity", paperEvidenceIntegrity(deployment.latest_paper_evidence));
  text("deployment-paper-execution", paperExecutionQuality(deployment.latest_paper_evidence));
  text("deployment-journal-coverage", journalCoverage(deployment.latest_paper_evidence));
  text("deployment-prediction-demo", predictionDemoCampaignSummary(deployment));
  text("deployment-prediction-demo-selected", predictionDemoCampaignSelectedSummary(deployment));
  text("deployment-prediction-demo-campaign-drift", predictionDemoCampaignDriftSummary(deployment));
  text("deployment-prediction-demo-batch-drift", predictionDemoBatchDriftSummary(deployment));
  text("deployment-prediction-demo-next", predictionDemoCampaignNextAction(deployment));
  text("deployment-statement-reconciliation", statementReconciliation(deployment.latest_broker_statement));
  text("deployment-statement-freshness", statementFreshness(deployment));
  text("deployment-profit-milestone", profitMilestone(deployment.latest_profit_milestone));
  text("deployment-evidence-review", strategyEvidenceReviewSummary((state.strategyEvidenceReviews || [])[0], deployment));
  text("deployment-evidence-review-next", strategyEvidenceReviewNextAction((state.strategyEvidenceReviews || [])[0], deployment));
  text("deployment-evidence-review-blockers", strategyEvidenceReviewBlockers((state.strategyEvidenceReviews || [])[0], deployment));
  text("deployment-approval-packet", deployment.latest_approval_packet?.status || "NOT_RUN");
  text("deployment-broker-diligence", brokerDiligence(deployment.latest_approval_packet));
  text("deployment-summary", deployment.summary || "--");

  const list = document.getElementById("deployment-gates-list");
  if (!list) return;
  list.innerHTML = "";
  const gates = deployment.gates || [];
  if (!gates.length) {
    const item = document.createElement("li");
    item.className = "empty-state";
    item.textContent = "No deployment gates yet";
    list.appendChild(item);
    return;
  }

  gates.forEach((gate) => {
    const item = document.createElement("li");
    item.innerHTML = `
      <strong>${statusBadge(gate.status)} ${escapeHtml(gate.name)}</strong>
      <time>${formatDate(gate.last_checked_at)} / ${escapeHtml(gate.gate_key)}</time>
      <span>${escapeHtml(gate.notes || "")}</span>
    `;
    list.appendChild(item);
  });
}

function renderBrokerStatementPreflight() {
  const preflight = state.brokerStatementPreflight;
  const latest = state.deployment?.latest_broker_statement || null;
  const analysis = preflight?.analysis_summary || latest?.statement_snapshot?.csv_analysis_summary || null;
  if (preflight) {
    const discrepancies = preflight.reconciliation_discrepancies || [];
    const reconcilePreview = discrepancies.length
      ? String(discrepancies[0].reason || "statement_discrepancy").replaceAll("_", " ")
      : "matched";
    text(
      "deployment-statement-csv-summary",
      `${preflight.status} / ${preflight.reconciliation_status || "NOT_READY"} / ${preflight.importable_count || 0} ready / ${preflight.rejected_count || 0} rejected / ${reconcilePreview} / ${money.format(Number(preflight.broker_net_pl || 0))}`,
    );
  } else if (latest) {
    text(
      "deployment-statement-csv-summary",
      `${latest.status} / ${latest.broker_trade_count || 0} broker / ${latest.aurex_trade_count || 0} Aurex`,
    );
  } else {
    text("deployment-statement-csv-summary", "--");
  }

  if (!analysis) {
    text("deployment-statement-csv-fixes", "--");
    return;
  }
  const fixes = analysis.fix_queue || [];
  text(
    "deployment-statement-csv-fixes",
    fixes.length
      ? fixes.map((item) => `${item.count} ${String(item.reason || "unknown").replaceAll("_", " ")}`).join(" / ")
      : "No rejected rows",
  );
}

function renderBacktestPreflight() {
  const preflight = state.backtestPreflight;
  const latest = (state.backtestReports || [])[0];
  const analysis = preflight?.analysis_summary || latest?.result?.metrics_snapshot || null;

  if (preflight) {
    text(
      "backtest-preflight-summary",
      `${preflight.status} / ${preflight.importable_count || 0} ready / ${preflight.rejected_count || 0} rejected`,
    );
  } else if (latest) {
    text(
      "backtest-preflight-summary",
      `${latest.result?.acceptance_passed ? "ACCEPTED" : "BLOCKED"} / ${latest.result?.total_trades || 0} trades`,
    );
  } else {
    text("backtest-preflight-summary", "--");
  }

  const acceptance = preflight?.analysis_summary || latest?.result || null;
  if (acceptance) {
    const passed = Boolean(acceptance.acceptance_passed);
    const reasons = acceptance.acceptance_reasons || [];
    text(
      "backtest-acceptance-summary",
      `${passed ? "PASS" : "BLOCKED"} / ${reasons[0] || "No acceptance result"}`,
    );
  } else {
    text("backtest-acceptance-summary", "--");
  }

  const eligibility = state.backtestPaperEligibility;
  const sourceEvidence = eligibility?.evidence_snapshot?.source_evidence || {};
  const sourceContractStatus = sourceEvidence.trusted
    ? "source contract passed"
    : sourceEvidence.policy
      ? "source contract blocked"
      : "source contract unavailable";
  text(
    "backtest-paper-eligibility",
    eligibility
      ? `${eligibility.approved ? "READY" : "BLOCKED"} / ${String(eligibility.reason || "unknown").replaceAll("_", " ")} / ${sourceContractStatus}`
      : "--",
  );

  renderBacktestAnalysis(analysis);
}

function renderBacktestSetup() {
  const setup = state.backtestStrategySetup;
  if (!setup) {
    text("backtest-setup-summary", "--");
    return;
  }
  const fingerprint = setup.settings_fingerprint ? shortHash(setup.settings_fingerprint) : "no fingerprint";
  text(
    "backtest-setup-summary",
    `${setup.strategy} v${setup.strategy_version} / ${setup.symbol} ${setup.timeframe} / ${fingerprint}`,
  );
}

function renderBacktestWindowPlan() {
  const plan = state.backtestWindowPlan;
  if (!plan) {
    text("backtest-window-plan-summary", "--");
    return;
  }
  text(
    "backtest-window-plan-summary",
    `${plan.status} / ${plan.window_count} folds / ${shortHash(plan.plan_hash)} / ${plan.outcome_fields_inspected.length} outcomes inspected`,
  );
}

function renderBacktestOhlcv() {
  const preflight = state.backtestOhlcvPreflight;
  const latest = (state.backtestDatasets || [])[0] || null;
  const quality = preflight?.quality_snapshot || latest?.quality_snapshot || null;
  const status = preflight?.status || (latest ? "IMPORTED" : "NOT_LOADED");
  text("backtest-ohlcv-state", status);
  className(
    "backtest-ohlcv-state",
    `status-pill ${status === "READY" || status === "IMPORTED" ? "status-ok" : "status-warn"}`,
  );
  text(
    "backtest-ohlcv-rows",
    preflight
      ? `${preflight.valid_rows} valid / ${preflight.rejected_rows} rejected`
      : latest
        ? `${latest.row_count} immutable rows`
        : "--",
  );
  const start = preflight?.data_start || latest?.data_start;
  const end = preflight?.data_end || latest?.data_end;
  text("backtest-ohlcv-coverage", start && end ? `${formatDate(start)} to ${formatDate(end)}` : "--");
  text(
    "backtest-ohlcv-gaps",
    quality
      ? `${quality.missing_interval_count || 0} missing / ${quality.interval_mismatch_count || 0} off interval`
      : "--",
  );
  text(
    "backtest-ohlcv-gap-evidence",
    quality?.documented_gaps?.length
      ? `${quality.documented_gap_count || 0}/${quality.observed_gaps?.length || 0} documented / ${quality.undocumented_gap_count || 0} uncovered`
      : quality?.observed_gaps?.length
        ? "No documented outage evidence"
        : "No observed gaps",
  );
  const artifacts = quality?.source_artifacts || [];
  const verifiedArtifacts = artifacts.filter((artifact) => artifact.checksum_verified).length;
  text(
    "backtest-ohlcv-source-verification",
    artifacts.length
      ? `${verifiedArtifacts}/${artifacts.length} verified / ${shortHash(quality.source_artifact_bundle_hash)}`
      : "No upstream artifact manifest",
  );
  text(
    "backtest-ohlcv-input-hash",
    shortHash(
      preflight?.canonical_csv_sha256 ||
      latest?.canonical_csv_sha256 ||
      quality?.canonical_csv_sha256,
    ),
  );
  text(
    "backtest-ohlcv-hash",
    shortHash(preflight?.evidence_hash || latest?.evidence_hash) || "--",
  );
  text(
    "backtest-ohlcv-latest",
    latest ? `${latest.symbol} ${latest.timeframe} / ${shortHash(latest.id)}` : "--",
  );
  const importButton = document.getElementById("backtest-ohlcv-import-button");
  if (importButton) importButton.disabled = preflight?.status !== "READY";
}

function renderBacktestReferenceReplay() {
  const select = document.getElementById("backtest-reference-dataset-id");
  if (!select) return;
  const selected = select.value;
  select.innerHTML = '<option value="">Import an immutable dataset first</option>';
  (state.backtestDatasets || []).forEach((dataset) => {
    const option = document.createElement("option");
    option.value = dataset.id;
    option.textContent = `${dataset.symbol} ${dataset.timeframe} / ${dataset.row_count} rows / ${shortHash(dataset.evidence_hash)}`;
    select.appendChild(option);
  });
  const selectedExists = (state.backtestDatasets || []).some((item) => item.id === selected);
  select.value = selectedExists ? selected : state.backtestDatasets?.[0]?.id || "";

  const replay = state.backtestReferenceReplay || state.backtestReferenceRuns?.[0] || null;
  const recorded = Boolean(replay?.immutable);
  const replayState = replay
    ? `${replay.status}${recorded ? " / RECORDED" : " / PREFLIGHT"}`
    : "NOT_RUN";
  text("backtest-reference-state", replayState);
  className(
    "backtest-reference-state",
    `status-pill ${replay?.status === "READY" ? "status-ok" : "status-warn"}`,
  );
  text("backtest-reference-engine", replay?.engine_version || "--");
  text(
    "backtest-reference-dataset",
    replay ? `${shortHash(replay.dataset_id)} / ${shortHash(replay.dataset_evidence_hash)}` : "--",
  );
  text("backtest-reference-trades", replay ? String(replay.metrics?.total_trades || 0) : "--");
  text(
    "backtest-reference-net-pl",
    replay ? money.format(Number(replay.metrics?.total_net_pl || 0)) : "--",
  );
  const warmup = replay?.diagnostics?.warmup;
  text(
    "backtest-reference-warmup",
    warmup
      ? `${formatWarmupPair(warmup.base_candles_available_at_start, warmup.base_candles_required)} base / ${formatWarmupPair(warmup.higher_candles_available_at_start, warmup.higher_candles_required)} HTF`
      : "--",
  );
  text("backtest-reference-eligibility", "COMPARISON ONLY / never acceptance evidence");
  text("backtest-reference-hash", shortHash(replay?.engine_evidence_hash));
  text("backtest-reference-record-hash", shortHash(replay?.record_evidence_hash));
  text(
    "backtest-reference-recorded-at",
    recorded && replay?.recorded_at ? formatDate(replay.recorded_at) : "NOT RECORDED",
  );
  text(
    "backtest-reference-blocker",
    replay?.reasons?.[0] || replay?.warnings?.[0] || "--",
  );
  const button = document.getElementById("backtest-reference-button");
  if (button) button.disabled = !select.value;
  const recordButton = document.getElementById("backtest-reference-record-button");
  if (recordButton) {
    recordButton.disabled = state.backtestReferenceReplay?.status !== "READY";
  }

  const replaySelect = document.getElementById("backtest-reference-validation-replay-id");
  const protocolSelect = document.getElementById(
    "backtest-reference-validation-protocol-id",
  );
  if (!replaySelect || !protocolSelect) return;
  const selectedReplay = replaySelect.value;
  replaySelect.innerHTML = '<option value="">Record a reference replay first</option>';
  (state.backtestReferenceRuns || []).forEach((run) => {
    const option = document.createElement("option");
    option.value = run.id;
    option.textContent = `${run.strategy} v${run.strategy_version} / ${run.metrics?.total_trades || 0} trades / ${shortHash(run.record_evidence_hash)}`;
    replaySelect.appendChild(option);
  });
  const replayExists = (state.backtestReferenceRuns || []).some(
    (run) => run.id === selectedReplay,
  );
  replaySelect.value = replayExists
    ? selectedReplay
    : state.backtestReferenceRuns?.[0]?.id || "";

  const selectedProtocol = protocolSelect.value;
  protocolSelect.innerHTML = '<option value="">Register a frozen protocol first</option>';
  (state.backtestProtocols || []).forEach((protocol) => {
    const option = document.createElement("option");
    option.value = protocol.id;
    option.textContent = `${protocol.status} / ${protocol.strategy} v${protocol.strategy_version} / ${(protocol.symbols || []).join(",")} ${protocol.timeframe} / ${shortHash(protocol.protocol_hash)}`;
    protocolSelect.appendChild(option);
  });
  const protocolExists = (state.backtestProtocols || []).some(
    (protocol) => protocol.id === selectedProtocol,
  );
  protocolSelect.value = protocolExists
    ? selectedProtocol
    : state.backtestProtocols?.[0]?.id || "";

  const validation = state.backtestReferenceValidationPreflight
    || state.backtestReferenceValidations?.[0]
    || null;
  const validationRecorded = Boolean(validation?.immutable);
  const validationState = validation
    ? `${validation.status}${validationRecorded ? " / RECORDED" : " / PREFLIGHT"}`
    : "NOT_RUN";
  text("backtest-reference-validation-state", validationState);
  className(
    "backtest-reference-validation-state",
    `status-pill ${validation?.status === "PASSED" ? "status-ok" : "status-warn"}`,
  );
  const metrics = validation?.metrics_snapshot || {};
  const outOfSample = metrics.out_of_sample || {};
  const walkForward = metrics.walk_forward || {};
  const distribution = metrics.trade_distribution || {};
  const regimes = metrics.market_regime_breakdown || {};
  const assignment = metrics.sample_assignment || {};
  const bindingChecks = validation?.binding_checks || [];
  const passedBindings = bindingChecks.filter((check) => check.status === "PASS").length;
  text(
    "backtest-reference-validation-binding",
    bindingChecks.length ? `${passedBindings}/${bindingChecks.length} passed` : "--",
  );
  text(
    "backtest-reference-validation-oos",
    validation
      ? `${outOfSample.total_trades || 0} trades / PF ${outOfSample.profit_factor || "--"} / EXP ${money.format(Number(outOfSample.expectancy || 0))}`
      : "--",
  );
  text(
    "backtest-reference-validation-walk-forward",
    validation
      ? `${walkForward.passed_windows || 0}/${walkForward.window_count || 0} passed / ${percent.format(Number(walkForward.pass_rate || 0))}`
      : "--",
  );
  text(
    "backtest-reference-validation-distribution",
    validation
      ? `${distribution.active_trading_days || 0} active days / ${percent.format(Number(distribution.max_single_day_trade_share || 0))} max day`
      : "--",
  );
  const upRegime = regimes.regimes?.TRENDING_UP || {};
  const downRegime = regimes.regimes?.TRENDING_DOWN || {};
  text(
    "backtest-reference-validation-regimes",
    validation
      ? `${regimes.regime_count || 0} regimes / up PF ${upRegime.profit_factor || "--"} / down PF ${downRegime.profit_factor || "--"}`
      : "--",
  );
  text(
    "backtest-reference-validation-assignment",
    validation
      ? `${assignment.in_sample_trade_count || 0} IS / ${assignment.out_of_sample_trade_count || 0} OOS / ${assignment.unassigned_trade_count || 0} unassigned`
      : "--",
  );
  text(
    "backtest-reference-validation-hash",
    shortHash(validation?.validation_evidence_hash),
  );
  text(
    "backtest-reference-validation-blocker",
    validation?.reasons?.[0]
      || validation?.acceptance_reasons?.[0]
      || validation?.warnings?.[0]
      || "--",
  );
  const validationButton = document.getElementById(
    "backtest-reference-validation-button",
  );
  if (validationButton) {
    validationButton.disabled = !replaySelect.value || !protocolSelect.value;
  }
  const validationRecordButton = document.getElementById(
    "backtest-reference-validation-record-button",
  );
  if (validationRecordButton) {
    validationRecordButton.disabled = !["PASSED", "REJECTED"].includes(
      state.backtestReferenceValidationPreflight?.status,
    );
  }
}

function renderBacktestParity() {
  const datasetSelect = document.getElementById("backtest-parity-dataset-id");
  const chartDatasetSelect = document.getElementById(
    "backtest-parity-chart-dataset-id",
  );
  const reportSelect = document.getElementById("backtest-parity-report-id");
  if (!datasetSelect || !chartDatasetSelect || !reportSelect) return;

  const selectedDataset = datasetSelect.value;
  const referenceDatasets = (state.backtestDatasets || []).filter(
    (dataset) => String(dataset.source || "").toLowerCase() === "binance-vision",
  );
  datasetSelect.innerHTML = referenceDatasets.length
    ? '<option value="">Select a verified Binance Vision dataset</option>'
    : '<option value="">Import verified Binance Vision data first</option>';
  referenceDatasets.forEach((dataset) => {
    const option = document.createElement("option");
    option.value = dataset.id;
    option.textContent = `${dataset.symbol} ${dataset.timeframe} / ${dataset.row_count} rows / ${shortHash(dataset.evidence_hash)}`;
    datasetSelect.appendChild(option);
  });
  const datasetExists = referenceDatasets.some(
    (dataset) => dataset.id === selectedDataset,
  );
  datasetSelect.value = datasetExists ? selectedDataset : "";

  const selectedChartDataset = chartDatasetSelect.value;
  const chartDatasets = (state.backtestDatasets || []).filter(
    (dataset) => String(dataset.source || "").toLowerCase() === "tradingview-chart-export",
  );
  chartDatasetSelect.innerHTML = chartDatasets.length
    ? '<option value="">Select the matching TradingView chart dataset</option>'
    : '<option value="">Import the matching TradingView chart CSV first</option>';
  chartDatasets.forEach((dataset) => {
    const option = document.createElement("option");
    option.value = dataset.id;
    option.textContent = `${dataset.symbol} ${dataset.timeframe} / ${dataset.row_count} rows / ${shortHash(dataset.evidence_hash)}`;
    chartDatasetSelect.appendChild(option);
  });
  const chartDatasetExists = chartDatasets.some(
    (dataset) => dataset.id === selectedChartDataset,
  );
  chartDatasetSelect.value = chartDatasetExists ? selectedChartDataset : "";

  const selectedReport = reportSelect.value;
  const tradingViewReports = (state.backtestReports || []).filter(
    (report) => report.source_format === "tradingview",
  );
  reportSelect.innerHTML = tradingViewReports.length
    ? '<option value="">Select an imported TradingView strategy report</option>'
    : '<option value="">Import a TradingView strategy report first</option>';
  tradingViewReports.forEach((report) => {
    const option = document.createElement("option");
    option.value = report.id;
    option.textContent = `${report.strategy} v${report.strategy_version} / ${(report.symbols || []).join(",")} ${report.timeframe} / ${report.result?.total_trades || 0} trades / ${shortHash(report.evidence_hash)}`;
    reportSelect.appendChild(option);
  });
  const reportExists = tradingViewReports.some((report) => report.id === selectedReport);
  reportSelect.value = reportExists ? selectedReport : "";

  const lineage = state.backtestParityExportManifest;
  const lineageManifest = lineage?.manifest || {};
  const lineageMatches = Boolean(
    lineage?.status === "READY"
    && lineageManifest.reference_dataset?.dataset_id === datasetSelect.value
    && lineageManifest.tradingview_chart_export?.dataset_id === chartDatasetSelect.value
    && lineageManifest.tradingview_report_export?.run_id === reportSelect.value,
  );
  const lineageStatus = lineageMatches
    ? "READY"
    : lineage?.status === "BLOCKED"
      ? "BLOCKED"
      : "NOT PREPARED";
  text("backtest-parity-lineage-state", lineageStatus);
  text(
    "backtest-parity-lineage-hash",
    lineageMatches ? shortHash(lineage?.manifest_hash) : "--",
  );
  const lineageButton = document.getElementById("backtest-parity-lineage-button");
  if (lineageButton) {
    lineageButton.disabled = !datasetSelect.value
      || !chartDatasetSelect.value
      || !reportSelect.value
      || !document.getElementById("backtest-parity-export-attestation")?.checked;
  }

  const parity = state.backtestParityPreflight || state.backtestParityRuns?.[0] || null;
  const summary = parity?.summary || {};
  const marketSummary = parity?.market_data_summary || {};
  const mismatchCounts = summary.field_mismatch_counts || {};
  const marketMismatchCounts = marketSummary.field_mismatch_counts || {};
  const topMismatch = Object.entries(mismatchCounts).sort((left, right) => right[1] - left[1])[0];
  const topMarketMismatch = Object.entries(marketMismatchCounts)
    .sort((left, right) => right[1] - left[1])[0];
  const status = parity?.status || "NOT_RUN";
  text("backtest-parity-state", status);
  className(
    "backtest-parity-state",
    `status-pill ${status === "PASSED" ? "status-ok" : "status-warn"}`,
  );
  text(
    "backtest-parity-report",
    parity ? `${shortHash(parity.tradingview_run_id)} / ${shortHash(parity.tradingview_evidence_hash)}` : "--",
  );
  text("backtest-parity-engine", parity?.engine_version || "--");
  text(
    "backtest-parity-market-counts",
    parity
      ? `${marketSummary.tradingview_candle_count || 0} TradingView / ${marketSummary.reference_candle_count || 0} Binance Vision`
      : "--",
  );
  text(
    "backtest-parity-market-match",
    parity
      ? `${marketSummary.matched_candle_count || 0}/${Math.max(marketSummary.tradingview_candle_count || 0, marketSummary.reference_candle_count || 0)} / ${percent.format(Number(marketSummary.match_rate || 0))}`
      : "--",
  );
  text(
    "backtest-parity-counts",
    parity ? `${summary.reference_trade_count || 0} TradingView / ${summary.replay_trade_count || 0} replay` : "--",
  );
  text(
    "backtest-parity-matches",
    parity ? `${summary.matched_trade_count || 0}/${Math.max(summary.reference_trade_count || 0, summary.replay_trade_count || 0)} / ${percent.format(Number(summary.match_rate || 0))}` : "--",
  );
  text(
    "backtest-parity-unmatched",
    parity ? `${summary.reference_only_count || 0} TradingView only / ${summary.replay_only_count || 0} replay only` : "--",
  );
  text(
    "backtest-parity-mismatch",
    topMarketMismatch
      ? `candle ${String(topMarketMismatch[0]).replaceAll("_", " ")} / ${topMarketMismatch[1]}`
      : topMismatch
        ? `${String(topMismatch[0]).replaceAll("_", " ")} / ${topMismatch[1]}`
        : parity ? "None" : "--",
  );
  text("backtest-parity-hash", shortHash(parity?.parity_evidence_hash));
  text("backtest-parity-eligibility", "COMPARISON ONLY / never acceptance evidence");
  text(
    "backtest-parity-note",
    parity?.reasons?.[0] || parity?.warnings?.[0] || "Select evidence sources to measure trade-level parity.",
  );

  const preflightButton = document.getElementById("backtest-parity-preflight-button");
  if (preflightButton) {
    preflightButton.disabled = !datasetSelect.value
      || !chartDatasetSelect.value
      || !reportSelect.value
      || !lineageMatches;
  }
  const recordButton = document.getElementById("backtest-parity-record-button");
  if (recordButton) {
    recordButton.disabled = !state.backtestParityPreflight?.parity_evidence_hash ||
      state.backtestParityPreflight?.status === "BLOCKED";
  }

  const body = document.getElementById("backtest-parity-body");
  if (!body) return;
  body.innerHTML = "";
  const marketMismatches = parity?.market_data_mismatches || [];
  const mismatches = parity?.mismatches || [];
  if (!marketMismatches.length && !mismatches.length) {
    body.appendChild(emptyRow(
      4,
      parity?.status === "PASSED"
        ? "No candle or trade-level mismatches"
        : "No parity comparison yet",
    ));
    return;
  }
  marketMismatches.slice(0, 100).forEach((mismatch) => {
    const tradingview = mismatch.tradingview || null;
    const reference = mismatch.reference || null;
    const candleText = (candle) => candle
      ? `O ${candle.open} / H ${candle.high} / L ${candle.low} / C ${candle.close} / V ${candle.volume}`
      : "--";
    const row = document.createElement("tr");
    row.innerHTML = `
      <td><strong>CANDLE ${escapeHtml(String(mismatch.status || "MISMATCH").replaceAll("_", " "))}</strong><span>${escapeHtml(mismatch.timestamp || "--")}</span></td>
      <td>${escapeHtml(candleText(tradingview))}</td>
      <td>${escapeHtml(candleText(reference))}</td>
      <td>${escapeHtml((mismatch.reasons || []).map((reason) => String(reason).replaceAll("_", " ")).join(", "))}</td>
    `;
    body.appendChild(row);
  });
  const remainingRows = Math.max(0, 100 - marketMismatches.length);
  mismatches.slice(0, remainingRows).forEach((mismatch) => {
    const row = document.createElement("tr");
    row.innerHTML = `
      <td><strong>${escapeHtml(String(mismatch.status || "MISMATCH").replaceAll("_", " "))}</strong><span>${escapeHtml((mismatch.field_results || []).map((item) => item.field).join(", ") || "sequence alignment")}</span></td>
      <td>${escapeHtml(mismatch.reference_entry_at || "--")}<span>#${escapeHtml(String(mismatch.reference_sequence || "--"))}</span></td>
      <td>${escapeHtml(mismatch.replay_entry_at || "--")}<span>#${escapeHtml(String(mismatch.replay_sequence || "--"))}</span></td>
      <td>${escapeHtml((mismatch.reasons || []).map((reason) => String(reason).replaceAll("_", " ")).join(", "))}</td>
    `;
    body.appendChild(row);
  });
}

function renderBacktestProtocols() {
  const select = document.getElementById("backtest-protocol-id");
  if (!select) return;
  const selected = select.value;
  select.innerHTML = '<option value="">Register or select a protocol before preflight</option>';
  (state.backtestProtocols || []).forEach((protocol) => {
    const option = document.createElement("option");
    option.value = protocol.id;
    option.textContent = `${protocol.status} / ${protocol.strategy} v${protocol.strategy_version} / ${(protocol.symbols || []).join(",")} ${protocol.timeframe} / ${shortHash(protocol.protocol_hash)}`;
    option.disabled = protocol.status === "CONSUMED";
    select.appendChild(option);
  });

  const selectedStillAvailable = (state.backtestProtocols || []).some(
    (protocol) => protocol.id === selected && protocol.status !== "CONSUMED",
  );
  const matching = (state.backtestProtocols || []).find(
    (protocol) => protocol.status === "REGISTERED" && backtestProtocolMatchesForm(protocol),
  );
  select.value = selectedStillAvailable ? selected : matching?.id || "";

  const protocolAudit =
    state.backtestPreflight?.analysis_summary?.metrics_snapshot?.backtest_protocol ||
    state.backtestReports?.[0]?.result?.metrics_snapshot?.backtest_protocol ||
    null;
  const active = (state.backtestProtocols || []).find(
    (protocol) => protocol.id === select.value,
  );
  const manifest = state.backtestRunManifest?.protocol_id === active?.id
    ? state.backtestRunManifest
    : null;
  const runPackage = state.backtestRunPackage?.protocol_id === active?.id
    ? state.backtestRunPackage
    : null;
  if (protocolAudit) {
    text(
      "backtest-protocol-summary",
      `${protocolAudit.status} / ${shortHash(protocolAudit.protocol_hash)} / ${(protocolAudit.reasons || [])[0] || "pre-registered"}`,
    );
  } else if (active) {
    text(
      "backtest-protocol-summary",
      `${active.status} / ${shortHash(active.protocol_hash)} / ${formatDate(active.registered_at)}`,
    );
  } else {
    text("backtest-protocol-summary", "BLOCKED / register the protocol before running results");
  }

  const source = manifest?.source_evidence || active?.protocol_snapshot?.strategy_source_evidence ||
    state.backtestStrategySetup?.strategy_source_evidence || null;
  const manifestStatus = manifest?.status || (active ? "NOT_VERIFIED" : "BLOCKED");
  text("backtest-run-manifest-state", manifestStatus);
  className(
    "backtest-run-manifest-state",
    `status-pill ${manifestStatus === "READY" ? "status-ok" : "status-warn"}`,
  );
  text(
    "backtest-run-source",
    source
      ? `${source.ready ? "CURRENT" : "BLOCKED"} / v${source.pine_version || "--"} / ${shortHash(source.pine_source_sha256)}`
      : "--",
  );
  text(
    "backtest-run-manifest-hash",
    manifest ? `${shortHash(manifest.manifest_hash)} / ${manifest.protocol_status}` : "--",
  );
  text(
    "backtest-run-ticker",
    runPackage?.ticker_id || manifest?.tradingview_setup?.chart?.ticker_id || "--",
  );
  text(
    "backtest-run-package-hash",
    runPackage
      ? `${runPackage.status} / ${shortHash(runPackage.package_hash)} / ${runPackage.source_byte_length || 0} bytes`
      : "--",
  );
  const passedChecks = (manifest?.checks || []).filter((item) => item.passed).length;
  text(
    "backtest-run-checks",
    manifest ? `${passedChecks}/${manifest.checks.length} passed` : "--",
  );
  text(
    "backtest-run-blocker",
    manifest?.reasons?.[0] || (manifest?.status === "READY" ? "None" : "Verify the selected protocol"),
  );
  const manifestButton = document.getElementById("backtest-run-manifest-button");
  if (manifestButton) manifestButton.disabled = !active;
  setDisabled("backtest-run-package-button", manifest?.status !== "READY");
  setDisabled("backtest-copy-pine-button", runPackage?.status !== "READY" || !runPackage?.pine_source);
  setDisabled("backtest-copy-setup-button", runPackage?.status !== "READY");
}

function backtestProtocolMatchesForm(protocol) {
  const snapshot = protocol.protocol_snapshot || {};
  return (
    snapshot.strategy === inputValue("backtest-strategy") &&
    snapshot.strategy_version === inputValue("backtest-version") &&
    (snapshot.symbols || []).join(",") ===
      inputValue("backtest-symbols").split(",").map((item) => item.trim().toUpperCase()).filter(Boolean).join(",") &&
    snapshot.timeframe === inputValue("backtest-timeframe") &&
    snapshot.source_reference === nullableInputValue("backtest-source-reference") &&
    snapshot.data_start === normalizedIsoInput("backtest-data-start") &&
    snapshot.data_end === normalizedIsoInput("backtest-data-end")
  );
}

function normalizedIsoInput(id) {
  const value = inputValue(id);
  if (!value) return null;
  const parsed = new Date(value);
  return Number.isNaN(parsed.getTime()) ? value : parsed.toISOString().replace(".000Z", "+00:00");
}

function renderBacktestAnalysis(analysis) {
  const snapshot = analysis?.metrics_snapshot || analysis || null;
  if (!snapshot) {
    text("backtest-oos-summary", "--");
    text("backtest-walk-forward-summary", "--");
    text("backtest-distribution-summary", "--");
    text("backtest-regime-summary", "--");
    text("backtest-parameter-summary", "--");
    text("backtest-fix-summary", "--");
    return;
  }

  const oos = snapshot.out_of_sample || {};
  const walkForward = snapshot.walk_forward || {};
  const distribution = snapshot.trade_distribution || {};
  const regime = snapshot.market_regime_breakdown || {};
  text(
    "backtest-oos-summary",
    `${oos.total_trades || 0} trades / PF ${formatRatio(oos.profit_factor)} / EXP ${money.format(Number(oos.expectancy || 0))}`,
  );
  text(
    "backtest-walk-forward-summary",
    walkForward.acceptance_eligible
      ? `EXPLICIT / ${walkForward.passed_windows || 0}/${walkForward.valid_window_count || 0} valid pass / ${walkForward.window_count || 0} declared / ${percent.format(Number(walkForward.pass_rate || 0))}`
      : `DIAGNOSTIC / ${walkForward.passed_windows || 0}/${walkForward.window_count || 0} slices / not acceptance evidence`,
  );
  text(
    "backtest-distribution-summary",
    `${distribution.active_trading_days || 0} active / max day ${percent.format(Number(distribution.max_single_day_trade_share || 0))}`,
  );
  text(
    "backtest-regime-summary",
    `${regime.regime_count || 0} regimes / ${regime.missing_market_regime_count || 0} missing`,
  );
  text("backtest-parameter-summary", backtestParameterEvidenceSummary(snapshot.strategy_parameter_evidence));

  const diagnostic = analysis?.diagnostic || null;
  if (diagnostic?.status && diagnostic.status !== "READY_FOR_IMPORT") {
    text(
      "backtest-fix-summary",
      `${String(diagnostic.status).replaceAll("_", " ")} / ${diagnostic.next_action || String((diagnostic.reasons || [])[0] || "Check export").replaceAll("_", " ")}`,
    );
    return;
  }

  const fixes = analysis?.fix_queue || [];
  text(
    "backtest-fix-summary",
    fixes.length
      ? fixes.map((item) => `${item.count} ${String(item.reason || "unknown").replaceAll("_", " ")}`).join(" / ")
      : "No rejected rows",
  );
}

function renderBacktestReports() {
  const reports = state.backtestReports || [];
  const latest = reports[0];
  const latestEligibility = state.backtestPaperEligibility;
  const latestIsEligibilityRun = latest?.id === latestEligibility?.backtest_run_id;
  const latestStatus = !latest
    ? "NO_REPORTS"
    : !latest.result?.acceptance_passed
      ? "METRICS BLOCKED"
      : latestIsEligibilityRun && latestEligibility?.approved
        ? "PAPER ELIGIBLE"
        : latestIsEligibilityRun
          ? "PROMOTION BLOCKED"
          : "METRICS ACCEPTED";
  text("backtest-import-state", latestStatus);
  className(
    "backtest-import-state",
    `status-pill ${latestIsEligibilityRun && latestEligibility?.approved ? "status-ok" : "status-warn"}`,
  );
  text("backtest-import-summary", latest ? backtestReportSummary(latest) : "No backtest reports yet");

  const body = document.getElementById("backtest-reports-body");
  if (!body) return;
  body.innerHTML = "";
  if (!reports.length) {
    body.appendChild(emptyRow(8, "No backtest reports imported yet"));
    return;
  }

  reports.forEach((report) => {
    const result = report.result || {};
    const snapshot = result.metrics_snapshot || {};
    const row = document.createElement("tr");
    const eligibilityApplies = report.id === latestEligibility?.backtest_run_id;
    const reportStatus = !result.acceptance_passed
      ? "METRICS BLOCKED"
      : eligibilityApplies && latestEligibility?.approved
        ? "PAPER ELIGIBLE"
        : eligibilityApplies
          ? "PROMOTION BLOCKED"
          : "METRICS ACCEPTED";
    row.innerHTML = `
      <td>${formatDate(report.data_end)}</td>
      <td><strong>${escapeHtml(report.strategy)}</strong><span>${escapeHtml(report.strategy_version)} / ${escapeHtml(report.source_format || "unknown")}</span></td>
      <td>${escapeHtml((report.symbols || []).join(", "))} / ${escapeHtml(report.timeframe || "")}</td>
      <td>${statusBadge(reportStatus)}</td>
      <td>${result.total_trades || 0}</td>
      <td>${snapshot.out_of_sample?.total_trades || 0}</td>
      <td>${snapshot.walk_forward?.passed_windows || 0}/${snapshot.walk_forward?.window_count || 0}</td>
      <td>${escapeHtml(String(report.evidence_hash || "").slice(0, 8))}</td>
    `;
    body.appendChild(row);
  });
}

function renderPredictionMarkets() {
  const summary = state.predictionSummary || {};
  const latestRecon = summary.latest_reconciliation || null;
  text("prediction-contract-count", String(summary.contracts || 0));
  text("prediction-intent-count", String(summary.order_intents || 0));
  text("prediction-order-count", String(summary.orders || 0));
  text("prediction-fill-count", String(summary.fills || 0));
  text("prediction-open-position-count", String(summary.open_positions || 0));
  text("prediction-settled-position-count", String(summary.settled_positions || 0));
  text("prediction-rejected-count", String(summary.rejected_intents || 0));
  text("prediction-reconciliation-state", latestRecon?.status || "NOT_RUN");
  text("prediction-live-state", summary.live_execution_enabled ? "Live enabled" : "Paper only");
  className(
    "prediction-live-state",
    `status-pill ${summary.live_execution_enabled ? "status-danger" : "status-ok"}`,
  );

  const latestContract = state.predictionContracts[0];
  const latestIntent = state.predictionIntents[0];
  const latestOpenPosition = state.predictionPositions.find((item) => item.status === "OPEN");
  maybeSetInput("prediction-contract-id", latestContract?.id);
  maybeSetInput("prediction-intent-id", latestIntent?.id);
  maybeSetInput("prediction-position-id", latestOpenPosition?.id || state.predictionPositions[0]?.id);
  renderPredictionDemoReadiness();
  renderPredictionDemoProgress();
  renderPredictionDemoRunbook();
  renderPredictionDemoLedger();
  renderPredictionDemoCampaignAudit();
  renderPredictionDemoBatchAudit();
  renderPredictionDemoBatch();
  renderPredictionContractCsvPreflight();
  renderPredictionContractMktDonorRunbook();
  renderPredictionContractMktDonorBootstrap();
  renderPredictionContractMktDonorLaunchPreflight();
  renderPredictionContractMktDonorCollectionStatus();
  renderPredictionContractMktRuntimeSafety();
  renderPredictionContractMktDonorReadiness();
  renderPredictionContractMktDbDiscovery();
  renderPredictionContractMktDbReadiness();
  renderPredictionContractMktDbInventory();
  renderPredictionContractMktDbPreflight();
  renderPredictionMktDbCampaignReadiness();
  renderPredictionMktDbCampaignManifest();
  renderPredictionMktDbCampaign();
  renderPredictionPaperIntentGate();

  renderPredictionContracts();
  renderPredictionOrders();
  renderPredictionPositions();
  renderPredictionEvidence();
}

function renderPredictionDemoReadiness() {
  const readiness = state.predictionDemoReadiness || null;
  if (!readiness) {
    text("prediction-demo-readiness-state", "UNKNOWN");
    className("prediction-demo-readiness-state", "status-pill status-warn");
    text("prediction-demo-readiness-start", "--");
    text("prediction-demo-readiness-lifecycle", "--");
    text("prediction-demo-readiness-current", "--");
    text("prediction-demo-readiness-progress", "--");
    text("prediction-demo-readiness-next", "Refresh readiness after the API is available.");
    return;
  }

  const status = readiness.status || "UNKNOWN";
  const statusClass = readiness.demo_lifecycle_verified
    ? "status-ok"
    : readiness.ready_to_start
      ? "status-warn"
      : "status-danger";
  text("prediction-demo-readiness-state", status);
  className("prediction-demo-readiness-state", `status-pill ${statusClass}`);
  text(
    "prediction-demo-readiness-start",
    readiness.ready_to_start ? "Ready to run paper demo" : "Blocked before demo",
  );
  text(
    "prediction-demo-readiness-lifecycle",
    readiness.demo_lifecycle_verified ? "Verified paper lifecycle" : "Not verified",
  );
  const currentCheck = readiness.current_check || null;
  text(
    "prediction-demo-readiness-current",
    currentCheck ? `${currentCheck.key} / ${currentCheck.summary}` : "All checks passed",
  );
  text(
    "prediction-demo-readiness-progress",
    `${readiness.completed_check_count || 0}/${readiness.total_check_count || 0} / ${Number(readiness.progress_pct || 0).toFixed(2)}%`,
  );
  text("prediction-demo-readiness-next", readiness.next_action || "Collect paper-demo evidence.");
}

function renderPredictionDemoProgress() {
  const progress = state.predictionDemoProgress || null;
  if (!progress) {
    text("prediction-demo-progress-state", "UNKNOWN");
    className("prediction-demo-progress-state", "status-pill status-warn");
    text("prediction-demo-progress-current", "--");
    text("prediction-demo-progress-completion", "--");
    text("prediction-demo-closed-records", "--");
    text("prediction-demo-calendar-days", "--");
    text("prediction-demo-active-days", "--");
    text("prediction-demo-unique-contracts", "--");
    text("prediction-demo-pl", "--");
    text("prediction-demo-expectancy", "--");
    text("prediction-demo-concentration", "--");
    text("prediction-demo-contract-concentration", "--");
    text("prediction-demo-provenance", "--");
    text("prediction-demo-ledger-clean", "--");
    text("prediction-demo-progress-next", "Refresh progress after the API is available.");
    return;
  }

  const status = progress.status || "UNKNOWN";
  const statusClass = progress.ready_for_live_review
    ? "status-ok"
    : status === "RECONCILIATION_REQUIRED" || status === "PAPER_DEMO_LEDGER_BLOCKED"
      ? "status-danger"
      : "status-warn";
  text("prediction-demo-progress-state", status);
  className("prediction-demo-progress-state", `status-pill ${statusClass}`);
  const currentCheck = progress.current_check || null;
  text(
    "prediction-demo-progress-current",
    currentCheck ? `${currentCheck.key} / ${currentCheck.summary}` : "All checks passed",
  );
  text(
    "prediction-demo-progress-completion",
    `${progress.completed_check_count || 0}/${progress.total_check_count || 0} / ${Number(progress.progress_pct || 0).toFixed(2)}%`,
  );
  text(
    "prediction-demo-closed-records",
    `${progress.closed_records || 0}/${progress.target_closed_records || 100} (${progress.remaining_records || 0} left)`,
  );
  text(
    "prediction-demo-calendar-days",
    `${progress.calendar_days || 0}/${progress.target_calendar_days || 30} (${progress.remaining_calendar_days || 0} left)`,
  );
  text(
    "prediction-demo-active-days",
    `${progress.active_days || 0}/${progress.target_active_days || 15} (${progress.remaining_active_days || 0} left)`,
  );
  text(
    "prediction-demo-unique-contracts",
    `${progress.unique_contracts || 0}/${progress.target_unique_contracts || 25} (${progress.remaining_unique_contracts || 0} left)`,
  );
  text("prediction-demo-pl", money.format(Number(progress.fee_net_realized_pl || 0)));
  text("prediction-demo-expectancy", money.format(Number(progress.expectancy || 0)));
  text(
    "prediction-demo-concentration",
    `${formatPercentNumber(progress.max_single_day_record_share || 0)} / max ${formatPercentNumber(progress.distribution?.max_single_day_share_limit || 0.25)}`,
  );
  text(
    "prediction-demo-contract-concentration",
    `${formatPercentNumber(progress.max_single_contract_record_share || 0)} / max ${formatPercentNumber(progress.distribution?.max_single_contract_share_limit || 0.10)}`,
  );
  text(
    "prediction-demo-provenance",
    `${progress.provenance_complete_records || 0}/${progress.closed_records || 0} sourced`,
  );
  text(
    "prediction-demo-ledger-clean",
    `${progress.countable_ledger_records || 0}/${progress.raw_closed_records || 0} clean; ${progress.ledger_blocked_records || 0} blocked`,
  );
  text("prediction-demo-progress-next", progress.next_action || "Collect paper-demo evidence.");
}

function renderPredictionDemoRunbook() {
  const runbook = state.predictionDemoRunbook || null;
  const body = document.getElementById("prediction-demo-runbook-body");
  if (!runbook) {
    text("prediction-demo-runbook-state", "UNKNOWN");
    text("prediction-demo-runbook-current", "--");
    text("prediction-demo-runbook-upstream", "--");
    text("prediction-demo-runbook-progress", "--");
    text("prediction-demo-runbook-next", "Refresh paper/demo runbook after the API is available.");
    text("prediction-demo-runbook-badge", "UNKNOWN");
    className("prediction-demo-runbook-badge", "status-pill status-warn");
    if (body) {
      body.innerHTML = "";
      body.appendChild(emptyRow(5, "Paper/demo runbook unavailable"));
    }
    return;
  }

  const status = runbook.status || "UNKNOWN";
  const statusClass = status === "RUNBOOK_READY_FOR_LIVE_REVIEW"
    ? "status-ok"
    : status === "RUNBOOK_COLLECT_EVIDENCE" || status === "RUNBOOK_RUN_PAPER_LIFECYCLE"
      ? "status-warn"
      : "status-danger";
  const currentStep = runbook.current_step || null;
  text("prediction-demo-runbook-state", status);
  text("prediction-demo-runbook-badge", status);
  className("prediction-demo-runbook-badge", `status-pill ${statusClass}`);
  text(
    "prediction-demo-runbook-current",
    currentStep ? `${currentStep.rank}. ${currentStep.label} / ${currentStep.status}` : "--",
  );
  const upstream = runbook.upstream_research_runbook || null;
  text(
    "prediction-demo-runbook-upstream",
    upstream
      ? `${upstream.status || "UNKNOWN"} / ${upstream.current_step_key || "no step"} / ${upstream.next_action || "--"}`
      : "Research gate satisfied or not required",
  );
  text(
    "prediction-demo-runbook-progress",
    `${runbook.completed_step_count || 0}/${runbook.total_step_count || 0} / ${Number(runbook.progress_pct || 0).toFixed(2)}%`,
  );
  text("prediction-demo-runbook-next", runbook.next_action || "Review paper/demo runbook.");
  if (!body) return;
  body.innerHTML = "";
  const steps = runbook.steps || [];
  if (!steps.length) {
    body.appendChild(emptyRow(5, "No paper/demo runbook steps available"));
    return;
  }
  steps.forEach((step) => {
    const row = document.createElement("tr");
    row.innerHTML = `
      <td>${step.rank}. <strong>${escapeHtml(step.label)}</strong><span>${escapeHtml(step.key)}</span></td>
      <td>${statusBadge(step.status)}</td>
      <td>${escapeHtml(step.evidence || "--")}</td>
      <td>${step.writes_ledger ? statusBadge("LEDGER_WRITE") : "Read-only"}</td>
      <td>${escapeHtml(step.next_action || "--")}</td>
    `;
    body.appendChild(row);
  });
}

function renderPredictionDemoLedger() {
  const ledger = state.predictionDemoLedger || null;
  text(
    "prediction-demo-ledger-state",
    ledger
      ? `${ledger.countable_records || 0}/${ledger.record_count || 0} clean`
      : "UNKNOWN",
  );
  className(
    "prediction-demo-ledger-state",
    `status-pill ${
      ledger && ledger.blocked_records === 0 && ledger.record_count > 0
        ? "status-ok"
        : ledger && ledger.record_count > 0
          ? "status-warn"
          : "status-danger"
    }`,
  );
  text(
    "prediction-demo-ledger-next",
    ledger?.next_action || "Run guided paper/demo trades from recorded prediction-market snapshots.",
  );

  const body = document.getElementById("prediction-demo-ledger-body");
  if (!body) return;
  body.innerHTML = "";
  const records = ledger?.records || [];
  if (!records.length) {
    body.appendChild(emptyRow(10, "No closed prediction paper/demo records yet"));
    return;
  }

  records.forEach((record) => {
    const row = document.createElement("tr");
    const missingEvidence = record.missing_evidence_kinds || [];
    const recordedEvidence = record.recorded_evidence_kinds || [];
    const evidenceLabel = missingEvidence.length
      ? `Missing ${missingEvidence.join(", ")}`
      : `${recordedEvidence.length} events`;
    row.innerHTML = `
      <td>${formatDate(record.settled_at)}</td>
      <td><strong>${escapeHtml(record.contract_ticker)}</strong><span>${escapeHtml(record.source || "manual_snapshot")}</span></td>
      <td>${escapeHtml(record.primary_strategy || "--")}</td>
      <td>${money.format(Number(record.realized_pl || 0))}</td>
      <td>${money.format(Number(record.fees || 0))}</td>
      <td>${escapeHtml(record.imported_from_mkt ? "MKT import" : record.csv_format || "manual")}</td>
      <td>${statusBadge(record.reconciliation_status || "NOT_MATCHED")}</td>
      <td>${escapeHtml(shortHash(record.evidence_hash))}</td>
      <td>${escapeHtml(evidenceLabel)}</td>
      <td>${record.counts_toward_target ? statusBadge("COUNTED") : escapeHtml(record.blockers.join(", "))}</td>
    `;
    body.appendChild(row);
  });
}

function renderPredictionDemoCampaignAudit() {
  const audit = state.predictionDemoCampaigns || null;
  const records = audit?.records || [];
  text(
    "prediction-demo-campaign-state",
    audit
      ? `${audit.record_count || 0} campaign(s) / ${audit.current_result_drifted_records || 0} drift`
      : "UNKNOWN",
  );
  className(
    "prediction-demo-campaign-state",
    `status-pill ${
      records.length
        ? audit.current_result_drifted_records
          ? "status-danger"
          : audit.side_sensitive_records === audit.acknowledged_records
          ? "status-ok"
          : "status-warn"
        : "status-warn"
    }`,
  );
  text(
    "prediction-demo-campaign-next",
    audit?.next_action || "Run a guarded MKT DB campaign replay to create campaign audit evidence.",
  );

  const body = document.getElementById("prediction-demo-campaign-body");
  if (!body) return;
  body.innerHTML = "";
  if (!records.length) {
    body.appendChild(emptyRow(13, "No prediction paper/demo campaign evidence yet"));
    return;
  }

  records.forEach((record) => {
    const row = document.createElement("tr");
    const cleanRecords = record.countable_records || 0;
    const rawRecords = record.raw_closed_records ?? cleanRecords;
    const targetRecords = record.target_closed_records || 100;
    const remainingRecords = record.remaining_records ?? Math.max(targetRecords - cleanRecords, 0);
    const currentCheck = record.current_check_key
      ? record.current_check_key.replaceAll("_", " ")
      : record.ready_for_live_review
        ? "ready"
        : "unknown";
    const currentResultStatus = record.current_result_ledger_status || "UNKNOWN";
    const currentResultClass = currentResultStatus === "CURRENT_RESULT_LEDGER_CLEAN"
      ? "status-ok"
      : currentResultStatus === "CURRENT_RESULT_LEDGER_EMPTY"
        ? "status-warn"
        : "status-danger";
    const currentResultSummary = `${record.current_result_countable_records || 0}/${record.current_result_records || 0} current`;
    row.innerHTML = `
      <td>${formatDate(record.occurred_at)}</td>
      <td>${statusBadge(record.status || "UNKNOWN")}</td>
      <td>${escapeHtml(record.strategy || "--")}</td>
      <td>${escapeHtml(record.side || "--")}</td>
      <td>${money.format(Number(record.fee_net_realized_pl || 0))}</td>
      <td>${record.completed_records || 0}/${record.attempted_records || 0}</td>
      <td>${cleanRecords}/${targetRecords} clean (${rawRecords} raw) / ${remainingRecords} left</td>
      <td><span class="status-pill ${currentResultClass}">${escapeHtml(currentResultStatus.replaceAll("_", " "))}</span><span>${escapeHtml(currentResultSummary)}</span></td>
      <td>${Number(record.progress_pct || 0).toFixed(2)}% / ${escapeHtml(currentCheck)}</td>
      <td><strong>${escapeHtml(record.source || "--")}</strong><span>${escapeHtml(record.source_reference || "--")}</span></td>
      <td><strong>${escapeHtml(record.donor_evidence_tier || "--")}</strong><span>${escapeHtml(record.donor_use_scope || "--")}</span></td>
      <td>${record.side_sensitivity_warning ? escapeHtml(record.side_sensitivity_warning.replaceAll("_", " ")) : "none"}</td>
      <td>${escapeHtml(shortHash(record.evidence_hash))}</td>
    `;
    body.appendChild(row);
  });
}

function renderPredictionDemoBatchAudit() {
  const audit = state.predictionDemoBatches || null;
  const records = audit?.records || [];
  text(
    "prediction-demo-batch-audit-state",
    audit
      ? `${audit.record_count || 0} batch(es) / ${audit.current_result_drifted_records || 0} drift`
      : "UNKNOWN",
  );
  className(
    "prediction-demo-batch-audit-state",
    `status-pill ${
      records.length
        ? audit.current_result_drifted_records
          ? "status-danger"
          : "status-ok"
        : "status-warn"
    }`,
  );
  text(
    "prediction-demo-batch-audit-next",
    audit?.next_action || "Run reviewed prediction paper/demo batch replay to create batch audit evidence.",
  );

  const body = document.getElementById("prediction-demo-batch-audit-body");
  if (!body) return;
  body.innerHTML = "";
  if (!records.length) {
    body.appendChild(emptyRow(9, "No prediction paper/demo batch evidence yet"));
    return;
  }

  records.forEach((record) => {
    const row = document.createElement("tr");
    const cleanRecords = record.countable_records || 0;
    const rawRecords = record.raw_closed_records ?? cleanRecords;
    const targetRecords = record.target_closed_records || 100;
    const remainingRecords = record.remaining_records ?? Math.max(targetRecords - cleanRecords, 0);
    const currentResultStatus = record.current_result_ledger_status || "UNKNOWN";
    const currentResultClass = currentResultStatus === "CURRENT_RESULT_LEDGER_CLEAN"
      ? "status-ok"
      : currentResultStatus === "CURRENT_RESULT_LEDGER_EMPTY"
        ? "status-warn"
        : "status-danger";
    const currentResultSummary = `${record.current_result_countable_records || 0}/${record.current_result_records || 0} current`;
    row.innerHTML = `
      <td>${formatDate(record.occurred_at)}</td>
      <td>${statusBadge(record.status || "UNKNOWN")}</td>
      <td>${escapeHtml(record.side || "--")}</td>
      <td>${money.format(Number(record.fee_net_realized_pl || 0))}</td>
      <td>${record.completed_records || 0}/${record.attempted_records || 0}</td>
      <td>${cleanRecords}/${targetRecords} clean (${rawRecords} raw) / ${remainingRecords} left</td>
      <td><span class="status-pill ${currentResultClass}">${escapeHtml(currentResultStatus.replaceAll("_", " "))}</span><span>${escapeHtml(currentResultSummary)}</span></td>
      <td>${escapeHtml(shortHash(record.reviewed_preflight_hash || record.preflight_hash))}</td>
      <td>${escapeHtml(shortHash(record.evidence_hash))}</td>
    `;
    body.appendChild(row);
  });
}

function renderPredictionDemoBatch() {
  const batch = state.predictionDemoBatch || null;
  const preflight = state.predictionDemoBatchPreflight || null;
  const preflightHash = batch?.preflight_hash || preflight?.preflight_hash || null;
  const status = batch?.status || preflight?.status || "NOT_RUN";
  const statusClass = status === "BATCH_COMPLETED" || status === "READY"
    ? "status-ok"
    : status === "BATCH_PARTIAL" || status === "NO_NEW_CONTRACTS" || status === "READY_WITH_SKIPS"
      ? "status-warn"
      : status === "NOT_RUN"
        ? "status-warn"
        : "status-danger";
  text("prediction-demo-batch-state", status);
  className("prediction-demo-batch-state", `status-pill ${statusClass}`);
  text("prediction-demo-batch-hash", preflightHash ? shortHash(preflightHash) : "--");
  text(
    "prediction-demo-batch-records",
    batch
      ? `${batch.completed_records || 0}/${batch.attempted_records || 0} completed`
      : preflight
        ? `${preflight.eligible_records || 0}/${preflight.available_contracts || 0} ready`
      : "--",
  );
  text(
    "prediction-demo-batch-skipped",
    batch
      ? `${batch.skipped_records || 0} skipped / ${batch.rejected_records || 0} rejected`
      : preflight
        ? `${preflight.skipped_records || 0} skipped / max ${preflight.max_records || 0}`
      : "--",
  );
  text(
    "prediction-demo-batch-next",
    batch?.next_action || preflight?.next_action || "Run only after importing resolved snapshots.",
  );
}

function renderPredictionContractCsvPreflight() {
  const report = state.predictionContractCsvPreflight || null;
  if (!report) {
    text("prediction-csv-preflight-state", "NOT_RUN");
    className("prediction-csv-preflight-state", "status-pill status-warn");
    text("prediction-csv-importable", "--");
    text("prediction-csv-rejected", "--");
    text("prediction-csv-actionable", "--");
    return;
  }

  const status = report.status || "UNKNOWN";
  const statusClass = status === "READY"
    ? "status-ok"
    : status === "READY_WITH_REJECTIONS"
      ? "status-warn"
      : "status-danger";
  const summary = report.analysis_summary || {};
  text("prediction-csv-preflight-state", `${status} / ${report.csv_format || "auto"}`);
  className("prediction-csv-preflight-state", `status-pill ${statusClass}`);
  text("prediction-csv-importable", String(report.importable_count || 0));
  text("prediction-csv-rejected", String(report.rejected_count || 0));
  text(
    "prediction-csv-actionable",
    `${summary.actionable_yes_rows || 0} YES / ${summary.actionable_no_rows || 0} NO`,
  );
}

function renderPredictionContractMktDonorRunbook() {
  const runbook = state.predictionContractMktDonorRunbook || null;
  const body = document.getElementById("prediction-mkt-donor-runbook-body");
  if (!runbook) {
    text("prediction-mkt-donor-runbook-state", "NOT_BUILT");
    className("prediction-mkt-donor-runbook-state", "status-pill status-warn");
    text("prediction-mkt-donor-runbook-blockers", "--");
    text("prediction-mkt-donor-runbook-next", "Build the donor runbook before collecting MKT data.");
    if (body) {
      body.innerHTML = "";
      body.appendChild(emptyRow(6, "Build the MKT donor runbook to see collection steps"));
    }
    return;
  }

  const status = runbook.status || "UNKNOWN";
  const statusClass = status === "RUNBOOK_REPLAY_READY"
    ? "status-ok"
    : status === "RUNBOOK_RESEARCH_READY" || status === "RUNBOOK_COLLECT_DATA"
      ? "status-warn"
      : "status-danger";
  const blockers = (runbook.blockers || [])
    .map((item) => String(item).replaceAll("_", " "))
    .join(" / ");
  text("prediction-mkt-donor-runbook-state", status);
  className("prediction-mkt-donor-runbook-state", `status-pill ${statusClass}`);
  text("prediction-mkt-donor-runbook-blockers", blockers || "none");
  text("prediction-mkt-donor-runbook-next", runbook.next_action || "Review donor runbook.");

  if (!body) return;
  body.innerHTML = "";
  const steps = runbook.steps || [];
  if (!steps.length) {
    body.appendChild(emptyRow(6, "No donor runbook steps available"));
    return;
  }

  steps.forEach((step) => {
    const row = document.createElement("tr");
    row.innerHTML = `
      <td><strong>${step.step || "--"}</strong><span>${escapeHtml(step.title || "--")}</span></td>
      <td>${statusBadge(step.status || "UNKNOWN")}</td>
      <td>${escapeHtml(step.purpose || "--")}<span>${escapeHtml(step.verification || "--")}</span></td>
      <td>${escapeHtml(step.safety_gate || "--")}</td>
      <td>${step.command ? `<code>${escapeHtml(step.command)}</code>` : "--"}</td>
      <td>${escapeHtml(step.next_action || "--")}</td>
    `;
    body.appendChild(row);
  });
}

function renderPredictionContractMktDonorBootstrap() {
  const report = state.predictionContractMktDonorBootstrap || null;
  const body = document.getElementById("prediction-mkt-donor-bootstrap-body");
  updatePredictionMktDonorLaunchCommandButton();
  if (!report) {
    text("prediction-mkt-donor-bootstrap-state", "NOT_RUN");
    className("prediction-mkt-donor-bootstrap-state", "status-pill status-warn");
    text("prediction-mkt-donor-bootstrap-settings", "--");
    text(
      "prediction-mkt-donor-bootstrap-next",
      "Prepare a demo-safe MKT runtime before collection.",
    );
    if (body) {
      body.innerHTML = "";
      body.appendChild(emptyRow(3, "Prepare the MKT demo bootstrap to see commands"));
    }
    return;
  }

  const status = report.status || "UNKNOWN";
  const statusClass = status === "BOOTSTRAP_READY" ? "status-ok" : "status-danger";
  text("prediction-mkt-donor-bootstrap-state", status);
  className("prediction-mkt-donor-bootstrap-state", `status-pill ${statusClass}`);
  text(
    "prediction-mkt-donor-bootstrap-settings",
    `${report.settings_written ? "written" : "existing"} / ${report.settings_path || "--"}`,
  );
  text(
    "prediction-mkt-donor-bootstrap-next",
    report.next_action || "Review MKT demo bootstrap.",
  );

  if (!body) return;
  body.innerHTML = "";
  const hints = report.command_hints || [];
  if (!hints.length) {
    body.appendChild(emptyRow(3, "No MKT demo bootstrap commands available"));
    return;
  }

  hints.forEach((hint) => {
    const row = document.createElement("tr");
    row.innerHTML = `
      <td><strong>${escapeHtml(hint.label || "--")}</strong><span><code>${escapeHtml(hint.command || "--")}</code></span></td>
      <td>${escapeHtml(hint.purpose || "--")}</td>
      <td>${escapeHtml(hint.live_execution || "--")}</td>
    `;
    body.appendChild(row);
  });
}

function renderPredictionContractMktDonorLaunchPreflight() {
  const report = state.predictionContractMktDonorLaunchPreflight || null;
  const body = document.getElementById("prediction-mkt-donor-launch-body");
  updatePredictionMktDonorLaunchCommandButton();
  if (!report) {
    text("prediction-mkt-donor-launch-state", "NOT_CHECKED");
    className("prediction-mkt-donor-launch-state", "status-pill status-warn");
    text("prediction-mkt-donor-launch-boundary", "--");
    className("prediction-mkt-donor-launch-boundary", "status-pill status-warn");
    text("prediction-mkt-donor-launch-command", "--");
    text("prediction-mkt-donor-launch-next", "Preflight MKT launch before running npm.");
    if (body) {
      body.innerHTML = "";
      body.appendChild(emptyRow(5, "Preflight the MKT launch command before running npm"));
    }
    return;
  }

  const status = report.status || "UNKNOWN";
  const statusClass = status === "LAUNCH_READY"
    ? "status-ok"
    : status === "LAUNCH_NEEDS_SETUP"
      ? "status-warn"
      : "status-danger";
  text("prediction-mkt-donor-launch-state", status);
  className("prediction-mkt-donor-launch-state", `status-pill ${statusClass}`);
  const boundaryClass = report.backtest_depth_ready
    ? "status-ok"
    : report.evidence_tier?.includes("SPARSE") || report.evidence_tier?.includes("CONTEXT")
      ? "status-warn"
      : "status-danger";
  text(
    "prediction-mkt-donor-launch-boundary",
    `${report.launch_scope || "UNKNOWN"} / ${report.evidence_tier || "UNKNOWN"} / ${report.aurex_use_scope || "--"}`,
  );
  className("prediction-mkt-donor-launch-boundary", `status-pill ${boundaryClass}`);
  text("prediction-mkt-donor-launch-command", report.launch_command || "--");
  text(
    "prediction-mkt-donor-launch-next",
    `${report.next_action || "Review launch preflight."} ${report.evidence_boundary || ""}`.trim(),
  );

  if (!body) return;
  body.innerHTML = "";
  const checks = report.checks || [];
  if (!checks.length) {
    body.appendChild(emptyRow(5, "No MKT launch preflight checks available"));
    return;
  }

  checks.forEach((check) => {
    const row = document.createElement("tr");
    row.innerHTML = `
      <td><strong>${escapeHtml(String(check.key || "--").replaceAll("_", " "))}</strong></td>
      <td>${statusBadge(check.status || "UNKNOWN")}</td>
      <td>${escapeHtml(check.observed || "--")}</td>
      <td>${escapeHtml(check.expected || "--")}</td>
      <td>${escapeHtml(check.next_action || "--")}</td>
    `;
    body.appendChild(row);
  });
}

function renderPredictionContractMktDonorCollectionStatus() {
  const report = state.predictionContractMktDonorCollectionStatus || null;
  const body = document.getElementById("prediction-mkt-donor-collection-body");
  const qualityBody = document.getElementById("prediction-mkt-donor-collection-quality-body");
  const healthBody = document.getElementById("prediction-mkt-donor-launch-health-body");
  updatePredictionMktDonorLaunchCommandButton();
  if (!report) {
    text("prediction-mkt-donor-collection-state", "NOT_CHECKED");
    className("prediction-mkt-donor-collection-state", "status-pill status-warn");
    text("prediction-mkt-donor-collection-db", "--");
    text("prediction-mkt-donor-collection-freshness", "--");
    text("prediction-mkt-donor-collection-quality", "--");
    text("prediction-mkt-donor-evidence-tier", "--");
    className("prediction-mkt-donor-evidence-tier", "status-pill status-warn");
    text("prediction-mkt-donor-collection-quality-next", "--");
    text("prediction-mkt-donor-launch-health", "--");
    className("prediction-mkt-donor-launch-health", "status-pill status-warn");
    text("prediction-mkt-donor-launch-health-next", "--");
    text(
      "prediction-mkt-donor-collection-next",
      "Check collection status after launching MKT.",
    );
    text("prediction-mkt-donor-collection-recheck", "--");
    if (body) {
      body.innerHTML = "";
      body.appendChild(emptyRow(4, "Check collection status after launching MKT"));
    }
    if (qualityBody) {
      qualityBody.innerHTML = "";
      qualityBody.appendChild(emptyRow(5, "Run collection status to inspect donor quality gates"));
    }
    if (healthBody) {
      healthBody.innerHTML = "";
      healthBody.appendChild(emptyRow(5, "Run collection status to inspect launch health gates"));
    }
    return;
  }

  const status = report.status || "UNKNOWN";
  const statusClass = status === "COLLECTION_REPLAY_READY"
    ? "status-ok"
    : status === "COLLECTION_BLOCKED" || status === "COLLECTION_INACTIVE" || status === "COLLECTION_STALE"
      ? "status-danger"
      : "status-warn";
  text("prediction-mkt-donor-collection-state", status);
  className("prediction-mkt-donor-collection-state", `status-pill ${statusClass}`);
  text(
    "prediction-mkt-donor-collection-db",
    `${report.db_inventory?.status || "UNKNOWN"} / ${report.db_path || "--"}`,
  );
  const freshness = report.collection_freshness_status || "UNKNOWN";
  const freshnessClass = freshness === "FRESHNESS_DB_RECENT" || freshness === "FRESHNESS_LOG_RECENT"
    ? "status-ok"
    : freshness === "FRESHNESS_WAITING_FOR_DB"
      ? "status-warn"
      : "status-danger";
  text(
    "prediction-mkt-donor-collection-freshness",
    `${freshness} / DB ${report.db_file_size_bytes ?? "--"} B / DB age ${formatAgeSeconds(report.db_age_seconds)} / log age ${formatAgeSeconds(report.latest_log_age_seconds)} / window ${formatAgeSeconds(report.freshness_window_seconds)} / DB mod ${formatDate(report.db_modified_at)} / log mod ${formatDate(report.latest_log_modified_at)}`,
  );
  className("prediction-mkt-donor-collection-freshness", `status-pill ${freshnessClass}`);
  const quality = report.collection_quality || null;
  const qualityStatus = quality?.status || "UNKNOWN";
  const qualityClass = qualityStatus === "QUALITY_BACKTEST_CANDIDATE"
    ? "status-ok"
    : qualityStatus.includes("SAMPLE") || qualityStatus === "QUALITY_CONTEXT_ONLY"
      ? "status-warn"
      : "status-danger";
  text(
    "prediction-mkt-donor-collection-quality",
    `${qualityStatus} / depth ${quality?.backtest_depth_progress_pct || 0}% / replay ${quality?.replay_candidate_count || 0}/${quality?.minimum_backtest_replay_rows || 100} / research ${quality?.research_candidate_count || 0}/${quality?.minimum_backtest_research_rows || 100} / context ${quality?.context_row_count || 0} / latest ${quality?.latest_row_at || "--"}`,
  );
  className("prediction-mkt-donor-collection-quality", `status-pill ${qualityClass}`);
  const evidenceTier = quality?.evidence_tier || "UNKNOWN";
  const evidenceTierClass = evidenceTier.includes("BACKTEST")
    ? "status-ok"
    : evidenceTier.includes("SPARSE") || evidenceTier.includes("CONTEXT")
      ? "status-warn"
      : "status-danger";
  text(
    "prediction-mkt-donor-evidence-tier",
    `${evidenceTier} / ${quality?.aurex_use_scope || "--"}`,
  );
  className("prediction-mkt-donor-evidence-tier", `status-pill ${evidenceTierClass}`);
  text(
    "prediction-mkt-donor-collection-quality-next",
    quality?.next_action || "Review donor collection quality.",
  );
  const health = report.launch_health || null;
  const healthStatus = health?.status || "UNKNOWN";
  const healthClass = healthStatus === "LAUNCH_HEALTH_BACKTEST_CANDIDATE"
    ? "status-ok"
    : ["LAUNCH_HEALTH_STARTING", "LAUNCH_HEALTH_COLLECTING", "LAUNCH_HEALTH_SAMPLE_READY", "LAUNCH_HEALTH_WAITING_FOR_DB"].includes(healthStatus)
      ? "status-warn"
      : ["LAUNCH_HEALTH_BLOCKED", "LAUNCH_HEALTH_INACTIVE", "LAUNCH_HEALTH_STALE"].includes(healthStatus)
        ? "status-danger"
      : "status-danger";
  text("prediction-mkt-donor-launch-health", healthStatus);
  className("prediction-mkt-donor-launch-health", `status-pill ${healthClass}`);
  text(
    "prediction-mkt-donor-launch-health-next",
    health?.next_action || "Review MKT donor launch health.",
  );
  text(
    "prediction-mkt-donor-collection-next",
    report.next_action || "Review MKT collection status.",
  );
  const recheckAfter = report.recommended_recheck_after_seconds;
  text(
    "prediction-mkt-donor-collection-recheck",
    recheckAfter === null || recheckAfter === undefined
      ? "Fix blockers before refreshing."
      : `${formatAgeSeconds(recheckAfter)} / ${formatDate(report.recommended_recheck_at)}`,
  );
  renderPredictionMktDonorCollectionQualityRows(qualityBody, quality);
  renderPredictionMktDonorLaunchHealthRows(healthBody, health);

  if (!body) return;
  body.innerHTML = "";
  const logs = report.log_files || [];
  if (!logs.length) {
    body.appendChild(emptyRow(4, "No MKT log files found in the selected userData folder"));
    return;
  }

  logs.forEach((logFile) => {
    const row = document.createElement("tr");
    row.innerHTML = `
      <td><strong>${escapeHtml(logFile.name || "--")}</strong></td>
      <td>${Number(logFile.size_bytes || 0).toLocaleString()} B</td>
      <td>${formatDate(logFile.modified_at)}</td>
      <td><code>${escapeHtml(logFile.path || "--")}</code></td>
    `;
    body.appendChild(row);
  });
}

function renderPredictionMktDonorCollectionQualityRows(body, quality) {
  if (!body) return;
  body.innerHTML = "";
  const checks = quality?.checks || [];
  const targets = quality?.targets || [];
  if (!checks.length && !targets.length) {
    body.appendChild(emptyRow(5, "No MKT collection quality gates returned"));
    return;
  }

  targets.forEach((target) => {
    const row = document.createElement("tr");
    row.innerHTML = `
      <td><strong>${escapeHtml(target.label || target.key || "--")}</strong><span>${escapeHtml(target.key || "--")}</span></td>
      <td>${statusBadge(target.status || "UNKNOWN")}</td>
      <td>${Number(target.current_count || 0).toLocaleString()} (${Number(target.progress_pct || 0).toFixed(2)}%)</td>
      <td>${Number(target.target_count || 0).toLocaleString()}</td>
      <td>${escapeHtml(target.next_action || "--")}</td>
    `;
    body.appendChild(row);
  });

  checks.forEach((check) => {
    const row = document.createElement("tr");
    row.innerHTML = `
      <td><strong>${escapeHtml(check.key || "--")}</strong><span>quality check</span></td>
      <td>${statusBadge(check.status || "UNKNOWN")}</td>
      <td>${escapeHtml(check.observed || "--")}</td>
      <td>${escapeHtml(check.expected || "--")}</td>
      <td>${escapeHtml(check.next_action || "--")}</td>
    `;
    body.appendChild(row);
  });
}

function renderPredictionMktDonorLaunchHealthRows(body, health) {
  if (!body) return;
  body.innerHTML = "";
  const checks = health?.checks || [];
  if (!checks.length) {
    body.appendChild(emptyRow(5, "No MKT launch health gates returned"));
    return;
  }

  checks.forEach((check) => {
    const row = document.createElement("tr");
    row.innerHTML = `
      <td><strong>${escapeHtml(check.key || "--")}</strong></td>
      <td>${statusBadge(check.status || "UNKNOWN")}</td>
      <td>${escapeHtml(check.observed || "--")}</td>
      <td>${escapeHtml(check.expected || "--")}</td>
      <td>${escapeHtml(check.next_action || "--")}</td>
    `;
    body.appendChild(row);
  });
}

function renderPredictionContractMktRuntimeSafety() {
  const report = state.predictionContractMktRuntimeSafety || null;
  const body = document.getElementById("prediction-mkt-runtime-safety-body");
  if (!report) {
    text("prediction-mkt-runtime-safety-state", "NOT_CHECKED");
    className("prediction-mkt-runtime-safety-state", "status-pill status-warn");
    text("prediction-mkt-runtime-safety-checks", "--");
    text("prediction-mkt-runtime-safety-blockers", "--");
    text("prediction-mkt-runtime-settings-path", "--");
    text("prediction-mkt-runtime-userdata-path", "--");
    text(
      "prediction-mkt-runtime-safety-next",
      "Run runtime safety before starting MKT donor collection.",
    );
    if (body) {
      body.innerHTML = "";
      body.appendChild(emptyRow(6, "Run MKT runtime safety before donor collection"));
    }
    return;
  }

  const status = report.status || "UNKNOWN";
  const statusClass = status === "SAFETY_CONFIRMED"
    ? "status-ok"
    : status === "SAFETY_DEFAULTS_ONLY"
      ? "status-warn"
      : "status-danger";
  const blockers = (report.blockers || [])
    .map((item) => String(item).replaceAll("_", " "))
    .join(" / ");
  text("prediction-mkt-runtime-safety-state", status);
  className("prediction-mkt-runtime-safety-state", `status-pill ${statusClass}`);
  text(
    "prediction-mkt-runtime-safety-checks",
    `${report.passed_checks || 0} pass / ${report.warning_checks || 0} warn / ${report.failed_checks || 0} fail`,
  );
  text("prediction-mkt-runtime-safety-blockers", blockers || "none");
  text(
    "prediction-mkt-runtime-settings-path",
    report.settings_path
      ? `${report.settings_path}${report.settings_auto_discovered ? " / discovered" : ""}`
      : "not selected",
  );
  text(
    "prediction-mkt-runtime-userdata-path",
    report.userdata_path
      ? `${report.userdata_path}${report.userdata_auto_discovered ? " / discovered" : ""}`
      : "not selected",
  );
  text(
    "prediction-mkt-runtime-safety-next",
    report.next_action || "Review MKT runtime safety.",
  );

  if (!body) return;
  body.innerHTML = "";
  const checks = report.checks || [];
  if (!checks.length) {
    body.appendChild(emptyRow(6, "No runtime safety checks available"));
    return;
  }

  checks.forEach((check) => {
    const row = document.createElement("tr");
    row.innerHTML = `
      <td><strong>${escapeHtml(String(check.key || "--").replaceAll("_", " "))}</strong></td>
      <td>${statusBadge(check.status || "UNKNOWN")}</td>
      <td>${escapeHtml(check.observed || "--")}</td>
      <td>${escapeHtml(check.expected || "--")}</td>
      <td><code>${escapeHtml(check.source || "--")}</code></td>
      <td>${escapeHtml(check.next_action || "--")}</td>
    `;
    body.appendChild(row);
  });
}

function renderPredictionContractMktDonorReadiness() {
  const report = state.predictionContractMktDonorReadiness || null;
  if (!report) {
    text("prediction-mkt-donor-readiness-state", "NOT_CHECKED");
    className("prediction-mkt-donor-readiness-state", "status-pill status-warn");
    text("prediction-mkt-donor-readiness-dbs", "--");
    text("prediction-mkt-donor-readiness-blockers", "--");
    text("prediction-mkt-donor-readiness-next", "Check donor readiness before DB discovery.");
    return;
  }

  const status = report.status || "UNKNOWN";
  const statusClass = status === "DONOR_READY"
    ? "status-ok"
    : status === "DONOR_DATA_MISSING" || status === "DONOR_DB_BLOCKED"
      ? "status-warn"
      : "status-danger";
  const discovery = report.discovery || {};
  const blockers = (report.blockers || [])
    .map((item) => String(item).replaceAll("_", " "))
    .join(" / ");
  text("prediction-mkt-donor-readiness-state", status);
  className("prediction-mkt-donor-readiness-state", `status-pill ${statusClass}`);
  text(
    "prediction-mkt-donor-readiness-dbs",
    `${discovery.ready_count || 0} ready / ${discovery.candidate_count || 0} found`,
  );
  text("prediction-mkt-donor-readiness-blockers", blockers || "none");
  text(
    "prediction-mkt-donor-readiness-next",
    report.next_action || "Review MKT donor readiness.",
  );
}

function renderPredictionContractMktDbDiscovery() {
  const report = state.predictionContractMktDbDiscovery || null;
  const body = document.getElementById("prediction-mkt-db-discovery-body");
  if (!report) {
    text("prediction-mkt-db-discovery-state", "NOT_RUN");
    className("prediction-mkt-db-discovery-state", "status-pill status-warn");
    text("prediction-mkt-db-discovery-ready", "--");
    text("prediction-mkt-db-discovery-next", "Discover local MKT SQLite DBs before readiness.");
    if (body) {
      body.innerHTML = "";
      body.appendChild(emptyRow(8, "Run DB discovery to inspect local MKT SQLite candidates"));
    }
    return;
  }

  const status = report.ready_count > 0
    ? "READY_DB_FOUND"
    : report.candidate_count > 0
      ? "DBS_BLOCKED"
      : "NO_DBS_FOUND";
  const statusClass = report.ready_count > 0
    ? "status-ok"
    : report.candidate_count > 0
      ? "status-warn"
      : "status-danger";
  text("prediction-mkt-db-discovery-state", `${status} / ${report.candidate_count || 0} found`);
  className("prediction-mkt-db-discovery-state", `status-pill ${statusClass}`);
  text("prediction-mkt-db-discovery-ready", `${report.ready_count || 0} ready`);
  text("prediction-mkt-db-discovery-next", report.next_action || "Review discovered DBs.");

  if (!body) return;
  body.innerHTML = "";
  const candidates = report.candidates || [];
  if (!candidates.length) {
    body.appendChild(emptyRow(8, "No MKT SQLite DB candidates found under the searched roots"));
    return;
  }

  const selectedPath = inputValue("prediction-mkt-db-path");
  candidates.forEach((candidate, index) => {
    const readiness = candidate.readiness || {};
    const summary = readiness.analysis_summary || {};
    const row = document.createElement("tr");
    if (candidate.db_path === selectedPath) row.className = "is-selected";
    const actionLabel = readiness.data_ready ? "Use" : "Inspect";
    const fileSize = candidate.file_size_bytes === null || candidate.file_size_bytes === undefined
      ? "--"
      : `${Number(candidate.file_size_bytes).toLocaleString()} B`;
    const next = readiness.error || readiness.next_action || "Review candidate readiness.";
    row.innerHTML = `
      <td><strong>${escapeHtml(candidate.db_path || "--")}</strong><span>${escapeHtml(fileSize)}</span></td>
      <td>${statusBadge(readiness.status || "UNKNOWN")}</td>
      <td>${readiness.importable_count || 0}/${readiness.rows_received || 0} usable</td>
      <td>${summary.actionable_yes_rows || 0} YES / ${summary.actionable_no_rows || 0} NO</td>
      <td>${readiness.rejected_count || 0}</td>
      <td>${formatDate(candidate.modified_at)}</td>
      <td>${escapeHtml(next)}</td>
      <td><button class="compact" type="button" data-mkt-db-candidate-index="${index}">${actionLabel}</button></td>
    `;
    body.appendChild(row);
  });
}

function renderPredictionContractMktDbReadiness() {
  const report = state.predictionContractMktDbReadiness || null;
  if (!report) {
    text("prediction-mkt-db-readiness-state", "NOT_CHECKED");
    className("prediction-mkt-db-readiness-state", "status-pill status-warn");
    text("prediction-mkt-db-readiness-rows", "--");
    text("prediction-mkt-db-readiness-next", "Check MKT DB data before campaign preflight.");
    return;
  }

  const status = report.status || "UNKNOWN";
  const statusClass = report.data_ready
    ? report.rejected_count > 0
      ? "status-warn"
      : "status-ok"
    : "status-danger";
  text("prediction-mkt-db-readiness-state", status);
  className("prediction-mkt-db-readiness-state", `status-pill ${statusClass}`);
  text(
    "prediction-mkt-db-readiness-rows",
    `${report.importable_count || 0}/${report.rows_received || 0} usable / ${report.rejected_count || 0} rejected`,
  );
  text("prediction-mkt-db-readiness-next", report.next_action || "Review MKT DB data readiness.");
}

function renderPredictionContractMktDbInventory() {
  const report = state.predictionContractMktDbInventory || null;
  const body = document.getElementById("prediction-mkt-db-inventory-body");
  if (!report) {
    text("prediction-mkt-db-inventory-state", "NOT_CHECKED");
    className("prediction-mkt-db-inventory-state", "status-pill status-warn");
    text("prediction-mkt-db-inventory-rows", "--");
    text("prediction-mkt-db-inventory-blockers", "--");
    text("prediction-mkt-db-inventory-next", "Inspect DB tables after donor data exists.");
    if (body) {
      body.innerHTML = "";
      body.appendChild(emptyRow(6, "Run DB inventory after selecting an MKT SQLite database"));
    }
    return;
  }

  const status = report.status || "UNKNOWN";
  const statusClass = report.replay_table_ready
    ? "status-ok"
    : report.research_tables_ready || status === "INVENTORY_COLLECTING"
      ? "status-warn"
      : "status-danger";
  const blockers = (report.blockers || [])
    .map((item) => String(item).replaceAll("_", " "))
    .join(" / ");
  text("prediction-mkt-db-inventory-state", status);
  className("prediction-mkt-db-inventory-state", `status-pill ${statusClass}`);
  text(
    "prediction-mkt-db-inventory-rows",
    `${report.total_rows || 0} rows / ${report.tables_available || 0} tables`,
  );
  text("prediction-mkt-db-inventory-blockers", blockers || "none");
  text("prediction-mkt-db-inventory-next", report.next_action || "Review MKT DB inventory.");

  if (!body) return;
  body.innerHTML = "";
  const tables = report.tables || [];
  if (!tables.length) {
    body.appendChild(emptyRow(6, "No MKT DB table inventory available"));
    return;
  }

  tables.forEach((table) => {
    const row = document.createElement("tr");
    row.innerHTML = `
      <td><strong>${escapeHtml(table.table || "--")}</strong><span>${escapeHtml(table.key || "--")}</span></td>
      <td>${escapeHtml(String(table.usable_for || "--").replaceAll("_", " "))}</td>
      <td>${table.exists ? table.row_count || 0 : statusBadge("MISSING")}</td>
      <td>${table.resolved_count === null || table.resolved_count === undefined ? "--" : table.resolved_count}</td>
      <td>${escapeHtml(table.latest_at || "--")}</td>
      <td>${escapeHtml(table.next_action || "--")}</td>
    `;
    body.appendChild(row);
  });
}

function renderPredictionContractMktDbPreflight() {
  const report = state.predictionContractMktDbPreflight || null;
  if (!report) {
    text("prediction-mkt-db-state", "NOT_RUN");
    className("prediction-mkt-db-state", "status-pill status-warn");
    text("prediction-mkt-db-importable", "--");
    text("prediction-mkt-db-rejected", "--");
    text("prediction-mkt-db-actionable", "--");
    return;
  }

  const status = report.status || "UNKNOWN";
  const statusClass = status === "READY" || status === "IMPORTED"
    ? "status-ok"
    : status === "READY_WITH_REJECTIONS" || status === "IMPORTED_WITH_REJECTIONS"
      ? "status-warn"
      : "status-danger";
  const summary = report.analysis_summary || {};
  const query = report.query_summary || {};
  const importable = report.importable_count ?? report.imported_count ?? 0;
  text("prediction-mkt-db-state", `${status} / ${query.status_filter || "resolved"}`);
  className("prediction-mkt-db-state", `status-pill ${statusClass}`);
  text("prediction-mkt-db-importable", String(importable));
  text("prediction-mkt-db-rejected", String(report.rejected_count || 0));
  text(
    "prediction-mkt-db-actionable",
    `${summary.actionable_yes_rows || 0} YES / ${summary.actionable_no_rows || 0} NO`,
  );
}

function renderPredictionMktDbCampaignReadiness() {
  const readiness = state.predictionDemoMktDbCampaignReadiness || null;
  if (!readiness) {
    text("prediction-mkt-db-campaign-readiness-state", "NOT_CHECKED");
    className("prediction-mkt-db-campaign-readiness-state", "status-pill status-warn");
    text("prediction-mkt-db-campaign-readiness-data", "--");
    text("prediction-mkt-db-campaign-evidence-tier", "--");
    className("prediction-mkt-db-campaign-evidence-tier", "status-pill status-warn");
    text("prediction-mkt-db-campaign-readiness-gate", "--");
    text("prediction-mkt-db-campaign-readiness-next", "Check campaign readiness before preflight.");
    return;
  }

  const status = readiness.status || "UNKNOWN";
  const statusClass = readiness.ready_for_campaign_replay
    ? "status-ok"
    : readiness.ready_for_campaign_preflight
      ? "status-warn"
      : "status-danger";
  const data = readiness.data_readiness || {};
  const gate = readiness.strategy_gate || {};
  text("prediction-mkt-db-campaign-readiness-state", status);
  className("prediction-mkt-db-campaign-readiness-state", `status-pill ${statusClass}`);
  text(
    "prediction-mkt-db-campaign-readiness-data",
    `${data.status || "UNKNOWN"} / ${data.importable_count || 0} usable`,
  );
  const evidenceTier = readiness.data_evidence_tier || "UNKNOWN";
  const evidenceTierClass = readiness.data_backtest_depth_ready
    ? "status-ok"
    : evidenceTier.includes("SPARSE") || evidenceTier.includes("CONTEXT")
      ? "status-warn"
      : "status-danger";
  text(
    "prediction-mkt-db-campaign-evidence-tier",
    `${evidenceTier} / ${readiness.data_use_scope || "--"}`,
  );
  className("prediction-mkt-db-campaign-evidence-tier", `status-pill ${evidenceTierClass}`);
  text(
    "prediction-mkt-db-campaign-readiness-gate",
    gate.approved
      ? `${gate.reason || "approved"} / ${shortHash(gate.evidence_hash)}`
      : gate.reason || "research gate blocked",
  );
  text(
    "prediction-mkt-db-campaign-readiness-next",
    readiness.next_action || "Review campaign readiness.",
  );
}

function renderPredictionMktDbCampaignManifest() {
  const manifest = state.predictionDemoMktDbCampaignManifest || null;
  if (!manifest) {
    text("prediction-mkt-db-campaign-manifest-state", "NOT_BUILT");
    className("prediction-mkt-db-campaign-manifest-state", "status-pill status-warn");
    text("prediction-mkt-db-campaign-manifest-hash", "--");
    text("prediction-mkt-db-campaign-manifest-next", "Build a campaign manifest before replay.");
    return;
  }

  const status = manifest.status || "UNKNOWN";
  const statusClass = manifest.replay_ready
    ? "status-ok"
    : status === "MANIFEST_PREFLIGHT_READY"
      ? "status-warn"
      : "status-danger";
  text("prediction-mkt-db-campaign-manifest-state", status);
  className("prediction-mkt-db-campaign-manifest-state", `status-pill ${statusClass}`);
  text("prediction-mkt-db-campaign-manifest-hash", shortHash(manifest.manifest_hash));
  text(
    "prediction-mkt-db-campaign-manifest-next",
    manifest.next_action || "Review campaign manifest before replay.",
  );
}

function renderPredictionMktDbCampaign() {
  const campaign =
    state.predictionDemoMktDbCampaign || state.predictionDemoMktDbCampaignPreflight || null;
  if (!campaign) {
    text("prediction-mkt-db-campaign-state", "NOT_RUN");
    className("prediction-mkt-db-campaign-state", "status-pill status-warn");
    text("prediction-mkt-db-campaign-imported", "--");
    text("prediction-mkt-db-campaign-completed", "--");
    text("prediction-mkt-db-campaign-projected-evidence", "--");
    text("prediction-mkt-db-campaign-projected-coverage", "--");
    text("prediction-mkt-db-campaign-projected-pl", "--");
    text("prediction-mkt-db-campaign-opposite-pl", "--");
    text("prediction-mkt-db-campaign-projection-blocker", "--");
    text("prediction-mkt-db-campaign-side-sensitivity", "--");
    text("prediction-mkt-db-campaign-evidence", "--");
    text("prediction-mkt-db-campaign-next", "Preflight before replay.");
    return;
  }

  const status = campaign.status || "UNKNOWN";
  const statusClass = status === "READY" || status === "CAMPAIGN_REPLAY_COMPLETED"
    ? "status-ok"
    : status === "READY_WITH_WARNINGS" || status === "CAMPAIGN_REPLAY_PARTIAL"
      ? "status-warn"
      : "status-danger";
  const imported =
    campaign.import_result?.imported_count ?? campaign.import_preflight?.importable_count ?? 0;
  const rejected =
    campaign.import_result?.rejected_count ?? campaign.import_preflight?.rejected_count ?? 0;
  const batch = campaign.batch || campaign.batch_preflight || {};
  const completed = batch.completed_records ?? batch.eligible_records ?? 0;
  const skipped = batch.skipped_records ?? 0;
  const projection =
    campaign.projected_replay || state.predictionDemoMktDbCampaignPreflight?.projected_replay || null;
  const opposite =
    campaign.opposite_side_projection ||
    state.predictionDemoMktDbCampaignPreflight?.opposite_side_projection ||
    null;

  text("prediction-mkt-db-campaign-state", status);
  className("prediction-mkt-db-campaign-state", `status-pill ${statusClass}`);
  text("prediction-mkt-db-campaign-imported", `${imported} ready / ${rejected} rejected`);
  text("prediction-mkt-db-campaign-completed", `${completed} complete / ${skipped} skipped`);
  text(
    "prediction-mkt-db-campaign-projected-evidence",
    campaignProjectionEvidenceSummary(projection),
  );
  text(
    "prediction-mkt-db-campaign-projected-coverage",
    campaignProjectionCoverageSummary(projection),
  );
  text(
    "prediction-mkt-db-campaign-projected-pl",
    projection ? money.format(Number(projection.projected_fee_net_realized_pl || 0)) : "--",
  );
  text(
    "prediction-mkt-db-campaign-opposite-pl",
    opposite
      ? `${opposite.side || "opposite"} ${money.format(Number(opposite.projected_fee_net_realized_pl || 0))}`
      : "--",
  );
  text(
    "prediction-mkt-db-campaign-projection-blocker",
    projection ? (projection.first_failed_check || "none").replaceAll("_", " ") : "--",
  );
  text(
    "prediction-mkt-db-campaign-side-sensitivity",
    campaign.side_sensitivity_warning
      ? campaign.side_sensitivity_warning.replaceAll("_", " ")
      : "not measured",
  );
  text(
    "prediction-mkt-db-campaign-evidence",
    campaign.campaign_evidence?.evidence_hash
      ? shortHash(campaign.campaign_evidence.evidence_hash)
      : "--",
  );
  text("prediction-mkt-db-campaign-next", campaign.next_action || "Review campaign result.");
}

function campaignProjectionEvidenceSummary(projection) {
  if (!projection) return "--";
  const clean = projection.projected_countable_records || 0;
  const raw = projection.projected_raw_closed_records ?? projection.projected_closed_records ?? 0;
  const target = projection.target_closed_records || 100;
  const remaining = projection.remaining_closed_records ?? Math.max(target - clean, 0);
  const progress = Number(projection.projected_progress_pct || 0).toFixed(2);
  return `${clean}/${target} clean (${raw} raw) / ${remaining} left / ${progress}%`;
}

function campaignProjectionCoverageSummary(projection) {
  if (!projection) return "--";
  const days = `${projection.projected_calendar_days || 0}/${projection.target_calendar_days || 30}`;
  const active = `${projection.projected_active_days || 0}/${projection.target_active_days || 15}`;
  const contracts = `${projection.projected_unique_contracts || 0}/${projection.target_unique_contracts || 25}`;
  const remainingContracts = projection.remaining_unique_contracts ?? 0;
  return `${days} days / ${active} active / ${contracts} contracts (${remainingContracts} left)`;
}

function renderPredictionPaperIntentGate() {
  const strategy = inputValue("prediction-strategy");
  const readiness = predictionReadinessForStrategy(strategy);
  const latestIntent = state.predictionIntents[0] || null;
  const latestGate = latestIntent?.intent_snapshot?.research_gate || null;
  const mktStrategy = strategy.toLowerCase().startsWith("mkt_");

  if (!mktStrategy) {
    text("prediction-intent-gate-state", "NOT_REQUIRED");
    className("prediction-intent-gate-state", "status-pill status-warn");
    text("prediction-intent-gate-evidence", "MKT research gate not required for this strategy label");
    text("prediction-intent-gate-next", "Use only for neutral simulator fixtures or separately gated strategies.");
  } else if (readiness?.readiness_state === "PAPER_RESEARCH_ELIGIBLE") {
    text("prediction-intent-gate-state", "PAPER_ALLOWED");
    className("prediction-intent-gate-state", "status-pill status-ok");
    text(
      "prediction-intent-gate-evidence",
      `${readiness.total_trades || 0} trades / ${readiness.oos_trades || 0} OOS / ${shortHash(readiness.evidence_hash)}`,
    );
    text("prediction-intent-gate-next", "Paper/demo only; live execution remains blocked.");
  } else if (readiness) {
    text("prediction-intent-gate-state", "BLOCKED");
    className("prediction-intent-gate-state", "status-pill status-danger");
    text(
      "prediction-intent-gate-evidence",
      `${readiness.resolved_observation_count || 0}/${readiness.observation_count || 0} resolved / ${readiness.first_blocker || readiness.readiness_state}`,
    );
    text("prediction-intent-gate-next", readiness.next_action || "Run the research gate first.");
  } else if (strategy) {
    text("prediction-intent-gate-state", "BLOCKED");
    className("prediction-intent-gate-state", "status-pill status-danger");
    text("prediction-intent-gate-evidence", "No MY_KRYPT_TRADER research candidate found");
    text("prediction-intent-gate-next", "Record/import the candidate and pass the research gate first.");
  } else {
    text("prediction-intent-gate-state", "NO_STRATEGY");
    className("prediction-intent-gate-state", "status-pill status-warn");
    text("prediction-intent-gate-evidence", "--");
    text("prediction-intent-gate-next", "Enter a strategy before creating a paper intent.");
  }

  if (latestGate) {
    const result = latestGate.approved ? "APPROVED" : "BLOCKED";
    text(
      "prediction-intent-gate-latest",
      `${result} / ${String(latestGate.reason || "--").replaceAll("_", " ")} / ${shortHash(latestGate.evidence_hash)}`,
    );
  } else {
    text("prediction-intent-gate-latest", "No paper intent gate attempt yet");
  }
}

function predictionReadinessForStrategy(strategy) {
  const normalized = String(strategy || "").trim();
  if (!normalized) return null;
  const items = state.researchReadinessQueue?.items || [];
  return (
    items.find((item) => item.strategy === normalized) ||
    items.find((item) => item.candidate_key === normalized) ||
    null
  );
}

function renderPredictionContracts() {
  const body = document.getElementById("prediction-contracts-body");
  if (!body) return;
  body.innerHTML = "";
  if (!state.predictionContracts.length) {
    body.appendChild(emptyRow(6, "No prediction contracts recorded yet"));
    return;
  }

  state.predictionContracts.forEach((contract) => {
    const row = document.createElement("tr");
    row.innerHTML = `
      <td>${formatDate(contract.last_seen_at)}</td>
      <td><strong>${escapeHtml(contract.contract_ticker)}</strong><span>${escapeHtml(contract.title)}</span></td>
      <td>${statusBadge(contract.status)}</td>
      <td>${formatPredictionQuote(contract.yes_bid_price, contract.yes_ask_price)}</td>
      <td>${formatPredictionQuote(contract.no_bid_price, contract.no_ask_price)}</td>
      <td><span>${escapeHtml(contract.id)}</span></td>
    `;
    body.appendChild(row);
  });
}

function renderPredictionOrders() {
  const body = document.getElementById("prediction-orders-body");
  if (!body) return;
  body.innerHTML = "";
  if (!state.predictionOrders.length) {
    body.appendChild(emptyRow(9, "No prediction paper orders yet"));
    return;
  }

  state.predictionOrders.forEach((order) => {
    const row = document.createElement("tr");
    row.innerHTML = `
      <td>${formatDate(order.submitted_at)}</td>
      <td>${statusBadge(order.status)}</td>
      <td>${escapeHtml(order.side)}</td>
      <td>${escapeHtml(order.action)}</td>
      <td>${formatContracts(order.quantity)}</td>
      <td>${formatContracts(order.filled_quantity)}</td>
      <td>${formatProbability(order.limit_price)}</td>
      <td>${formatProbability(order.average_fill_price)}</td>
      <td>${money.format(Number(order.fees || 0))}</td>
    `;
    body.appendChild(row);
  });
}

function renderPredictionPositions() {
  const body = document.getElementById("prediction-positions-body");
  if (!body) return;
  body.innerHTML = "";
  if (!state.predictionPositions.length) {
    body.appendChild(emptyRow(9, "No prediction paper positions yet"));
    return;
  }

  state.predictionPositions.forEach((position) => {
    const row = document.createElement("tr");
    row.innerHTML = `
      <td>${formatDate(position.opened_at)}</td>
      <td>${statusBadge(position.status)}</td>
      <td>${escapeHtml(position.side)}</td>
      <td>${formatContracts(position.quantity)}</td>
      <td>${formatProbability(position.average_entry_price)}</td>
      <td>${money.format(Number(position.fees || 0))}</td>
      <td>${money.format(Number(position.lifecycle_fees || position.fees || 0))}</td>
      <td>${money.format(Number(position.realized_pl || 0))}</td>
      <td><span>${escapeHtml(position.id)}</span></td>
    `;
    body.appendChild(row);
  });
}

function renderPredictionEvidence() {
  const list = document.getElementById("prediction-evidence-list");
  if (!list) return;
  list.innerHTML = "";
  if (!state.predictionEvidence.length) {
    const item = document.createElement("li");
    item.className = "empty-state";
    item.textContent = "No prediction-market evidence yet";
    list.appendChild(item);
    return;
  }

  state.predictionEvidence.forEach((event) => {
    const item = document.createElement("li");
    const hash = String(event.evidence_hash || "").slice(0, 10);
    item.innerHTML = `
      <strong>${statusBadge(event.kind)} ${escapeHtml(event.entity_type)}</strong>
      <time>${formatDate(event.occurred_at)} / ${escapeHtml(event.contract_ticker || "no contract")} / ${escapeHtml(hash)}</time>
      <span>${escapeHtml(predictionEvidenceSummary(event))}</span>
    `;
    list.appendChild(item);
  });
}

function renderSignals() {
  renderSignalContract();
  renderSignalRunbook();
  renderSignalAlertSetup();
  renderSignalVerification();
  renderSignalPreflight();
  text("signals-count", `${state.signals.length} latest`);
  const body = document.getElementById("signals-body");
  if (!body) return;
  body.innerHTML = "";
  if (!state.signals.length) {
    body.appendChild(emptyRow(8, "No signals received yet"));
    return;
  }

  state.signals.forEach((signal) => {
    const row = document.createElement("tr");
    const reason = signal.rejection_reason || signal.latest_risk_decision?.reason || "";
    const provenance = signalProvenanceSummary(signal);
    row.innerHTML = `
      <td>${formatDate(signal.received_at)}</td>
      <td>${escapeHtml(signal.strategy)}</td>
      <td>${escapeHtml(signal.symbol)}</td>
      <td>${escapeHtml(signal.direction)}</td>
      <td>${statusBadge(signal.status)}</td>
      <td>${escapeHtml(provenance)}</td>
      <td>${escapeHtml(signalDeliverySummary(signal))}</td>
      <td>${escapeHtml(reason)}</td>
    `;
    body.appendChild(row);
  });
}

function renderSignalAlertSetup() {
  const setup = state.signalAlertSetup;
  if (!setup) {
    text("signals-alert-setup-status", "--");
    text("signals-alert-setup-url", "--");
    text("signals-alert-setup-auth", "--");
    text("signals-alert-setup-next", "--");
    className("signals-alert-setup-status", "status-pill");
    return;
  }
  text("signals-alert-setup-status", setup.status || "--");
  className(
    "signals-alert-setup-status",
    `status-pill ${setup.ready_for_alert_preflight ? "status-ok" : "status-warn"}`,
  );
  text("signals-alert-setup-url", setup.webhook_url_template || setup.webhook_endpoint || "--");
  text("signals-alert-setup-auth", setup.webhook_secret_transport || "--");
  text("signals-alert-setup-next", (setup.next_actions || [])[0] || "--");
  hydrateSignalAlertPayload(setup, { replace: false });
}

function renderSignalVerification() {
  const verification = state.signalVerification;
  const body = document.getElementById("signals-verification-body");
  if (!verification) {
    text("signals-verification-status", "--");
    text("signals-verification-delivery", "--");
    text("signals-verification-pipeline", "--");
    text("signals-verification-origin", "--");
    text("signals-verification-signal", "--");
    text("signals-verification-trade", "--");
    className("signals-verification-status", "status-pill");
    if (body) {
      body.innerHTML = "";
      body.appendChild(emptyRow(4, "TradingView verification unavailable"));
    }
    return;
  }
  text("signals-verification-status", verification.status || "--");
  className(
    "signals-verification-status",
    `status-pill ${verification.verified ? "status-ok" : "status-warn"}`,
  );
  text(
    "signals-verification-delivery",
    verification.delivery_verified ? "VERIFIED" : "UNPROVEN",
  );
  text(
    "signals-verification-pipeline",
    verification.pipeline_verified ? "VERIFIED" : "UNPROVEN",
  );
  text(
    "signals-verification-origin",
    `${verification.delivery_origin_status || "UNKNOWN"} / ${verification.delivery_auth_transport || "--"}`,
  );
  text("signals-verification-signal", shortHash(verification.latest_signal_id));
  text("signals-verification-trade", shortHash(verification.paper_trade_id));
  if (!body) return;
  body.innerHTML = "";
  const checks = verification.checks || [];
  if (!checks.length) {
    body.appendChild(emptyRow(4, "No TradingView verification checks available"));
    return;
  }
  checks.forEach((check) => {
    const row = document.createElement("tr");
    row.innerHTML = `
      <td>${escapeHtml(humanizeReason(check.check_key))}</td>
      <td>${statusBadge(check.status)}</td>
      <td>${escapeHtml(check.evidence)}</td>
      <td>${escapeHtml(check.next_action)}</td>
    `;
    body.appendChild(row);
  });
}

function renderSignalRunbook() {
  const runbook = state.signalRunbook;
  const body = document.getElementById("signals-runbook-body");
  if (!runbook) {
    text("signals-runbook-status", "--");
    text("signals-runbook-current", "--");
    text("signals-runbook-progress", "--");
    className("signals-runbook-status", "status-pill");
    if (body) {
      body.innerHTML = "";
      body.appendChild(emptyRow(4, "TradingView runbook unavailable"));
    }
    return;
  }
  text("signals-runbook-status", runbook.status || "--");
  className(
    "signals-runbook-status",
    `status-pill ${runbook.ready_to_preflight ? "status-ok" : "status-warn"}`,
  );
  const current = runbook.current_step;
  text("signals-runbook-current", current ? current.title : "--");
  text(
    "signals-runbook-progress",
    `${runbook.completed_step_count || 0}/${runbook.total_step_count || 0} / ${Number(runbook.progress_pct || 0).toFixed(2)}%`,
  );
  if (!body) return;
  body.innerHTML = "";
  const steps = runbook.steps || [];
  if (!steps.length) {
    body.appendChild(emptyRow(4, "No TradingView runbook steps available"));
    return;
  }
  steps.forEach((step) => {
    const row = document.createElement("tr");
    row.innerHTML = `
      <td>${escapeHtml(step.title)}</td>
      <td>${statusBadge(step.status)}</td>
      <td>${escapeHtml(step.evidence)}</td>
      <td>${escapeHtml(step.next_action)}</td>
    `;
    body.appendChild(row);
  });
}

function renderSignalContract() {
  const contract = state.signalContract;
  if (!contract) {
    text("signals-contract-status", "--");
    text("signals-contract-backtest", "--");
    text("signals-contract-version", "--");
    text("signals-contract-fingerprint", "--");
    text("signals-contract-next", "--");
    className("signals-contract-status", "status-pill");
    return;
  }
  const status = `${contract.status} / ${humanizeReason(contract.reason)}`;
  text("signals-contract-status", status);
  className(
    "signals-contract-status",
    `status-pill ${contract.ready_for_paper ? "status-ok" : "status-warn"}`,
  );
  text("signals-contract-backtest", shortHash(contract.accepted_backtest_run_id));
  text("signals-contract-version", contract.strategy_version || "--");
  text("signals-contract-fingerprint", signalContractFingerprint(contract));
  text("signals-contract-next", (contract.next_actions || [])[0] || "--");
  hydrateSignalPreflightPayload(contract);
}

function signalContractFingerprint(contract) {
  if (!contract) return "--";
  if (contract.settings_fingerprint_preview) return `${contract.settings_fingerprint_preview}...`;
  if (contract.requires_provenance) return "missing";
  return "not tracked";
}

function hydrateSignalPreflightPayload(contract) {
  const input = document.getElementById("signal-preflight-payload");
  if (!input || input.value || !contract?.example_payload) return;
  input.value = JSON.stringify(contract.example_payload, null, 2);
}

function hydrateSignalAlertPayload(setup, { replace = false } = {}) {
  const input = document.getElementById("signal-preflight-payload");
  if (!input || !setup?.alert_message) return;
  if (!replace && input.value) return;
  input.value = JSON.stringify(setup.alert_message, null, 2);
}

function renderSignalPreflight() {
  const preflight = state.signalPreflight;
  if (!preflight) {
    text("signals-preflight-status", "--");
    text("signals-preflight-size", "--");
    text("signals-preflight-webhook", "--");
    text("signals-preflight-duplicate", "--");
    text("signals-preflight-idempotency", "--");
    text("signals-preflight-next", "--");
    className("signals-preflight-status", "status-pill");
    return;
  }
  text("signals-preflight-status", `${preflight.status} / ${humanizeReason(preflight.reason)}`);
  className(
    "signals-preflight-status",
    `status-pill ${preflight.would_execute_paper ? "status-ok" : "status-warn"}`,
  );
  const size = preflight.position_size === null || preflight.position_size === undefined
    ? "--"
    : String(preflight.position_size);
  text("signals-preflight-size", size);
  text("signals-preflight-webhook", signalPreflightWebhookSummary(preflight));
  text("signals-preflight-duplicate", signalPreflightDuplicateSummary(preflight));
  text("signals-preflight-idempotency", shortHash(preflight.idempotency_key));
  text("signals-preflight-next", (preflight.next_actions || [])[0] || "--");
}

function signalPreflightWebhookSummary(preflight) {
  if (!preflight) return "--";
  return `${preflight.expected_webhook_status || "--"} / HTTP ${preflight.expected_webhook_http_status || "--"}`;
}

function signalPreflightDuplicateSummary(preflight) {
  if (!preflight) return "--";
  if (preflight.duplicate_status === "DUPLICATE") {
    return `DUPLICATE / ${shortHash(preflight.duplicate_signal_id)}`;
  }
  return `CLEAR / ${preflight.duplicate_cooldown_minutes || 0}m`;
}

function renderPaperEvidenceImports() {
  const batches = state.paperEvidenceImports || [];
  const latest = batches[0];
  text("evidence-import-state", latest ? latest.status : "NO_IMPORTS");
  className("evidence-import-state", `status-pill ${latest ? importStatusClass(latest.status) : "status-warn"}`);
  text("evidence-import-summary", latest ? evidenceImportSummary(latest) : "No paper evidence imports yet");

  const body = document.getElementById("evidence-imports-body");
  if (!body) return;
  body.innerHTML = "";
  if (!batches.length) {
    body.appendChild(emptyRow(8, "No paper evidence import batches yet"));
    return;
  }

  batches.forEach((batch) => {
    const row = document.createElement("tr");
    row.innerHTML = `
      <td>${formatDate(batch.imported_at)}</td>
      <td><strong>${escapeHtml(batch.source)}</strong><span>${escapeHtml(batch.source_reference)}</span></td>
      <td>${statusBadge(batch.status)}</td>
      <td>${batch.rows_received || 0}</td>
      <td>${batch.imported_count || 0}</td>
      <td>${batch.skipped_count || 0}</td>
      <td>${batch.rejected_count || 0}</td>
      <td><strong>${escapeHtml(shortHash(batch.import_hash))}</strong><span>${escapeHtml(shortHash(firstImportedEvidenceHash(batch)))}</span></td>
    `;
    body.appendChild(row);
  });
}

function renderPaperEvidenceCollection() {
  const collection = state.paperEvidenceCollection;
  if (!collection) return;
  text("evidence-collection-status", collection.status || "--");
  text("evidence-collection-backtest", collection.accepted_backtest_status || "--");
  text("evidence-collection-paper", collection.paper_evidence_status || "--");
  text(
    "evidence-collection-imported",
    paperEvidenceCollectionImportSummary(collection),
  );
  text(
    "evidence-collection-trades",
    `${collection.total_trades || 0}/${collection.minimum_trades || 100} (${collection.trades_remaining || 0} left)`,
  );
  text(
    "evidence-collection-days",
    `${collection.calendar_days_observed || 0}/${collection.minimum_calendar_days || 30} (${collection.calendar_days_remaining || 0} left)`,
  );
  text(
    "evidence-collection-active-days",
    `${collection.active_trading_days || 0}/${collection.minimum_active_trading_days || 15} (${collection.active_days_remaining || 0} left)`,
  );
  text(
    "evidence-collection-execution",
    paperExecutionQualityFromCollection(collection),
  );
  const freshnessReasons = collection.paper_evidence_freshness_reasons || [];
  text(
    "evidence-collection-drift",
    freshnessReasons.length
      ? freshnessReasons.slice(0, 3).map((reason) => String(reason).replaceAll("_", " ")).join(" / ")
      : "Clean",
  );
  text("evidence-collection-next", (collection.next_actions || [])[0] || "--");
}

function renderPaperEvidencePreflight() {
  const preflight = state.paperEvidencePreflight;
  const latestBatch = (state.paperEvidenceImports || [])[0];
  const analysis = preflight?.analysis_summary || latestBatch?.analysis_summary || null;
  renderPaperEvidenceAnalysis(analysis);
  if (!preflight) {
    text("evidence-preflight-summary", "--");
    return;
  }
  text(
    "evidence-preflight-summary",
    `${preflight.status} / ${preflight.scope_status || "NO_SCOPE"} / ${preflight.scoped_importable_count || 0} scoped / ${preflight.out_of_scope_importable_count || 0} out / ${preflight.rejected_count || 0} rejected`,
  );
}

function renderPaperEvidenceAnalysis(analysis) {
  if (!analysis) {
    text("evidence-analysis-window", "--");
    text("evidence-analysis-fixes", "--");
    return;
  }

  text(
    "evidence-analysis-window",
    `${analysis.ready_or_imported_count || 0} rows / ${analysis.active_trading_days || 0} active days / ${analysis.calendar_day_span || 0} days / ${money.format(Number(analysis.net_realized_pl || 0))}`,
  );
  const fixes = analysis.fix_queue || [];
  if (fixes.length) {
    text(
      "evidence-analysis-fixes",
      fixes
        .map((item) => `${item.count} ${String(item.reason || "unknown").replaceAll("_", " ")}`)
        .join(" / "),
    );
    return;
  }
  text("evidence-analysis-fixes", (analysis.next_actions || [])[0] || "No rejected rows");
}

function renderTrades() {
  text("trades-count", `${state.trades.length} latest`);
  const body = document.getElementById("trades-body");
  if (!body) return;
  body.innerHTML = "";
  if (!state.trades.length) {
    body.appendChild(emptyRow(7, "No paper trades yet"));
    return;
  }

  state.trades.forEach((trade) => {
    const row = document.createElement("tr");
    row.innerHTML = `
      <td>${formatDate(trade.opened_at)}</td>
      <td>${escapeHtml(trade.strategy)}</td>
      <td>${escapeHtml(trade.symbol)}</td>
      <td>${escapeHtml(trade.direction)}</td>
      <td>${statusBadge(trade.status)}</td>
      <td>${money.format(Number(trade.realized_pl || 0))}</td>
      <td>${trade.r_multiple || "--"}</td>
    `;
    body.appendChild(row);
  });
}

function renderEvents() {
  text("events-count", `${state.events.length} latest`);
  const list = document.getElementById("events-list");
  if (!list) return;
  list.innerHTML = "";
  if (!state.events.length) {
    const item = document.createElement("li");
    item.className = "empty-state";
    item.textContent = "No system events yet";
    list.appendChild(item);
    return;
  }

  state.events.forEach((event) => {
    const item = document.createElement("li");
    item.innerHTML = `
      <strong>${statusBadge(event.severity)} ${escapeHtml(event.message)}</strong>
      <time>${formatDate(event.occurred_at)} / ${escapeHtml(event.category)}</time>
    `;
    list.appendChild(item);
  });
}

function emptyRow(columns, message) {
  const row = document.createElement("tr");
  const cell = document.createElement("td");
  cell.colSpan = columns;
  cell.className = "empty-state";
  cell.textContent = message;
  row.appendChild(cell);
  return row;
}

function statusBadge(value) {
  const normalized = String(value || "--");
  const isDanger =
    normalized.includes("REJECTED") ||
    normalized === "ERROR" ||
    normalized === "CRITICAL" ||
    normalized === "FAIL" ||
    normalized === "VIOLATION" ||
    normalized === "HALTED" ||
    normalized === "REVOKED";
  const isWarn =
    normalized === "WARNING" ||
    normalized === "BLOCKED" ||
    normalized.includes("BLOCKED") ||
    normalized.startsWith("NEEDS") ||
    normalized === "NOT_RUN" ||
    normalized === "NOT_READY" ||
    normalized === "PENDING" ||
    normalized.includes("OPEN");
  const cls = isDanger ? "status-danger" : isWarn ? "status-warn" : "status-ok";
  return `<span class="status-pill ${cls}">${escapeHtml(normalized)}</span>`;
}

function formatDate(value) {
  if (!value) return "--";
  return new Date(value).toLocaleString();
}

function formatAgeSeconds(value) {
  if (value === null || value === undefined || Number.isNaN(Number(value))) return "--";
  const seconds = Math.max(0, Number(value));
  if (seconds < 60) return `${Math.floor(seconds)}s`;
  const minutes = seconds / 60;
  if (minutes < 60) return `${Math.floor(minutes)}m`;
  const hours = minutes / 60;
  if (hours < 24) return `${Math.floor(hours)}h ${Math.floor(minutes % 60)}m`;
  const days = hours / 24;
  return `${Math.floor(days)}d ${Math.floor(hours % 24)}h`;
}

function shortHash(value) {
  return String(value || "").slice(0, 10) || "--";
}

function formatWarmupPair(available, required) {
  if (available === null || available === undefined) {
    return required === null || required === undefined ? "n/a" : `--/${required}`;
  }
  return required === null || required === undefined ? `${available}/--` : `${available}/${required}`;
}

function maybeSetInput(id, value) {
  const input = document.getElementById(id);
  if (input && !input.value && value) input.value = value;
}

function setInput(id, value) {
  const input = document.getElementById(id);
  if (input && value !== undefined && value !== null) input.value = value;
}

function formatProbability(value) {
  if (value === null || value === undefined || value === "") return "--";
  return Number(value).toFixed(2);
}

function formatPercentNumber(value) {
  if (value === null || value === undefined || value === "") return "--";
  return percent.format(Number(value));
}

function formatPredictionQuote(bid, ask) {
  return `${formatProbability(bid)} / ${formatProbability(ask)}`;
}

function formatContracts(value) {
  if (value === null || value === undefined) return "--";
  return Number(value).toLocaleString(undefined, { maximumFractionDigits: 4 });
}

function predictionEvidenceSummary(event) {
  const payload = event.payload || {};
  if (payload.rejection_reasons?.length) {
    return payload.rejection_reasons.map((item) => String(item).replaceAll("_", " ")).join(" / ");
  }
  if (payload.realized_pl !== undefined) return `P/L ${money.format(Number(payload.realized_pl || 0))}`;
  if (payload.status) return String(payload.status).replaceAll("_", " ");
  if (payload.quantity && payload.price) return `${payload.quantity} @ ${payload.price}`;
  return event.evidence_hash || "--";
}

function equityCurvePath(points) {
  const values = points.map((point) => Number(point.equity || 0));
  const min = Math.min(...values);
  const max = Math.max(...values);
  const range = max - min || 1;
  const left = 18;
  const right = 742;
  const top = 38;
  const bottom = 178;
  return points
    .map((point, index) => {
      const x = points.length === 1 ? left : left + (index / (points.length - 1)) * (right - left);
      const normalized = (Number(point.equity || 0) - min) / range;
      const y = bottom - normalized * (bottom - top);
      return `${index === 0 ? "M" : "L"}${x.toFixed(1)} ${y.toFixed(1)}`;
    })
    .join(" ");
}

function escapeHtml(value) {
  return String(value || "").replace(/[&<>"']/g, (char) => {
    const map = { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#039;" };
    return map[char];
  });
}

function approvalCount(snapshot) {
  const keys = ["broker_approved", "account_approved", "jurisdiction_approved", "live_execution_approved"];
  const count = keys.filter((key) => snapshot[key]).length;
  return `${count}/4`;
}

function backtestEvidence(deployment) {
  const gate = (deployment.gates || []).find((item) => item.gate_key === "accepted_backtest_complete");
  if (!gate) return "NOT_RUN";
  const evidence = gate.evidence_snapshot || {};
  const trades = evidence.total_trades || 0;
  const walkForward = evidence.walk_forward || {};
  const wfSummary = `${walkForward.passed_windows || 0}/${walkForward.window_count || 0} WF`;
  const reasons = evidence.live_readiness_reasons || [];
  if (reasons.includes("accepted_backtest_strategy_parameters_missing")) {
    return `${gate.status} / ${backtestParameterEvidenceSummary(evidence.strategy_parameter_evidence)}`;
  }
  const hash = evidence.config_hash ? String(evidence.config_hash).slice(0, 8) : "no hash";
  return `${gate.status} / ${trades} trades / ${wfSummary} / ${hash}`;
}

function backtestParameterEvidenceSummary(parameterEvidence) {
  if (!parameterEvidence) return "--";
  const required = parameterEvidence.required_parameters || [];
  const missing = parameterEvidence.missing_parameters || [];
  if (!parameterEvidence.known_strategy) return "not tracked for strategy";
  if (!missing.length) return `COMPLETE / ${required.length} recorded`;
  return `MISSING / ${missing.length} missing / ${String(missing[0]).replaceAll("_", " ")}`;
}

function humanizeReason(value) {
  return String(value || "--").replaceAll("_", " ");
}

function signalProvenanceSummary(signal) {
  const gate = signal.latest_risk_decision?.rules_snapshot?.signal_backtest_provenance_gate;
  if (gate) {
    if (gate.known_strategy === false) return "not tracked for strategy";
    if (gate.blocked) {
      const reason = gate.reason || (gate.reasons || [])[0] || "blocked";
      return `BLOCKED / ${String(reason).replaceAll("_", " ")}`;
    }
    return `MATCHED / v${gate.signal_strategy_version || "--"} / ${shortHash(gate.signal_settings_fingerprint)}`;
  }
  if (signal.strategy_version || signal.settings_fingerprint) {
    return `PAYLOAD / v${signal.strategy_version || "--"} / ${shortHash(signal.settings_fingerprint)}`;
  }
  return "--";
}

function signalDeliverySummary(signal) {
  const latency = Number(signal.processing_latency_ms);
  const latencyLabel = Number.isFinite(latency) ? `${latency.toFixed(1)} ms` : "--";
  return `${latencyLabel} / ${shortHash(signal.idempotency_key)}`;
}

function paperEvidenceProgress(evidence) {
  if (!evidence) return "0/100 trades / 0/30 days";
  return `${evidence.total_trades}/${evidence.minimum_trades} trades / ${evidence.calendar_days_observed}/${evidence.minimum_calendar_days} days`;
}

function paperEvidenceFreshness(deployment) {
  const gate = (deployment.gates || []).find((item) => item.gate_key === "paper_evidence_complete");
  if (!gate) return "NOT_RUN";
  const reasons = gate.evidence_snapshot?.freshness_reasons || [];
  if (!reasons.length) return `${gate.status} / current`;
  return `${gate.status} / ${String(reasons[0]).replaceAll("_", " ")}`;
}

function paperEvidenceScope(evidence) {
  if (!evidence) return "0 in scope / 0 excluded";
  const snapshot = evidence.evidence_snapshot || {};
  return `${snapshot.in_scope_trade_count || 0} in scope / ${snapshot.out_of_scope_trade_count || 0} excluded`;
}

function paperEvidenceCoverage(evidence) {
  if (!evidence) return "0/15 active / max day 0%/25%";
  const snapshot = evidence.evidence_snapshot || {};
  const activeDays = snapshot.active_trading_days || 0;
  const minimumActiveDays = snapshot.minimum_active_trading_days || 15;
  const maxShare = percent.format(Number(snapshot.max_single_day_trade_share || 0));
  const limit = percent.format(Number(snapshot.max_single_day_trade_share_limit || 0.25));
  return `${activeDays}/${minimumActiveDays} active / max day ${maxShare}/${limit}`;
}

function paperEvidenceIntegrity(evidence) {
  if (!evidence) return "DD $0.00/$0.00 / 0 unexplained / 0 risk";
  const drawdown = money.format(Number(evidence.max_drawdown || 0));
  const limit = money.format(Number(evidence.max_allowed_drawdown || 0));
  return `DD ${drawdown}/${limit} / ${evidence.unexplained_trade_count} unexplained / ${evidence.risk_rule_violation_count} risk`;
}

function paperExecutionQuality(evidence) {
  if (!evidence) return "0 evidence-grade / 0 non-grade / no fills";
  const snapshot = evidence.evidence_snapshot || {};
  const models = Object.entries(snapshot.fill_model_counts || {})
    .map(([model, count]) => `${model} ${count}`)
    .join(", ") || "no fills";
  return `${snapshot.evidence_grade_trade_count || 0} evidence-grade / ${snapshot.non_evidence_grade_trade_count || 0} non-grade / ${snapshot.execution_quality_violation_count || 0} violations / ${models}`;
}

function paperExecutionQualityFromCollection(collection) {
  const models = Object.entries(collection.fill_model_counts || {})
    .map(([model, count]) => `${model} ${count}`)
    .join(", ") || "no fills";
  return `${collection.evidence_grade_trade_count || 0} evidence-grade / ${collection.non_evidence_grade_trade_count || 0} non-grade / ${collection.execution_quality_violation_count || 0} violations / ${models}`;
}

function journalCoverage(evidence) {
  if (!evidence) return "0 journaled / 0 missing / 0 violations";
  return `${evidence.journaled_trade_count} journaled / ${evidence.unjournaled_trade_count} missing / ${evidence.journal_rule_violation_count} violations`;
}

function predictionDemoCampaignSummary(deployment) {
  const gate = predictionDemoCampaignGate(deployment);
  if (!gate) return "NOT_RUN";
  const evidence = gate.evidence_snapshot || {};
  if (evidence.required_for_strategy === false) return `${gate.status} / not required`;
  const closed = `${evidence.closed_records || 0}/${evidence.target_closed_records || 100}`;
  const rawClosed = evidence.raw_closed_records ?? evidence.closed_records ?? 0;
  const cleanLedger = `${evidence.countable_ledger_records || 0}/${rawClosed}`;
  const blockedLedger = evidence.ledger_blocked_records || 0;
  const contracts = `${evidence.unique_contracts || 0}/${evidence.target_unique_contracts || 25}`;
  const reasons = evidence.reasons || [];
  const detail = reasons[0] ? String(reasons[0]).replaceAll("_", " ") : "ready";
  return `${gate.status} / ${closed} records / ${cleanLedger} clean / ${blockedLedger} blocked / ${contracts} contracts / ${detail}`;
}

function predictionDemoCampaignGate(deployment) {
  return (deployment.gates || []).find((item) => item.gate_key === "prediction_demo_campaign_quality");
}

function predictionDemoCampaignSelectedSummary(deployment) {
  const gate = predictionDemoCampaignGate(deployment);
  if (!gate) return "NOT_RUN";
  const evidence = gate.evidence_snapshot || {};
  if (evidence.required_for_strategy === false) return `${gate.status} / not required`;
  const selected = evidence.strategy_campaign_audit_records || 0;
  const total = evidence.campaign_audit_records || 0;
  const clean = evidence.strategy_campaign_current_result_clean_records || 0;
  const drift = evidence.strategy_campaign_current_result_drifted_records || 0;
  const latest = evidence.latest_strategy_campaign_record || null;
  const ledger = latest?.current_result_ledger_status
    ? String(latest.current_result_ledger_status).replaceAll("_", " ")
    : selected
      ? "reviewed"
      : "missing selected strategy evidence";
  return `${selected}/${total} selected / ${clean} clean / ${drift} drift / ${ledger}`;
}

function predictionDemoCampaignDriftSummary(deployment) {
  const gate = predictionDemoCampaignGate(deployment);
  if (!gate) return "NOT_RUN";
  const evidence = gate.evidence_snapshot || {};
  if (evidence.required_for_strategy === false) return "not required";
  const selectedDrift = evidence.strategy_campaign_current_result_drifted_records || 0;
  const totalDrift = evidence.campaign_current_result_drifted_records || 0;
  const blockers = evidence.latest_strategy_campaign_record?.current_result_ledger_blockers
    || evidence.latest_campaign_record?.current_result_ledger_blockers
    || [];
  const detail = blockers[0] ? String(blockers[0]).replaceAll("_", " ") : "no drift";
  return `${selectedDrift} selected / ${totalDrift} total / ${detail}`;
}

function predictionDemoBatchDriftSummary(deployment) {
  const gate = predictionDemoCampaignGate(deployment);
  if (!gate) return "NOT_RUN";
  const evidence = gate.evidence_snapshot || {};
  if (evidence.required_for_strategy === false) return "not required";
  const selected = evidence.strategy_batch_audit_records || 0;
  const total = evidence.batch_audit_records || 0;
  const selectedDrift = evidence.strategy_batch_current_result_drifted_records || 0;
  const totalDrift = evidence.batch_current_result_drifted_records || 0;
  const blockers = evidence.latest_strategy_batch_record?.current_result_ledger_blockers
    || evidence.latest_batch_record?.current_result_ledger_blockers
    || [];
  const detail = blockers[0] ? String(blockers[0]).replaceAll("_", " ") : "no drift";
  return `${selected}/${total} selected / ${selectedDrift}/${totalDrift} drift / ${detail}`;
}

function predictionDemoCampaignNextAction(deployment) {
  const gate = predictionDemoCampaignGate(deployment);
  if (!gate) return "Run deployment gates.";
  const evidence = gate.evidence_snapshot || {};
  if (evidence.required_for_strategy === false) return "Not required for this strategy.";
  return evidence.next_action || "Review prediction demo campaign quality.";
}

function mktDonorCredentialBoundarySummary(deployment) {
  const gate = (deployment.gates || []).find((item) => item.gate_key === "mkt_donor_credential_boundary");
  if (!gate) return "NOT_RUN";
  const evidence = gate.evidence_snapshot || {};
  if (evidence.required_for_strategy === false) return `${gate.status} / not required`;
  const productionCount = evidence.production_credential_material_count || 0;
  const demo = evidence.demo_credential_pair_present ? "demo pair present" : "no demo pair";
  const reasons = evidence.reasons || [];
  const detail = reasons[0] ? String(reasons[0]).replaceAll("_", " ") : demo;
  return `${gate.status} / prod files ${productionCount} / ${detail}`;
}

function statementReconciliation(report) {
  if (!report) return "NOT_RUN";
  const tradeCount = `${report.aurex_trade_count || 0}/${report.broker_trade_count || 0}`;
  const net = money.format(Number(report.aurex_net_pl || 0));
  return `${report.status} / ${tradeCount} trades / ${net}`;
}

function statementFreshness(deployment) {
  const gate = (deployment.gates || []).find((item) => item.gate_key === "broker_statement_reconciliation");
  if (!gate) return "NOT_RUN";
  const reasons = gate.evidence_snapshot?.freshness_reasons || [];
  if (!reasons.length) return `${gate.status} / current`;
  return `${gate.status} / ${String(reasons[0]).replaceAll("_", " ")}`;
}

function profitMilestone(report) {
  if (!report) return "NOT_RUN";
  const net = money.format(Number(report.total_net_pl || 0));
  const target = money.format(Number(report.target_net_profit || 100));
  return `${report.status} / ${net}/${target}`;
}

function strategyEvidenceReviewSummary(review, deployment) {
  const gate = (deployment?.gates || []).find((item) => item.gate_key === "strategy_evidence_review_clear");
  if (!review && !gate) return "NOT_RUN";
  const evidence = gate?.evidence_snapshot || {};
  const gateStatus = gate?.status || "NOT_RUN";
  const decision = review?.decision || evidence.decision || "NO_REVIEW";
  const freshness = evidence.freshness_reasons || [];
  const reasons = review?.reasons || evidence.reasons || [];
  const detail = freshness[0] || reasons[0] || "current evidence";
  return `${gateStatus} / ${decision} / ${String(detail).replaceAll("_", " ")}`;
}

function strategyEvidenceReviewNextAction(review, deployment) {
  const gate = (deployment?.gates || []).find((item) => item.gate_key === "strategy_evidence_review_clear");
  const evidence = gate?.evidence_snapshot || {};
  const nextActions = review?.next_actions || evidence.next_actions || [];
  if (nextActions.length) return String(nextActions[0]);
  const decision = review?.decision || evidence.decision || "NO_REVIEW";
  if (decision === "CANDIDATE") return "Continue broker/account approval and daily review; live trading remains disabled.";
  if (decision === "DO_NOT_TRADE") return "Reject or redesign the strategy before another evidence cycle.";
  return "Run strategy evidence review after required gates are refreshed.";
}

function strategyEvidenceReviewBlockers(review, deployment) {
  const gate = (deployment?.gates || []).find((item) => item.gate_key === "strategy_evidence_review_clear");
  const evidence = gate?.evidence_snapshot || {};
  const freshness = evidence.freshness_reasons || [];
  const reasons = review?.reasons || evidence.reasons || [];
  const blockers = [...freshness, ...reasons].filter(Boolean);
  if (!blockers.length) return "No blockers reported";
  const preview = blockers.slice(0, 3).map((item) => String(item).replaceAll("_", " ")).join(" / ");
  const suffix = blockers.length > 3 ? ` +${blockers.length - 3}` : "";
  return `${preview}${suffix}`;
}

function activationAuditSummary(attempt) {
  if (!attempt) return "NOT_RUN";
  const blockers = attempt.blocking_gate_keys || [];
  if (!blockers.length) return attempt.message || "No blocking gates reported";
  const nextActions = attempt.next_actions || [];
  if (nextActions.length) {
    return `${attempt.status} / ${blockers.length} blockers / ${nextActions[0]}`;
  }
  const preview = blockers.slice(0, 3).map((key) => key.replaceAll("_", " ")).join(" / ");
  const suffix = blockers.length > 3 ? ` +${blockers.length - 3}` : "";
  return `${attempt.status} / ${blockers.length} blockers / ${preview}${suffix}`;
}

function liveExecutionAdapterSummary(deployment) {
  const gate = (deployment.gates || []).find((item) => item.gate_key === "live_execution_adapter_ready");
  if (!gate) return "NOT_RUN";
  const evidence = gate.evidence_snapshot || {};
  const adapter = evidence.adapter || evidence.configured_adapter || "disabled";
  const reasons = evidence.reasons || [];
  const detail = reasons[0] ? String(reasons[0]).replaceAll("_", " ") : "ready";
  return `${gate.status} / ${adapter} / ${detail}`;
}

function brokerDiligence(packet) {
  if (!packet) return "No packet";
  const referenceCount = [
    packet.account_constraints_reference,
    packet.execution_policy_reference,
    packet.fee_slippage_model_reference,
    packet.paper_to_live_checklist_reference,
  ].filter(Boolean).length;
  const leverage = packet.leverage_allowed ? "leverage flagged" : "no leverage";
  return `${referenceCount}/4 refs / ${leverage}`;
}

function importStatusClass(status) {
  if (status === "IMPORTED") return "status-ok";
  if (status === "REJECTED") return "status-danger";
  return "status-warn";
}

function evidenceImportSummary(batch) {
  return `${batch.imported_count || 0} imported / ${batch.skipped_count || 0} skipped / ${batch.rejected_count || 0} rejected`;
}

function firstImportedEvidenceHash(batch) {
  const hashes = batch?.evidence_snapshot?.imported_external_trade_hashes || {};
  return Object.values(hashes)[0] || null;
}

function paperEvidenceCollectionImportSummary(collection) {
  const firstOutOfScope = (collection.out_of_scope_import_summary || [])[0];
  const scopeText = firstOutOfScope
    ? ` / ${firstOutOfScope.symbol || "--"} ${firstOutOfScope.count || 0} out`
    : "";
  return `${collection.scoped_imported_count || 0} scoped / ${collection.out_of_scope_imported_count || 0} out${scopeText} / ${collection.imported_count || 0} accepted / ${collection.rejected_count || 0} rejected`;
}

function backtestReportSummary(report) {
  const result = report.result || {};
  const snapshot = result.metrics_snapshot || {};
  const oos = snapshot.out_of_sample || {};
  const walkForward = snapshot.walk_forward || {};
  const distribution = snapshot.trade_distribution || {};
  const hash = String(report.config_hash || "").slice(0, 8) || "no hash";
  const walkForwardMode = walkForward.acceptance_eligible ? "verified WF" : "diagnostic slices";
  return `${result.total_trades || 0} trades / ${oos.total_trades || 0} OOS / ${walkForward.passed_windows || 0}/${walkForward.window_count || 0} ${walkForwardMode} / ${distribution.active_trading_days || 0} days / ${hash}`;
}

function formatRatio(value) {
  if (value === null || value === undefined) return "--";
  return Number(value).toFixed(2);
}

async function enableKillSwitch() {
  await api("/risk/kill-switch", { method: "POST", body: "{}" });
  await refresh();
}

async function resetKillSwitch() {
  await api("/risk/kill-switch/reset", { method: "POST", body: "{}" });
  await refresh();
}

async function toggleStrategy(strategy, isEnabled) {
  await api(`/strategies/${encodeURIComponent(strategy)}`, {
    method: "PATCH",
    body: JSON.stringify({ is_enabled: !isEnabled }),
  });
  await refresh();
}

async function runAnalystScan() {
  await api("/analyst/risk-anomalies/scan", {
    method: "POST",
    body: JSON.stringify({ limit: 100 }),
  });
  await api("/analyst/strategy-degradation/scan", {
    method: "POST",
    body: JSON.stringify({ limit: 100 }),
  });
  await refresh();
}

async function runBrokerChecks() {
  await api("/broker/readiness/run", { method: "POST", body: "{}" });
  await refresh();
}

async function brokerEmergencyStop() {
  await api("/broker/emergency-stop", { method: "POST", body: "{}" });
  await refresh();
}

function operatorProfilePayload() {
  const scope = inputValue("operator-profile-product-scope") || "SPOT_ONLY";
  const attestedAt = new Date().toISOString();
  const attestedAtInput = document.getElementById("operator-profile-attested-at");
  if (attestedAtInput) attestedAtInput.value = attestedAt;
  return {
    schema_version: "aurex-post-v4-operator-access-input-v1",
    attested_at: attestedAt,
    operator_identifier: inputValue("operator-profile-operator-identifier"),
    attestation_statement: document.getElementById("operator-profile-attestation")?.checked
      ? "I_ATTEST_THIS_PROFILE_IS_ACCURATE_AND_CONTAINS_NO_CREDENTIALS"
      : "MISSING_OPERATOR_ATTESTATION",
    jurisdiction: inputValue("operator-profile-jurisdiction"),
    intended_execution_venue: inputValue("operator-profile-venue"),
    account_identifier_alias: inputValue("operator-profile-account-alias"),
    account_status: inputValue("operator-profile-account-status"),
    api_access_status: inputValue("operator-profile-api-access-status"),
    sandbox_access_status: inputValue("operator-profile-sandbox-status"),
    permitted_product_scope: scope,
    other_product_scope: scope === "OTHER"
      ? inputValue("operator-profile-other-scope") || null
      : null,
    derivatives_access_confirmed: Boolean(
      document.getElementById("operator-profile-derivatives-access")?.checked,
    ),
    derivatives_suitability_acknowledged: Boolean(
      document.getElementById("operator-profile-derivatives-suitability")?.checked,
    ),
    maximum_effective_leverage: inputValue("operator-profile-leverage"),
    legal_and_tax_obligations_acknowledged: Boolean(
      document.getElementById("operator-profile-legal-ack")?.checked,
    ),
    starting_trading_capital: inputValue("operator-profile-capital"),
    capital_currency: inputValue("operator-profile-capital-currency"),
    capital_is_borrowed: !document.getElementById("operator-profile-unborrowed")?.checked,
    capital_excludes_emergency_funds: Boolean(
      document.getElementById("operator-profile-emergency-funds")?.checked,
    ),
    maximum_total_loss: inputValue("operator-profile-total-loss"),
    maximum_daily_loss: inputValue("operator-profile-daily-loss"),
    maximum_per_trade_loss: inputValue("operator-profile-trade-loss"),
    one_time_data_budget: inputValue("operator-profile-one-time-budget"),
    monthly_data_budget: inputValue("operator-profile-monthly-budget"),
    data_budget_currency: inputValue("operator-profile-budget-currency"),
    paid_data_permitted: Boolean(
      document.getElementById("operator-profile-paid-data")?.checked,
    ),
    venue_terms_reference: inputValue("operator-profile-terms-reference"),
    fee_schedule_reference: inputValue("operator-profile-fee-reference"),
    api_documentation_reference: inputValue("operator-profile-api-reference"),
    product_access_evidence_reference: inputValue("operator-profile-product-reference"),
    sandbox_evidence_reference: inputValue("operator-profile-sandbox-reference"),
    capital_source_attestation_reference: inputValue("operator-profile-capital-reference"),
    data_budget_attestation_reference: inputValue("operator-profile-budget-reference"),
    credentials_stored_or_embedded: !document.getElementById(
      "operator-profile-no-credentials",
    )?.checked,
  };
}

async function preflightOperatorProfile() {
  const payload = operatorProfilePayload();
  state.operatorProfilePreflight = null;
  state.operatorProfileValidatedInput = null;
  const result = await api("/operator-profile/preflight", {
    method: "POST",
    body: JSON.stringify(payload),
  });
  state.operatorProfilePreflight = result;
  state.operatorProfileValidatedInput = result.status === "PASS" ? payload : null;
  renderOperatorProfile();
  return result;
}

function resetOperatorProfile() {
  document.getElementById("operator-profile-form")?.reset();
  const otherScope = document.getElementById("operator-profile-other-scope");
  if (otherScope) {
    otherScope.value = "";
    otherScope.disabled = true;
  }
  const attestedAt = document.getElementById("operator-profile-attested-at");
  if (attestedAt) attestedAt.value = new Date().toISOString();
  state.operatorProfilePreflight = null;
  state.operatorProfileValidatedInput = null;
  renderOperatorProfile();
  return { status: "RESET" };
}

function downloadOperatorProfileInput() {
  const payload = state.operatorProfileValidatedInput;
  if (!payload || state.operatorProfilePreflight?.status !== "PASS") {
    throw new Error("A passing no-write preflight is required before download.");
  }
  const filename =
    state.operatorProfilePreflight.input_filename
    || state.operatorProfileTemplate?.input_filename
    || "aurex-operator-profile-input.json";
  const blob = new Blob([`${JSON.stringify(payload, null, 2)}\n`], {
    type: "application/json",
  });
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = filename;
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
  URL.revokeObjectURL(url);
  return { status: "DOWNLOADED", filename };
}

async function copyOperatorProfileFreezeCommand() {
  if (
    state.operatorProfilePreflight?.status !== "PASS"
    || !state.operatorProfileValidatedInput
  ) {
    throw new Error("A passing no-write preflight is required first.");
  }
  const filename =
    state.operatorProfilePreflight.input_filename
    || "aurex-operator-profile-input.json";
  const command = String(
    state.operatorProfilePreflight.freeze_command
    || state.operatorProfileTemplate?.freeze_command
    || "",
  ).replace("<path-to-input.json>", filename);
  await copyTextToClipboard(command);
  return { status: "COPIED" };
}

function updateOperatorProductScope() {
  const scope = inputValue("operator-profile-product-scope");
  const input = document.getElementById("operator-profile-other-scope");
  if (!input) return;
  input.disabled = scope !== "OTHER";
  if (input.disabled) input.value = "";
}

function invalidateOperatorProfilePreflight() {
  if (!state.operatorProfilePreflight && !state.operatorProfileValidatedInput) return;
  state.operatorProfilePreflight = null;
  state.operatorProfileValidatedInput = null;
  renderOperatorProfile();
}

async function runDeploymentChecks() {
  await api("/live/deployment/checks/run", { method: "POST", body: "{}" });
  await refresh();
}

async function createDailyReview() {
  await api("/live/deployment/daily-review", { method: "POST", body: "{}" });
  await refresh();
}

async function runPaperEvidence() {
  await api("/live/deployment/paper-evidence/run", { method: "POST", body: "{}" });
  await refresh();
}

async function preflightBrokerStatementCsv() {
  const statementReference = document.getElementById("statement-reference")?.value || "";
  const csvText = document.getElementById("statement-csv")?.value || "";
  state.brokerStatementPreflight = await api("/live/deployment/broker-statements/preflight-csv", {
    method: "POST",
    body: JSON.stringify({
      statement_reference: statementReference,
      csv_text: csvText,
    }),
  });
  renderBrokerStatementPreflight();
}

async function reconcileBrokerStatementCsv() {
  const statementReference = document.getElementById("statement-reference")?.value || "";
  const csvText = document.getElementById("statement-csv")?.value || "";
  await api("/live/deployment/broker-statements/reconcile-csv", {
    method: "POST",
    body: JSON.stringify({
      statement_reference: statementReference,
      csv_text: csvText,
    }),
  });
  state.brokerStatementPreflight = null;
  await refresh();
}

async function loadBacktestReportTemplate() {
  const response = await fetch("/backtests/report-template.csv");
  if (!response.ok) {
    throw new Error(`/backtests/report-template.csv returned ${response.status}`);
  }
  const input = document.getElementById("backtest-csv");
  if (input) input.value = await response.text();
}

async function loadBacktestStrategySetup() {
  const strategy = inputValue("backtest-strategy");
  if (!strategy) {
    throw new Error("Enter the ID of a frozen strategy charter first.");
  }
  const symbol = backtestPrimarySymbol();
  const timeframe = inputValue("backtest-timeframe") || "15m";
  const path = `/backtests/strategy-setup?strategy=${encodeURIComponent(strategy)}&symbol=${encodeURIComponent(symbol)}&timeframe=${encodeURIComponent(timeframe)}`;
  state.backtestStrategySetup = await api(path);
  hydrateBacktestStrategySetup(state.backtestStrategySetup);
  state.backtestWindowPlan = null;
  state.backtestPreflight = null;
  renderBacktestSetup();
  renderBacktestWindowPlan();
  renderBacktestProtocols();
  return state.backtestStrategySetup;
}

function backtestPrimarySymbol() {
  return (
    inputValue("backtest-symbols")
      .split(",")
      .map((symbol) => symbol.trim().toUpperCase())
      .find(Boolean) || "BTCUSDT"
  );
}

function hydrateBacktestStrategySetup(setup) {
  setInput("backtest-strategy", setup.strategy);
  setInput("backtest-version", setup.strategy_version);
  setInput("backtest-symbols", setup.symbol);
  setInput("backtest-timeframe", setup.timeframe);
  setInput("backtest-data-source", setup.data_source);
  setInput("backtest-csv-timezone", setup.csv_timezone);
  setInput("backtest-source-reference", setup.source_reference);
  setInput("backtest-parameters", JSON.stringify(setup.parameters || {}, null, 2));
  setInput("backtest-cost-model", JSON.stringify(setup.cost_model || {}, null, 2));
  setInput("backtest-slippage-model", JSON.stringify(setup.slippage_model || {}, null, 2));
  setInput("backtest-risk-snapshot", JSON.stringify(setup.risk_snapshot || {}, null, 2));
  setInput(
    "backtest-walk-forward-windows",
    JSON.stringify(setup.walk_forward_windows || [], null, 2),
  );
  setInput("backtest-acceptance", JSON.stringify(setup.acceptance_criteria || {}, null, 2));
  setInput("backtest-protocol-id", "");
}

async function planBacktestWalkForwardWindows() {
  const acceptance = jsonInputValue("backtest-acceptance");
  const requestedWindows = Number(acceptance.min_walk_forward_windows || 3);
  if (!Number.isInteger(requestedWindows) || requestedWindows < 2 || requestedWindows > 12) {
    throw new Error("min_walk_forward_windows must be an integer from 2 through 12.");
  }
  state.backtestWindowPlan = await api("/backtests/window-plan", {
    method: "POST",
    body: JSON.stringify({
      strategy: inputValue("backtest-strategy"),
      in_sample_start: inputValue("backtest-is-start"),
      in_sample_end: inputValue("backtest-is-end"),
      parameters: jsonInputValue("backtest-parameters"),
      window_count: requestedWindows,
      initial_training_fraction: "0.333333",
    }),
  });
  setInput(
    "backtest-walk-forward-windows",
    JSON.stringify(state.backtestWindowPlan.windows || [], null, 2),
  );
  setInput("backtest-protocol-id", "");
  state.backtestPreflight = null;
  renderBacktestWindowPlan();
  renderBacktestPreflight();
  renderBacktestProtocols();
  return state.backtestWindowPlan;
}

async function loadBacktestCsvFile(event) {
  const file = event.target.files?.[0];
  if (!file) return;
  const maxBytes = 20 * 1024 * 1024;
  if (file.size > maxBytes) {
    event.target.value = "";
    throw new Error("TradingView CSV exceeds the 20 MiB dashboard limit.");
  }
  const csvText = await file.text();
  if (!csvText.trim()) {
    event.target.value = "";
    throw new Error("TradingView CSV is empty.");
  }
  setInput("backtest-csv", csvText);
  state.backtestCsvFileName = file.name;
  state.backtestPreflight = null;
  renderBacktestPreflight();
  showNotification(`${file.name} loaded. Run preflight before import.`, {
    tone: "success",
    title: "CSV ready",
  });
}

function backtestOhlcvPayload() {
  const manifest = jsonInputValue("backtest-ohlcv-manifest");
  const documentedGaps = jsonInputValue("backtest-ohlcv-documented-gaps");
  if (!Array.isArray(documentedGaps)) {
    throw new Error("Documented outage evidence must be a JSON array.");
  }
  return {
    symbol: backtestPrimarySymbol(),
    timeframe: inputValue("backtest-timeframe") || "15m",
    source: inputValue("backtest-ohlcv-source"),
    source_reference: inputValue("backtest-ohlcv-source-reference"),
    csv_timezone: inputValue("backtest-ohlcv-timezone") || "UTC",
    continuity: inputValue("backtest-ohlcv-continuity") || "continuous_24_7",
    documented_gaps: documentedGaps,
    source_artifacts: manifest.source_artifacts || [],
    transformation: manifest.transformation || null,
    csv_text: inputValue("backtest-ohlcv-csv"),
  };
}

async function preflightBacktestOhlcv() {
  state.backtestOhlcvPreflight = await api("/backtests/ohlcv/preflight-csv", {
    method: "POST",
    body: JSON.stringify(backtestOhlcvPayload()),
  });
  renderBacktestOhlcv();
  return state.backtestOhlcvPreflight;
}

async function importBacktestOhlcv() {
  const dataset = await api("/backtests/ohlcv/import-csv", {
    method: "POST",
    body: JSON.stringify(backtestOhlcvPayload()),
  });
  state.backtestDatasets = [
    dataset,
    ...(state.backtestDatasets || []).filter((item) => item.id !== dataset.id),
  ];
  state.backtestOhlcvPreflight = null;
  renderBacktestOhlcv();
  renderBacktestReferenceReplay();
  return dataset;
}

function backtestReferencePayload() {
  return {
    dataset_id: inputValue("backtest-reference-dataset-id"),
    strategy: inputValue("backtest-strategy"),
    strategy_version: inputValue("backtest-version"),
    parameters: jsonInputValue("backtest-parameters"),
    tick_size: inputValue("backtest-reference-tick-size"),
    point_value: inputValue("backtest-reference-point-value"),
    minimum_contract: inputValue("backtest-reference-minimum-contract"),
    commission_percent: inputValue("backtest-reference-commission"),
    slippage_ticks: Number(inputValue("backtest-reference-slippage-ticks")),
    intrabar_policy: "stop_first",
  };
}

async function preflightReferenceReplay() {
  state.backtestReferenceReplay = await api("/backtests/reference-replay/preflight", {
    method: "POST",
    body: JSON.stringify(backtestReferencePayload()),
  });
  renderBacktestReferenceReplay();
  return state.backtestReferenceReplay;
}

async function recordReferenceReplay() {
  const record = await api("/backtests/reference-replay/runs", {
    method: "POST",
    body: JSON.stringify(backtestReferencePayload()),
  });
  state.backtestReferenceRuns = [
    record,
    ...(state.backtestReferenceRuns || []).filter((item) => item.id !== record.id),
  ];
  state.backtestReferenceReplay = null;
  renderBacktestReferenceReplay();
  return record;
}

function referenceReplayValidationPayload() {
  return {
    reference_replay_run_id: inputValue("backtest-reference-validation-replay-id"),
    protocol_id: inputValue("backtest-reference-validation-protocol-id"),
  };
}

async function preflightReferenceReplayValidation() {
  state.backtestReferenceValidationPreflight = await api(
    "/backtests/reference-replay/validations/preflight",
    {
      method: "POST",
      body: JSON.stringify(referenceReplayValidationPayload()),
    },
  );
  renderBacktestReferenceReplay();
  return state.backtestReferenceValidationPreflight;
}

async function recordReferenceReplayValidation() {
  const validation = await api("/backtests/reference-replay/validations", {
    method: "POST",
    body: JSON.stringify(referenceReplayValidationPayload()),
  });
  state.backtestReferenceValidations = [
    validation,
    ...(state.backtestReferenceValidations || []).filter(
      (item) => item.id !== validation.id,
    ),
  ];
  state.backtestReferenceValidationPreflight = null;
  renderBacktestReferenceReplay();
  return validation;
}

function backtestParityPayload() {
  const lineage = state.backtestParityExportManifest;
  if (lineage?.status !== "READY" || !lineage.manifest_hash) {
    throw new Error("Prepare and review a READY paired-export lineage first.");
  }
  return {
    dataset_id: inputValue("backtest-parity-dataset-id"),
    tradingview_chart_dataset_id: inputValue(
      "backtest-parity-chart-dataset-id",
    ),
    tradingview_run_id: inputValue("backtest-parity-report-id"),
    tick_size: inputValue("backtest-parity-tick-size"),
    point_value: inputValue("backtest-parity-point-value"),
    minimum_contract: inputValue("backtest-parity-minimum-contract"),
    export_attestation: lineage.manifest.attestation,
    reviewed_export_manifest_hash: lineage.manifest_hash,
    tolerances: {
      entry_time_seconds: Number(inputValue("backtest-parity-entry-seconds")),
      exit_time_seconds: Number(inputValue("backtest-parity-exit-seconds")),
      price_ticks: Number(inputValue("backtest-parity-price-ticks")),
      quantity_relative: inputValue("backtest-parity-quantity-relative"),
      money_absolute: inputValue("backtest-parity-money-absolute"),
    },
  };
}

async function preflightBacktestParityExportManifest() {
  if (!document.getElementById("backtest-parity-export-attestation")?.checked) {
    throw new Error("Confirm the paired-export attestation first.");
  }
  state.backtestParityPreflight = null;
  state.backtestParityExportManifest = await api(
    "/backtests/parity/export-manifest/preflight",
    {
      method: "POST",
      body: JSON.stringify({
        dataset_id: inputValue("backtest-parity-dataset-id"),
        tradingview_chart_dataset_id: inputValue(
          "backtest-parity-chart-dataset-id",
        ),
        tradingview_run_id: inputValue("backtest-parity-report-id"),
        export_attestation: {
          statement: TRADINGVIEW_PAIRED_EXPORT_ATTESTATION,
          attested_at: new Date().toISOString(),
        },
      }),
    },
  );
  renderBacktestParity();
  return state.backtestParityExportManifest;
}

async function preflightBacktestParity() {
  state.backtestParityPreflight = await api("/backtests/parity/preflight", {
    method: "POST",
    body: JSON.stringify(backtestParityPayload()),
  });
  renderBacktestParity();
  return state.backtestParityPreflight;
}

async function recordBacktestParity() {
  const record = await api("/backtests/parity/runs", {
    method: "POST",
    body: JSON.stringify(backtestParityPayload()),
  });
  state.backtestParityRuns = [
    record,
    ...(state.backtestParityRuns || []).filter((item) => item.id !== record.id),
  ];
  state.backtestParityPreflight = null;
  renderBacktestParity();
  return record;
}

async function loadBacktestOhlcvFile(event) {
  const file = event.target.files?.[0];
  if (!file) return;
  const maxBytes = 50 * 1024 * 1024;
  if (file.size > maxBytes) {
    event.target.value = "";
    throw new Error("OHLCV CSV exceeds the 50 MiB dashboard limit.");
  }
  const csvText = await file.text();
  if (!csvText.trim()) {
    event.target.value = "";
    throw new Error("OHLCV CSV is empty.");
  }
  setInput("backtest-ohlcv-csv", csvText);
  state.backtestOhlcvPreflight = null;
  renderBacktestOhlcv();
  showNotification(`${file.name} loaded. Run data preflight before import.`, {
    tone: "success",
    title: "Historical data ready",
  });
}

async function loadBacktestOhlcvManifestFile(event) {
  const file = event.target.files?.[0];
  if (!file) return;
  if (file.size > 2 * 1024 * 1024) {
    event.target.value = "";
    throw new Error("Source manifest exceeds the 2 MiB dashboard limit.");
  }
  const manifestText = await file.text();
  let manifest;
  try {
    manifest = JSON.parse(manifestText);
  } catch {
    event.target.value = "";
    throw new Error("Source manifest is not valid JSON.");
  }
  setInput("backtest-ohlcv-manifest", JSON.stringify(manifest, null, 2));
  setInput("backtest-ohlcv-source", manifest.source || "binance-vision");
  setInput("backtest-ohlcv-source-reference", manifest.source_reference || "");
  setInput("backtest-ohlcv-continuity", manifest.continuity || "continuous_24_7");
  setInput(
    "backtest-ohlcv-documented-gaps",
    JSON.stringify(manifest.documented_gaps || [], null, 2),
  );
  state.backtestOhlcvPreflight = null;
  renderBacktestOhlcv();
}

async function registerBacktestProtocol() {
  const protocol = await api("/backtests/protocols", {
    method: "POST",
    body: JSON.stringify(backtestProtocolPayload()),
  });
  state.backtestProtocols = [
    protocol,
    ...(state.backtestProtocols || []).filter((item) => item.id !== protocol.id),
  ];
  state.backtestPreflight = null;
  state.backtestRunManifest = null;
  state.backtestRunPackage = null;
  renderBacktestProtocols();
  setInput("backtest-protocol-id", protocol.id);
  renderBacktestProtocols();
  await loadBacktestRunManifest();
  return protocol;
}

async function loadBacktestRunManifest() {
  const protocolId = inputValue("backtest-protocol-id");
  if (!protocolId) throw new Error("Select a registered protocol first.");
  state.backtestRunManifest = await api(
    `/backtests/protocols/${encodeURIComponent(protocolId)}/run-manifest`,
  );
  renderBacktestProtocols();
  renderCommandEvidencePath();
  return state.backtestRunManifest;
}

async function loadBacktestTradingViewRunPackage() {
  const protocolId = inputValue("backtest-protocol-id");
  if (!protocolId) throw new Error("Select a registered protocol first.");
  state.backtestRunPackage = await api(
    `/backtests/protocols/${encodeURIComponent(protocolId)}/tradingview-run-package`,
  );
  renderBacktestProtocols();
  return state.backtestRunPackage;
}

async function copyBacktestPineSource() {
  if (state.backtestRunPackage?.status !== "READY") {
    throw new Error("Prepare a READY TradingView run package first.");
  }
  await copyTextToClipboard(state.backtestRunPackage.pine_source);
}

async function copyBacktestTradingViewSetup() {
  if (state.backtestRunPackage?.status !== "READY") {
    throw new Error("Prepare a READY TradingView run package first.");
  }
  await copyTextToClipboard(JSON.stringify({
    protocol_id: state.backtestRunPackage.protocol_id,
    protocol_hash: state.backtestRunPackage.protocol_hash,
    manifest_hash: state.backtestRunPackage.manifest_hash,
    package_hash: state.backtestRunPackage.package_hash,
    pine_source_sha256: state.backtestRunPackage.pine_source_sha256,
    tradingview_url: state.backtestRunPackage.tradingview_url,
    tradingview_setup: state.backtestRunPackage.tradingview_setup,
  }, null, 2));
}

async function preflightBacktestReportCsv() {
  state.backtestPreflight = await api("/backtests/reports/preflight-csv", {
    method: "POST",
    body: JSON.stringify(backtestReportPayload()),
  });
  renderBacktestPreflight();
  renderBacktestProtocols();
}

async function preflightTradingViewSignal() {
  state.signalPreflight = await api("/signals/preflight/tradingview", {
    method: "POST",
    body: JSON.stringify(jsonInputValue("signal-preflight-payload")),
  });
  renderSignalPreflight();
  return state.signalPreflight;
}

async function loadTradingViewAlertSetup() {
  const strategy = state.signalContract?.strategy;
  const symbol = state.signalContract?.symbol;
  if (!strategy || !symbol) {
    throw new Error("No qualified strategy signal contract is available.");
  }
  const path = `/signals/tradingview-alert-setup?strategy=${encodeURIComponent(strategy)}&symbol=${encodeURIComponent(symbol)}`;
  state.signalAlertSetup = await api(path);
  hydrateSignalAlertPayload(state.signalAlertSetup, { replace: true });
  renderSignalAlertSetup();
  return state.signalAlertSetup;
}

async function importBacktestReportCsv() {
  await api("/backtests/reports/import-csv", {
    method: "POST",
    body: JSON.stringify(backtestReportPayload()),
  });
  state.backtestPreflight = null;
  await refresh();
}

function backtestReportPayload() {
  return {
    protocol_id: nullableInputValue("backtest-protocol-id"),
    strategy: inputValue("backtest-strategy"),
    strategy_version: inputValue("backtest-version"),
    symbols: inputValue("backtest-symbols")
      .split(",")
      .map((symbol) => symbol.trim().toUpperCase())
      .filter(Boolean),
    timeframe: inputValue("backtest-timeframe"),
    data_source: inputValue("backtest-data-source"),
    csv_format: "auto",
    csv_timezone: inputValue("backtest-csv-timezone") || "UTC",
    source_reference: nullableInputValue("backtest-source-reference"),
    data_start: inputValue("backtest-data-start"),
    data_end: inputValue("backtest-data-end"),
    in_sample_start: nullableInputValue("backtest-is-start"),
    in_sample_end: nullableInputValue("backtest-is-end"),
    out_of_sample_start: nullableInputValue("backtest-oos-start"),
    out_of_sample_end: nullableInputValue("backtest-oos-end"),
    parameters: jsonInputValue("backtest-parameters"),
    cost_model: jsonInputValue("backtest-cost-model"),
    slippage_model: jsonInputValue("backtest-slippage-model"),
    risk_snapshot: jsonInputValue("backtest-risk-snapshot"),
    walk_forward_windows: jsonInputValue("backtest-walk-forward-windows"),
    acceptance_criteria: jsonInputValue("backtest-acceptance"),
    csv_text: inputValue("backtest-csv"),
  };
}

function backtestProtocolPayload() {
  const payload = backtestReportPayload();
  delete payload.protocol_id;
  delete payload.csv_format;
  delete payload.csv_text;
  if (!payload.source_reference) {
    throw new Error("A stable source reference is required before protocol registration.");
  }
  return payload;
}

async function loadPaperEvidenceTemplate() {
  const response = await fetch("/paper/evidence/template.csv");
  if (!response.ok) {
    throw new Error(`/paper/evidence/template.csv returned ${response.status}`);
  }
  const input = document.getElementById("evidence-csv");
  if (input) input.value = await response.text();
}

async function importPaperEvidenceCsv() {
  const source = document.getElementById("evidence-source")?.value || "";
  const sourceReference = document.getElementById("evidence-source-reference")?.value || "";
  const csvText = document.getElementById("evidence-csv")?.value || "";
  await api("/paper/evidence/import-csv", {
    method: "POST",
    body: JSON.stringify({
      source,
      source_reference: sourceReference,
      csv_text: csvText,
    }),
  });
  await refresh();
}

async function preflightPaperEvidenceCsv() {
  const source = document.getElementById("evidence-source")?.value || "";
  const sourceReference = document.getElementById("evidence-source-reference")?.value || "";
  const csvText = document.getElementById("evidence-csv")?.value || "";
  state.paperEvidencePreflight = await api("/paper/evidence/preflight-csv", {
    method: "POST",
    body: JSON.stringify({
      source,
      source_reference: sourceReference,
      csv_text: csvText,
    }),
  });
  renderPaperEvidencePreflight();
}

async function submitApprovalPacket(payload) {
  await api("/live/deployment/approval-packet", {
    method: "POST",
    body: JSON.stringify(payload),
  });
  await refresh();
}

function approvalPacketPayload() {
  return {
    broker_name: inputValue("approval-broker-name"),
    account_label: inputValue("approval-account-label"),
    account_type: inputValue("approval-account-type"),
    asset_class: inputValue("approval-asset-class"),
    jurisdiction: inputValue("approval-jurisdiction"),
    currency: inputValue("approval-currency") || "USD",
    broker_terms_reference: inputValue("approval-terms-reference"),
    fee_schedule_reference: inputValue("approval-fee-reference"),
    margin_policy_reference: inputValue("approval-margin-reference"),
    account_constraints_reference: inputValue("approval-constraints-reference"),
    execution_policy_reference: inputValue("approval-execution-reference"),
    fee_slippage_model_reference: inputValue("approval-cost-model-reference"),
    paper_to_live_checklist_reference: inputValue("approval-checklist-reference"),
    sandbox_test_reference: inputValue("approval-sandbox-reference") || null,
    leverage_allowed: Boolean(document.getElementById("approval-leverage-allowed")?.checked),
    tax_notes: inputValue("approval-tax-notes") || null,
    credentials_stored: Boolean(document.getElementById("approval-credentials-stored")?.checked),
  };
}

function inputValue(id) {
  return document.getElementById(id)?.value?.trim() || "";
}

function nullableInputValue(id) {
  return inputValue(id) || null;
}

function jsonInputValue(id) {
  const raw = inputValue(id);
  if (!raw) return {};
  try {
    return JSON.parse(raw);
  } catch (error) {
    throw new Error(`${id} contains invalid JSON`);
  }
}

async function createPredictionSnapshot() {
  const payload = predictionSnapshotPayload();
  const contract = await api("/prediction-market/contracts/snapshot", {
    method: "POST",
    body: JSON.stringify(payload),
  });
  const input = document.getElementById("prediction-contract-id");
  if (input) input.value = contract.id;
  await refresh();
  return contract;
}

async function loadPredictionContractSnapshotTemplate() {
  const response = await fetch("/prediction-market/contracts/template.csv");
  if (!response.ok) {
    throw new Error(`/prediction-market/contracts/template.csv returned ${response.status}`);
  }
  const input = document.getElementById("prediction-contract-csv");
  if (input) input.value = await response.text();
}

async function preflightPredictionContractSnapshotCsv() {
  state.predictionContractCsvPreflight = await api("/prediction-market/contracts/preflight-csv", {
    method: "POST",
    body: JSON.stringify(predictionContractSnapshotCsvPayload()),
  });
  renderPredictionContractCsvPreflight();
}

async function importPredictionContractSnapshotCsv() {
  await api("/prediction-market/contracts/import-csv", {
    method: "POST",
    body: JSON.stringify(predictionContractSnapshotCsvPayload()),
  });
  state.predictionContractCsvPreflight = null;
  await refresh();
}

function predictionContractSnapshotCsvPayload() {
  return {
    source: inputValue("prediction-csv-source") || "prediction_market_csv",
    source_reference: inputValue("prediction-csv-source-reference") || "manual-upload",
    csv_format: inputValue("prediction-csv-format") || "auto",
    csv_text: inputValue("prediction-contract-csv"),
  };
}

function predictionContractSnapshotMktDbDiscoveryPayload() {
  const dbPath = inputValue("prediction-mkt-db-path") || "My-Krypt-Trader/.aurex-demo-userdata/data/krypt-trader.db";
  const root = dbPath.includes("/") || dbPath.includes("\\")
    ? dbPath.replace(/[\\/][^\\/]*$/, "")
    : "My-Krypt-Trader";
  return {
    search_roots: Array.from(new Set([root, "My-Krypt-Trader", "My-Krypt-Trader/python"])),
    limit: 25,
    status_filter: inputValue("prediction-mkt-db-status-filter") || "resolved",
    min_volume: nullableInputValue("prediction-mkt-db-min-volume"),
    require_settlement_value: Boolean(
      document.getElementById("prediction-mkt-db-require-settlement")?.checked,
    ),
  };
}

function predictionContractSnapshotMktDonorReadinessPayload() {
  const discovery = predictionContractSnapshotMktDbDiscoveryPayload();
  const dbPath = inputValue("prediction-mkt-db-path") || "My-Krypt-Trader/.aurex-demo-userdata/data/krypt-trader.db";
  const marker = "My-Krypt-Trader";
  const markerIndex = dbPath.indexOf(marker);
  const mktRoot = markerIndex >= 0
    ? dbPath.slice(0, markerIndex + marker.length)
    : "My-Krypt-Trader";
  return {
    mkt_root: mktRoot,
    ...discovery,
  };
}

function predictionContractSnapshotMktRuntimeSafetyPayload() {
  const readiness = predictionContractSnapshotMktDonorReadinessPayload();
  return {
    mkt_root: readiness.mkt_root,
    settings_path: nullableInputValue("prediction-mkt-settings-path"),
    userdata_path: nullableInputValue("prediction-mkt-userdata-path"),
  };
}

function predictionContractSnapshotMktDonorBootstrapPayload() {
  const readiness = predictionContractSnapshotMktDonorReadinessPayload();
  return {
    mkt_root: readiness.mkt_root,
    userdata_path: nullableInputValue("prediction-mkt-userdata-path"),
    overwrite_existing_settings: false,
  };
}

function predictionContractSnapshotMktDonorCollectionStatusPayload() {
  const runtime = predictionContractSnapshotMktRuntimeSafetyPayload();
  return {
    ...runtime,
    db_path: predictionContractSnapshotMktDonorCollectionDbPath(),
    status_filter: inputValue("prediction-mkt-db-status-filter") || "resolved",
    limit: Number(inputValue("prediction-mkt-db-limit") || 100),
    min_volume: nullableInputValue("prediction-mkt-db-min-volume"),
    require_settlement_value: Boolean(
      document.getElementById("prediction-mkt-db-require-settlement")?.checked,
    ),
  };
}

function predictionContractSnapshotMktDonorCollectionDbPath() {
  const selected = inputValue("prediction-mkt-db-path");
  const defaultPath = "My-Krypt-Trader/.aurex-demo-userdata/data/krypt-trader.db";
  return selected && selected !== defaultPath ? selected : null;
}

function predictionContractSnapshotMktDonorLaunchPreflightPayload() {
  const runtime = predictionContractSnapshotMktRuntimeSafetyPayload();
  return {
    ...runtime,
    db_path: predictionContractSnapshotMktDonorCollectionDbPath(),
  };
}

function predictionContractSnapshotMktDonorRunbookPayload() {
  return {
    ...predictionContractSnapshotMktDonorReadinessPayload(),
    db_path: inputValue("prediction-mkt-db-path") || "My-Krypt-Trader/.aurex-demo-userdata/data/krypt-trader.db",
    settings_path: nullableInputValue("prediction-mkt-settings-path"),
    userdata_path: nullableInputValue("prediction-mkt-userdata-path"),
  };
}

async function buildPredictionContractSnapshotMktDonorRunbook() {
  const response = await api("/prediction-market/contracts/mkt-donor-runbook", {
    method: "POST",
    body: JSON.stringify(predictionContractSnapshotMktDonorRunbookPayload()),
  });
  hydratePredictionMktRuntimePaths(response.runtime_safety || null);
  hydratePredictionMktCollectionDbPath(response.collection_status || null);
  state.predictionContractMktDonorRunbook = response;
  state.predictionContractMktDonorReadiness = response.donor_readiness || null;
  state.predictionContractMktDonorCollectionStatus = response.collection_status || null;
  state.predictionContractMktRuntimeSafety = response.runtime_safety || null;
  state.predictionContractMktDbDiscovery = response.donor_readiness?.discovery || null;
  state.predictionContractMktDbInventory = response.db_inventory || null;
  state.predictionContractMktDbReadiness = response.db_inventory?.markets_readiness || null;
  renderPredictionContractMktDonorRunbook();
  renderPredictionContractMktDonorCollectionStatus();
  renderPredictionContractMktRuntimeSafety();
  renderPredictionContractMktDonorReadiness();
  renderPredictionContractMktDbDiscovery();
  renderPredictionContractMktDbInventory();
  renderPredictionContractMktDbReadiness();
  return response;
}

async function checkPredictionContractSnapshotMktRuntimeSafety() {
  const response = await api("/prediction-market/contracts/mkt-runtime-safety", {
    method: "POST",
    body: JSON.stringify(predictionContractSnapshotMktRuntimeSafetyPayload()),
  });
  hydratePredictionMktRuntimePaths(response);
  state.predictionContractMktRuntimeSafety = response;
  renderPredictionContractMktRuntimeSafety();
  return response;
}

async function bootstrapPredictionContractSnapshotMktDonor() {
  const response = await api("/prediction-market/contracts/mkt-donor-bootstrap", {
    method: "POST",
    body: JSON.stringify(predictionContractSnapshotMktDonorBootstrapPayload()),
  });
  hydratePredictionMktRuntimePaths(response.runtime_safety || null);
  hydratePredictionMktBootstrapDbPath(response);
  state.predictionContractMktDonorBootstrap = response;
  state.predictionContractMktRuntimeSafety = response.runtime_safety || null;
  renderPredictionContractMktDonorBootstrap();
  renderPredictionContractMktRuntimeSafety();
  return response;
}

async function preflightPredictionContractSnapshotMktDonorLaunch() {
  const response = await api("/prediction-market/contracts/mkt-donor-launch-preflight", {
    method: "POST",
    body: JSON.stringify(predictionContractSnapshotMktDonorLaunchPreflightPayload()),
  });
  hydratePredictionMktRuntimePaths(response.runtime_safety || null);
  hydratePredictionMktCollectionDbPath(response.collection_status || null);
  state.predictionContractMktDonorLaunchPreflight = response;
  state.predictionContractMktDonorCollectionStatus = response.collection_status || null;
  state.predictionContractMktRuntimeSafety = response.runtime_safety || null;
  state.predictionContractMktDbInventory = response.collection_status?.db_inventory || null;
  state.predictionContractMktDbReadiness = response.collection_status?.db_inventory?.markets_readiness || null;
  renderPredictionContractMktDonorLaunchPreflight();
  renderPredictionContractMktDonorCollectionStatus();
  renderPredictionContractMktRuntimeSafety();
  renderPredictionContractMktDbInventory();
  renderPredictionContractMktDbReadiness();
  return response;
}

async function checkPredictionContractSnapshotMktDonorCollectionStatus() {
  const response = await api("/prediction-market/contracts/mkt-donor-collection-status", {
    method: "POST",
    body: JSON.stringify(predictionContractSnapshotMktDonorCollectionStatusPayload()),
  });
  hydratePredictionMktRuntimePaths(response.runtime_safety || null);
  state.predictionContractMktDonorCollectionStatus = response;
  state.predictionContractMktRuntimeSafety = response.runtime_safety || null;
  state.predictionContractMktDbInventory = response.db_inventory || null;
  state.predictionContractMktDbReadiness = response.db_inventory?.markets_readiness || null;
  renderPredictionContractMktDonorCollectionStatus();
  renderPredictionContractMktRuntimeSafety();
  renderPredictionContractMktDbInventory();
  renderPredictionContractMktDbReadiness();
  return response;
}

function hydratePredictionMktRuntimePaths(report) {
  if (!report) return;
  if (!inputValue("prediction-mkt-settings-path") && report.settings_path) {
    setInput("prediction-mkt-settings-path", report.settings_path);
  }
  if (!inputValue("prediction-mkt-userdata-path") && report.userdata_path) {
    setInput("prediction-mkt-userdata-path", report.userdata_path);
  }
}

function hydratePredictionMktBootstrapDbPath(report) {
  const expectedDb = (report?.command_hints || [])
    .find((hint) => hint.label === "Expected donor DB")?.command;
  if (!expectedDb) return;
  setInput("prediction-mkt-db-path", expectedDb);
  setInput("prediction-mkt-db-source-reference", `${expectedDb}::markets`);
}

function hydratePredictionMktCollectionDbPath(report) {
  if (!report?.db_path) return;
  setInput("prediction-mkt-db-path", report.db_path);
  setInput("prediction-mkt-db-source-reference", `${report.db_path}::markets`);
}

async function checkPredictionContractSnapshotMktDonorReadiness() {
  const response = await api("/prediction-market/contracts/mkt-donor-readiness", {
    method: "POST",
    body: JSON.stringify(predictionContractSnapshotMktDonorReadinessPayload()),
  });
  state.predictionContractMktDonorReadiness = response;
  state.predictionContractMktDbDiscovery = response.discovery || null;
  const ready = (response.discovery?.candidates || []).find((candidate) => candidate.readiness?.data_ready);
  if (ready?.db_path) {
    setInput("prediction-mkt-db-path", ready.db_path);
    setInput("prediction-mkt-db-source-reference", `${ready.db_path}::markets`);
    state.predictionContractMktDbReadiness = ready.readiness;
    state.predictionContractMktDbInventory = null;
    state.predictionContractMktDonorRunbook = null;
    state.predictionContractMktRuntimeSafety = null;
    state.predictionDemoMktDbCampaignManifest = null;
  }
  renderPredictionContractMktDonorRunbook();
  renderPredictionContractMktRuntimeSafety();
  renderPredictionContractMktDonorReadiness();
  renderPredictionContractMktDbDiscovery();
  renderPredictionContractMktDbReadiness();
  renderPredictionContractMktDbInventory();
  renderPredictionMktDbCampaignManifest();
  return response;
}

async function discoverPredictionContractSnapshotMktDbs() {
  const response = await api("/prediction-market/contracts/discover-mkt-dbs", {
    method: "POST",
    body: JSON.stringify(predictionContractSnapshotMktDbDiscoveryPayload()),
  });
  state.predictionContractMktDbDiscovery = response;
  const ready = (response.candidates || []).find((candidate) => candidate.readiness?.data_ready);
  if (ready?.db_path) {
    setInput("prediction-mkt-db-path", ready.db_path);
    setInput("prediction-mkt-db-source-reference", `${ready.db_path}::markets`);
    state.predictionContractMktDbReadiness = ready.readiness;
    state.predictionContractMktDbInventory = null;
    state.predictionContractMktDonorRunbook = null;
    state.predictionContractMktRuntimeSafety = null;
    state.predictionDemoMktDbCampaignManifest = null;
  }
  renderPredictionContractMktDonorRunbook();
  renderPredictionContractMktRuntimeSafety();
  renderPredictionContractMktDbDiscovery();
  renderPredictionContractMktDbReadiness();
  renderPredictionContractMktDbInventory();
  renderPredictionMktDbCampaignManifest();
  return response;
}

function selectPredictionContractSnapshotMktDbCandidate(index) {
  const candidate = (state.predictionContractMktDbDiscovery?.candidates || [])[Number(index)];
  if (!candidate) return null;
  setInput("prediction-mkt-db-path", candidate.db_path);
  setInput(
    "prediction-mkt-db-source-reference",
    candidate.readiness?.source_reference || `${candidate.db_path}::markets`,
  );
  state.predictionContractMktDbReadiness = candidate.readiness || null;
  state.predictionContractMktDbInventory = null;
  state.predictionContractMktDonorRunbook = null;
  state.predictionContractMktRuntimeSafety = null;
  state.predictionDemoMktDbCampaignManifest = null;
  renderPredictionContractMktDonorRunbook();
  renderPredictionContractMktRuntimeSafety();
  renderPredictionContractMktDbDiscovery();
  renderPredictionContractMktDbReadiness();
  renderPredictionContractMktDbInventory();
  renderPredictionMktDbCampaignManifest();
  return candidate;
}

async function checkPredictionContractSnapshotMktDbReadiness() {
  state.predictionContractMktDbReadiness = await api(
    "/prediction-market/contracts/mkt-db-readiness",
    {
      method: "POST",
      body: JSON.stringify(predictionContractSnapshotMktDbPayload()),
    },
  );
  renderPredictionContractMktDbReadiness();
  return state.predictionContractMktDbReadiness;
}

async function inspectPredictionContractSnapshotMktDbInventory() {
  const response = await api("/prediction-market/contracts/mkt-db-inventory", {
    method: "POST",
    body: JSON.stringify(predictionContractSnapshotMktDbPayload()),
  });
  state.predictionContractMktDbInventory = response;
  state.predictionContractMktDbReadiness = response.markets_readiness || null;
  renderPredictionContractMktDbInventory();
  renderPredictionContractMktDbReadiness();
  return response;
}

async function preflightPredictionContractSnapshotMktDb() {
  state.predictionContractMktDbPreflight = await api("/prediction-market/contracts/preflight-mkt-db", {
    method: "POST",
    body: JSON.stringify(predictionContractSnapshotMktDbPayload()),
  });
  renderPredictionContractMktDbPreflight();
  return state.predictionContractMktDbPreflight;
}

async function importPredictionContractSnapshotMktDb() {
  const response = await api("/prediction-market/contracts/import-mkt-db", {
    method: "POST",
    body: JSON.stringify(predictionContractSnapshotMktDbPayload()),
  });
  state.predictionContractMktDbPreflight = response;
  await refresh();
  state.predictionContractMktDbPreflight = response;
  renderPredictionContractMktDbPreflight();
  return response;
}

function predictionContractSnapshotMktDbPayload() {
  return {
    db_path: inputValue("prediction-mkt-db-path") || "My-Krypt-Trader/.aurex-demo-userdata/data/krypt-trader.db",
    source: inputValue("prediction-mkt-db-source") || "my-krypt-trader",
    source_reference:
      inputValue("prediction-mkt-db-source-reference") ||
      "My-Krypt-Trader/.aurex-demo-userdata/data/krypt-trader.db::markets",
    status_filter: inputValue("prediction-mkt-db-status-filter") || "resolved",
    limit: Number(inputValue("prediction-mkt-db-limit") || 100),
    min_volume: nullableInputValue("prediction-mkt-db-min-volume"),
    require_settlement_value: Boolean(
      document.getElementById("prediction-mkt-db-require-settlement")?.checked,
    ),
  };
}

function predictionDemoMktDbCampaignPayload({ includeRunControls = false } = {}) {
  const dbImport = predictionContractSnapshotMktDbPayload();
  const batchPayload = predictionDemoBatchPayload();
  delete batchPayload.reviewed_preflight_hash;
  const payload = {
    db_import: dbImport,
    batch: {
      ...batchPayload,
      source: dbImport.source,
      source_reference: dbImport.source_reference,
      require_imported_snapshot: true,
      require_settlement_value: true,
      skip_existing: true,
    },
  };
  if (includeRunControls) {
    payload.acknowledge_side_sensitivity = Boolean(
      document.getElementById("prediction-mkt-db-ack-side-sensitivity")?.checked,
    );
    payload.side_selection_rationale = nullableInputValue("prediction-mkt-db-side-rationale");
    payload.reviewed_manifest_hash = state.predictionDemoMktDbCampaignManifest?.manifest_hash || null;
  }
  return payload;
}

async function preflightPredictionDemoMktDbCampaign() {
  const response = await api("/prediction-market/paper/demo-mkt-db-campaign-preflight", {
    method: "POST",
    body: JSON.stringify(predictionDemoMktDbCampaignPayload()),
  });
  state.predictionDemoMktDbCampaignPreflight = response;
  state.predictionDemoMktDbCampaignManifest = null;
  state.predictionDemoMktDbCampaign = null;
  state.predictionDemoBatchPreflight = response.batch_preflight;
  state.predictionDemoBatch = null;
  renderPredictionMktDbCampaignManifest();
  renderPredictionMktDbCampaign();
  renderPredictionDemoBatch();
  return response;
}

async function checkPredictionDemoMktDbCampaignReadiness() {
  const response = await api("/prediction-market/paper/demo-mkt-db-campaign-readiness", {
    method: "POST",
    body: JSON.stringify(predictionDemoMktDbCampaignPayload({ includeRunControls: true })),
  });
  state.predictionDemoMktDbCampaignReadiness = response;
  state.predictionDemoMktDbCampaignManifest = null;
  state.predictionContractMktDbReadiness = response.data_readiness;
  state.predictionDemoMktDbCampaignPreflight = response.campaign_preflight || null;
  state.predictionDemoBatchPreflight = response.campaign_preflight?.batch_preflight || null;
  renderPredictionMktDbCampaignReadiness();
  renderPredictionMktDbCampaignManifest();
  renderPredictionContractMktDbReadiness();
  renderPredictionMktDbCampaign();
  renderPredictionDemoBatch();
  return response;
}

async function buildPredictionDemoMktDbCampaignManifest() {
  const response = await api("/prediction-market/paper/demo-mkt-db-campaign-manifest", {
    method: "POST",
    body: JSON.stringify(predictionDemoMktDbCampaignPayload({ includeRunControls: true })),
  });
  state.predictionDemoMktDbCampaignManifest = response;
  state.predictionDemoMktDbCampaignReadiness = response.readiness || null;
  state.predictionContractMktDbReadiness = response.readiness?.data_readiness || null;
  state.predictionDemoMktDbCampaignPreflight = response.readiness?.campaign_preflight || null;
  state.predictionDemoBatchPreflight = response.readiness?.campaign_preflight?.batch_preflight || null;
  state.predictionDemoMktDbCampaign = null;
  renderPredictionMktDbCampaignReadiness();
  renderPredictionMktDbCampaignManifest();
  renderPredictionContractMktDbReadiness();
  renderPredictionMktDbCampaign();
  renderPredictionDemoBatch();
  return response;
}

async function runPredictionDemoMktDbCampaign() {
  const response = await api("/prediction-market/paper/demo-mkt-db-campaign-run", {
    method: "POST",
    body: JSON.stringify(predictionDemoMktDbCampaignPayload({ includeRunControls: true })),
  });
  state.predictionDemoMktDbCampaign = response;
  state.predictionDemoBatch = response.batch;
  await refresh();
  state.predictionDemoMktDbCampaign = response;
  state.predictionDemoBatch = response.batch;
  renderPredictionMktDbCampaign();
  renderPredictionDemoBatch();
  return response;
}

async function runPredictionDemo() {
  const baseKey = inputValue("prediction-idempotency-key") || "ui-guided-demo";
  const response = await api("/prediction-market/paper/demo-run", {
    method: "POST",
    body: JSON.stringify({
      contract_id: nullableInputValue("prediction-contract-id"),
      strategy: inputValue("prediction-strategy"),
      side: inputValue("prediction-side") || "YES",
      quantity: inputValue("prediction-quantity") || "1",
      limit_price: nullableInputValue("prediction-limit-price"),
      available_quantity: nullableInputValue("prediction-available-quantity"),
      execution_price: nullableInputValue("prediction-execution-price"),
      latency_ms: Number(inputValue("prediction-latency-ms") || 0),
      settlement_value: nullableInputValue("prediction-settlement-value"),
      idempotency_key: `${baseKey}-${Date.now()}`.slice(0, 128),
      risk_limits: predictionExecutionRiskLimitsPayload(),
    }),
  });
  const intentInput = document.getElementById("prediction-intent-id");
  if (intentInput && response.intent?.id) intentInput.value = response.intent.id;
  const positionInput = document.getElementById("prediction-position-id");
  if (positionInput && response.position?.id) positionInput.value = response.position.id;
  await refresh();
  return response;
}

function predictionDemoBatchPayload() {
  return {
    strategy: inputValue("prediction-strategy"),
    side: inputValue("prediction-side") || "YES",
    quantity: inputValue("prediction-quantity") || "1",
    limit_price: nullableInputValue("prediction-limit-price"),
    available_quantity: nullableInputValue("prediction-available-quantity"),
    latency_ms: Number(inputValue("prediction-latency-ms") || 0),
    max_records: Number(inputValue("prediction-batch-max-records") || 5),
    source: nullableInputValue("prediction-csv-source"),
    require_imported_snapshot: true,
    require_settlement_value: true,
    skip_existing: true,
    idempotency_prefix: `ui-demo-batch-${Date.now()}`.slice(0, 64),
    reviewed_preflight_hash: state.predictionDemoBatchPreflight?.preflight_hash || null,
    risk_limits: predictionExecutionRiskLimitsPayload(),
  };
}

async function preflightPredictionDemoBatch() {
  state.predictionDemoBatchPreflight = await api("/prediction-market/paper/demo-batch-preflight", {
    method: "POST",
    body: JSON.stringify(predictionDemoBatchPayload()),
  });
  state.predictionDemoBatch = null;
  renderPredictionDemoBatch();
  return state.predictionDemoBatchPreflight;
}

async function runPredictionDemoBatch() {
  const response = await api("/prediction-market/paper/demo-batch-run", {
    method: "POST",
    body: JSON.stringify(predictionDemoBatchPayload()),
  });
  state.predictionDemoBatch = response;
  await refresh();
  state.predictionDemoBatch = response;
  renderPredictionDemoBatch();
  return response;
}

async function registerResearchCandidate() {
  const candidate = await api("/strategies/research-candidates", {
    method: "POST",
    body: JSON.stringify(researchCandidatePayload()),
  });
  state.selectedResearchCandidateId = candidate.id;
  await refresh();
  return candidate;
}

async function recordResearchObservation() {
  const observation = await api("/strategies/research-candidates/observations", {
    method: "POST",
    body: JSON.stringify(researchObservationPayload()),
  });
  state.selectedResearchCandidateId = observation.candidate_id;
  await refresh();
  return observation;
}

async function checkMktResearchIntakeReadiness() {
  const result = await api("/strategies/research-candidates/mkt-intake-readiness", {
    method: "POST",
    body: JSON.stringify(mktResearchImportPayload()),
  });
  state.researchMktIntakeReadiness = result;
  state.researchMktImport = result.preflight || null;
  renderMktResearchIntakeReadiness();
  renderMktResearchImport();
  return result;
}

async function buildMktResearchIntakeRunbook() {
  const result = await api("/strategies/research-candidates/mkt-intake-runbook", {
    method: "POST",
    body: JSON.stringify(mktResearchImportPayload()),
  });
  state.researchMktRunbook = result;
  await checkMktResearchIntakeReadiness();
  state.researchMktRunbook = result;
  renderMktResearchRunbook();
  return result;
}

async function preflightMktResearchCandidates() {
  const result = await api("/strategies/research-candidates/preflight-mkt", {
    method: "POST",
    body: JSON.stringify(mktResearchImportPayload()),
  });
  state.researchMktImport = result;
  renderMktResearchImport();
  return result;
}

async function importMktResearchCandidates() {
  const result = await api("/strategies/research-candidates/import-mkt", {
    method: "POST",
    body: JSON.stringify(mktResearchImportPayload()),
  });
  state.researchMktImport = result;
  state.selectedResearchCandidateId = result.candidate_ids?.[0] || state.selectedResearchCandidateId;
  await refresh();
  state.researchMktImport = result;
  renderMktResearchImport();
  return result;
}

async function runResearchCandidateBacktest() {
  const candidateKey = inputValue("research-candidate-key");
  const candidate =
    ensureSelectedResearchCandidate() ||
    state.researchCandidates.find((item) => item.candidate_key === candidateKey) ||
    state.researchCandidates[0];
  if (!candidate?.id) throw new Error("Record a research candidate before running the gate.");
  const result = await api(
    `/strategies/research-candidates/${encodeURIComponent(candidate.id)}/backtest`,
    {
      method: "POST",
      body: JSON.stringify(researchBacktestPayload()),
    },
  );
  state.selectedResearchCandidateId = result.candidate_id;
  await refresh();
  return result;
}

function researchCandidatePayload() {
  return {
    source: "MY_KRYPT_TRADER",
    candidate_key: inputValue("research-candidate-key"),
    strategy: inputValue("research-strategy"),
    display_name: inputValue("research-display-name"),
    hypothesis: inputValue("research-hypothesis"),
    status: "RESEARCH_ONLY",
    source_reference: "My-Krypt-Trader",
    raw_payload: { source: "aurex_dashboard" },
    normalized_payload: { trade_eligible: false },
  };
}

function researchObservationPayload() {
  return {
    candidate_key: inputValue("research-candidate-key"),
    source: "MY_KRYPT_TRADER",
    strategy: inputValue("research-strategy"),
    display_name: inputValue("research-display-name"),
    hypothesis: inputValue("research-hypothesis"),
    observation_type: inputValue("research-observation-type"),
    source_event_id: nullableInputValue("research-source-event-id"),
    symbol: nullableInputValue("research-symbol"),
    contract_ticker: nullableInputValue("research-contract-ticker"),
    side: nullableInputValue("research-side"),
    confidence: nullableInputValue("research-confidence"),
    implied_probability: nullableInputValue("research-implied-probability"),
    expected_edge: nullableInputValue("research-expected-edge"),
    observation_snapshot: {
      imported_as_research_candidate: true,
      trusted_profitable_strategy: false,
    },
    raw_payload: { source: "aurex_dashboard" },
  };
}

function mktResearchImportPayload() {
  return {
    db_path: inputValue("research-mkt-db-path") || "My-Krypt-Trader/.aurex-demo-userdata/data/krypt-trader.db",
    sources: ["whale", "momentum", "crypto15m"],
    limit_per_source: 500,
    include_resolved: true,
    include_unresolved: true,
    acknowledge_research_only_import: Boolean(
      document.getElementById("research-mkt-ack-research-only")?.checked,
    ),
  };
}

function researchBacktestPayload() {
  return {
    minimum_trades: 100,
    minimum_oos_trades: 30,
    minimum_oos_profit_factor: "1.15",
    maximum_oos_drawdown: "25",
    minimum_active_days: 15,
    maximum_single_day_share: "0.25",
    oos_fraction: "0.30",
    minimum_walk_forward_windows: 3,
    minimum_walk_forward_pass_rate: "0.67",
    require_known_regime: true,
    minimum_regime_groups: 1,
    minimum_regime_trades: 10,
    minimum_regime_pass_rate: "0.67",
    tested_variant_count: 1,
    maximum_tested_variants: 12,
    multiple_testing_profit_factor_step: "0.02",
    maximum_multiple_testing_profit_factor_penalty: "0.25",
    fee_rate: "0.07",
  };
}

async function createPredictionOrderIntent() {
  const payload = predictionOrderIntentPayload();
  const intent = await api("/prediction-market/paper/order-intents", {
    method: "POST",
    body: JSON.stringify(payload),
  });
  const input = document.getElementById("prediction-intent-id");
  if (input) input.value = intent.id;
  await refresh();
  return intent;
}

async function submitPredictionOrder() {
  const intentId = inputValue("prediction-intent-id") || state.predictionIntents[0]?.id;
  if (!intentId) throw new Error("Prediction intent ID is required.");
  const response = await api(
    `/prediction-market/paper/order-intents/${encodeURIComponent(intentId)}/submit`,
    {
      method: "POST",
      body: JSON.stringify({
        available_quantity: inputValue("prediction-available-quantity") || "0",
        latency_ms: Number(inputValue("prediction-latency-ms") || 0),
        execution_price: nullableInputValue("prediction-execution-price"),
        raw_payload: { source: "aurex_dashboard" },
      }),
    },
  );
  const positionInput = document.getElementById("prediction-position-id");
  if (positionInput && response.position?.id) positionInput.value = response.position.id;
  await refresh();
  return response;
}

async function cancelPredictionOrderIntent() {
  const intentId = inputValue("prediction-intent-id") || state.predictionIntents[0]?.id;
  if (!intentId) throw new Error("Prediction intent ID is required.");
  const intent = await api(
    `/prediction-market/paper/order-intents/${encodeURIComponent(intentId)}/cancel`,
    {
      method: "POST",
      body: JSON.stringify({ reason: "operator_manual_cancel" }),
    },
  );
  await refresh();
  return intent;
}

async function settlePredictionPosition() {
  const positionId = inputValue("prediction-position-id") || state.predictionPositions[0]?.id;
  if (!positionId) throw new Error("Prediction position ID is required.");
  const settlementValue = nullableInputValue("prediction-settlement-value");
  if (!settlementValue) throw new Error("Settlement value is required for manual settlement.");
  const settlement = await api(
    `/prediction-market/paper/positions/${encodeURIComponent(positionId)}/settle`,
    {
      method: "POST",
      body: JSON.stringify({
        settlement_value: settlementValue,
      }),
    },
  );
  await refresh();
  return settlement;
}

async function cancelStalePredictionOrders() {
  const result = await api("/prediction-market/paper/stale-orders/cancel", {
    method: "POST",
    body: "{}",
  });
  await refresh();
  return result;
}

async function runPredictionReconciliation() {
  const report = await api("/prediction-market/paper/reconciliation/run", {
    method: "POST",
    body: "{}",
  });
  await refresh();
  return report;
}

function predictionSnapshotPayload() {
  const expiration = nullableInputValue("prediction-expiration") || defaultPredictionExpiration();
  return {
    venue: "KALSHI",
    event_ticker: inputValue("prediction-event-ticker"),
    market_title: inputValue("prediction-market-title"),
    contract_ticker: inputValue("prediction-contract-ticker"),
    contract_title: inputValue("prediction-contract-title"),
    category: nullableInputValue("prediction-category"),
    status: "OPEN",
    yes_bid_price: nullableInputValue("prediction-yes-bid"),
    yes_ask_price: nullableInputValue("prediction-yes-ask"),
    no_bid_price: nullableInputValue("prediction-no-bid"),
    no_ask_price: nullableInputValue("prediction-no-ask"),
    closes_at: expiration,
    expiration_at: expiration,
    raw_payload: { source: "aurex_dashboard" },
  };
}

function predictionOrderIntentPayload() {
  const contractId = inputValue("prediction-contract-id") || state.predictionContracts[0]?.id;
  if (!contractId) throw new Error("Prediction contract ID is required.");
  return {
    contract_id: contractId,
    strategy: inputValue("prediction-strategy"),
    side: inputValue("prediction-side") || "YES",
    action: inputValue("prediction-action") || "BUY",
    quantity: inputValue("prediction-quantity"),
    limit_price: inputValue("prediction-limit-price"),
    idempotency_key: inputValue("prediction-idempotency-key"),
    expires_at: new Date(Date.now() + 2 * 60 * 1000).toISOString(),
    risk_limits: predictionExecutionRiskLimitsPayload(),
  };
}

function predictionExecutionRiskLimitsPayload() {
  return {
    max_order_cost: inputValue("prediction-max-order-cost") || "50",
    max_contract_exposure: inputValue("prediction-max-contract-exposure") || "50",
    max_open_positions: 25,
    max_quote_age_seconds: nullableInputValue("prediction-max-quote-age-seconds"),
    max_spread: nullableInputValue("prediction-max-spread"),
    max_latency_ms: nullableInputValue("prediction-max-latency-ms"),
    max_slippage: nullableInputValue("prediction-max-slippage"),
  };
}

function defaultPredictionExpiration() {
  return new Date(Date.now() + 60 * 60 * 1000).toISOString();
}

async function recordLiveApproval() {
  await api("/live/deployment/approvals", {
    method: "POST",
    body: JSON.stringify({
      approval_type: inputValue("approval-record-type") || "BROKER",
      approved: Boolean(document.getElementById("approval-record-approved")?.checked),
      approver: inputValue("approval-record-approver"),
      evidence_reference: inputValue("approval-record-evidence") || null,
      notes: inputValue("approval-record-notes") || null,
    }),
  });
  await refresh();
}

async function runProfitMilestone() {
  await api("/live/deployment/profit-milestone/run", { method: "POST", body: "{}" });
  await refresh();
}

async function runStrategyEvidenceReview() {
  await api("/live/deployment/evidence-review/run", { method: "POST", body: "{}" });
  await refresh();
}

async function activationAudit() {
  state.activationAttempt = await api("/live/deployment/activation-attempt", {
    method: "POST",
    body: "{}",
  });
  await refresh();
}

bindAction("refresh-button", () => refresh({ announce: true }));
bindAction("native-start-button", () => controlNativeSupervisor("start"), { title: "Requested", tone: "info", message: "Supervisor start requested; feed readiness remains unverified." });
bindAction("native-stop-button", () => controlNativeSupervisor("stop"), { title: "Requested", tone: "info", message: "Cooperative stop requested; an in-flight step may still be finishing." });
bindAction("kill-switch-button", enableKillSwitch, "Kill switch enabled.");
bindAction("reset-kill-switch-button", resetKillSwitch, "Kill switch reset.");
bindAction("analyst-scan-button", runAnalystScan, "Analyst scan complete.");
bindAction("broker-check-button", runBrokerChecks, "Broker checks refreshed.");
bindAction("broker-stop-button", brokerEmergencyStop, "Broker emergency stop recorded.");
bindAction("operator-profile-reset-button", resetOperatorProfile, "Operator input cleared.");
bindAction(
  "operator-profile-preflight-button",
  preflightOperatorProfile,
  (result) => ({
    message: `Operator profile preflight: ${result?.status || "checked"}.`,
    tone: result?.status === "PASS" ? "success" : "warning",
    title: result?.status === "PASS" ? "Preflight passed" : "Preflight blocked",
  }),
);
bindAction(
  "operator-profile-download-button",
  downloadOperatorProfileInput,
  "Credential-free operator input downloaded.",
);
bindAction(
  "operator-profile-copy-freeze-button",
  copyOperatorProfileFreezeCommand,
  "Independent freeze command copied.",
);
bindAction("deployment-check-button", runDeploymentChecks, "Deployment gates refreshed.");
bindAction("deployment-review-button", createDailyReview, "Daily review recorded.");
bindAction("deployment-evidence-button", runPaperEvidence, "Paper evidence report generated.");
bindAction("statement-preflight-button", preflightBrokerStatementCsv, "Statement preflight complete.");
bindAction("statement-reconcile-button", reconcileBrokerStatementCsv, "Statement reconciliation complete.");
bindAction("backtest-setup-button", loadBacktestStrategySetup, "Backtest setup loaded.");
bindAction(
  "backtest-ohlcv-preflight-button",
  preflightBacktestOhlcv,
  (result) => `Historical data preflight: ${result?.status || "checked"}.`,
);
bindAction(
  "backtest-ohlcv-import-button",
  importBacktestOhlcv,
  (result) =>
    result?.reused_existing
      ? "Existing immutable historical dataset selected."
      : "Immutable historical dataset imported.",
);
bindAction(
  "backtest-reference-button",
  preflightReferenceReplay,
  (result) => `Comparison-only reference replay: ${result?.status || "checked"}.`,
);
bindAction(
  "backtest-reference-record-button",
  recordReferenceReplay,
  (result) => result?.reused_existing
    ? "Existing immutable replay evidence selected."
    : "Immutable replay evidence recorded.",
);
bindAction(
  "backtest-reference-validation-button",
  preflightReferenceReplayValidation,
  (result) => `Frozen validation: ${result?.status || "checked"}.`,
);
bindAction(
  "backtest-reference-validation-record-button",
  recordReferenceReplayValidation,
  (result) => result?.reused_existing
    ? "Existing immutable validation selected."
    : "Immutable replay validation recorded.",
);
bindAction(
  "backtest-parity-lineage-button",
  preflightBacktestParityExportManifest,
  (result) => ({
    message: `Paired-export lineage: ${result?.status || "checked"}.`,
    tone: result?.status === "READY" ? "success" : "warning",
    title: result?.status === "READY" ? "Lineage ready" : "Lineage blocked",
  }),
);
bindAction(
  "backtest-parity-preflight-button",
  preflightBacktestParity,
  (result) => ({
    message: `TradingView parity: ${result?.status || "checked"}.`,
    tone: result?.status === "PASSED" ? "success" : "warning",
    title: result?.status === "PASSED" ? "Parity passed" : "Parity not passed",
  }),
);
bindAction(
  "backtest-parity-record-button",
  recordBacktestParity,
  (result) => result?.reused_existing ? "Existing parity evidence selected." : "Immutable parity evidence recorded.",
);
bindAction(
  "backtest-window-plan-button",
  planBacktestWalkForwardWindows,
  "Outcome-blind walk-forward folds planned.",
);
bindAction(
  "backtest-protocol-button",
  registerBacktestProtocol,
  "Immutable backtest protocol registered.",
);
bindAction(
  "backtest-run-manifest-button",
  loadBacktestRunManifest,
  (result) => `Frozen TradingView run: ${result?.status || "checked"}.`,
);
bindAction(
  "backtest-run-package-button",
  loadBacktestTradingViewRunPackage,
  (result) => `TradingView run package: ${result?.status || "checked"}.`,
);
bindAction("backtest-copy-pine-button", copyBacktestPineSource, "Exact Pine source copied.");
bindAction("backtest-copy-setup-button", copyBacktestTradingViewSetup, "Frozen setup copied.");
bindAction("backtest-template-button", loadBacktestReportTemplate, "Backtest template loaded.");
bindAction("backtest-preflight-button", preflightBacktestReportCsv, "Backtest preflight complete.");
bindAction("backtest-import-button", importBacktestReportCsv, "Backtest evidence imported.");
document.getElementById("operator-profile-form")?.addEventListener(
  "input",
  invalidateOperatorProfilePreflight,
);
document.getElementById("operator-profile-product-scope")?.addEventListener(
  "change",
  () => {
    updateOperatorProductScope();
    invalidateOperatorProfilePreflight();
  },
);
document.getElementById("backtest-csv-file")?.addEventListener("change", (event) => {
  loadBacktestCsvFile(event).catch((error) => {
    showNotification(error.message || "CSV loading failed.", {
      tone: "error",
      title: "CSV rejected",
    });
  });
});
document.getElementById("backtest-ohlcv-file")?.addEventListener("change", (event) => {
  loadBacktestOhlcvFile(event).catch((error) => {
    showNotification(error.message || "OHLCV CSV loading failed.", {
      tone: "error",
      title: "Historical data rejected",
    });
  });
});
document.getElementById("backtest-ohlcv-manifest-file")?.addEventListener("change", (event) => {
  loadBacktestOhlcvManifestFile(event).catch((error) => {
    showNotification(error.message || "Source manifest loading failed.", {
      tone: "error",
      title: "Source manifest rejected",
    });
  });
});
[
  "backtest-parity-dataset-id",
  "backtest-parity-chart-dataset-id",
  "backtest-parity-report-id",
].forEach((id) => {
  document.getElementById(id)?.addEventListener("change", () => {
    state.backtestParityExportManifest = null;
    state.backtestParityPreflight = null;
    renderBacktestParity();
  });
});
document.getElementById("backtest-parity-export-attestation")?.addEventListener(
  "change",
  () => {
    state.backtestParityExportManifest = null;
    state.backtestParityPreflight = null;
    renderBacktestParity();
  },
);
[
  "backtest-parity-tick-size",
  "backtest-parity-point-value",
  "backtest-parity-minimum-contract",
  "backtest-parity-entry-seconds",
  "backtest-parity-exit-seconds",
  "backtest-parity-price-ticks",
  "backtest-parity-quantity-relative",
  "backtest-parity-money-absolute",
].forEach((id) => {
  document.getElementById(id)?.addEventListener("change", () => {
    state.backtestParityPreflight = null;
    renderBacktestParity();
  });
});
document.getElementById("backtest-protocol-id")?.addEventListener("change", () => {
  state.backtestRunManifest = null;
  state.backtestRunPackage = null;
  state.backtestPreflight = null;
  renderBacktestProtocols();
  renderBacktestPreflight();
});
bindAction("signal-alert-setup-button", loadTradingViewAlertSetup, "TradingView alert setup loaded.");
bindAction("signal-preflight-button", preflightTradingViewSignal, (result) =>
  result?.would_execute_paper ? "TradingView payload preflight passed." : "TradingView payload preflight blocked.",
);
bindAction("research-candidate-button", registerResearchCandidate, "Research candidate recorded.");
bindAction("research-observation-button", recordResearchObservation, "Research observation recorded.");
bindAction(
  "research-mkt-readiness-button",
  checkMktResearchIntakeReadiness,
  "MKT research intake readiness checked.",
);
bindAction(
  "research-mkt-runbook-button",
  buildMktResearchIntakeRunbook,
  (result) => `MKT research runbook: ${result?.status || "built"}.`,
);
bindAction(
  "research-mkt-preflight-button",
  preflightMktResearchCandidates,
  "MKT research preflight checked.",
);
bindAction("research-mkt-import-button", importMktResearchCandidates, "MKT research imported.");
bindAction("research-backtest-button", runResearchCandidateBacktest, "Research gate evaluated.");
bindAction("prediction-snapshot-button", createPredictionSnapshot, "Prediction contract snapshot recorded.");
bindAction(
  "prediction-csv-template-button",
  loadPredictionContractSnapshotTemplate,
  "Prediction snapshot template loaded.",
);
bindAction(
  "prediction-csv-preflight-button",
  preflightPredictionContractSnapshotCsv,
  "Prediction snapshot preflight complete.",
);
bindAction(
  "prediction-csv-import-button",
  importPredictionContractSnapshotCsv,
  "Prediction snapshots imported.",
);
bindAction(
  "prediction-mkt-donor-runbook-button",
  buildPredictionContractSnapshotMktDonorRunbook,
  (result) => `MKT donor runbook: ${result?.status || "built"}.`,
);
bindAction(
  "prediction-mkt-donor-bootstrap-button",
  bootstrapPredictionContractSnapshotMktDonor,
  (result) => `MKT demo bootstrap: ${result?.status || "prepared"}.`,
);
bindAction(
  "prediction-mkt-donor-launch-preflight-button",
  preflightPredictionContractSnapshotMktDonorLaunch,
  (result) => `MKT launch preflight: ${result?.status || "checked"}.`,
);
bindAction(
  "prediction-mkt-donor-copy-launch-command-button",
  copyPredictionMktDonorLaunchCommand,
  "MKT launch command copied.",
);
bindAction(
  "prediction-mkt-donor-collection-status-button",
  checkPredictionContractSnapshotMktDonorCollectionStatus,
  (result) => `MKT collection status: ${result?.status || "checked"}.`,
);
bindAction(
  "prediction-mkt-runtime-safety-button",
  checkPredictionContractSnapshotMktRuntimeSafety,
  (result) => `MKT runtime safety: ${result?.status || "checked"}.`,
);
bindAction(
  "prediction-mkt-donor-readiness-button",
  checkPredictionContractSnapshotMktDonorReadiness,
  (result) => `MKT donor readiness: ${result?.status || "checked"}.`,
);
bindAction(
  "prediction-mkt-db-discover-button",
  discoverPredictionContractSnapshotMktDbs,
  (result) => `MKT DB discovery: ${result?.ready_count || 0} ready of ${result?.candidate_count || 0}.`,
);
bindAction(
  "prediction-mkt-db-readiness-button",
  checkPredictionContractSnapshotMktDbReadiness,
  (result) => `MKT DB readiness: ${result?.status || "checked"}.`,
);
bindAction(
  "prediction-mkt-db-inventory-button",
  inspectPredictionContractSnapshotMktDbInventory,
  (result) => `MKT DB inventory: ${result?.status || "checked"}.`,
);
bindAction(
  "prediction-mkt-db-preflight-button",
  preflightPredictionContractSnapshotMktDb,
  (result) => `MKT DB preflight: ${result?.status || "completed"}.`,
);
bindAction(
  "prediction-mkt-db-import-button",
  importPredictionContractSnapshotMktDb,
  (result) => `MKT DB import: ${result?.imported_count || 0} imported.`,
);
bindAction(
  "prediction-mkt-db-campaign-readiness-button",
  checkPredictionDemoMktDbCampaignReadiness,
  (result) => `MKT DB campaign readiness: ${result?.status || "checked"}.`,
);
bindAction(
  "prediction-mkt-db-campaign-manifest-button",
  buildPredictionDemoMktDbCampaignManifest,
  (result) => `MKT DB campaign manifest: ${result?.status || "built"}.`,
);
bindAction(
  "prediction-mkt-db-campaign-preflight-button",
  preflightPredictionDemoMktDbCampaign,
  (result) => `MKT DB campaign preflight: ${result?.status || "completed"}.`,
);
bindAction(
  "prediction-mkt-db-campaign-run-button",
  runPredictionDemoMktDbCampaign,
  (result) =>
    result?.status === "CAMPAIGN_REPLAY_COMPLETED"
      ? `MKT DB campaign replay completed: ${result.batch?.completed_records || 0} record(s).`
      : `MKT DB campaign replay: ${result?.status || "completed"}.`,
);
bindAction(
  "prediction-demo-run-button",
  runPredictionDemo,
  (result) =>
    result?.status === "PAPER_DEMO_VERIFIED"
      ? "Prediction paper demo lifecycle verified."
      : `Prediction demo run: ${result?.status || "completed"}.`,
);
bindAction(
  "prediction-demo-batch-preflight-button",
  preflightPredictionDemoBatch,
  (result) =>
    result?.status === "READY" || result?.status === "READY_WITH_SKIPS"
      ? `Prediction batch preflight: ${result.eligible_records || 0} ready.`
      : `Prediction batch preflight: ${result?.status || "completed"}.`,
);
bindAction(
  "prediction-demo-batch-button",
  runPredictionDemoBatch,
  (result) =>
    result?.status === "BATCH_COMPLETED"
      ? `Prediction batch replay completed: ${result.completed_records || 0} record(s).`
      : `Prediction batch replay: ${result?.status || "completed"}.`,
);
bindAction(
  "prediction-intent-button",
  createPredictionOrderIntent,
  (intent) =>
    intent?.status === "REJECTED"
      ? "Prediction paper intent rejected; evidence recorded."
      : "Prediction paper intent recorded.",
);
bindAction("prediction-submit-button", submitPredictionOrder, "Prediction paper order submitted.");
bindAction("prediction-cancel-button", cancelPredictionOrderIntent, "Prediction paper order cancelled.");
bindAction("prediction-settle-button", settlePredictionPosition, "Prediction position settled.");
bindAction("prediction-expire-button", cancelStalePredictionOrders, "Stale prediction orders expired.");
bindAction("prediction-reconcile-button", runPredictionReconciliation, "Prediction ledger reconciled.");
bindAction(
  "approval-packet-button",
  () => submitApprovalPacket(approvalPacketPayload()),
  "Approval packet recorded.",
);
bindAction("approval-record-button", recordLiveApproval, "Approval decision recorded.");
bindAction("profit-milestone-button", runProfitMilestone, "Profit milestone check complete.");
bindAction("evidence-review-button", runStrategyEvidenceReview, "Strategy evidence review complete.");
bindAction("deployment-audit-button", activationAudit, "Activation audit complete.");
bindAction("evidence-template-button", loadPaperEvidenceTemplate, "Paper evidence template loaded.");
bindAction("evidence-preflight-button", preflightPaperEvidenceCsv, "Paper evidence preflight complete.");
bindAction("evidence-import-button", importPaperEvidenceCsv, "Paper evidence imported.");
document.getElementById("strategies-body")?.addEventListener("click", (event) => {
  const button = event.target.closest("button[data-strategy]");
  if (!button) return;
  const strategy = button.dataset.strategy;
  const isEnabled = button.dataset.enabled === "true";
  runUiAction(
    button,
    () => toggleStrategy(strategy, isEnabled),
    `${strategy} ${isEnabled ? "disabled" : "enabled"}.`,
  );
});
function bindResearchInspect(tableId) {
  document.getElementById(tableId)?.addEventListener("click", (event) => {
    const button = event.target.closest("button[data-research-candidate-id]");
    if (!button) return;
    runUiAction(
      button,
      async () => {
        state.selectedResearchCandidateId = button.dataset.researchCandidateId;
        await refreshResearchEvidence();
        renderResearchCandidates();
        return state.researchEvidence;
      },
      "Research evidence loaded.",
    );
  });
}

bindResearchInspect("research-candidates-body");
bindResearchInspect("research-readiness-body");
document.getElementById("prediction-mkt-db-discovery-body")?.addEventListener("click", (event) => {
  const button = event.target.closest("button[data-mkt-db-candidate-index]");
  if (!button) return;
  runUiAction(
    button,
    () => selectPredictionContractSnapshotMktDbCandidate(button.dataset.mktDbCandidateIndex),
    (candidate) =>
      candidate?.readiness?.data_ready
        ? "Ready MKT DB candidate selected."
        : "Blocked MKT DB candidate loaded for inspection.",
  );
});
document.getElementById("prediction-strategy")?.addEventListener("input", renderPredictionPaperIntentGate);

initializeNavigation();
refresh().catch((error) => {
  renderHealth();
  showNotification(error.message, { tone: "error", title: "Connection failed", duration: 12000 });
});
