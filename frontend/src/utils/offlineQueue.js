/**
 * Offline / poor-network queue for GPS + SOS payloads.
 * Stores in localStorage and flushes when online again.
 * (Bluetooth/LoRa hardware not required — demo store-and-forward.)
 */
const QUEUE_KEY = "saferoute_offline_queue_v1";

function readQueue() {
  try {
    return JSON.parse(localStorage.getItem(QUEUE_KEY) || "[]");
  } catch {
    return [];
  }
}

function writeQueue(items) {
  localStorage.setItem(QUEUE_KEY, JSON.stringify(items.slice(-80)));
}

export function enqueueOffline(item) {
  const q = readQueue();
  q.push({ ...item, queued_at: new Date().toISOString() });
  writeQueue(q);
  return q.length;
}

export function pendingOfflineCount() {
  return readQueue().length;
}

export async function flushOfflineQueue({ token, postLocation, postSos }) {
  if (!navigator.onLine) return { flushed: 0, remaining: pendingOfflineCount() };
  const q = readQueue();
  if (!q.length) return { flushed: 0, remaining: 0 };

  const remaining = [];
  let flushed = 0;
  for (const item of q) {
    try {
      if (item.kind === "location" && postLocation) {
        await postLocation(token, item.journeyId, item.payload);
        flushed += 1;
      } else if (item.kind === "sos" && postSos) {
        await postSos(token, item.journeyId, item.payload);
        flushed += 1;
      } else {
        remaining.push(item);
      }
    } catch {
      remaining.push(item);
    }
  }
  writeQueue(remaining);
  return { flushed, remaining: remaining.length };
}
