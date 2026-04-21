package com.aiissuetracker.service;

import com.aiissuetracker.config.DynatraceProperties;
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
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

@Service
public class DynatraceService {

    private final DynatraceProperties dynatraceProperties;
    private final RestTemplate restTemplate;
    private final ObjectMapper objectMapper;

    @Value("${mock.enabled:true}")
    private boolean mockEnabled;

    public DynatraceService(DynatraceProperties dynatraceProperties,
                            RestTemplate restTemplate,
                            ObjectMapper objectMapper) {
        this.dynatraceProperties = dynatraceProperties;
        this.restTemplate = restTemplate;
        this.objectMapper = objectMapper;
    }

    public String getTrace(String traceId) {
        if (mockEnabled) {
            return buildMockDynatraceResponse(traceId);
        }
        return callRealDynatrace(traceId);
    }

    // ---------------------------------------------------------------------------
    // Mock response — realistic Dynatrace Distributed Traces API payload
    // ---------------------------------------------------------------------------

    private String buildMockDynatraceResponse(String traceId) {
        try {
            Instant now = Instant.now();
            long startMs = now.minus(5, ChronoUnit.MINUTES).toEpochMilli();

            Map<String, Object> rootSpan = span(
                "4e8b7f2c1a9d0e3f", null,
                "order-service", "POST /api/orders",
                startMs, 1250, true,
                "java.lang.RuntimeException: Failed to process order — null payment reference",
                Map.of("http.method", "POST",
                       "http.url", "/api/orders",
                       "http.status_code", "500",
                       "peer.service", "payment-service")
            );

            Map<String, Object> paymentSpan = span(
                "1a2b3c4d5e6f7890", "4e8b7f2c1a9d0e3f",
                "payment-service", "processPayment",
                startMs + 150, 800, false, null,
                Map.of("db.type", "postgresql",
                       "db.statement", "INSERT INTO payments (order_id, amount, status) VALUES (?, ?, ?)",
                       "db.instance", "payments-db-primary")
            );

            Map<String, Object> inventorySpan = span(
                "2c3d4e5f6a7b8901", "4e8b7f2c1a9d0e3f",
                "inventory-service", "checkStock",
                startMs + 200, 150, false, null,
                Map.of("inventory.itemId", "ITEM-42",
                       "inventory.quantity", "5",
                       "cache.hit", "false")
            );

            Map<String, Object> notifySpan = span(
                "3d4e5f6a7b8c9012", "4e8b7f2c1a9d0e3f",
                "notification-service", "sendOrderConfirmation",
                startMs + 1000, 200, true,
                "Connection timeout to SMTP relay after 200ms",
                Map.of("messaging.system", "smtp",
                       "messaging.destination", "customer@example.com")
            );

            Map<String, Object> response = new LinkedHashMap<>();
            response.put("traceId", traceId);
            response.put("status", "ERROR");
            response.put("startTime", startMs);
            response.put("endTime", startMs + 1250);
            response.put("duration", 1250);
            response.put("entryServiceName", "order-service");
            response.put("entryOperation", "POST /api/orders");
            response.put("spanCount", 4);
            response.put("errorSpanCount", 2);
            response.put("spans", List.of(rootSpan, paymentSpan, inventorySpan, notifySpan));
            response.put("_mock", true);

            return objectMapper.writerWithDefaultPrettyPrinter().writeValueAsString(response);
        } catch (Exception e) {
            return "{\"error\": \"Failed to build mock Dynatrace response: " + e.getMessage() + "\"}";
        }
    }

    private Map<String, Object> span(String spanId, String parentSpanId,
                                     String serviceName, String operationName,
                                     long startTime, long duration,
                                     boolean error, String errorMessage,
                                     Map<String, String> tags) {
        Map<String, Object> s = new LinkedHashMap<>();
        s.put("spanId", spanId);
        s.put("parentSpanId", parentSpanId);
        s.put("serviceName", serviceName);
        s.put("operationName", operationName);
        s.put("startTime", startTime);
        s.put("duration", duration);
        s.put("error", error);
        s.put("errorMessage", errorMessage);
        s.put("tags", tags);
        return s;
    }

    // ---------------------------------------------------------------------------
    // Real Dynatrace call (used when mock.enabled=false)
    // ---------------------------------------------------------------------------

    private String callRealDynatrace(String traceId) {
        try {
            String url = dynatraceProperties.getBaseUrl() + "/api/v2/traces/" + traceId;

            HttpHeaders headers = new HttpHeaders();
            headers.set("Authorization", "Api-Token " + dynatraceProperties.getApiToken());
            headers.setAccept(List.of(MediaType.APPLICATION_JSON));

            HttpEntity<Void> entity = new HttpEntity<>(headers);
            ResponseEntity<String> response = restTemplate.exchange(
                url, HttpMethod.GET, entity, String.class);
            return response.getBody();
        } catch (Exception e) {
            return "{\"error\": \"Dynatrace query failed: " + e.getMessage() + "\"}";
        }
    }
}
