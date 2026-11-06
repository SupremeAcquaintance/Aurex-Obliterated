/* Local disposable-copy rehearsal. Never enables strategies or sends orders. */
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const { parseArgs } = require("node:util");
const { chromium } = require("playwright");

async function main() {
  const { values } = parseArgs({ options: {
    "base-url": { type: "string" },
    "expected-instance": { type: "string" },
    "report-directory": { type: "string" },
    "browser-channel": { type: "string", default: "msedge" },
    "allow-disposable-controls": { type: "boolean", default: false },
    "exercise-managed-controls": { type: "boolean", default: false },
  } });
  const url = new URL(values["base-url"]);
  assert.equal(url.hostname, "127.0.0.1");
  assert.equal(url.protocol, "http:");
  assert.match(values["expected-instance"], /^[0-9a-f]{32}$/);
  assert.equal(values["allow-disposable-controls"], true, "explicit disposable-copy authority required");
  const output = path.resolve(values["report-directory"]);
  fs.mkdirSync(output, { recursive: false });
  const result = { status: "IN_PROGRESS", live_authority: false, fixture_failures_are_qualification: false, checks: [] };
  let browser;
  try {
    browser = await chromium.launch({ headless: true, channel: values["browser-channel"] });
    const context = await browser.newContext({ viewport: { width: 1440, height: 1000 } });
    await context.route("**/*", (route) => new URL(route.request().url()).origin === url.origin ? route.continue() : route.abort());
    const page = await context.newPage();
    const errors = [];
    const failedResponses = [];
    page.on("pageerror", (error) => errors.push(error.message));
    page.on("response", (response) => { if (response.status() >= 400) failedResponses.push({ url: new URL(response.url()).pathname, status: response.status() }); });
    const runtime = await context.request.get(`${url.origin}/system/private-runtime`);
    assert.equal(runtime.status(), 200);
    const status = await runtime.json();
    assert.equal(status.instance_id, values["expected-instance"]);
    assert.equal(status.live_authority, false);
    assert.equal(status.starts_native_supervisor, false);
    result.instance_id = status.instance_id;
    const readinessResponse = await context.request.get(`${url.origin}/system/readiness`);
    assert.equal(readinessResponse.status(), 200);
    const readiness = await readinessResponse.json();
    assert.equal(readiness.source_integrity_verified, true);
    assert.equal(readiness.research_checkpoint_verified, true);
    assert.equal(readiness.live_ready, false);
    assert.equal(readiness.production_ready, false);
    result.checks.push("exact_source_readiness_verified_no_live_authority");

    async function settled() {
      await page.waitForFunction(() => {
        const value = document.getElementById("last-sync-state")?.textContent || "";
        return value.startsWith("Synced ") || value.includes("degraded /");
      }, null, { timeout: 120000 });
      assert.deepEqual(errors, []);
    }
    async function refresh() {
      await page.getByRole("button", { name: "Refresh", exact: true }).click();
      await page.waitForFunction(() => document.getElementById("refresh-button")?.getAttribute("aria-busy") !== "true", null, { timeout: 120000 });
      await settled();
    }
    async function layout(label) {
      const dimensions = await page.evaluate(() => ({ width: innerWidth, scroll: document.documentElement.scrollWidth }));
      assert.ok(dimensions.scroll <= dimensions.width + 1, `${label} horizontal overflow: ${JSON.stringify(dimensions)}`);
    }
    await page.goto(`${url.origin}/dashboard`, { waitUntil: "domcontentloaded" });
    await settled();
    assert.match(await page.locator("#last-sync-state").textContent(), /^Synced /);
    assert.equal(await page.locator("#runtime-service").innerText(), "Private / loopback only");
    const managed = values["exercise-managed-controls"];
    assert.equal(await page.locator("#runtime-supervisor").innerText(), managed ? "IDLE" : "UNCONFIGURED");
    assert.equal(await page.locator("#native-start-button").isEnabled(), managed);
    assert.equal(await page.locator("#native-stop-button").isDisabled(), true);
    assert.equal(await page.locator("#runtime-acceptance").innerText(), "Not accepted");
    assert.equal(await page.locator("#preview-line-main").getAttribute("d"), "");
    assert.equal(await page.locator("#preview-chart-empty").isVisible(), true);
    assert.deepEqual(failedResponses, []);
    result.checks.push("real_private_service_initial_refresh", "truthful_runtime_and_empty_equity");
    if (managed) {
      const initial = await (await context.request.get(`${url.origin}/system/native-supervisor`)).json();
      assert.equal(initial.mode, "OBSERVE", "only the no-entry observer is rehearsed");
      assert.equal(initial.live_authority, false);
      assert.equal(initial.forward_qualifying, false);
      let previousRun = null;
      for (const width of [1440, 390]) {
        await page.setViewportSize({ width, height: width === 390 ? 844 : 1000 });
        await page.locator("#native-start-button").click();
        await page.waitForFunction(() => document.getElementById("runtime-supervisor")?.textContent === "PROCESS_RUNNING", null, { timeout: 60000 });
        assert.equal(await page.locator("#native-start-button").isDisabled(), true);
        assert.equal(await page.locator("#native-stop-button").isEnabled(), true);
        assert.match(await page.locator("#native-process").textContent(), /feed unverified/);
        const running = await (await context.request.get(`${url.origin}/system/native-supervisor`)).json();
        assert.equal(running.process_alive, true);
        assert.notEqual(running.run_id, previousRun);
        previousRun = running.run_id;
        await layout(`${width} supervisor running`);
        await page.locator(".runtime-status").screenshot({ path: path.join(output, `supervisor-running-${width}.png`), animations: "disabled" });
        await page.locator("#native-stop-button").click();
        await page.waitForFunction(() => document.getElementById("runtime-supervisor")?.textContent === "STOPPED", null, { timeout: 120000 });
        const stopped = await (await context.request.get(`${url.origin}/system/native-supervisor`)).json();
        assert.equal(stopped.process_alive, false);
        assert.equal(stopped.journal_verified, true);
        assert.equal(stopped.forced_shutdown, false);
        assert.equal(stopped.last_result.processed_bars, 0);
        assert.equal(stopped.forward_qualifying, false);
        assert.equal(await page.locator("#native-start-button").isEnabled(), true);
        assert.equal(await page.locator("#native-stop-button").isDisabled(), true);
      }
      await page.setViewportSize({ width: 1440, height: 1000 });
      result.checks.push("owned_no_data_fixture_start_stop_restart_desktop_mobile");
      result.native_market_acquisition = "TEST_SUBSTITUTE_NOT_FORWARD_EVIDENCE";
    }
    await layout("desktop command");
    await page.screenshot({ path: path.join(output, "command-desktop.png"), animations: "disabled" });

    const views = await page.locator("[data-view-target]").evaluateAll((buttons) => buttons.map((button) => button.dataset.viewTarget));
    for (const viewport of [{ width: 1440, height: 1000 }, { width: 390, height: 844 }]) {
      await page.setViewportSize(viewport);
      for (const view of views) {
        await page.locator(`[data-view-target="${view}"]`).click();
        const active = await page.locator("[data-dashboard-view]").evaluateAll((sections) => sections.filter((section) => !section.hidden).map((section) => section.dataset.dashboardView));
        assert.ok(active.length > 0 && active.every((name) => name === view), `${view}: inactive views visible`);
        assert.equal(await page.locator(`[data-view-target="${view}"]`).getAttribute("aria-current"), "page");
        await layout(`${viewport.width} ${view}`);
      }
    }
    await page.locator('[data-view-target="command"]').click();
    await page.screenshot({ path: path.join(output, "command-mobile.png"), animations: "disabled" });
    result.checks.push("all_views_isolated_desktop_mobile", "no_document_horizontal_overflow");
    await page.setViewportSize({ width: 1440, height: 1000 });

    await page.getByRole("button", { name: "Enable kill switch", exact: true }).click();
    await page.waitForFunction(() => document.getElementById("metric-kill-switch")?.textContent === "Enabled", null, { timeout: 120000 });
    await page.waitForFunction(() => document.getElementById("kill-switch-button")?.getAttribute("aria-busy") !== "true", null, { timeout: 120000 });
    const risk = await context.request.get(`${url.origin}/risk/status`);
    assert.equal((await risk.json()).kill_switch_enabled, true);
    assert.equal(await page.locator("#reset-kill-switch-button").isEnabled(), true);
    result.checks.push("disposable_copy_kill_switch_verified");

    const failuresBeforeFixture = failedResponses.length;
    for (const endpoint of ["/risk/status", "/system/readiness", "/system/private-runtime", "/system/native-supervisor", "/performance/equity-curve?limit=80"]) {
      await page.route(`${url.origin}${endpoint}`, (route) => route.fulfill({ status: 503, contentType: "application/json", body: JSON.stringify({ detail: "deliberate_rehearsal_failure" }) }));
    }
    await refresh();
    assert.equal(await page.locator("#metric-equity").innerText(), "Unknown");
    assert.equal(await page.locator("#metric-kill-switch").innerText(), "Unknown");
    assert.equal(await page.locator("#preview-risk-pill").textContent(), "Risk state unknown");
    assert.equal(await page.locator("#reset-kill-switch-button").isDisabled(), true);
    assert.equal(await page.locator("#runtime-state").innerText(), "NOT VERIFIED");
    assert.equal(await page.locator("#runtime-supervisor").innerText(), "Unknown");
    assert.equal(await page.locator("#native-start-button").isDisabled(), true);
    assert.equal(await page.locator("#native-stop-button").isDisabled(), true);
    assert.equal(await page.locator("#preview-line-main").getAttribute("d"), "");
    assert.equal(await page.locator("#preview-chart-empty").innerText(), "Equity data unavailable");
    assert.equal(await page.locator("#command-evidence-pine").innerText(), "NOT_CHECKED");
    await page.screenshot({ path: path.join(output, "degraded-desktop.png"), animations: "disabled" });
    result.checks.push("injected_failures_clear_safety_state_disable_reset");
    await page.unrouteAll({ behavior: "wait" });
    await refresh();
    assert.match(await page.locator("#last-sync-state").textContent(), /^Synced /);
    assert.equal(await page.locator("#metric-kill-switch").innerText(), "Enabled");
    assert.equal(await page.locator("#runtime-supervisor").innerText(), managed ? "STOPPED" : "UNCONFIGURED");
    assert.equal(await page.locator("#native-start-button").isEnabled(), managed);
    result.checks.push("real_backend_recovery_after_injected_failure");
    assert.deepEqual(errors, []);
    result.real_failed_responses_before_fixture = failedResponses.slice(0, failuresBeforeFixture);
    assert.deepEqual(result.real_failed_responses_before_fixture, []);
    result.injected_failure_response_count = failedResponses.length - failuresBeforeFixture;
    result.status = "PASS_DISPOSABLE_OPERATOR_UI_REHEARSAL";
  } catch (error) {
    result.status = "FAIL_OPERATOR_UI_REHEARSAL";
    result.error = String(error);
    process.exitCode = 1;
  } finally {
    if (browser) await browser.close();
    fs.writeFileSync(path.join(output, "result.json"), JSON.stringify(result, null, 2) + "\n", { flag: "wx" });
    console.log(JSON.stringify(result, null, 2));
  }
}
main().catch((error) => { console.error(String(error)); process.exitCode = 1; });
