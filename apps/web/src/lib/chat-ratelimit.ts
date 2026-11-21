interface RateBucket {
  dateKey: string;
  count: number;
}

const g = globalThis as unknown as {
  __southbiChatRateMap?: Map<string, RateBucket>;
};

function getMap(): Map<string, RateBucket> {
  if (!g.__southbiChatRateMap) {
    g.__southbiChatRateMap = new Map();
  }
  return g.__southbiChatRateMap;
}

export function checkAndConsumeChatQuota(params: {
  key: string;
  isAuthenticated: boolean;
  todayKey?: string;
}): { allowed: boolean; remaining: number; limit: number } {
  const limit = params.isAuthenticated ? 20 : 5;
  const today = params.todayKey || new Date().toISOString().slice(0, 10);
  const map = getMap();

  const existing = map.get(params.key);
  if (!existing || existing.dateKey !== today) {
    map.set(params.key, { dateKey: today, count: 1 });
    return { allowed: true, remaining: limit - 1, limit };
  }

  if (existing.count >= limit) {
    return { allowed: false, remaining: 0, limit };
  }

  existing.count += 1;
  return { allowed: true, remaining: limit - existing.count, limit };
}

export function resetChatRateLimitForTests(): void {
  getMap().clear();
}
