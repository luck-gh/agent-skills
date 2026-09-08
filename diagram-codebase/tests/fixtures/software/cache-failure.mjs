// Separate adapter example: cache failure falls back to the authoritative store.
export async function readOrder(id, cache, store) {
  try {
    const cached = await cache.read(id);
    if (cached !== undefined) return cached;
  } catch {
    // A cache outage is not equivalent to an order missing from the store.
  }
  const record = await store.read(id);
  if (record === undefined) throw new Error('not found');
  return record;
}
