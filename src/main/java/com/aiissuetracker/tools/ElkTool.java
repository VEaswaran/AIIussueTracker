package com.aiissuetracker.tools;

import com.aiissuetracker.service.ElkService;
import org.springframework.ai.tool.annotation.Tool;
import org.springframework.ai.tool.annotation.ToolParam;
import org.springframework.stereotype.Component;

@Component
public class ElkTool {

    private final ElkService elkService;

    public ElkTool(ElkService elkService) {
        this.elkService = elkService;
    }

    @Tool(
        name = "elk_search",
        description = "Search ELK (Elasticsearch/Kibana) logs to trace and diagnose a reported issue. " +
            "Provide the distributed traceId to retrieve all log entries belonging to that transaction. " +
            "Optionally supply an errorMessage keyword (e.g. 'NullPointerException'), a serviceName " +
            "(e.g. 'order-service'), and a timeRangeHours look-back window (default 24 h). " +
            "Returns Elasticsearch _search hits with @timestamp, log level, message, stackTrace, and host."
    )
    public String elkSearch(
            @ToolParam(description = "The distributed trace ID to search for in ELK logs (required)")
            String traceId,

            @ToolParam(description = "Error message keyword or text to filter relevant log entries (optional)",
                       required = false)
            String errorMessage,

            @ToolParam(description = "Service or application name to narrow the search, e.g. 'order-service' (optional)",
                       required = false)
            String serviceName,

            @ToolParam(description = "Look-back window in hours; how far back to search in the log timeline (optional, default 24)",
                       required = false)
            Integer timeRangeHours) {

        return elkService.search(traceId, errorMessage, serviceName,
                timeRangeHours != null ? timeRangeHours : 24);
    }
}
