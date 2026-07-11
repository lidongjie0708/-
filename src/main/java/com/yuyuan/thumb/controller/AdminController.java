package com.yuyuan.thumb.controller;

import cn.hutool.core.bean.BeanUtil;
import com.baomidou.mybatisplus.core.conditions.query.QueryWrapper;
import com.baomidou.mybatisplus.extension.plugins.pagination.Page;
import com.yuyuan.thumb.common.BaseResponse;
import com.yuyuan.thumb.common.ResultUtils;
import com.yuyuan.thumb.model.dto.blog.PageResponse;
import com.yuyuan.thumb.model.entity.AgentAnalysisLog;
import com.yuyuan.thumb.model.entity.Blog;
import com.yuyuan.thumb.model.entity.RagEvalLog;
import com.yuyuan.thumb.model.entity.User;
import com.yuyuan.thumb.model.vo.AdminUserVO;
import com.yuyuan.thumb.service.AgentAnalysisLogService;
import com.yuyuan.thumb.service.BlogService;
import com.yuyuan.thumb.service.RagEvalLogService;
import com.yuyuan.thumb.service.UserService;
import org.springframework.security.core.context.SecurityContextHolder;
import org.springframework.web.bind.annotation.DeleteMapping;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PutMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;
import org.springframework.format.annotation.DateTimeFormat;

import java.time.LocalDateTime;
import java.util.HashMap;
import java.util.List;
import java.util.Map;

@RestController
@RequestMapping("/admin")
public class AdminController {

    private final UserService userService;
    private final BlogService blogService;
    private final RagEvalLogService ragEvalLogService;
    private final AgentAnalysisLogService agentAnalysisLogService;

    public AdminController(UserService userService,
                           BlogService blogService,
                           RagEvalLogService ragEvalLogService,
                           AgentAnalysisLogService agentAnalysisLogService) {
        this.userService = userService;
        this.blogService = blogService;
        this.ragEvalLogService = ragEvalLogService;
        this.agentAnalysisLogService = agentAnalysisLogService;
    }

    @GetMapping("/overview")
    public BaseResponse<Map<String, Object>> overview() {
        if (!isAdmin()) {
            return ResultUtils.error(403, "Only admin can view dashboard overview");
        }
        Map<String, Object> data = new HashMap<>();
        data.put("userCount", userService.count());
        data.put("enabledUserCount", userService.count(new QueryWrapper<User>().eq("enabled", 1)));
        data.put("blogCount", blogService.count());
        data.put("pendingAuditBlogCount", blogService.count(new QueryWrapper<Blog>().eq("audit_status", 0)));
        data.put("embeddedBlogCount", blogService.count(new QueryWrapper<Blog>().eq("embedding_status", 2)));
        data.put("ragLogCount", ragEvalLogService.count());
        data.put("analyticsLogCount", agentAnalysisLogService.count());
        data.put("failedAnalyticsLogCount", agentAnalysisLogService.count(new QueryWrapper<AgentAnalysisLog>().eq("status", "FAILED")));
        return ResultUtils.success(data);
    }

    @GetMapping("/users/page")
    public BaseResponse<PageResponse<AdminUserVO>> pageUsers(
            @RequestParam(defaultValue = "1") Integer pageNum,
            @RequestParam(defaultValue = "10") Integer pageSize,
            @RequestParam(required = false) String username,
            @RequestParam(required = false) String role,
            @RequestParam(required = false) Integer enabled) {
        if (!isAdmin()) {
            return ResultUtils.error(403, "Only admin can view users");
        }

        QueryWrapper<User> wrapper = new QueryWrapper<>();
        if (username != null && !username.isBlank()) {
            wrapper.like("username", username.trim());
        }
        if (role != null && !role.isBlank()) {
            wrapper.eq("role", role.trim().toUpperCase());
        }
        if (enabled != null) {
            wrapper.eq("enabled", enabled);
        }
        wrapper.orderByDesc("id");

        Page<User> page = userService.page(new Page<>(safePageNum(pageNum), safePageSize(pageSize)), wrapper);
        List<AdminUserVO> records = page.getRecords().stream()
                .map(user -> BeanUtil.copyProperties(user, AdminUserVO.class))
                .toList();
        return ResultUtils.success(toPageResponse(page, records));
    }

    @PutMapping("/users/{userId}/enabled")
    public BaseResponse<Boolean> updateUserEnabled(@PathVariable Long userId, @RequestParam Integer enabled) {
        if (!isAdmin()) {
            return ResultUtils.error(403, "Only admin can update users");
        }
        if (enabled == null || (enabled != 0 && enabled != 1)) {
            return ResultUtils.error(400, "enabled must be 0 or 1");
        }
        User user = new User();
        user.setId(userId);
        user.setEnabled(enabled);
        return ResultUtils.success(userService.updateById(user));
    }

