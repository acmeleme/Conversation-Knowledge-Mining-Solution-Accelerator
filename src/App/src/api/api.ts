import {
  historyListResponse,
  historyReadResponse,
  ChartsResponse,
} from "../configs/StaticData";
import {
  AppConfig,
  ChartConfigItem,
  ChatMessage,
  Conversation,
  ConversationRequest,
  CosmosDBHealth,
  CosmosDBStatus,
} from "../types/AppTypes";
const baseURL = process.env.REACT_APP_API_BASE_URL;// base API URL

// Cached Easy Auth id_token used as Bearer for cross-domain API calls.
let _cachedIdToken: string | null = null;

async function getIdToken(): Promise<string | null> {
  if (_cachedIdToken) return _cachedIdToken;
  try {
    const res = await fetch("/.auth/me");
    if (!res.ok) return null;
    const payload = await res.json();
    const token = payload?.[0]?.id_token ?? null;
    if (token) _cachedIdToken = token;
    return token;
  } catch {
    return null;
  }
}

async function apiFetch(url: string, options: RequestInit = {}): Promise<Response> {
  const token = await getIdToken();
  const headers = new Headers(options.headers as HeadersInit);
  if (token) headers.set("Authorization", `Bearer ${token}`);
  return fetch(url, { ...options, headers });
}

const normalizeToken = (value: string) =>
  String(value || "")
    .trim()
    .toLowerCase();

const normalizeSentiment = (value: string) => {
  const v = normalizeToken(value);
  if (v === "satisfied") {
    return "positive";
  }
  if (v === "dissatisfied") {
    return "negative";
  }
  return v;
};

const slugify = (value: string) =>
  normalizeToken(value).replace(/[^a-z0-9]+/g, "-").replace(/^-+|-+$/g, "");

const tokenize = (value: string) =>
  normalizeToken(value)
    .split(/[^a-z0-9]+/)
    .map((x) => x.trim())
    .filter((x) => !!x && !["and", "de", "da", "do", "the", "of"].includes(x));

const getFallbackFilterData = () => {
  const topicChart = ChartsResponse.find((chart) => normalizeToken(chart.id) === "topics");
  const barChart = ChartsResponse.find(
    (chart) => normalizeToken(chart.id) === "avg_handling_time_by_topic"
  );
  const topicRows = Array.isArray(topicChart?.chart_value)
    ? (topicChart?.chart_value as any[])
    : [];
  const barRows = Array.isArray(barChart?.chart_value)
    ? (barChart?.chart_value as any[])
    : [];

  const topicNames = new Set<string>();
  topicRows.forEach((row: any) => {
    if (row?.name) {
      topicNames.add(String(row.name));
    }
  });
  barRows.forEach((row: any) => {
    if (row?.name) {
      topicNames.add(String(row.name));
    }
  });

  const topicValues = Array.from(topicNames)
    .sort((a, b) => a.localeCompare(b))
    .map((name) => ({ key: slugify(name), displayValue: name }));

  return [
    {
      filter_name: "Topic",
      filter_values: topicValues,
    },
    {
      filter_name: "Sentiment",
      filter_values: [
        { key: "positive", displayValue: "Positive" },
        { key: "neutral", displayValue: "Neutral" },
        { key: "negative", displayValue: "Negative" },
        { key: "all", displayValue: "All" },
      ],
    },
    {
      filter_name: "DateRange",
      filter_values: [
        { key: "7days", displayValue: "Last 7 days" },
        { key: "14days", displayValue: "Last 14 days" },
        { key: "90days", displayValue: "Last 90 days" },
        { key: "yearToDate", displayValue: "Year to Date" },
      ],
    },
  ];
};

