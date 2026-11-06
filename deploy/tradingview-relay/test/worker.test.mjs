import assert from "node:assert/strict";
import { createHash, createHmac } from "node:crypto";
import { readFile } from "node:fs/promises";
import test from "node:test";
import { Miniflare } from "miniflare";
import worker, { configuration, DOMAIN, MAX_BODY, ReceiptBox } from "../src/worker.mjs";

const body = '{"fixture":"synthetic-only, never external evidence"}';
const key = (name) => createHash("sha256").update(`test-only-${name}`).digest("hex");
function environment(overrides = {}) {
  const now = Date.now();
  return {
    ARMED: "true", TV_SECRET: key("tv"), READ_SECRET: key("read"), SIGNING_KEY: key("sign"),
    CAMPAIGN_ID: "synthetic-campaign-0001", WORKER_HOSTNAME: "aurex-fixture.test.workers.dev",
    STARTS_AT: new Date(now - 60000).toISOString(), EXPIRES_AT: new Date(now + 60000).toISOString(),
    SOURCE_REVIEWED_AT: new Date(now - 120000).toISOString(),
    EXPECTED_BODY_SHA256: createHash("sha256").update(body).digest("hex"), ...overrides,
  };
}

function fixture(overrides = {}) {
  const env = environment(overrides);
  const rows = new Map();
  const storage = {
    get: async (key) => rows.get(key), put: async (key, value) => rows.set(key, value),
    setAlarm: async () => {}, deleteAll: async () => rows.clear(),
    transaction: async (fn) => fn(storage),
  };
  const box = new ReceiptBox({ storage }, env);
  env.RECEIPT_BOX = { idFromName: (name) => name, get: () => box };
  return { env, rows, box };
}

function incoming(env, { path = "/webhooks/tradingview", content = body, headers = {},
  query = `?secret=${env.TV_SECRET}`, method = "POST", cf = true, ...rest } = {}) {
  const request = new Request(`https://${env.WORKER_HOSTNAME}${path}${query}`, {
    method, body: method === "POST" ? content : undefined,
    headers: { "content-type": "application/json", "cf-connecting-ip": "52.89.214.238",
      "cf-ray": "0123456789abcdef-JNB", ...headers }, ...rest,
  });
  if (cf) Object.defineProperty(request, "cf", { value: { country: "US" } });
  return request;
}

test("synthetic receipt preserves bytes and has independently verifiable HMAC", async () => {
  const { env, rows } = fixture();
  const first = await worker.fetch(incoming(env), env);
  assert.equal(first.status, 202);
  const stored = rows.get("receipt");
  const digest = createHmac("sha256", Buffer.from(env.SIGNING_KEY, "hex"))
    .update(DOMAIN + stored.payload_b64).digest("hex");
  assert.equal(stored.signature_hex, digest);
  const payload = JSON.parse(Buffer.from(stored.payload_b64, "base64"));
  assert.equal(Buffer.from(payload.body_b64, "base64").toString(), body);
  assert.equal(payload.evidence_kind, "CLOUDFLARE_EDGE_RELAY_NOT_DIRECT_PEER");
  for (const secret of [env.TV_SECRET, env.READ_SECRET, env.SIGNING_KEY]) {
    assert.equal(JSON.stringify(stored).includes(secret), false);
  }
  const duplicate = await worker.fetch(incoming(env), env);
  assert.equal((await duplicate.json()).status, "ALREADY_RECEIVED");
  assert.deepEqual(rows.get("receipt"), stored);
});

for (const [name, options, status] of [
  ["no platform metadata", { cf: false }, 403],
  ["wrong IP despite spoofed forwarded-for", { headers: { "cf-connecting-ip": "127.0.0.1",
    "x-forwarded-for": "52.89.214.238" } }, 403],
  ["worker subrequest", { headers: { "cf-worker": "other.example" } }, 403],
  ["alterable same-zone IP", { headers: { "x-real-ip": "52.89.214.238" } }, 403],
  ["missing ray", { headers: { "cf-ray": "" } }, 403],
  ["wrong secret", { query: `?secret=${key("wrong")}` }, 401],
  ["duplicate secret", { query: `?secret=${key("tv")}&secret=${key("tv")}` }, 401],
  ["extra query", { query: `?secret=${key("tv")}&other=value` }, 401],
  ["wrong body", { content: "{}" }, 422],
  ["oversized", { content: "x".repeat(MAX_BODY + 1) }, 413],
  ["wrong content type", { headers: { "content-type": "text/plain" } }, 415],
  ["encoded body", { headers: { "content-encoding": "gzip" } }, 415],
  ["dashboard", { path: "/dashboard" }, 404],
  ["unauthenticated read", { path: "/receipt", method: "GET", query: "" }, 401],
]) {
  test(`reject ${name} without storing a receipt`, async () => {
    const { env, rows } = fixture();
    assert.equal((await worker.fetch(incoming(env, options), env)).status, status);
    assert.equal(rows.size, 0);
  });
}

