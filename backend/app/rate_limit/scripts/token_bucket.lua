-- Token bucket, evaluated atomically by Redis (no other command interleaves).
--
-- State is a HASH { tokens, ts }. On each call we refill for the time elapsed
-- since `ts`, then consume `cost` if enough tokens remain.
--
-- KEYS[1]  bucket key
-- ARGV[1]  rate      tokens replenished per second
-- ARGV[2]  capacity  maximum tokens (the burst ceiling)
-- ARGV[3]  now       current time in seconds (float, supplied by caller)
-- ARGV[4]  cost      tokens this request consumes
-- ARGV[5]  ttl       seconds to retain an idle bucket
--
-- returns { allowed (0|1), remaining (int string), retry_after (seconds string) }

local key      = KEYS[1]
local rate     = tonumber(ARGV[1])
local capacity = tonumber(ARGV[2])
local now      = tonumber(ARGV[3])
local cost     = tonumber(ARGV[4])
local ttl      = math.floor(tonumber(ARGV[5]))

local state  = redis.call('HMGET', key, 'tokens', 'ts')
local tokens = tonumber(state[1])
local ts     = tonumber(state[2])

if tokens == nil then
  tokens = capacity
  ts = now
end

-- refill; clamp elapsed at 0 so a backwards clock never drains the bucket
local elapsed = now - ts
if elapsed < 0 then elapsed = 0 end
tokens = math.min(capacity, tokens + elapsed * rate)

local allowed = 0
if tokens >= cost then
  allowed = 1
  tokens = tokens - cost
end

redis.call('HSET', key, 'tokens', tokens, 'ts', now)
redis.call('EXPIRE', key, ttl)

local retry_after = 0.0
if allowed == 0 and rate > 0 then
  retry_after = (cost - tokens) / rate
end

local remaining = math.floor(tokens)
return { allowed, tostring(remaining), string.format('%.6f', retry_after) }
