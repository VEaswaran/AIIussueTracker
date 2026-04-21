package com.aiissuetracker.config;

import com.aiissuetracker.tools.DynatraceTool;
import com.aiissuetracker.tools.ElkTool;
import org.springframework.ai.tool.ToolCallbackProvider;
import org.springframework.ai.tool.method.MethodToolCallbackProvider;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.web.client.RestTemplate;

@Configuration
public class AppConfig {

    @Bean
    public RestTemplate restTemplate() {
        return new RestTemplate();
    }

    /**
     * Registers all @Tool-annotated methods with the MCP server.
     * The spring-ai-mcp-server-webmvc auto-configuration discovers ToolCallbackProvider beans
     * and exposes each @Tool method as an MCP tool over SSE/HTTP.
     */
    @Bean
    public ToolCallbackProvider issueTrackerTools(ElkTool elkTool, DynatraceTool dynatraceTool) {
        return MethodToolCallbackProvider.builder()
                .toolObjects(elkTool, dynatraceTool)
                .build();
    }
}