test("stop prevents intake while authenticated collection remains available", async () => {
  const { env, rows } = fixture();
  const auth = { authorization: `Bearer ${env.READ_SECRET}` };
  await worker.fetch(incoming(env), env);
  assert.equal((await worker.fetch(incoming(env, {
    path: "/control/stop", query: "", headers: auth,
  }), env)).status, 200);
  assert.equal((await worker.fetch(incoming(env), env)).status, 410);
  const collected = await worker.fetch(incoming(env, {
    path: "/receipt", method: "GET", query: "", headers: auth,
  }), env);
  assert.equal(collected.status, 200);
  assert.deepEqual(await collected.json(), rows.get("receipt"));
});

test("wrong auth scheme and redirects cannot expose a receipt", async () => {
  const { env } = fixture();
  assert.equal((await worker.fetch(incoming(env, { path: "/receipt", method: "GET", query: "",
    headers: { authorization: env.READ_SECRET } }), env)).status, 401);
  assert.equal((await worker.fetch(new Request("http://elsewhere.example/receipt"), env)).status, 400);
});

test("disabled, stale, overlong, or weakly keyed configuration fails closed", async () => {
  for (const overrides of [
    { ARMED: "false" }, { TV_SECRET: "0".repeat(64) }, { SIGNING_KEY: key("tv") },
    { EXPIRES_AT: new Date(Date.now() + 7200000).toISOString() },
    { SOURCE_REVIEWED_AT: new Date(Date.now() - 86400000).toISOString() },
  ]) {
    const { env, rows } = fixture(overrides);
    assert.throws(() => configuration(env));
    assert.equal((await worker.fetch(incoming(env), env)).status, 503);
    assert.equal(rows.size, 0);
  }
});

test("expired and not-yet-started campaigns reject intake", async () => {
  for (const delta of [-180000, 180000]) {
    const env = environment({
      STARTS_AT: new Date(Date.now() + delta).toISOString(),
      EXPIRES_AT: new Date(Date.now() + delta + 60000).toISOString(),
      SOURCE_REVIEWED_AT: new Date(Date.now() - 3600000).toISOString(),
    });
    assert.equal((await worker.fetch(incoming(env), env)).status, 410);
  }
});

test("slow body is bounded, without relying on Content-Length", async () => {
  const { env, rows } = fixture();
  const stream = new ReadableStream({ start() {} });
  assert.equal((await worker.fetch(incoming(env, { content: stream, duplex: "half" }), env)).status, 408);
  assert.equal(rows.size, 0);
});

test("workerd SQLite mailbox serializes concurrent writes and persists across restart", async () => {
  // Only synthetic envelopes are inserted into this local runtime; never origin evidence.
  const script = await readFile(new URL("../src/worker.mjs", import.meta.url), "utf8");
  const env = environment();
  const mf = new Miniflare({ modules: true, script, compatibilityDate: "2026-06-01",
    bindings: env, durableObjects: { RECEIPT_BOX: { className: "ReceiptBox", useSQLite: true } } });
  try {
    const ns = await mf.getDurableObjectNamespace("RECEIPT_BOX");
    const stub = ns.get(ns.idFromName("synthetic-campaign-0001"));
    const submit = (n) => stub.fetch("https://mailbox/receipt", {
      method: "POST", body: JSON.stringify({ synthetic: n }),
    });
    // Concurrent requests deliberately exercise the actor transaction boundary.
    const a = submit(1);
    const b = submit(2);
    const results = [(await (await a).json()).status, (await (await b).json()).status].sort();
    assert.deepEqual(results, ["ALREADY_RECEIVED", "RECEIVED"]);
    const stored = await (await stub.fetch("https://mailbox/receipt")).json();
    await mf.setOptions({ modules: true, script, compatibilityDate: "2026-06-01",
      bindings: env, durableObjects: { RECEIPT_BOX: { className: "ReceiptBox", useSQLite: true } } });
    const ns2 = await mf.getDurableObjectNamespace("RECEIPT_BOX");
    const again = ns2.get(ns2.idFromName("synthetic-campaign-0001"));
    assert.deepEqual(await (await again.fetch("https://mailbox/receipt")).json(), stored);
    assert.equal((await again.fetch("https://mailbox/stop", { method: "POST" })).status, 200);
    assert.equal((await again.fetch("https://mailbox/receipt", {
      method: "POST", body: JSON.stringify({ synthetic: 3 }),
    })).status, 410);
  } finally { await mf.dispose(); }
});
