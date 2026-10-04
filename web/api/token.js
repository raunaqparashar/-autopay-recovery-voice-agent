// Issues a short-lived LiveKit token and dispatches the hosted agent for the chosen fictional customer.
// Guards: one live call at a time, per-IP cooldown, fixed customer list. Keys come from Vercel env vars.
import { AccessToken, RoomAgentDispatch, RoomConfiguration, RoomServiceClient } from 'livekit-server-sdk';

const CUSTOMERS = new Set(['C001', 'C002', 'C003', 'C004', 'C005', 'C006', 'C007', 'C008', 'C009']);
const ROOM_PREFIX = 'demo-';
const COOLDOWN_MS = 60_000;
const recent = new Map(); // ip -> last start time (best effort; resets on cold start)

export default async function handler(req, res) {
  if (req.method !== 'POST') return res.status(405).json({ error: 'POST only' });

  const { LIVEKIT_URL, LIVEKIT_API_KEY, LIVEKIT_API_SECRET } = process.env;
  const customer = String(req.body?.customer || 'C001');
  if (!CUSTOMERS.has(customer)) return res.status(400).json({ error: 'Unknown customer' });

  const ip = (req.headers['x-forwarded-for'] || '').split(',')[0].trim() || 'unknown';
  const last = recent.get(ip) || 0;
  if (Date.now() - last < COOLDOWN_MS) {
    return res.status(429).json({ error: 'Please wait a minute before starting another call.' });
  }

  const rooms = new RoomServiceClient(LIVEKIT_URL.replace('wss://', 'https://'), LIVEKIT_API_KEY, LIVEKIT_API_SECRET);
  const active = (await rooms.listRooms()).filter((r) => r.name.startsWith(ROOM_PREFIX) && r.numParticipants > 0);
  if (active.length > 0) {
    return res.status(429).json({ error: 'Someone else is on a demo call right now. Please try again in a few minutes.' });
  }
  recent.set(ip, Date.now());

  const room = `${ROOM_PREFIX}${customer}-${Math.random().toString(36).slice(2, 8)}`;
  const at = new AccessToken(LIVEKIT_API_KEY, LIVEKIT_API_SECRET, { identity: `visitor-${Date.now()}`, ttl: '10m' });
  at.addGrant({ room, roomJoin: true, canPublish: true, canSubscribe: true });
  at.roomConfig = new RoomConfiguration({
    agents: [new RoomAgentDispatch({ agentName: 'autopay-recovery', metadata: JSON.stringify({ customer_id: customer }) })],
  });

  res.status(200).json({ url: LIVEKIT_URL, token: await at.toJwt(), room });
}