    @PutMapping("/users/{userId}/role")
    public BaseResponse<Boolean> updateUserRole(@PathVariable Long userId, @RequestParam String role) {
        if (!isAdmin()) {
            return ResultUtils.error(403, "Only admin can update roles");
        }
        User target = userService.getById(userId);
        if (target == null) {
            return ResultUtils.error(404, "User not found");
        }
        String normalizedRole = role == null ? "" : role.trim().toUpperCase();
        if (!"USER".equals(normalizedRole) && !"ADMIN".equals(normalizedRole)) {
            return ResultUtils.error(400, "role must be USER or ADMIN");
        }
        User update = new User();
        update.setId(userId);
        update.setRole(normalizedRole);
        return ResultUtils.success(userService.updateById(update));
    }

    @DeleteMapping("/users/{userId}")
    public BaseResponse<Boolean> deleteUser(@PathVariable Long userId) {
        if (!isAdmin()) {
            return ResultUtils.error(403, "Only admin can delete users");
        }
        User target = userService.getById(userId);
        String currentUsername = SecurityContextHolder.getContext().getAuthentication().getName();
        if (target != null && currentUsername.equals(target.getUsername())) {
            return ResultUtils.error(400, "Admin cannot delete current login user");
        }
        return ResultUtils.success(userService.removeById(userId));
    }

    @GetMapping("/blogs/page")
    public BaseResponse<PageResponse<Blog>> pageBlogs(
            @RequestParam(defaultValue = "1") Integer pageNum,
            @RequestParam(defaultValue = "10") Integer pageSize,
            @RequestParam(required = false) String title,
            @RequestParam(required = false) Long userId,
            @RequestParam(required = false) Integer auditStatus,
            @RequestParam(required = false) Integer embeddingStatus) {
        if (!isAdmin()) {
            return ResultUtils.error(403, "Only admin can view blogs");
        }
        QueryWrapper<Blog> wrapper = new QueryWrapper<>();
        if (title != null && !title.isBlank()) {
            wrapper.like("title", title.trim());
        }
        if (userId != null) {
            wrapper.eq("userId", userId);
        }
        if (auditStatus != null) {
            wrapper.eq("audit_status", auditStatus);
        }
        if (embeddingStatus != null) {
            wrapper.eq("embedding_status", embeddingStatus);
        }
        wrapper.orderByDesc("create_time");
        Page<Blog> page = blogService.page(new Page<>(safePageNum(pageNum), safePageSize(pageSize)), wrapper);
        return ResultUtils.success(toPageResponse(page, page.getRecords()));
    }

    @PutMapping("/blogs/{blogId}/audit-status")
    public BaseResponse<Boolean> updateBlogAuditStatus(@PathVariable Long blogId, @RequestParam Integer auditStatus) {
        if (!isAdmin()) {
            return ResultUtils.error(403, "Only admin can update blog audit status");
        }
        if (auditStatus == null || auditStatus < 0 || auditStatus > 2) {
            return ResultUtils.error(400, "auditStatus must be 0, 1, or 2");
        }
        Blog blog = new Blog();
        blog.setId(blogId);
        blog.setAuditStatus(auditStatus);
        return ResultUtils.success(blogService.updateById(blog));
    }

    @PutMapping("/blogs/{blogId}/embedding-status")
    public BaseResponse<Boolean> updateBlogEmbeddingStatus(@PathVariable Long blogId, @RequestParam Integer embeddingStatus) {
        if (!isAdmin()) {
            return ResultUtils.error(403, "Only admin can update blog embedding status");
        }
        if (embeddingStatus == null || embeddingStatus < 0 || embeddingStatus > 3) {
            return ResultUtils.error(400, "embeddingStatus must be 0, 1, 2, or 3");
        }
        Blog blog = new Blog();
        blog.setId(blogId);
        blog.setEmbeddingStatus(embeddingStatus);
        return ResultUtils.success(blogService.updateById(blog));
    }

    @DeleteMapping("/blogs/{blogId}")
    public BaseResponse<Boolean> deleteBlog(@PathVariable Long blogId) {
        if (!isAdmin()) {
            return ResultUtils.error(403, "Only admin can delete blogs");
        }
        return ResultUtils.success(blogService.removeById(blogId));
    }

