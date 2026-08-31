# gateway/

The hot path. Phase 4: incoming request → identify tenant/service via API key →
rate-limit check → forward via httpx to tenant backend, or reject with 429.
Kept separate from the management API deliberately. Not implemented yet.
