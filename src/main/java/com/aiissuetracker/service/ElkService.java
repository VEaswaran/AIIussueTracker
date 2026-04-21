package com.aiissuetracker.service;

import com.aiissuetracker.config.ElkProperties;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.http.HttpEntity;
import org.springframework.http.HttpHeaders;
import org.springframework.http.HttpMethod;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;
import org.springframework.stereotype.Service;
import org.springframework.web.client.RestTemplate;

import java.time.Instant;
import java.time.temporal.ChronoUnit;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

@Service
public class ElkService {

    private final ElkProperties elkProperties;
    private final RestTemplate restTemplate;
    private final ObjectMapper objectMapper;

    @Value("${mock.enabled:true}")
    private boolean mockEnabled;

    public ElkService(ElkProperties elkProperties, RestTemplate restTemplate, ObjectMapper objectMapper) {
        this.elkProperties = elkProperties;
        this.restTemplate = restTemplate;
        this.objectMapper = objectMapper;
    }

    public String search(String traceId, String errorMessage, String serviceName, int timeRangeHours) {
        if (mockEnabled) {
            return buildMockElkResponse(traceId, errorMessage, serviceName, timeRangeHours);
        }
        return callRealElk(traceId, errorMessage, serviceName, timeRangeHours);
    }

    // ---------------------------------------------------------------------------
    // Mock response — realistic Elasticsearch _search payload
    // ---------------------------------------------------------------------------

    private String buildMockElkResponse(String traceId, String errorMessage,
                                        String serviceName, int timeRangeHours) {
        try {
            String svc  = serviceName  != null ? serviceName  : "order-service";
            String errMsg = errorMessage != null ? errorMessage : "Unexpected error during processing";
            Instant now = Instant.now();
            String dateIndex = now.toString().substring(0, 10).replace("-", ".");

            Map<String, Object> hit1 = hit(
                "logs-" + dateIndex, "yQx1CJUB_Pf9G2V3bHR2", 2.5,
                buildSource(traceId, "4e8b7f2c1a9d0e3f",
                    now.minus(5, ChronoUnit.MINUTES), "ERROR",
                    "com.example." + svc.replace("-", "") + ".ServiceHandler",
                    "Failed to process request: " + errMsg, svc,
                    "prod-app-node-03.internal", "http-nio-8080-exec-4",
                    "java.lang.RuntimeException: " + errMsg
                    + "\n\tat com.example.service.Handler.process(Handler.java:142)"
                    + "\n\tat com.example.service.Controller.handle(Controller.java:87)")
            );

            Map<String, Object> hit2 = hit(
                "logs-" + dateIndex, "zRy2DKUB_Pf9G2V3cIS3", 1.8,
                buildSource(traceId, "1a2b3c4d5e6f7890",
                    now.minus(5, ChronoUnit.MINUTES).minusMillis(2000), "WARN",
                    "com.example.gateway.ExternalGateway",
                    "External service call timed out after 5000ms", "gateway-service",
                    "prod-app-node-01.internal", "async-executor-2", null)
            );

            Map<String, Object> hit3 = hit(
                "logs-" + dateIndex, "aAz3ELUB_Pf9G2V3dJT4", 1.2,
                buildSource(traceId, "2c3d4e5f6a7b8901",
                    now.minus(5, ChronoUnit.MINUTES).minusMillis(4500), "INFO",
                    "com.example." + svc.replace("-", "") + ".ServiceHandler",
                    "Incoming request received for traceId=" + traceId, svc,
                    "prod-app-node-03.internal", "http-nio-8080-exec-4", null)
            );

            Map<String, Object> hitsTotal = map("value", 3, "relation", "eq");
            Map<String, Object> hitsBlock = new LinkedHashMap<>();
            hitsBlock.put("total", hitsTotal);
            hitsBlock.put("max_score", 2.5);
            hitsBlock.put("hits", List.of(hit1, hit2, hit3));

            Map<String, Object> shards = map("total", 5, "successful", 5, "skipped", 0, "failed", 0);

            Map<String, Object> response = new LinkedHashMap<>();
            response.put("took", 12);
            response.put("timed_out", false);
            response.put("_shards", shards);
            response.put("hits", hitsBlock);
            response.put("_mock", true);
            response.put("_query", Map.of(
                "traceId", traceId,
                "errorMessage", errMsg,
                "serviceName", svc,
                "timeRangeHours", timeRangeHours
            ));

            return objectMapper.writerWithDefaultPrettyPrinter().writeValueAsString(response);
        } catch (Exception e) {
            return "{\"error\": \"Failed to build mock ELK response: " + e.getMessage() + "\"}";
        }
    }