    @GetMapping("/rag/logs/page")
    public BaseResponse<PageResponse<RagEvalLog>> pageRagLogs(
            @RequestParam(defaultValue = "1") Integer pageNum,
            @RequestParam(defaultValue = "10") Integer pageSize,
            @RequestParam(required = false) String question,
            @RequestParam(required = false) Long userId,
            @RequestParam(required = false) Integer hasCitations,
            @RequestParam(required = false) Double minConfidence,
            @RequestParam(required = false) @DateTimeFormat(iso = DateTimeFormat.ISO.DATE_TIME) LocalDateTime createdFrom,
            @RequestParam(required = false) @DateTimeFormat(iso = DateTimeFormat.ISO.DATE_TIME) LocalDateTime createdTo) {
        if (!isAdmin()) {
            return ResultUtils.error(403, "Only admin can view RAG logs");
        }
        QueryWrapper<RagEvalLog> wrapper = new QueryWrapper<>();
        if (question != null && !question.isBlank()) {
            wrapper.like("question", question.trim());
        }
        if (userId != null) {
            wrapper.eq("user_id", userId);
        }
        if (hasCitations != null) {
            wrapper.eq("has_citations", hasCitations);
        }
        if (minConfidence != null) {
            wrapper.ge("confidence", minConfidence);
        }
        if (createdFrom != null) {
            wrapper.ge("created_at", createdFrom);
        }
        if (createdTo != null) {
            wrapper.le("created_at", createdTo);
        }
        wrapper.orderByDesc("created_at");
        Page<RagEvalLog> page = ragEvalLogService.page(new Page<>(safePageNum(pageNum), safePageSize(pageSize)), wrapper);
        return ResultUtils.success(toPageResponse(page, page.getRecords()));
    }

    @GetMapping("/analytics/logs/page")
    public BaseResponse<PageResponse<AgentAnalysisLog>> pageAnalyticsLogs(
            @RequestParam(defaultValue = "1") Integer pageNum,
            @RequestParam(defaultValue = "10") Integer pageSize,
            @RequestParam(required = false) String question,
            @RequestParam(required = false) String intent,
            @RequestParam(required = false) String status,
            @RequestParam(required = false) Long userId,
            @RequestParam(required = false) Integer minRowCount,
            @RequestParam(required = false) @DateTimeFormat(iso = DateTimeFormat.ISO.DATE_TIME) LocalDateTime createdFrom,
            @RequestParam(required = false) @DateTimeFormat(iso = DateTimeFormat.ISO.DATE_TIME) LocalDateTime createdTo) {
        if (!isAdmin()) {
            return ResultUtils.error(403, "Only admin can view analytics logs");
        }
        QueryWrapper<AgentAnalysisLog> wrapper = new QueryWrapper<>();
        if (question != null && !question.isBlank()) {
            wrapper.like("question", question.trim());
        }
        if (intent != null && !intent.isBlank()) {
            wrapper.eq("intent", intent.trim());
        }
        if (status != null && !status.isBlank()) {
            wrapper.eq("status", status.trim());
        }
        if (userId != null) {
            wrapper.eq("user_id", userId);
        }
        if (minRowCount != null) {
            wrapper.ge("row_count", minRowCount);
        }
        if (createdFrom != null) {
            wrapper.ge("created_at", createdFrom);
        }
        if (createdTo != null) {
            wrapper.le("created_at", createdTo);
        }
        wrapper.orderByDesc("created_at");
        Page<AgentAnalysisLog> page = agentAnalysisLogService.page(new Page<>(safePageNum(pageNum), safePageSize(pageSize)), wrapper);
        return ResultUtils.success(toPageResponse(page, page.getRecords()));
    }

    @GetMapping("/rag/logs/{logId}")
    public BaseResponse<RagEvalLog> getRagLog(@PathVariable Long logId) {
        if (!isAdmin()) {
            return ResultUtils.error(403, "Only admin can view RAG logs");
        }
        RagEvalLog log = ragEvalLogService.getById(logId);
        return log == null ? ResultUtils.error(404, "RAG log not found") : ResultUtils.success(log);
    }

    @GetMapping("/analytics/logs/{logId}")
    public BaseResponse<AgentAnalysisLog> getAnalyticsLog(@PathVariable Long logId) {
        if (!isAdmin()) {
            return ResultUtils.error(403, "Only admin can view analytics logs");
        }
        AgentAnalysisLog log = agentAnalysisLogService.getById(logId);
        return log == null ? ResultUtils.error(404, "Analytics log not found") : ResultUtils.success(log);
    }

    private boolean isAdmin() {
        String username = SecurityContextHolder.getContext().getAuthentication().getName();
        User user = userService.getOne(new QueryWrapper<User>().eq("username", username), false);
        return user != null && "ADMIN".equalsIgnoreCase(user.getRole());
    }

    private int safePageNum(Integer pageNum) {
        return pageNum == null || pageNum < 1 ? 1 : pageNum;
    }

    private int safePageSize(Integer pageSize) {
        return pageSize == null || pageSize < 1 ? 10 : Math.min(pageSize, 100);
    }

    private <T> PageResponse<T> toPageResponse(Page<?> page, List<T> records) {
        PageResponse<T> response = new PageResponse<>();
        response.setRecords(records);
        response.setTotal(page.getTotal());
        response.setPageNum((int) page.getCurrent());
        response.setPageSize((int) page.getSize());
        response.setTotalPages((int) page.getPages());
        return response;
    }
}
