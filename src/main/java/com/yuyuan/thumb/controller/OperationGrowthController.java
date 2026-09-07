package com.yuyuan.thumb.controller;

import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.baomidou.mybatisplus.extension.plugins.pagination.Page;
import com.yuyuan.thumb.common.BaseResponse;
import com.yuyuan.thumb.common.ResultUtils;
import com.yuyuan.thumb.model.dto.blog.PageResponse;
import com.yuyuan.thumb.model.dto.operations.OperationActionObservationResponse;
import com.yuyuan.thumb.model.entity.OperationAction;
import com.yuyuan.thumb.model.entity.OperationFinding;
import com.yuyuan.thumb.model.entity.User;
import com.yuyuan.thumb.service.OperationActionService;
import com.yuyuan.thumb.service.OperationExperimentService;
import com.yuyuan.thumb.service.OperationFindingService;
import com.yuyuan.thumb.service.UserService;
import lombok.RequiredArgsConstructor;
import org.springframework.http.HttpStatus;
import org.springframework.security.core.context.SecurityContextHolder;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

import java.time.LocalDateTime;

/** Read-only operations growth evidence APIs. Mutation remains in OperationActionController. */
@RestController
@RequestMapping("/agent/operations")
@RequiredArgsConstructor
public class OperationGrowthController {
    private final OperationFindingService operationFindingService;
    private final OperationExperimentService operationExperimentService;
    private final OperationActionService operationActionService;
    private final UserService userService;

    @GetMapping("/findings")
    public BaseResponse<PageResponse<OperationFinding>> findings(
            @RequestParam(defaultValue = "1") Integer pageNum,
            @RequestParam(defaultValue = "10") Integer pageSize,
            @RequestParam(required = false) String status,
            @RequestParam(required = false) String findingType,
            @RequestParam(required = false) LocalDateTime observedFrom,
            @RequestParam(required = false) LocalDateTime observedTo) {
        if (!isAdmin()) return ResultUtils.error(HttpStatus.FORBIDDEN.value(), "NO_PERMISSION");
        int safePage = pageNum == null || pageNum < 1 ? 1 : pageNum;
        int safeSize = pageSize == null || pageSize < 1 ? 10 : Math.min(pageSize, 100);
        LambdaQueryWrapper<OperationFinding> query = new LambdaQueryWrapper<>();
        if (hasText(status)) query.eq(OperationFinding::getStatus, status.trim());
        if (hasText(findingType)) query.eq(OperationFinding::getFindingType, findingType.trim());
        if (observedFrom != null) query.ge(OperationFinding::getObservedTo, observedFrom);
        if (observedTo != null) query.le(OperationFinding::getObservedFrom, observedTo);
        query.orderByDesc(OperationFinding::getCreatedAt);
        Page<OperationFinding> result = operationFindingService.page(new Page<>(safePage, safeSize), query);
        PageResponse<OperationFinding> response = new PageResponse<>();
        response.setRecords(result.getRecords());
        response.setTotal(result.getTotal());
        response.setPageNum((int) result.getCurrent());
        response.setPageSize((int) result.getSize());
        response.setTotalPages((int) result.getPages());
        return ResultUtils.success(response);
    }

    @GetMapping("/actions/{actionId}/observations")
    public BaseResponse<?> observations(@PathVariable String actionId) {
        if (!isAdmin()) return ResultUtils.error(HttpStatus.FORBIDDEN.value(), "NO_PERMISSION");
        OperationAction action = operationActionService.getById(actionId);
        if (action == null) return ResultUtils.error(HttpStatus.NOT_FOUND.value(), "Action not found");
        OperationActionObservationResponse response = new OperationActionObservationResponse();
        response.setActionId(actionId);
        response.setExperiments(operationExperimentService.listByActionId(actionId));
        return ResultUtils.success(response);
    }

    private boolean isAdmin() {
        if (SecurityContextHolder.getContext().getAuthentication() == null) return false;
        String username = SecurityContextHolder.getContext().getAuthentication().getName();
        User user = userService.getOne(new LambdaQueryWrapper<User>().eq(User::getUsername, username), false);
        return user != null && "ADMIN".equalsIgnoreCase(user.getRole());
    }

    private boolean hasText(String value) {
        return value != null && !value.isBlank();
    }
}