    private Map<String, Object> buildSource(String traceId, String spanId, Instant ts,
                                            String level, String logger, String message,
                                            String service, String host, String thread,
                                            String stackTrace) {
        Map<String, Object> src = new LinkedHashMap<>();
        src.put("@timestamp", ts.toString());
        src.put("traceId", traceId);
        src.put("spanId", spanId);
        src.put("level", level);
        src.put("logger", logger);
        src.put("message", message);
        src.put("service", service);
        src.put("host", host);
        src.put("thread", thread);
        src.put("stackTrace", stackTrace);
        return src;
    }

    private Map<String, Object> hit(String index, String id, double score, Map<String, Object> source) {
        Map<String, Object> h = new LinkedHashMap<>();
        h.put("_index", index);
        h.put("_id", id);
        h.put("_score", score);
        h.put("_source", source);
        return h;
    }

    private Map<String, Object> map(Object... pairs) {
        Map<String, Object> m = new LinkedHashMap<>();
        for (int i = 0; i < pairs.length; i += 2) {
            m.put(pairs[i].toString(), pairs[i + 1]);
        }
        return m;
    }

    // ---------------------------------------------------------------------------
    // Real Elasticsearch call (used when mock.enabled=false)
    // ---------------------------------------------------------------------------

    private String callRealElk(String traceId, String errorMessage,
                                String serviceName, int timeRangeHours) {
        try {
            String url = elkProperties.getBaseUrl() + "/" + elkProperties.getIndex() + "/_search";

            List<Object> mustClauses = new ArrayList<>();
            mustClauses.add(Map.of("term", Map.of("traceId", traceId)));
            if (errorMessage != null && !errorMessage.isBlank()) {
                mustClauses.add(Map.of("match", Map.of("message", errorMessage)));
            }

            List<Object> filterClauses = new ArrayList<>();
            if (serviceName != null && !serviceName.isBlank()) {
                filterClauses.add(Map.of("term", Map.of("service", serviceName)));
            }
            filterClauses.add(Map.of("range", Map.of("@timestamp",
                Map.of("gte", "now-" + timeRangeHours + "h", "lte", "now"))));

            Map<String, Object> boolQuery = new LinkedHashMap<>();
            boolQuery.put("must", mustClauses);
            boolQuery.put("filter", filterClauses);

            Map<String, Object> query = new LinkedHashMap<>();
            query.put("query", Map.of("bool", boolQuery));
            query.put("size", 20);
            query.put("sort", List.of(Map.of("@timestamp", "desc")));

            HttpHeaders headers = new HttpHeaders();
            headers.setContentType(MediaType.APPLICATION_JSON);
            if (elkProperties.getApiKey() != null && !elkProperties.getApiKey().isBlank()) {
                headers.set("Authorization", "ApiKey " + elkProperties.getApiKey());
            }

            HttpEntity<String> entity = new HttpEntity<>(
                objectMapper.writeValueAsString(query), headers);
            ResponseEntity<String> response = restTemplate.exchange(
                url, HttpMethod.POST, entity, String.class);
            return response.getBody();
        } catch (Exception e) {
            return "{\"error\": \"ELK query failed: " + e.getMessage() + "\"}";
        }
    }
}
