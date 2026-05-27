# Chat API Endpoint Documentation

## Overview
This document describes the exact chat API endpoint used by the frontend chat component to send messages to the backend conversation agent.

---

## Endpoint Details

### POST `/api/chat`

**Full URL:** `{baseURL}/api/chat`

**HTTP Method:** `POST`

**Protocol:** HTTP/HTTPS

**Authentication:** Bearer Token (via Easy Auth) + Client Principal ID Header

---

## Request Structure

### Headers

| Header | Value | Required | Source |
|--------|-------|----------|--------|
| `Content-Type` | `application/json` | Yes | Frontend |
| `Authorization` | `Bearer {id_token}` | Yes | Easy Auth (injected by `apiFetch` interceptor) |
| `X-Ms-Client-Principal-Id` | `{userId}` | Yes | From `localStorage` (Entra Object ID) |

**Header Source:**
- `Authorization`: Injected by the `apiFetch` function's auth interceptor (line 663 in api.ts)
- `X-Ms-Client-Principal-Id`: Extracted from localStorage and used for user tracking (line 672)
- Backend retrieves user context using `get_authenticated_user_details(request.headers)` (line 75 in api_routes.py)

### Request Body (JSON)

```json
{
  "messages": [
    {
      "role": "user",
      "content": "user message text"
    },
    {
      "role": "assistant",
      "content": "previous assistant response"
    }
  ],
  "conversation_id": "unique-conversation-uuid",
  "last_rag_response": {
    "...": "RAG response data (optional)"
  }
}
```

**Body Field Details:**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `messages` | `array[object]` | Yes | Full conversation history with all prior messages. Each message has `role` ("user" or "assistant") and `content` (message text). |
| `conversation_id` | `string` | Yes | Unique identifier for the conversation session (stored in Cosmos DB). |
| `last_rag_response` | `object` | No | Previous RAG (Retrieval-Augmented Generation) response data passed from the client for context. |

**Body Source:**
```typescript
// Frontend: src/App/src/api/api.ts (lines 674-678)
body: JSON.stringify({
  messages: options.messages,
  conversation_id: options.id,
  last_rag_response: options.last_rag_response
})
```

---

## Response Structure

### Response Type: **Server-Sent Events (Streaming) / JSONL Format**

The endpoint returns a **streaming response** using `application/json-lines` media type. Each line is a separate JSON object followed by `\n\n`.

**Response Status:** `200 OK` (on success) or `403 Forbidden` (if access denied) or `500 Internal Server Error`

### Success Response Format

Each streamed line is a JSON object:

```json
{
  "id": "unique-chunk-id",
  "model": "rag-model",
  "created": 1234567890,
  "object": "extensions.chat.completion.chunk",
  "choices": [
    {
      "messages": [
        {
          "role": "assistant",
          "content": "response text chunk"
        }
      ],
      "delta": {
        "role": "assistant",
        "content": "response text chunk"
      }
    }
  ],
  "history_metadata": {...},
  "apim-request-id": ""
}
```

**Response Field Details:**

| Field | Type | Description |
|-------|------|-------------|
| `id` | `string` | Unique UUID for this chunk |
| `model` | `string` | Always "rag-model" |
| `created` | `integer` | Unix timestamp when chunk was created |
| `object` | `string` | Always "extensions.chat.completion.chunk" |
| `choices[0].messages` | `array` | Array containing the assistant message chunk |
| `choices[0].delta` | `object` | Streaming delta with role and content |
| `history_metadata` | `object` | Metadata from the request (passed through) |

### Error Response Format

```json
{
  "error": "Error message describing the issue"
}
```

**Possible Error Cases:**

| Status | Error Message | Reason |
|--------|---------------|--------|
| `403` | `"Access denied. Billing and Payment Issues requires the faturamento role."` | User lacks required role to access billing topics (query contains billing keywords). |
| `500` | `"An internal error occurred while processing the conversation."` | Backend exception occurred. |
| `500` | `"Rate limit is exceeded. Try again in X seconds."` | Azure OpenAI rate limit exceeded. |

### Access Control (RBAC)

The endpoint implements query-based access control:

**Billing Topics Restriction:**
- Keywords: "billing", "billing issues", "payments", "payment problems", "faturamento", "pagamento", "cobrança"
- If query contains these keywords AND user lacks "faturamento" role → **403 Forbidden**
- Implementation: Lines 173-185 in api_routes.py

---

## Backend Handler

### Location
**File:** `src/api/api/api_routes.py`  
**Function:** `conversation()` (async)  
**Lines:** 162-201

### Handler Flow

