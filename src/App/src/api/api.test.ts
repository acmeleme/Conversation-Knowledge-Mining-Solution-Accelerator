export {};

describe("apiFetch X-User-Id propagation", () => {
  const originalFetch = global.fetch;
  const originalApiBaseUrl = process.env.REACT_APP_API_BASE_URL;

  beforeEach(() => {
    jest.resetModules();
    jest.clearAllMocks();
    localStorage.clear();
    process.env.REACT_APP_API_BASE_URL = "http://localhost";
  });

  afterEach(() => {
    if (originalFetch) {
      global.fetch = originalFetch;
    } else {
      delete (global as any).fetch;
    }

    if (originalApiBaseUrl === undefined) {
      delete process.env.REACT_APP_API_BASE_URL;
    } else {
      process.env.REACT_APP_API_BASE_URL = originalApiBaseUrl;
    }
  });

  it("adds X-User-Id when Easy Auth exposes user_id", async () => {
    const fetchMock = jest
      .fn()
      .mockResolvedValueOnce({ ok: true })
      .mockResolvedValueOnce({
        ok: true,
        json: async () => [{ id_token: "id-token-123", access_token: "access-token-123", user_id: "test@example.com" }],
      })
      .mockResolvedValueOnce({
        ok: true,
        status: 200,
        statusText: "OK",
        json: async () => ({ ok: true }),
      });

    global.fetch = fetchMock as unknown as typeof fetch;

    const { fetchChartData } = await import("./api");
    await fetchChartData();

    expect(fetchMock).toHaveBeenCalledTimes(3);
    expect(fetchMock.mock.calls[2][0]).toBe("http://localhost/api/fetchChartData");

    const requestHeaders = fetchMock.mock.calls[2][1]?.headers as Headers;
    expect(requestHeaders.get("Authorization")).toContain("access-token-123");
    expect(requestHeaders.get("X-User-Id")).toBe("test@example.com");
    expect(fetchMock.mock.calls[2][1]?.credentials).toBe("include");
  });

  it("omits X-User-Id when Easy Auth does not return user_id", async () => {
    const fetchMock = jest
      .fn()
      .mockResolvedValueOnce({ ok: true })
      .mockResolvedValueOnce({
        ok: true,
        json: async () => [{ id_token: "id-token-456" }],
      })
      .mockResolvedValueOnce({ ok: true })
      .mockResolvedValueOnce({
        ok: true,
        json: async () => [{ id_token: "id-token-456" }],
      })
      .mockResolvedValueOnce({
        ok: true,
        status: 200,
        statusText: "OK",
        json: async () => ({ ok: true }),
      });

    global.fetch = fetchMock as unknown as typeof fetch;

    const { fetchChartData } = await import("./api");
    await fetchChartData();

    expect(fetchMock).toHaveBeenCalledTimes(5);

    const requestHeaders = fetchMock.mock.calls[4][1]?.headers as Headers;
    expect(requestHeaders.get("Authorization")).toContain("id-token-456");
    expect(requestHeaders.get("X-User-Id")).toBeNull();
    expect(fetchMock.mock.calls[4][1]?.credentials).toBe("include");
  });
});

describe("fetchChartDataWithFilters fallback topic filtering", () => {
  const originalFetch = global.fetch;

  beforeEach(() => {
    jest.resetModules();
    jest.clearAllMocks();
  });

  afterEach(() => {
    if (originalFetch) {
      global.fetch = originalFetch;
    } else {
      delete (global as any).fetch;
    }
  });

  it("filters key phrases by selected topic when fallback is used", async () => {
    global.fetch = jest.fn().mockRejectedValue(new Error("network")) as unknown as typeof fetch;

    const { fetchChartDataWithFilters } = await import("./api");

    const charts = await fetchChartDataWithFilters({
      selected_filters: {
        Topic: ["Seguro — Sinistros e Indenizações"],
        Sentiment: ["all"],
      },
    });

    const keyPhrasesChart = charts.find((chart: any) => chart.id === "KEY_PHRASES");
    expect(keyPhrasesChart).toBeDefined();

    const texts = (keyPhrasesChart?.chart_value ?? []).map((item: any) => item.text);
    expect(texts).toContain("sinistro pendente");
    expect(texts).not.toContain("fatura cartão");
  });
});

describe("Easy Auth endpoint discovery", () => {
  const originalFetch = global.fetch;
  const originalApiBaseUrl = process.env.REACT_APP_API_BASE_URL;

  beforeEach(() => {
    jest.resetModules();
    jest.clearAllMocks();
    process.env.REACT_APP_API_BASE_URL = "https://example.com/api";
  });

  afterEach(() => {
    if (originalFetch) {
      global.fetch = originalFetch;
    } else {
      delete (global as any).fetch;
    }

    if (originalApiBaseUrl === undefined) {
      delete process.env.REACT_APP_API_BASE_URL;
    } else {
      process.env.REACT_APP_API_BASE_URL = originalApiBaseUrl;
    }
  });

  it("uses API base origin for remote /.auth/me lookup when base URL contains path", async () => {
    const fetchMock = jest
      .fn()
      .mockResolvedValueOnce({ ok: true })
      .mockResolvedValueOnce({ ok: false })
      .mockResolvedValueOnce({
        ok: true,
        json: async () => [{ id_token: "id-token-origin" }],
      })
      .mockResolvedValueOnce({
        ok: true,
        status: 200,
        statusText: "OK",
        json: async () => ({ ok: true }),
      });

    global.fetch = fetchMock as unknown as typeof fetch;

    const { fetchChartData } = await import("./api");
    await fetchChartData();

    const calledEndpoints = fetchMock.mock.calls.map((call) => call[0]);
    expect(calledEndpoints).toContain("https://example.com/.auth/me");
    expect(calledEndpoints).not.toContain("https://example.com/api/.auth/me");
  });
});