const buildFallbackFilteredCharts = (bodyData: any) => {
  const selectedFilters = bodyData?.selected_filters ?? {};
  const selectedTopicsRaw: string[] = Array.isArray(selectedFilters.Topic)
    ? selectedFilters.Topic
    : [];
  const selectedSentimentsRaw: string[] = Array.isArray(selectedFilters.Sentiment)
    ? selectedFilters.Sentiment
    : [];

  const selectedTopics = new Set<string>();
  const topicOptions = getFallbackFilterData().find((x) => x.filter_name === "Topic")?.filter_values ?? [];

  selectedTopicsRaw.forEach((topicKeyOrName) => {
    const raw = normalizeToken(topicKeyOrName);
    if (!raw) {
      return;
    }
    selectedTopics.add(raw);
    const match = topicOptions.find((item) => normalizeToken(item.key) === raw);
    if (match?.displayValue) {
      selectedTopics.add(normalizeToken(match.displayValue));
    }
  });

  const selectedSentiments = new Set(
    selectedSentimentsRaw.map((x) => normalizeSentiment(x)).filter((x) => !!x)
  );

  const selectedTopicTokenSets = Array.from(selectedTopics).map((item) => tokenize(item));
  const topicMatchesSelection = (topicName: string) => {
    if (selectedTopics.size === 0) {
      return true;
    }
    const normalizedTopic = normalizeToken(topicName);
    if (selectedTopics.has(normalizedTopic) || selectedTopics.has(slugify(normalizedTopic))) {
      return true;
    }
    const topicTokens = new Set(tokenize(topicName));
    return selectedTopicTokenSets.some(
      (tokens) => tokens.length > 0 && tokens.some((token) => topicTokens.has(token))
    );
  };

  const includesAllSentiments =
    selectedSentiments.size === 0 || selectedSentiments.has("all");

  const topicChart = ChartsResponse.find((chart) => normalizeToken(chart.id) === "topics");
  const barChart = ChartsResponse.find(
    (chart) => normalizeToken(chart.id) === "avg_handling_time_by_topic"
  );
  const wordCloudChart = ChartsResponse.find(
    (chart) => normalizeToken(chart.id) === "key_phrases"
  );

  const topicChartValues = topicChart?.chart_value;
  const topicsRows = Array.isArray(topicChartValues) ? [...topicChartValues] : [];

  let filteredTopics = topicsRows.filter((row: any) => {
    const topicMatch = topicMatchesSelection(String(row?.name || ""));
    const sentimentMatch =
      includesAllSentiments ||
      selectedSentiments.has(normalizeSentiment(String(row?.average_sentiment || "")));
    return topicMatch && sentimentMatch;
  });

  const topicSentimentByName = new Map<string, string>();
  const topicFrequencyByName = new Map<string, number>();
  filteredTopics.forEach((row: any) => {
    const topicName = normalizeToken(row?.name);
    topicSentimentByName.set(topicName, normalizeSentiment(String(row?.average_sentiment || "")));
    topicFrequencyByName.set(topicName, Number(row?.call_frequency || 0));
  });

  const barChartValues = barChart?.chart_value;
  const barRows = Array.isArray(barChartValues) ? [...barChartValues] : [];
  let filteredBarRows = barRows.filter((row: any) => {
    const topicName = normalizeToken(row?.name);
    const topicMatch = topicMatchesSelection(String(row?.name || ""));
    const sentimentOfTopic = topicSentimentByName.get(topicName);
    const sentimentMatch =
      includesAllSentiments ||
      (sentimentOfTopic ? selectedSentiments.has(sentimentOfTopic) : true);
    return topicMatch && sentimentMatch;
  });

  // When selected topics are present only in one chart source (table or bar),
  // synthesize minimal rows so the filtered dashboard remains consistent.
  if (selectedTopics.size > 0 && filteredTopics.length === 0 && filteredBarRows.length > 0) {
    filteredTopics = filteredBarRows.map((row: any) => ({
      name: row?.name,
      call_frequency: 1,
      average_sentiment: "neutral",
    }));
  }

  if (selectedTopics.size > 0 && filteredBarRows.length === 0 && filteredTopics.length > 0) {
    const fallbackBarAverage =
      barRows.length > 0
        ? Number(
            (
              barRows.reduce((sum: number, row: any) => sum + Number(row?.value || 0), 0) /
              barRows.length
            ).toFixed(1)
          )
        : 0;

    filteredBarRows = filteredTopics.map((row: any) => ({
      name: row?.name,
      value: fallbackBarAverage,
    }));
  }

  const wordCloudChartValues = wordCloudChart?.chart_value;
  const wordCloudRows = Array.isArray(wordCloudChartValues)
    ? [...wordCloudChartValues]
    : [];
  const filteredWordCloudRows = wordCloudRows.filter((row: any) => {
    if (includesAllSentiments) {
      return true;
    }
    return selectedSentiments.has(normalizeSentiment(String(row?.average_sentiment || "")));
  });

  const sentimentTotals = filteredTopics.reduce(
    (acc: Record<string, number>, row: any) => {
      const sentiment = normalizeSentiment(String(row?.average_sentiment || "neutral"));
      const count = Number(row?.call_frequency || 0);
      acc[sentiment] = (acc[sentiment] || 0) + count;
      return acc;
    },
    { positive: 0, neutral: 0, negative: 0 }
  );

  const totalCalls = Object.values(sentimentTotals).reduce((sum, val) => sum + Number(val || 0), 0);
  const safeTotalCalls = totalCalls > 0 ? totalCalls : 1;

  const weightedAHT = filteredBarRows.reduce((acc: number, row: any) => {
    const topicName = normalizeToken(row?.name);
    const frequency = topicFrequencyByName.get(topicName) ?? 1;
    return acc + Number(row?.value || 0) * frequency;
  }, 0);
  const totalWeight = filteredBarRows.reduce((acc: number, row: any) => {
    const topicName = normalizeToken(row?.name);
    return acc + (topicFrequencyByName.get(topicName) ?? 1);
  }, 0);
  const avgHandlingTime = totalWeight > 0 ? Number((weightedAHT / totalWeight).toFixed(1)) : 0;

  const satisfactionPct = Number(
    ((sentimentTotals.positive / safeTotalCalls) * 100).toFixed(0)
  );

  const donutRows = ["positive", "neutral", "negative"].map((name) => ({
    name,
    value: Number(((sentimentTotals[name] / safeTotalCalls) * 100).toFixed(0)),
  }));

  return ChartsResponse.map((chart) => {
    const chartId = normalizeToken(chart.id);
    if (chartId === "topics") {
      return { ...chart, chart_value: filteredTopics };
    }
    if (chartId === "avg_handling_time_by_topic") {
      return { ...chart, chart_value: filteredBarRows };
    }
    if (chartId === "key_phrases") {
      return { ...chart, chart_value: filteredWordCloudRows };
    }
    if (chartId === "sentiment") {
      return { ...chart, chart_value: donutRows };
    }
    if (chartId === "total_calls") {
      return {
        ...chart,
        chart_value: [
          {
            name1: "Total Calls",
            value: totalCalls,
            unit_of_measurement: "",
          },
        ],
      };
    }
    if (chartId === "satisfied") {
      return {
        ...chart,
        chart_value: [
          {
            name: "Satisfied",
            value: satisfactionPct,
            unit_of_measurement: "%",
          },
        ],
      };
    }
    if (chartId === "avg_handling_time") {
      return {
        ...chart,
        chart_value: [
          {
            name: "Average Handling Time",
            value: avgHandlingTime,
            unit_of_measurement: "mins",
          },
        ],
      };
    }
    return chart;
  });
};

