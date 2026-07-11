package com.yuyuan.thumb.controller;

import com.baomidou.mybatisplus.core.conditions.query.QueryWrapper;
import com.baomidou.mybatisplus.extension.plugins.pagination.Page;
import com.yuyuan.thumb.common.BaseResponse;
import com.yuyuan.thumb.common.ResultUtils;
import com.yuyuan.thumb.model.dto.blog.PageResponse;
import com.yuyuan.thumb.model.entity.AgentAnalysisLog;
import com.yuyuan.thumb.model.entity.User;
import com.yuyuan.thumb.service.AgentAnalysisLogService;
import com.yuyuan.thumb.service.UserService;
import org.springframework.security.core.context.SecurityContextHolder;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

@RestController
@RequestMapping("/agent/analytics/logs")
public class AgentAnalysisLogController {

    private final AgentAnalysisLogService agentAnalysisLogService;
    private final UserService userService;

    public AgentAnalysisLogController(AgentAnalysisLogService agentAnalysisLogService, UserService userService) {
        this.agentAnalysisLogService = agentAnalysisLogService;
        this.userService = userService;
    }

    @GetMapping("/page")
    public BaseResponse<PageResponse<AgentAnalysisLog>> pageLogs(
            @RequestParam(defaultValue = "1") Integer pageNum,
            @RequestParam(defaultValue = "10") Integer pageSize,
            @RequestParam(required = false) String question,
            @RequestParam(required = false) String intent,
            @RequestParam(required = false) String status,
            @RequestParam(required = false) Long userId) {
        if (!isAdmin()) {
            return ResultUtils.error(403, "Only admin can view analytics Agent logs");
        }

        int safePageNum = pageNum == null || pageNum < 1 ? 1 : pageNum;
        int safePageSize = pageSize == null || pageSize < 1 ? 10 : Math.min(pageSize, 100);

        QueryWrapper<AgentAnalysisLog> queryWrapper = new QueryWrapper<>();
        if (question != null && !question.isBlank()) {
            queryWrapper.like("question", question.trim());
        }
        if (intent != null && !intent.isBlank()) {
            queryWrapper.eq("intent", intent.trim());
        }
        if (status != null && !status.isBlank()) {
            queryWrapper.eq("status", status.trim());
        }
        if (userId != null) {
            queryWrapper.eq("user_id", userId);
        }
        queryWrapper.orderByDesc("created_at");

        Page<AgentAnalysisLog> page = agentAnalysisLogService.page(new Page<>(safePageNum, safePageSize), queryWrapper);
        PageResponse<AgentAnalysisLog> response = new PageResponse<>();
        response.setRecords(page.getRecords());
        response.setTotal(page.getTotal());
        response.setPageNum((int) page.getCurrent());
        response.setPageSize((int) page.getSize());
        response.setTotalPages((int) page.getPages());
        return ResultUtils.success(response);
    }

    private boolean isAdmin() {
        String username = SecurityContextHolder.getContext().getAuthentication().getName();
        if ("admin".equalsIgnoreCase(username)) {
            return true;
        }
        User user = userService.getOne(new QueryWrapper<User>().eq("username", username), false);
        return user != null && "ADMIN".equalsIgnoreCase(user.getRole());
    }
}
