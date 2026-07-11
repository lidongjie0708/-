package com.yuyuan.thumb.config;

import org.springframework.boot.web.client.RestTemplateBuilder;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.web.client.RestTemplate;

import java.time.Duration;

/**
 * RestTemplate 配置
 * <p>
 * 用于调用外部 Python Agent 微服务的 HTTP 客户端。
 * 生产环境建议配合连接池和超时控制使用。
 */
@Configuration
public class RestTemplateConfig {

    @Bean
    public RestTemplate restTemplate(RestTemplateBuilder builder, AgentConfig agentConfig) {
        return builder
                .setConnectTimeout(Duration.ofMillis(agentConfig.getConnectTimeout()))
                .setReadTimeout(Duration.ofMillis(agentConfig.getReadTimeout()))
                .build();
    }
}