const fallbackLayoutConfig = {
  appConfig: {
    THREE_COLUMN: {
      DASHBOARD: 50,
      CHAT: 33,
      CHATHISTORY: 17,
    },
    TWO_COLUMN: {
      DASHBOARD_CHAT: {
        DASHBOARD: 65,
        CHAT: 35,
      },
      CHAT_CHATHISTORY: {
        CHAT: 80,
        CHATHISTORY: 20,
      },
    },
  },
  charts: ChartsResponse.map((chart) => ({
    id: chart.id,
    name: chart.chart_name,
    type: chart.chart_type,
    layout: (chart as any).layout ?? { row: 0, column: 0 },
  })),
};

export const fetchChartData = async () => {
  try {
    const response = await apiFetch(`${baseURL}/api/fetchChartData`);
    if (!response.ok) {
      throw new Error(`Error: ${response.status} ${response.statusText}`);
    }
    const data = await response.json();
    return data;
  } catch (error) {
    console.error("Failed to fetch chart data:", error);
    return ChartsResponse;
  }
};

export const fetchChartDataWithFilters = async (bodyData: any) => {
  try {
    const response = await apiFetch(`${baseURL}/api/fetchChartDataWithFilters`, {
      headers: {
        "Content-Type": "application/json",
      },
      method: "POST",
      body: JSON.stringify(bodyData),
    });
    if (!response.ok) {
      throw new Error(`Error: ${response.status} ${response.statusText}`);
    }
    const data = await response.json();
    return data;
  } catch (error) {
    console.error("Failed to fetch filtered chart data:", error);
    return buildFallbackFilteredCharts(bodyData);
  }
};

