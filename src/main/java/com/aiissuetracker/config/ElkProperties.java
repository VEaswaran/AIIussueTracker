package com.aiissuetracker.config;

import org.springframework.boot.context.properties.ConfigurationProperties;

@ConfigurationProperties(prefix = "elk")
public class ElkProperties {

    private String baseUrl = "http://localhost:9200";
    private String index = "logs-*";
    private String apiKey = "";

    public String getBaseUrl() { return baseUrl; }
    public void setBaseUrl(String baseUrl) { this.baseUrl = baseUrl; }

    public String getIndex() { return index; }
    public void setIndex(String index) { this.index = index; }

    public String getApiKey() { return apiKey; }
    public void setApiKey(String apiKey) { this.apiKey = apiKey; }
}
