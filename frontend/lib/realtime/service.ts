import { WebPubSubServiceClient } from "@azure/web-pubsub";

interface RealtimeConfig {
  connectionString: string;
  hubName: string;
  groupName: string;
}

const getConfig = (): RealtimeConfig => {
  const connectionString = process.env.AZURE_WEBPUBSUB_CONNECTION_STRING;
  const hubName = process.env.AZURE_WEBPUBSUB_HUB_NAME;
  const groupName = process.env.AZURE_WEBPUBSUB_GROUP;

  if (!connectionString || !hubName || !groupName) {
    throw new Error(
      "Realtime no configurado: faltan variables de Azure Web PubSub.",
    );
  }

  return {
    connectionString,
    hubName,
    groupName,
  };
};

const createClient = (): WebPubSubServiceClient => {
  const { connectionString, hubName } = getConfig();

  return new WebPubSubServiceClient(connectionString, hubName);
};

export const getRealtimeGroupName = (): string => getConfig().groupName;

export const negotiateRealtimeConnection = async (userId: string) => {
  const client = createClient();
  const group = getRealtimeGroupName();

  const token = await client.getClientAccessToken({
    userId,
    groups: [group],
    roles: [
      `webpubsub.joinLeaveGroup.${group}`,
      `webpubsub.sendToGroup.${group}`,
    ],
  });

  return {
    group,
    hub: client.hubName,
    url: token.url,
    userId,
  };
};

export const publishRealtimeEvent = async (event: Record<string, unknown>) => {
  const client = createClient();
  const group = getRealtimeGroupName();

  await client.group(group).sendToAll(event);
};
