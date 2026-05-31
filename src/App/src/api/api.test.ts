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
      delete (global as typeof globalThis & { fetch?: typeof fetch }).fetch;
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
        json: async () => [{ id_token: "token-123", user_id: "test@example.com" }],
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
    expect(requestHeaders.get("Authorization")).toBe("Bearer token-123");
    expect(requestHeaders.get("X-User-Id")).toBe("test@example.com");
  });

  it("omits X-User-Id when Easy Auth does not return user_id", async () => {
    const fetchMock = jest
      .fn()
      .mockResolvedValueOnce({ ok: true })
      .mockResolvedValueOnce({
        ok: true,
        json: async () => [{ id_token: "token-456" }],
      })
      .mockResolvedValueOnce({ ok: true })
      .mockResolvedValueOnce({
        ok: true,
        json: async () => [{ id_token: "token-456" }],
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
    expect(requestHeaders.get("Authorization")).toBe("Bearer token-456");
    expect(requestHeaders.get("X-User-Id")).toBeNull();
  });
});
