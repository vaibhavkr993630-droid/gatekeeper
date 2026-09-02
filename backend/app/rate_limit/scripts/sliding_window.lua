-- Sliding window counter, evaluated atomically by Redis.
--
-- Approximation (the "Cloudflare" method): keep one integer counter per fixed
-- window and estimate the rolling count as
--     estimate = prev_window_count * (1 - elapsed_fraction) + current_window_count
-- This is O(1) memory (two integer keys) versus the sliding-window *log*, which
-- stores every request timestamp in a sorted set. The trade-off is a small,
-- bounded over/under-count near window boundaries.
--
-- KEYS[1]  base key; sub-keys are base..':'..window_index (same Redis slot)
-- ARGV[1]  now      current time in seconds (float, supplied by caller)
-- ARGV[2]  window   window size in seconds
-- ARGV[3]  limit    requests allowed per window
-- ARGV[4]  cost     units this request consumes
--
-- returns { allowed (0|1), remaining (int string), retry_after (seconds string) }

local base   = KEYS[1]
local now    = tonumber(ARGV[1])
local window = tonumber(ARGV[2])
local limit  = tonumber(ARGV[3])
local cost   = tonumber(ARGV[4])

local idx     = math.floor(now / window)
local elapsed = (now - idx * window) / window     -- fraction of current window elapsed [0,1)

local cur_key  = base .. ':' .. idx
local prev_key = base .. ':' .. (idx - 1)

local cur  = tonumber(redis.call('GET', cur_key)  or '0')
local prev = tonumber(redis.call('GET', prev_key) or '0')

local estimated = prev * (1 - elapsed) + cur

local allowed = 0
if estimated + cost <= limit then
  allowed = 1
  redis.call('INCRBY', cur_key, cost)
  redis.call('EXPIRE', cur_key, math.ceil(window * 2) + 1)
  estimated = estimated + cost
end

local remaining = math.floor(limit - estimated)
if remaining < 0 then remaining = 0 end

local retry_after = 0.0
if allowed == 0 then
  local over = estimated + cost - limit
  if prev > 0 then
    -- prev's contribution decays by prev/window per second; wait for `over` to bleed off
    retry_after = over / (prev / window)
  else
    -- nothing decaying in this window; relief comes when the next window opens
    retry_after = window - (now - idx * window)
  end
  if retry_after < 0 then retry_after = 0 end
  if retry_after > window then retry_after = window end
end

return { allowed, tostring(remaining), string.format('%.6f', retry_after) }
