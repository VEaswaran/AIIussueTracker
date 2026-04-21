package com.aiissuetracker.tools;

import com.aiissuetracker.service.DynatraceService;
import org.springframework.ai.tool.annotation.Tool;
import org.springframework.ai.tool.annotation.ToolParam;
import org.springframework.stereotype.Component;

@Component
public class DynatraceTool {

    private final DynatraceService dynatraceService;

    public DynatraceTool(DynatraceService dynatraceService) {
        this.dynatraceService = dynatraceService;
    }

    @Tool(
        name = "dynatrace_trace",
        description = "Fetch distributed trace details from Dynatrace for a given trace ID. " +
            "Returns the full trace including entry service, total duration, status (OK/ERROR), " +
            "and every span in the call chain with spanId, parentSpanId, serviceName, operationName, " +
            "duration (ms), error flag, and errorMessage. " +
            "Use this tool to understand which service or span caused a failure and how long each hop took."
    )
    public String dynatraceTrace(
            @ToolParam(description = "The distributed trace ID to look up in Dynatrace (required)")
            String traceId) {

        return dynatraceService.getTrace(traceId);
    }
}
