export class ApiError extends Error {
  constructor(status, detail) {
    const message = typeof detail === "string" ? detail : Array.isArray(detail)
      ? detail.map(item => item.msg || "Invalid input").join("; ") : detail?.message || "The request could not be completed.";
    super(message);
    this.status = status;
    this.detail = detail;
  }
}

export async function api(path, options = {}) {
  const response = await fetch(path, { ...options, headers: { Accept: "application/json", ...options.headers } });
  const data = await response.json().catch(() => ({}));
  if (!response.ok) throw new ApiError(response.status, data.detail || "The server could not complete this request.");
  return data;
}

export function jsonPost(body) {
  return { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) };
}

export function parseFrame(frame) {
  const data = frame.split("\n").filter(line => line.startsWith("data:")).map(line => line.slice(5).trimStart()).join("\n");
  return data ? JSON.parse(data) : null;
}

const pause = (ms, signal) => new Promise(resolve => {
  if (signal.aborted) return resolve();
  const done = () => { clearTimeout(timer); signal.removeEventListener("abort", done); resolve(); };
  const timer = setTimeout(done, ms);
  signal.addEventListener("abort", done, { once: true });
});

export async function streamEvents(run, { signal, onEvent, onConnection, onTerminal, onError }) {
  let retries = 0;
  while (!signal.aborted) {
    let reader;
    try {
      onConnection(retries ? "reconnecting" : "connecting");
      const response = await fetch(`${run.eventsUrl || `/api/runs/${encodeURIComponent(run.runId)}/events`}?after=${run.lastSequence}${run.mode === "replay" ? "&speed=4" : ""}`, {
        signal, headers: { Accept: "text/event-stream", ...(run.lastSequence ? { "Last-Event-ID": `${run.runId}:${run.lastSequence}` } : {}) },
      });
      if (!response.ok) {
        const body = await response.json().catch(() => ({}));
        throw new ApiError(response.status, body.detail || "Live events are unavailable.");
      }
      if (!response.body) throw new Error("Streaming is unavailable in this browser.");
      onConnection("connected");
      reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";
      while (!signal.aborted) {
        const { value, done } = await reader.read();
        buffer += decoder.decode(value || new Uint8Array(), { stream: !done });
        buffer = buffer.replaceAll("\r\n", "\n");
        let boundary;
        while ((boundary = buffer.indexOf("\n\n")) !== -1) {
          const frame = buffer.slice(0, boundary);
          buffer = buffer.slice(boundary + 2);
          if (frame.includes("event: history_expired")) throw new ApiError(404, "This run expired from the retained history.");
          const event = parseFrame(frame);
          if (!event) continue;
          onEvent(event);
          retries = 0;
          if (["run_completed", "run_failed"].includes(event.type)) {
            await reader.cancel();
            await onTerminal();
            return;
          }
        }
        if (buffer.length > 262144) throw new Error("An event exceeded the supported message size.");
        if (done) break;
      }
      // A closed response is not a completed inference. Reconnect from the last
      // accepted sequence; a client disconnect never cancels the server query.
      if (!signal.aborted) {
        const record = await api(`/api/runs/${encodeURIComponent(run.runId)}`, { signal });
        if (record.status !== "running" && run.lastSequence >= record.last_sequence) {
          await onTerminal();
          return;
        }
      }
    } catch (error) {
      if (signal.aborted) return;
      if (error instanceof ApiError && [404, 410, 422].includes(error.status)) {
        onError(error);
        return;
      }
      onConnection("reconnecting");
    } finally {
      if (reader) await reader.cancel().catch(() => {});
    }
    retries += 1;
    await pause(Math.min(10000, 750 * 2 ** Math.min(retries, 4)), signal);
  }
}
