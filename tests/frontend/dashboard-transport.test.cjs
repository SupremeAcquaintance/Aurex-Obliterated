const assert = require("node:assert/strict");
const { test } = require("node:test");
const { requestJson, settleResources, serialQueue } = require("../../apps/frontend/dashboard-transport.js");

test("source reads are bounded, preserve ordering and retain failures", async () => {
  let active = 0, maximum = 0;
  const resources = Array.from({ length: 43 }, (_, i) => [String(i), i]);
  const results = await settleResources(resources, async (i) => {
    maximum = Math.max(maximum, ++active);
    await new Promise((resolve) => setTimeout(resolve, (i % 3) + 1));
    active--;
    if (i === 17) throw new Error("source unavailable");
    return i;
  });
  assert.equal(maximum, 4);
  assert.equal(active, 0);
  assert.equal(results.length, 43);
  results.forEach((result, i) => {
    assert.equal(result.status, i === 17 ? "rejected" : "fulfilled");
    if (i !== 17) assert.equal(result.value, i);
  });
});

test("empty and synchronous-failure source sets settle", async () => {
  assert.deepEqual(await settleResources([]), []);
  const results = await settleResources([["a", "/a"]], () => { throw new Error("offline"); });
  assert.equal(results[0].status, "rejected");
});

test("post-mutation refresh runs after old reads, including after a failed refresh", async () => {
  const schedule = serialQueue();
  const events = [];
  const first = schedule(async () => {
    events.push("old reads");
    await new Promise((resolve) => setTimeout(resolve, 5));
    events.push("old reads settled");
    throw new Error("failed source");
  });
  const second = schedule(() => events.push("new reads"));
  await assert.rejects(first, /failed source/);
  await second;
  assert.deepEqual(events, ["old reads", "old reads settled", "new reads"]);
});

test("request preserves structured rejection and makes no automatic retry", async (t) => {
  let calls = 0;
  t.mock.method(global, "fetch", async () => {
    calls++;
    return new Response(JSON.stringify({ detail: { message: "Blocked", errors: [{ field: "mode", message: "disabled" }] } }), { status: 403 });
  });
  await assert.rejects(requestJson("/control", { method: "POST", body: "{}" }), (error) => {
    assert.equal(error.status, 403);
    return error.message === "Blocked / mode: disabled";
  });
  assert.equal(calls, 1);
});

test("read timeout covers a stalled response body", async (t) => {
  t.mock.method(global, "fetch", async (_, options) => ({
    ok: true,
    json: () => new Promise((_, reject) => options.signal.addEventListener("abort", () => reject(new DOMException("aborted", "AbortError")))),
  }));
  await assert.rejects(requestJson("/slow", { timeoutMs: 10 }), /timed out; state is unknown/);
});

test("successful JSON request disables cache and retains caller headers", async (t) => {
  t.mock.method(global, "fetch", async (_, options) => {
    assert.equal(options.cache, "no-store");
    assert.equal(options.headers["Content-Type"], "application/json");
    assert.equal(options.headers["X-Test"], "yes");
    return new Response(JSON.stringify({ result: "ok" }));
  });
  assert.deepEqual(await requestJson("/status", { headers: { "X-Test": "yes" } }), { result: "ok" });
});
