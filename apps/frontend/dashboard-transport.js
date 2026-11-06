/* Bounded reads and ordered refreshes; mutations are never retried automatically. */
const AurexTransport = (() => {
  async function requestJson(path, options = {}) {
    const method = (options.method || "GET").toUpperCase();
    const { timeoutMs = method === "GET" ? 30000 : 0, ...request } = options;
    const controller = timeoutMs ? new AbortController() : null;
    const timer = controller ? setTimeout(() => controller.abort(), timeoutMs) : null;
    try {
      const response = await fetch(path, {
        ...request,
        cache: "no-store",
        headers: { "Content-Type": "application/json", ...request.headers },
        ...(controller ? { signal: controller.signal } : {}),
      });
      if (!response.ok) {
        let detail = "";
        try {
          const payload = await response.json();
          if (typeof payload.detail === "string") {
            detail = payload.detail;
          } else if (payload.detail?.message) {
            const first = payload.detail.errors?.[0];
            const field = first?.field ? `${first.field}: ` : "";
            detail = `${payload.detail.message}${first?.message ? ` / ${field}${first.message}` : ""}`;
          }
        } catch (error) {
          if (error.name === "AbortError") throw error;
        }
        throw Object.assign(new Error(detail || `${path} returned ${response.status}`), {
          status: response.status,
        });
      }
      return await response.json();
    } catch (error) {
      if (controller?.signal.aborted) throw new Error(`${path} timed out; state is unknown.`);
      throw error;
    } finally {
      if (timer !== null) clearTimeout(timer);
    }
  }

  async function settleResources(resources, load = requestJson) {
    const results = new Array(resources.length);
    let next = 0;
    async function worker() {
      while (next < resources.length) {
        const index = next++;
        try {
          results[index] = { status: "fulfilled", value: await load(resources[index][1]) };
        } catch (reason) {
          results[index] = { status: "rejected", reason };
        }
      }
    }
    await Promise.all(Array.from({ length: Math.min(4, resources.length) }, worker));
    return results;
  }

  function serialQueue() {
    let tail = Promise.resolve();
    return (work) => {
      const result = tail.then(work);
      tail = result.catch(() => {});
      return result;
    };
  }
  return Object.freeze({ requestJson, settleResources, serialQueue });
})();

if (typeof module !== "undefined") module.exports = AurexTransport;
