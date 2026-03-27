import { createClient } from "redis";

const REDIS_CHAT_TTL_SECONDS = Number.parseInt(
  process.env.REDIS_CHAT_TTL_SECONDS ?? "604800",
  10,
);
const REDIS_CHAT_MAX_MESSAGES = Number.parseInt(
  process.env.REDIS_CHAT_MAX_MESSAGES ?? "500",
  10,
);

type RedisClient = ReturnType<typeof createClient>;

const globalForRedis = globalThis as unknown as {
  redisClient?: RedisClient;
};

const getRedisUrl = (): string => {
  const redisUrl = process.env.REDIS_URL;
  if (!redisUrl) {
    throw new Error("Missing REDIS_URL environment variable");
  }
  return redisUrl;
};

const createRedisClient = () => {
  const client = createClient({ url: getRedisUrl() });
  client.on("error", (error) => {
    console.error("Redis client error", error);
  });
  return client;
};

const getRedisClient = (): RedisClient => {
  if (!globalForRedis.redisClient) {
    globalForRedis.redisClient = createRedisClient();
  }
  return globalForRedis.redisClient;
};

const ensureConnected = async () => {
  const redisClient = getRedisClient();
  if (!redisClient.isOpen) {
    await redisClient.connect();
  }
  return redisClient;
};

const getMessagesKey = (sessionId: string) =>
  `realtime:chat:${sessionId}:messages`;
const getSessionKey = (sessionId: string) =>
  `realtime:chat:${sessionId}:session`;

export interface PersistedChatMessage {
  id: string;
  role: "user" | "assistant" | "system";
  content: string;
  timestamp: string;
  source: string;
}

export interface PersistedChatSession {
  sessionId: string;
  userId: string;
  createdAt: string;
  updatedAt: string;
}

export const upsertSession = async (
  sessionId: string,
  userId: string,
): Promise<PersistedChatSession> => {
  const redisClient = await ensureConnected();
  const now = new Date().toISOString();
  const sessionKey = getSessionKey(sessionId);

  const existingCreatedAt = await redisClient.hGet(sessionKey, "createdAt");
  const createdAt = existingCreatedAt ?? now;

  await redisClient.hSet(sessionKey, {
    createdAt,
    sessionId,
    updatedAt: now,
    userId,
  });
  await redisClient.expire(sessionKey, REDIS_CHAT_TTL_SECONDS);

  return {
    createdAt,
    sessionId,
    updatedAt: now,
    userId,
  };
};

export const appendMessage = async (
  sessionId: string,
  message: PersistedChatMessage,
): Promise<void> => {
  const redisClient = await ensureConnected();
  const messagesKey = getMessagesKey(sessionId);

  await redisClient.rPush(messagesKey, JSON.stringify(message));
  await redisClient.lTrim(messagesKey, -REDIS_CHAT_MAX_MESSAGES, -1);
  await redisClient.expire(messagesKey, REDIS_CHAT_TTL_SECONDS);
};

export const getMessages = async (
  sessionId: string,
  limit = 200,
): Promise<PersistedChatMessage[]> => {
  const redisClient = await ensureConnected();
  const messagesKey = getMessagesKey(sessionId);
  const size = await redisClient.lLen(messagesKey);

  if (size === 0) {
    return [];
  }

  const start = Math.max(0, size - Math.max(limit, 1));
  const rawEntries = await redisClient.lRange(messagesKey, start, -1);

  const parsed = rawEntries
    .map((entry) => {
      try {
        return JSON.parse(entry) as PersistedChatMessage;
      } catch {
        return null;
      }
    })
    .filter((entry): entry is PersistedChatMessage => entry !== null);

  return parsed;
};

export const clearSessionHistory = async (sessionId: string): Promise<void> => {
  const redisClient = await ensureConnected();
  await redisClient.del([getMessagesKey(sessionId), getSessionKey(sessionId)]);
};