export const fetchFilterData = async () => {
  try {
    const response = await apiFetch(`${baseURL}/api/fetchFilterData`);
    if (!response.ok) {
      throw new Error(`Error: ${response.status} ${response.statusText}`);
    }
    const data = await response.json();
    return data;
  } catch (error) {
    console.error("Failed to fetch filter data:", error);
    return getFallbackFilterData();
  }
};

export type UserInfo = {
  access_token: string;
  expires_on: string;
  id_token: string;
  provider_name: string;
  user_claims: any[];
  user_id: string;
};

export async function getUserInfo(): Promise<UserInfo[]> {
  const authEndpoints = [
    "/.auth/me",
    baseURL ? `${baseURL}/.auth/me` : "",
  ].filter((endpoint, index, arr) => endpoint && arr.indexOf(endpoint) === index);

  let response: Response | null = null;
  for (const endpoint of authEndpoints) {
    try {
      const authResponse = await fetch(endpoint);
      if (authResponse.ok) {
        response = authResponse;
        break;
      }
    } catch {
      // Ignore and continue to try the next endpoint.
    }
  }

  if (!response) {
    console.warn("No identity provider endpoint available. Continuing without authenticated user context.");
    return [];
  }

  const payload = await response.json();
  const userClaims = payload[0]?.user_claims || [];
  const objectIdClaim = userClaims.find(
    (claim: any) =>
      claim.typ === "http://schemas.microsoft.com/identity/claims/objectidentifier"
  );
  const userId = objectIdClaim?.val;
  if (userId) {
    localStorage.setItem("userId", userId);
  }
  return payload;
}


function getUserIdFromLocalStorage(): string | null {
  return localStorage.getItem("userId");
}

export const historyRead = async (convId: string): Promise<ChatMessage[]> => {
  const userId = getUserIdFromLocalStorage();
  const response = await apiFetch(`${baseURL}/history/read`, {
    method: "POST",
    body: JSON.stringify({
      conversation_id: convId,
    }),
    headers: {
      "Content-Type": "application/json",
      "X-Ms-Client-Principal-Id": userId || "",
    },
  })
    .then(async (res) => {
      if (!res.ok) {
        return historyReadResponse.messages.map((msg: any) => ({
          id: msg.id,
          role: msg.role,
          content: msg.content.content,
          date: msg.createdAt,
          feedback: msg.feedback ?? undefined,
          context: msg.context,
          contentType: msg.contentType,
        }));
      }
      const payload = await res.json();
      const messages: ChatMessage[] = [];

      if (Array.isArray(payload?.messages)) {
        payload.messages.forEach((msg: any) => {
          const message: ChatMessage = {
            id: msg.id,
            role: msg.role,
            content: msg.content.content,
            date: msg.createdAt,
            feedback: msg.feedback ?? undefined,
            context: msg.context,
            citations: msg.content.citations,
            contentType: msg.contentType,
          };
          messages.push(message);
        });
      }
      return messages;
    })
    .catch((_err) => {
      console.error("There was an issue fetching your data.");
      return [];
    });
  return response;
};