```
1. Parse request JSON → extract messages, conversation_id, query
2. Check RBAC: Verify user has access to billing topics if query contains billing keywords
3. Initialize ChatService with authenticated request
4. Call chat_service.stream_chat_request(request_json, conversation_id, query)
5. Return StreamingResponse with media_type="application/json-lines"
```

### Backend Processing

**File:** `src/api/services/chat_service.py`

**Method:** `stream_chat_request()` (async generator)  
**Lines:** 248-364

**Processing Steps:**

1. **Language Detection** (line 253)
   - Detects language from first user message (English, Portuguese, or Spanish)
   - Cached per conversation for consistency

2. **Guardrails** (lines 256-262)
   - Query classification using `classify_query()`
   - Blocks out-of-scope queries with guardrail message
   - Scopes: IN_SCOPE, OUT_OF_SCOPE, OFFENSIVE, PII_DETECTED

3. **Memory/Context** (lines 254, 291-292)
   - Retrieves memory context via FoundryMemoryService
   - Enriches query with historical context

4. **Agent Invocation** (lines 296-301)
   - Calls `stream_openai_text()` which:
     - Manages Azure AI agent threads (via ExpCache with 1-hour TTL)
     - Uses AzureAIAgentThread for session management
     - Streams text from Azure OpenAI with truncation strategy (last 4 messages)
     - Implements enhanced guardrails during streaming

5. **Response Formatting** (lines 308-339)
   - Wraps each streamed chunk in chat completion format
   - Adds metadata (id, model, created timestamp)
   - Yields JSON-formatted lines

6. **Error Handling** (lines 347-362)
   - AgentException: Rate limit or runtime errors
   - Generic Exception: Catches all other errors
   - Returns JSON error objects

7. **Memory Update** (lines 342-345)
   - Asynchronously saves conversation turn to memory service
   - Called after streaming completes

---

## Frontend Usage

### Location
**File:** `src/App/src/api/api.ts`  
**Function:** `callConversationApi()`  
**Lines:** 663-703

### Frontend Handler Flow

```typescript
1. Extract userId from localStorage (Entra Object ID)
2. Call apiFetch() with POST to /api/chat
3. apiFetch() interceptor:
   - Adds Authorization header with Bearer token from Easy Auth
   - Adds X-Ms-Client-Principal-Id header with userId
4. Return raw Response object (supports streaming)
```

### Response Parsing

**File:** `src/App/src/components/Chat/Chat.tsx`

The Chat component parses the streaming response by:

1. Reading the Response body as a stream
2. Splitting by `\n\n` delimiter
3. Parsing each line as JSON
4. Extracting `choices[0].delta.content` for display
5. Accumulating text for full message context

---

## Request Flow Diagram

```
┌─────────────────────────────┐
│  Frontend Chat Component    │
│  (Chat.tsx)                 │
└──────────────┬──────────────┘
               │
               ├─ User types message
               │
               ├─ collects messages array
               │
               ├─ calls callConversationApi()
               │
┌──────────────▼──────────────────────────────┐
│  callConversationApi()                       │
│  (src/App/src/api/api.ts, line 663)          │
│                                              │
│  ├─ Adds Authorization: Bearer {id_token}  │
│  ├─ Adds X-Ms-Client-Principal-Id: userId  │
│  ├─ POST body: {messages, conversation_id} │
│  └─ Returns Response (streaming)            │
└──────────────┬──────────────────────────────┘
               │
   HTTP POST /api/chat
               │
┌──────────────▼──────────────────────────────┐
│  Backend: conversation() handler             │
│  (src/api/api/api_routes.py, line 162)       │
│                                              │
│  ├─ Verify RBAC (billing topics)            │
│  ├─ Extract query from messages             │
│  └─ Call ChatService.stream_chat_request()  │
└──────────────┬──────────────────────────────┘
               │
┌──────────────▼──────────────────────────────┐
│  ChatService.stream_chat_request()           │
│  (src/api/services/chat_service.py, line248)│
│                                              │
│  ├─ Detect language                         │
│  ├─ Check guardrails                        │
│  ├─ Fetch memory context                    │
│  ├─ Call stream_openai_text()               │
│  │  └─ Stream from Azure OpenAI             │
│  ├─ Format each chunk as chat completion    │
│  ├─ Yield JSON-line responses               │
│  └─ Save memory context async               │
└──────────────┬──────────────────────────────┘
               │
   application/json-lines stream
               │
┌──────────────▼──────────────────────────────┐
│  Frontend Response Handler                   │
│  (Chat.tsx)                                  │
│                                              │
│  ├─ Parse streamed JSON chunks              │
│  ├─ Extract delta.content from each chunk   │
│  └─ Accumulate and display in chat          │
└──────────────────────────────────────────────┘
```

