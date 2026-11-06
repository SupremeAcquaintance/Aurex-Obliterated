// A single-message diagnostic mailbox, never an execution or general proxy endpoint.
export const SCHEMA = "aurex-tradingview-relay-receipt-v1";
export const DOMAIN = "aurex-tradingview-relay-v1\n";
export const SENDERS = ["52.89.214.238", "34.212.75.30", "54.218.53.128", "52.32.178.7"];
export const MAX_BODY = 16 * 1024;
const RETENTION_MS = 24 * 60 * 60 * 1000;
const encoder = new TextEncoder();
const hex = (bytes) => [...new Uint8Array(bytes)].map((b) => b.toString(16).padStart(2, "0")).join("");
const unhex = (value) => Uint8Array.from(value.match(/../g), (b) => parseInt(b, 16));
const base64 = (bytes) => btoa(String.fromCharCode(...bytes));
const utc = (value) => /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}Z$/.test(value)
  && Number.isFinite(Date.parse(value)) && new Date(value).toISOString() === value;

function response(status, value = { status: "REJECTED" }) {
  return Response.json(value, { status, headers: { "Cache-Control": "no-store" } });
}

export function configuration(env) {
  const keys = [env.TV_SECRET, env.READ_SECRET, env.SIGNING_KEY];
  if (env.ARMED !== "true" || keys.some((k) => !/^[0-9a-f]{64}$/.test(k ?? ""))
      || new Set(keys).size !== 3 || keys.some((k) => new Set(k).size < 8)
      || !/^[a-z0-9-]{16,64}$/.test(env.CAMPAIGN_ID ?? "")
      || !/^[a-z0-9-]+\.[a-z0-9-]+\.workers\.dev$/.test(env.WORKER_HOSTNAME ?? "")
      || !/^[0-9a-f]{64}$/.test(env.EXPECTED_BODY_SHA256 ?? "")
      || ![env.STARTS_AT, env.EXPIRES_AT, env.SOURCE_REVIEWED_AT].every(utc)) {
    throw new Error("CONFIGURATION_BLOCKED");
  }
  const start = Date.parse(env.STARTS_AT);
  const end = Date.parse(env.EXPIRES_AT);
  const reviewed = Date.parse(env.SOURCE_REVIEWED_AT);
  if (end <= start || end - start > 3600000 || reviewed > start || end - reviewed > RETENTION_MS) {
    throw new Error("CONFIGURATION_BLOCKED");
  }
  return { start, end };
}

async function tokenMatches(value, expected) {
  if (!/^[0-9a-f]{64}$/.test(value ?? "")) return false;
  const key = await crypto.subtle.importKey("raw", encoder.encode(expected),
    { name: "HMAC", hash: "SHA-256" }, false, ["sign", "verify"]);
  const signature = await crypto.subtle.sign("HMAC", key, encoder.encode(value));
  return crypto.subtle.verify("HMAC", key, signature, encoder.encode(expected));
}

async function boundedBody(request) {
  if (!request.body) throw new Error("BODY_INVALID");
  const reader = request.body.getReader();
  let timeout;
  let size = 0;
  const chunks = [];
  const deadline = new Promise((_, reject) => {
    timeout = setTimeout(() => reject(new Error("BODY_TIMEOUT")), 1500);
  });
  try {
    while (true) {
      const { done, value } = await Promise.race([reader.read(), deadline]);
      if (done) break;
      size += value.length;
      if (size > MAX_BODY) throw new Error("BODY_TOO_LARGE");
      chunks.push(value);
    }
  } catch (error) {
    void reader.cancel().catch(() => {});
    throw error;
  } finally {
    clearTimeout(timeout);
  }
  const body = new Uint8Array(size);
  let offset = 0;
  for (const chunk of chunks) { body.set(chunk, offset); offset += chunk.length; }
  return body;
}

export async function signedEnvelope(body, request, env, receivedAt) {
  const payload = {
    schema_version: SCHEMA,
    campaign_id: env.CAMPAIGN_ID,
    worker_hostname: env.WORKER_HOSTNAME,
    received_at: receivedAt,
    expires_at: env.EXPIRES_AT,
    source_reviewed_at: env.SOURCE_REVIEWED_AT,
    source_ip: request.headers.get("cf-connecting-ip"),
    cf_ray: request.headers.get("cf-ray"),
    method: "POST",
    path: "/webhooks/tradingview",
    evidence_kind: "CLOUDFLARE_EDGE_RELAY_NOT_DIRECT_PEER",
    body_sha256: hex(await crypto.subtle.digest("SHA-256", body)),
    body_b64: base64(body),
  };
  const payload_b64 = base64(encoder.encode(JSON.stringify(payload)));
  const key = await crypto.subtle.importKey("raw", unhex(env.SIGNING_KEY),
    { name: "HMAC", hash: "SHA-256" }, false, ["sign"]);
  const signature = await crypto.subtle.sign("HMAC", key, encoder.encode(DOMAIN + payload_b64));
  return { payload_b64, signature_hex: hex(signature) };
}

