import { EventEmitter } from 'node:events';

const bus = new EventEmitter();
const cache = new Map();
const store = new Map([['42', { id: '42', state: 'ready' }]]);
let audit = [];

bus.on('order-read', order => { audit.push(order.id); });

export async function handleOrder(id) {
  const hit = cache.get(id);
  if (hit) return hit;
  const record = store.get(id);
  if (!record) throw new Error('not found');
  cache.set(id, record);
  queueMicrotask(() => bus.emit('order-read', record));
  return record;
}

export function auditEntries() { return [...audit]; }