---

## Security & Authentication

### Authentication Mechanism

1. **Easy Auth Integration**
   - Frontend loads user context from `/.auth/me` (bootstrapped)
   - Azure App Service manages authentication transparently
   - Token stored in memory (not localStorage for security)

2. **Bearer Token**
   - Passed in `Authorization: Bearer {id_token}` header
   - Backend validates via Azure App Service middleware
   - Claims extracted by `get_authenticated_user_details()`

3. **User Tracking**
   - `X-Ms-Client-Principal-Id` header: Entra Object ID
   - Backend uses this for per-user request tracking
   - Enables audit logging and rate limiting per user

4. **RBAC (Role-Based Access Control)**
   - Billing queries blocked unless user has "faturamento" role
   - Roles retrieved via `get_current_user_roles(request)`
   - Enforced at endpoint handler level (pre-agent)

5. **Guardrails**
   - Multi-layer protection against out-of-scope queries
   - Detects: out-of-scope topics, offensive content, PII patterns
   - Blocks query at backend before sending to OpenAI

---

## Important Notes

1. **Streaming Response**
   - Response is **not** traditional SSE (Server-Sent Events)
   - Uses `application/json-lines` format (JSON Lines / NDJSON)
   - Each line is a complete JSON object followed by `\n\n`
   - Frontend must handle streaming line-by-line

2. **Conversation Persistence**
   - `conversation_id` maps to Cosmos DB document
   - Agent threads cached in memory for 1 hour (TTL)
   - Full message history sent with every request (no server-side session)

3. **Agent Thread Management**
   - Azure AI Agent Threads cached per conversation_id
   - LRU eviction and TTL expiration trigger thread deletion
   - Truncation strategy keeps last 4 messages in context

4. **Language Support**
   - English, Portuguese, Spanish automatically detected
   - Agent responds in detected language
   - Language cached per conversation

5. **Memory Service**
   - Optional FoundryMemoryService for context persistence
   - Searches memory before querying agent
   - Updates memory asynchronously after response

6. **Rate Limiting**
   - Handled by Azure OpenAI backend
   - Returns 429 error in AgentException
   - Frontend can parse and display retry hint

---

## Testing the Endpoint

### cURL Example

```bash
curl -X POST "http://localhost:5001/api/chat" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer {your_id_token}" \
  -H "X-Ms-Client-Principal-Id: {user_object_id}" \
  -d '{
    "messages": [
      {
        "role": "user",
        "content": "What are call metrics for today?"
      }
    ],
    "conversation_id": "conv-12345",
    "last_rag_response": null
  }'
```

### Expected Response (Streamed JSONL)

```
{"id":"uuid1","model":"rag-model","created":1234567890,"object":"extensions.chat.completion.chunk","choices":[{"messages":[{"role":"assistant","content":"Today"}],"delta":{"role":"assistant","content":"Today"}}],"history_metadata":{},"apim-request-id":""}

{"id":"uuid2","model":"rag-model","created":1234567891,"object":"extensions.chat.completion.chunk","choices":[{"messages":[{"role":"assistant","content":" we"}],"delta":{"role":"assistant","content":" we"}}],"history_metadata":{},"apim-request-id":""}
```

---

## Related Files

| File | Purpose |
|------|---------|
| `src/App/src/api/api.ts` | Frontend API client, `callConversationApi()` function |
| `src/App/src/components/Chat/Chat.tsx` | Chat UI component, response parsing |
| `src/api/api/api_routes.py` | FastAPI route handler, `conversation()` function |
| `src/api/services/chat_service.py` | ChatService class, streaming logic |
| `src/api/auth/auth_utils.py` | User authentication utilities |
| `src/api/auth/rbac.py` | Role-based access control |
| `src/api/helpers/guardrails_enhanced.py` | Query guardrails implementation |

---

## Summary

**Endpoint:** `POST /api/chat`  
**Protocol:** HTTP/HTTPS with Bearer token + client principal header  
**Request:** JSON with messages array, conversation_id, optional RAG response  
**Response:** Streaming JSON Lines (NDJSON) with chat completion chunks  
**Authentication:** Easy Auth (Bearer token) + X-Ms-Client-Principal-Id header  
**Access Control:** RBAC for billing topics  
**Agent Backend:** Azure OpenAI via ConversationAgentFactory  
**Caching:** Agent threads cached per conversation (1-hour TTL)  
**Language:** Auto-detected per conversation, supports EN/PT/ES  