export const historyList = async (
  offset = 0
): Promise<Conversation[] | null> => {
  const userId = getUserIdFromLocalStorage();
  let response = await apiFetch(`${baseURL}/history/list?offset=${offset}`, {
    method: "GET",
  headers: {
    "Content-Type": "application/json",
    "X-Ms-Client-Principal-Id": userId || "",
  },
})
    .then(async (res) => {
      let payload = await res.json();
      if (!Array.isArray(payload)) {
        console.error("There was an issue fetching your data.");
        return null;
      }
      const conversations: Conversation[] = payload.map((conv: any) => {
        const conversation: Conversation = {
          id: conv.id,
          title: conv.title,
          date: conv.createdAt,
          updatedAt: conv?.updatedAt,
          messages: [],
        };
        return conversation;
      });
      return conversations;
    })
    .catch((_err) => {
      console.error("There was an issue fetching your data.", _err);
      const conversations: Conversation[] = historyListResponse.map(
        (conv: any) => {
          const conversation: Conversation = {
            id: conv.id,
            title: conv.title,
            date: conv.createdAt,
            updatedAt: conv?.updatedAt,
            messages: [],
          };
          return conversation;
        }
      );
      return conversations;
    });
  return response;
};

export const historyUpdate = async (
  messages: ChatMessage[],
  convId: string
): Promise<Response> => {
  const userId = getUserIdFromLocalStorage();
  const response = await apiFetch(`${baseURL}/history/update`, {
    method: "POST",
    body: JSON.stringify({
      conversation_id: convId,
      messages: messages,
    }),
    headers: {
      "Content-Type": "application/json",
      "X-Ms-Client-Principal-Id": userId || "",
    },
  })
    .then(async (res) => {
      return res;
    })
    .catch((_err) => {
      console.error("There was an issue fetching your data.");
      const errRes: Response = {
        ...new Response(),
        ok: false,
        status: 500,
      };
      return errRes;
    });
  return response;
};

export async function getLayoutConfig(): Promise<{
  appConfig: AppConfig;
  charts: ChartConfigItem[];
}> {
  const userId = getUserIdFromLocalStorage();
  const response = await apiFetch(`${baseURL}/api/layout-config`, {
    method: "GET",
    headers: {
      "Content-Type": "application/json",
      "X-Ms-Client-Principal-Id": userId || "",
    },
  });
  try {
    if (response.ok) {
      const layoutConfigData = await response.json();
      return layoutConfigData;
    }
  } catch {
    console.error("Failed to parse Layout config data");
  }
  return {
    appConfig: fallbackLayoutConfig.appConfig as AppConfig,
    charts: fallbackLayoutConfig.charts as unknown as ChartConfigItem[],
  };
}

export async function getIsChartDisplayDefault(): Promise<{
  isChartDisplayDefault: boolean;
}> {
  const userId = getUserIdFromLocalStorage();
  const response = await apiFetch(`${baseURL}/api/display-chart-default`, {
    method: "GET",
    headers: {
      "Content-Type": "application/json",
      "X-Ms-Client-Principal-Id": userId || "",
    },
  });
  try {
    if (response.ok) {
      const responseData = await response.json();
      const tempChartDisplayFlag = responseData.isChartDisplayDefault.toLowerCase() === 'true' ? true : false
      return { isChartDisplayDefault: tempChartDisplayFlag }
    }
  } catch {
    console.error("Failed to get chart config flag");
  }
  return {
    isChartDisplayDefault: true
  };
}

export async function callConversationApi(
  options: ConversationRequest,
  abortSignal: AbortSignal
): Promise<Response> {
  const userId = getUserIdFromLocalStorage();
  const response = await apiFetch(`${baseURL}/api/chat`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "X-Ms-Client-Principal-Id": userId || "",
    },
    body: JSON.stringify({
      messages: options.messages,
      conversation_id: options.id,
      last_rag_response: options.last_rag_response
    }),
    signal: abortSignal,
  });

  if (!response.ok) {
    const errorData = await response.json();
    throw new Error(JSON.stringify(errorData.error));
  }

  return response;
}

