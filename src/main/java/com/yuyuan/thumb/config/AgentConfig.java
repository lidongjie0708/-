package com.yuyuan.thumb.config;

import lombok.Data;
import org.springframework.boot.context.properties.ConfigurationProperties;
import org.springframework.context.annotation.Configuration;

/**
 * Agent 微服务连接配置
 * <p>
 * 通过配置中心或 application.yml 管理，生产环境通过环境变量覆盖。
 * 用于 Java 后端调用 Python Agent 服务的 HTTP 客户端配置。
 */
@Data
@Configuration
@ConfigurationProperties(prefix = "agent")
public class AgentConfig {

    /** Agent 服务基础 URL，如 http://localhost:8000 */
    private String baseUrl = "http://localhost:8000";

    /** HTTP 连接超时时间（毫秒） */
    private int connectTimeout = 5000;

    /** HTTP 读取超时时间（毫秒） */
    private int readTimeout = 30000;

    /** 最大重试次数 */
    private int maxRetries = 2;

    /** 是否启用 Agent 功能（生产环境通过此开关控制降级） */
    private boolean enabled = true;

    private String internalToken;
}
