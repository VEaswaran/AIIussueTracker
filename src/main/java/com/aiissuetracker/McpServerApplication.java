package com.aiissuetracker;

import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;
import org.springframework.boot.context.properties.EnableConfigurationProperties;

import com.aiissuetracker.config.DynatraceProperties;
import com.aiissuetracker.config.ElkProperties;

@SpringBootApplication
@EnableConfigurationProperties({ElkProperties.class, DynatraceProperties.class})
public class McpServerApplication {

    public static void main(String[] args) {
        SpringApplication.run(McpServerApplication.class, args);
    }
}
