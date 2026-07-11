package com.yuyuan.thumb.controller;

import com.baomidou.mybatisplus.core.conditions.query.QueryWrapper;
import com.baomidou.mybatisplus.extension.plugins.pagination.Page;
import com.yuyuan.thumb.common.BaseResponse;
import com.yuyuan.thumb.common.ResultUtils;
import com.yuyuan.thumb.model.dto.blog.PageResponse;
import com.yuyuan.thumb.model.entity.RagEvalLog;
import com.yuyuan.thumb.model.entity.User;
import com.yuyuan.thumb.service.RagEvalLogService;
import com.yuyuan.thumb.service.UserService;
import org.springframework.security.core.context.SecurityContextHolder;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

@RestController
@RequestMapping("/agent/rag/logs")
public class RagEvalLogController {

    private final RagEvalLogService ragEvalLogService;
    private final UserService userService;

    public RagEvalLogController(RagEvalLogService ragEvalLogService, UserService userService) {
        this.ragEvalLogService = ragEvalLogService;
        this.userService = userService;
    }

    @GetMapping("/page")
    public BaseResponse<PageResponse<RagEvalLog>> pageLogs(
            @RequestParam(defaultValue = "1") Integer pageNum,
            @RequestParam(defaultValue = "10") Integer pageSize,
            @RequestParam(required = false) String question,
            @RequestParam(required = false) Long userId,
            @RequestParam(required = false) Integer hasCitations) {
        if (!isAdmin()) {
            return ResultUtils.error(403, "Only admin can view RAG observation logs");
        }

        int safePageNum = pageNum == null || pageNum < 1 ? 1 : pageNum;
        int safePageSize = pageSize == null || pageSize < 1 ? 10 : Math.min(pageSize, 100);

        QueryWrapper<RagEvalLog> queryWrapper = new QueryWrapper<>();
        if (question != null && !question.isBlank()) {
            queryWrapper.like("question", question.trim());
        }
        if (userId != null) {
            queryWrapper.eq("user_id", userId);
        }
        if (hasCitations != null) {
            queryWrapper.eq("has_citations", hasCitations);
        }
        queryWrapper.orderByDesc("created_at");

        Page<RagEvalLog> page = ragEvalLogService.page(new Page<>(safePageNum, safePageSize), queryWrapper);

        PageResponse<RagEvalLog> response = new PageResponse<>();
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