export const historyRename = async (
  convId: string,
  title: string
): Promise<Response> => {
  const userId = getUserIdFromLocalStorage();
  const response = await apiFetch(`${baseURL}/history/rename`, {
    method: "POST",
    body: JSON.stringify({
      conversation_id: convId,
      title: title,
    }),
    headers: {
      "Content-Type": "application/json",
      "X-Ms-Client-Principal-Id": userId || "",
    },
  })
    .then((res) => {
      return res;
    })
    .catch((_err) => {
      console.error("There was an issue fetching your data.");
      const errRes: Response = {
        ...new Response(),
        ok: false,
        status: 500,
      };
      return errRes;
    });
  return response;
};

export const historyDelete = async (convId: string): Promise<Response> => {
  const userId = getUserIdFromLocalStorage();
  const response = await apiFetch(`${baseURL}/history/delete`, {
    method: "DELETE",
    body: JSON.stringify({
      conversation_id: convId,
    }),
    headers: {
      "Content-Type": "application/json",
      "X-Ms-Client-Principal-Id": userId || "",
    },
  })
    .then((res) => {
      return res;
    })
    .catch((_err) => {
      console.error("There was an issue fetching your data.");
      const errRes: Response = {
        ...new Response(),
        ok: false,
        status: 500,
      };
      return errRes;
    });
  return response;
};

export const historyDeleteAll = async (): Promise<Response> => {
  const userId = getUserIdFromLocalStorage();
  const response = await fetch(`${baseURL}/history/delete_all`, {
    method: "DELETE",
    body: JSON.stringify({}),
    headers: {
      "Content-Type": "application/json",
      "X-Ms-Client-Principal-Id": userId || "",
    },
  })
    .then((res) => {
      return res;
    })
    .catch((_err) => {
      console.error("There was an issue fetching your data.");
      const errRes: Response = {
        ...new Response(),
        ok: false,
        status: 500,
      };
      return errRes;
    });
  return response;
};

export const historyEnsure = async (): Promise<CosmosDBHealth> => {
  const userId = getUserIdFromLocalStorage();
  const response = await fetch(`${baseURL}/history/ensure`, {
    method: "GET",
    headers: {
      "Content-Type": "application/json",
      "X-Ms-Client-Principal-Id": userId || "",
    },
  })
    .then(async (res) => {
      const respJson = await res.json();
      let formattedResponse;
      if (respJson.message) {
        formattedResponse = CosmosDBStatus.Working;
      } else {
        if (res.status === 500) {
          formattedResponse = CosmosDBStatus.NotWorking;
        } else if (res.status === 401) {
          formattedResponse = CosmosDBStatus.InvalidCredentials;
        } else if (res.status === 422) {
          formattedResponse = respJson.error;
        } else {
          formattedResponse = CosmosDBStatus.NotConfigured;
        }
      }
      if (!res.ok) {
        return {
          cosmosDB: false,
          status: formattedResponse,
        };
      } else {
        return {
          cosmosDB: true,
          status: formattedResponse,
        };
      }
    })
    .catch((err) => {
      console.error("There was an issue fetching your data.");
      return {
        cosmosDB: false,
        status: err,
      };
    });
  return response;
};

export const historyGenerate = async (
  options: ConversationRequest,
  abortSignal: AbortSignal,
  convId?: string
): Promise<Response> => {
  let body;
  if (convId) {
    body = JSON.stringify({
      conversation_id: convId,
      messages: options.messages,
    });
  } else {
    body = JSON.stringify({
      messages: options.messages,
    });
  }
  const userId = getUserIdFromLocalStorage();
  const response = await fetch(`${baseURL}/history/generate`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "X-Ms-Client-Principal-Id": userId || "",
    },
    body: body,
    signal: abortSignal,
  })
    .then((res) => {
      return res;
    })
    .catch((_err) => {
      console.error("There was an issue fetching your data.");
      return new Response();
    });
  return response;
};

export const fetchCitationContent = async (body: any) => {
  try {
    const response = await fetch(`${baseURL}/api/fetch-azure-search-content`, {
      headers: {
        "Content-Type": "application/json",
      },
      method: "POST",
      body: JSON.stringify(body),
    });
    if (!response.ok) {
      throw new Error(`Error: ${response.status} ${response.statusText}`);
    }
    const data = await response.json();
    return data;
  } catch (error) {
    console.error("Failed to fetch azure search content:", error);
    throw error;
  }
};
