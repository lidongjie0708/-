package com.yuyuan.thumb.service.agent;

import com.yuyuan.thumb.config.AgentConfig;
import com.yuyuan.thumb.model.dto.agent.AgentRequest;
import com.yuyuan.thumb.model.dto.agent.AgentResponse;
import lombok.extern.slf4j.Slf4j;
import org.springframework.core.ParameterizedTypeReference;
import org.springframework.http.HttpEntity;
import org.springframework.http.HttpHeaders;
import org.springframework.http.HttpMethod;
import org.springframework.http.ResponseEntity;
import org.springframework.stereotype.Component;
import org.springframework.util.StringUtils;
import org.springframework.web.client.RestClientException;
import org.springframework.web.client.RestTemplate;

import java.util.Collections;
import java.util.Map;

/**
 * Agent 微服务 HTTP 调用客户端
 * <p>
 * 封装对 Python Agent 服务的 HTTP 请求，支持重试和异常转换。
 * 生产环境可在此处集成熔断（Resilience4j）和链路追踪（SkyWalking）。
 */
@Slf4j
@Component
public class AgentClient {

    private final RestTemplate restTemplate;
    private final AgentConfig agentConfig;

    public AgentClient(RestTemplate restTemplate, AgentConfig agentConfig) {
        this.restTemplate = restTemplate;
        this.agentConfig = agentConfig;
    }

    /**
     * 调用 Agent 服务执行任务
     */
    public AgentResponse execute(AgentRequest request) {
        if (!agentConfig.isEnabled()) {
            log.warn("Agent 功能已禁用，跳过任务: action={}, contentId={}", request.getAction(), request.getContentId());
            return buildDisabledResponse(request);
        }

        String url = agentConfig.getBaseUrl() + "/api/agent/execute";
        HttpEntity<AgentRequest> httpEntity = new HttpEntity<>(request, buildHeaders());

        int retries = 0;
        int maxRetries = Math.max(agentConfig.getMaxRetries(), 0);

        while (retries <= maxRetries) {
            try {
                ResponseEntity<AgentResponse> response = restTemplate.exchange(
                        url,
                        HttpMethod.POST,
                        httpEntity,
                        new ParameterizedTypeReference<>() {}
                );
                AgentResponse body = response.getBody();
                if (body != null) {
                    log.info("Agent 调用成功: action={}, contentId={}, success={}",
                            request.getAction(), request.getContentId(), body.isSuccess());
                    return body;
                }
                return AgentResponse.builder()
                        .success(false)
                        .action(request.getAction())
                        .result(Collections.emptyMap())
                        .errorMessage("Agent 返回空响应")
                        .build();
            } catch (RestClientException e) {
                retries++;
                if (retries <= maxRetries) {
                    log.warn("Agent 调用失败，第 {} 次重试: action={}, error={}",
                            retries, request.getAction(), e.getMessage());
                } else {
                    log.error("Agent 调用失败，已耗尽重试次数: action={}, contentId={}, error={}",
                            request.getAction(), request.getContentId(), e.getMessage());
                    return AgentResponse.builder()
                            .success(false)
                            .action(request.getAction())
                            .result(Collections.emptyMap())
                            .errorMessage("Agent 服务不可用: " + e.getMessage())
                            .build();
                }
            }
        }

        return buildDisabledResponse(request);
    }

    /**
     * 健康检查：探测 Agent 服务是否存活
     */
    public boolean healthCheck() {
        if (!agentConfig.isEnabled()) {
            return false;
        }
        try {
            String url = agentConfig.getBaseUrl() + "/actuator/health";
            ResponseEntity<Map<String, Object>> response = restTemplate.exchange(
                    url, HttpMethod.GET, null,
                    new ParameterizedTypeReference<>() {}
            );
            return response.getStatusCode().is2xxSuccessful();
        } catch (Exception e) {
            log.warn("Agent 健康检查失败: {}", e.getMessage());
            return false;
        }
    }

    private AgentResponse buildDisabledResponse(AgentRequest request) {
        return AgentResponse.builder()
                .success(false)
                .action(request.getAction())
                .result(Collections.emptyMap())
                .errorMessage("Agent 功能已禁用")
                .build();
    }

    private HttpHeaders buildHeaders() {
        HttpHeaders headers = new HttpHeaders();
        if (StringUtils.hasText(agentConfig.getInternalToken())) {
            headers.set("X-Internal-Agent-Token", agentConfig.getInternalToken());
        }
        return headers;
    }
}