export default {
  async fetch(request, env) {
    try {
      const { start, end } = configuration(env);
      const url = new URL(request.url);
      if (url.protocol !== "https:" || url.hostname !== env.WORKER_HOSTNAME || url.port) {
        return response(400);
      }
      const now = Date.now();
      if (now > end + RETENTION_MS) return response(410);
      const isIntake = url.pathname === "/webhooks/tradingview" && request.method === "POST";
      const isRead = url.pathname === "/receipt" && request.method === "GET";
      const isStop = url.pathname === "/control/stop" && request.method === "POST";
      if (!isIntake && !isRead && !isStop) return response(404);
      if (!isIntake) {
        const authorization = request.headers.get("authorization") ?? "";
        if (url.search || !/^Bearer [0-9a-f]{64}$/.test(authorization) || !await tokenMatches(
          authorization.slice(7), env.READ_SECRET)) {
          return response(401);
        }
        const stub = env.RECEIPT_BOX.get(env.RECEIPT_BOX.idFromName(env.CAMPAIGN_ID));
        return await stub.fetch(new Request(`https://mailbox${isRead ? "/receipt" : "/stop"}`,
          { method: isRead ? "GET" : "POST" }));
      }
      if (now < start || now > end) return response(410);
      // Trust only provider-added metadata on direct Internet requests to this Worker.
      // Worker subrequests have different CF-Connecting-IP semantics and are rejected.
      if (!request.cf || !SENDERS.includes(request.headers.get("cf-connecting-ip"))
          || ["cf-worker", "cf-ew-via", "x-real-ip", "forwarded", "cf-connecting-ipv6",
              "cf-pseudo-ipv4", "cf-connecting-o2o"].some((h) => request.headers.has(h))
          || !/^[0-9a-f]{16}-[A-Z]{3}$/.test(request.headers.get("cf-ray") ?? "")) {
        return response(403);
      }
      if ([...url.searchParams.keys()].some((k) => k !== "secret")
          || url.searchParams.getAll("secret").length !== 1
          || !await tokenMatches(url.searchParams.get("secret"), env.TV_SECRET)) return response(401);
      if (request.headers.get("content-type")?.split(";", 1)[0].trim().toLowerCase()
          !== "application/json" || request.headers.has("content-encoding")) return response(415);
      const body = await boundedBody(request);
      if (hex(await crypto.subtle.digest("SHA-256", body)) !== env.EXPECTED_BODY_SHA256) {
        return response(422);
      }
      const envelope = await signedEnvelope(body, request, env, new Date(now).toISOString());
      const stub = env.RECEIPT_BOX.get(env.RECEIPT_BOX.idFromName(env.CAMPAIGN_ID));
      return await stub.fetch(new Request("https://mailbox/receipt", {
        method: "POST", body: JSON.stringify(envelope),
      }));
    } catch (error) {
      const code = { BODY_TOO_LARGE: 413, BODY_TIMEOUT: 408, BODY_INVALID: 400 }[error.message];
      // Never echo exceptions, request URLs, bodies, or secrets to clients or logs.
      return response(code ?? 503);
    }
  },
};

export class ReceiptBox {
  constructor(state, env) { this.state = state; this.env = env; }

  async fetch(request) {
    const url = new URL(request.url);
    if (request.method === "GET" && url.pathname === "/receipt") {
      const envelope = await this.state.storage.get("receipt");
      return envelope ? response(200, envelope) : response(404, { status: "PENDING" });
    }
    if (request.method === "POST" && url.pathname === "/stop") {
      await this.state.storage.put("stopped", true);
      await this.state.storage.setAlarm(Date.parse(this.env.EXPIRES_AT) + RETENTION_MS);
      return response(200, { status: "STOPPED" });
    }
    if (request.method !== "POST" || url.pathname !== "/receipt") return response(404);
    const envelope = await request.json();
    // Persist before acknowledging. One transaction handles concurrent retries.
    return this.state.storage.transaction(async (txn) => {
      if (await txn.get("stopped")) return response(410);
      if (Date.now() > Date.parse(this.env.EXPIRES_AT)) return response(410);
      const existing = await txn.get("receipt");
      if (!existing) {
        await txn.put("receipt", envelope);
        await txn.setAlarm(Date.parse(this.env.EXPIRES_AT) + RETENTION_MS);
      }
      return response(202, { status: existing ? "ALREADY_RECEIVED" : "RECEIVED",
        trading_authority: false });
    });
  }

  async alarm() { await this.state.storage.deleteAll(); }
}
