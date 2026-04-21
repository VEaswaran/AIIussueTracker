# AI Issue Tracker — MCP Server

Spring Boot 3.3 / Java 17 MCP server that exposes two tools for AI-driven issue triage:

| Tool | Purpose |
|---|---|
| `elk_search` | Search Elasticsearch logs by trace ID, error message, service, time range |
| `dynatrace_trace` | Fetch full distributed trace + spans from Dynatrace by trace ID |

Transport: **SSE over HTTP** (`spring-ai-starter-mcp-server-webmvc`)

---

## Prerequisites

- Java 17+
- Maven 3.8+

---

## Build & Run

```bash
mvn spring-boot:run
```

Or build a fat JAR:

```bash
mvn package
java -jar target/ai-issue-tracker-mcp-1.0.0.jar
```

Server starts on **http://localhost:8080**

---

## MCP Endpoints

| Endpoint | Method | Purpose |
|---|---|---|
| `/sse` | GET | SSE connection for MCP clients |
| `/mcp/messages` | POST | MCP JSON-RPC message channel |

---

## Register in MCP Registry

### Claude Desktop (`claude_desktop_config.json`)

```json
{
  "mcpServers": {
    "ai-issue-tracker": {
      "url": "http://localhost:8080/sse"
    }
  }
}
```

### Cursor / Windsurf (`.cursor/mcp.json` or `.windsurf/mcp.json`)

```json
{
  "mcpServers": {
    "ai-issue-tracker": {
      "url": "http://localhost:8080/sse",
      "type": "sse"
    }
  }
}
```

---

## Tool Parameters

### `elk_search`

| Parameter | Required | Description |
|---|---|---|
| `traceId` | Yes | Distributed trace ID to search in ELK |
| `errorMessage` | No | Keyword to filter log messages |
| `serviceName` | No | Service/app name filter (e.g. `order-service`) |
| `timeRangeHours` | No | Look-back window in hours (default: 24) |

### `dynatrace_trace`

| Parameter | Required | Description |
|---|---|---|
| `traceId` | Yes | Distributed trace ID to look up in Dynatrace |

---

## Configuration

All config lives in `src/main/resources/application.properties`:

```properties
# Flip to false once real credentials are available
mock.enabled=true

# ELK
elk.base-url=http://localhost:9200
elk.index=logs-*
elk.api-key=CHANGEME

# Dynatrace
dynatrace.base-url=https://YOUR_ENV.live.dynatrace.com
dynatrace.api-token=CHANGEME
```

When `mock.enabled=true`, both tools return realistic fake JSON responses.  
When `mock.enabled=false`, they call the real REST APIs using the configured credentials.

---

## Example Chat Interaction

> **User:** I'm seeing a 500 error in the order service. The trace ID is `abc123-xyz`. Can you check what happened?

The AI model will:
1. Call `elk_search(traceId="abc123-xyz", serviceName="order-service")` → retrieves log entries
2. Call `dynatrace_trace(traceId="abc123-xyz")` → retrieves full span chain
3. Summarise root cause, affected services, and error messages

---

## Project Structure

```
src/main/java/com/aiissuetracker/
├── McpServerApplication.java          Entry point
├── config/
│   ├── AppConfig.java                 RestTemplate + ToolCallbackProvider beans
│   ├── ElkProperties.java             @ConfigurationProperties for ELK
│   └── DynatraceProperties.java       @ConfigurationProperties for Dynatrace
├── service/
│   ├── ElkService.java                Mock + real Elasticsearch HTTP logic
│   └── DynatraceService.java          Mock + real Dynatrace HTTP logic
└── tools/
    ├── ElkTool.java                   @Tool: elk_search
    └── DynatraceTool.java             @Tool: dynatrace_trace
```
