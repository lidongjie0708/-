package com.yuyuan.thumb.controller;

import com.baomidou.mybatisplus.core.conditions.query.QueryWrapper;
import com.yuyuan.thumb.common.BaseResponse;
import com.yuyuan.thumb.common.ResultUtils;
import com.yuyuan.thumb.config.AgentConfig;
import com.yuyuan.thumb.model.entity.User;
import com.yuyuan.thumb.service.UserService;
import com.yuyuan.thumb.util.JwtUtil;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.security.core.context.SecurityContextHolder;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import java.util.HashMap;
import java.util.Map;

@RestController
@RequestMapping("/agent")
public class AgentTokenController {

    private final JwtUtil jwtUtil;
    private final UserService userService;
    private final AgentConfig agentConfig;
    private final long aiTokenTtlMillis;

    public AgentTokenController(
            JwtUtil jwtUtil,
            UserService userService,
            AgentConfig agentConfig,
            @Value("${agent.ai-token-ttl-millis:300000}") long aiTokenTtlMillis) {
        this.jwtUtil = jwtUtil;
        this.userService = userService;
        this.agentConfig = agentConfig;
        this.aiTokenTtlMillis = aiTokenTtlMillis;
    }

    @PostMapping("/token")
    public BaseResponse<Map<String, Object>> createAgentToken() {
        String username = SecurityContextHolder.getContext().getAuthentication().getName();
        User user = userService.getOne(new QueryWrapper<User>().eq("username", username), false);
        if (user == null) {
            return ResultUtils.error(404, "User not found");
        }
        String token = jwtUtil.generateAiToken(username, user.getId(), user.getRole(), aiTokenTtlMillis);
        Map<String, Object> data = new HashMap<>();
        data.put("token", token);
        data.put("tokenType", "Bearer");
        data.put("expiresIn", aiTokenTtlMillis / 1000);
        data.put("pythonStreamBaseUrl", agentConfig.getBaseUrl());
        return ResultUtils.success(data);
    }
}
