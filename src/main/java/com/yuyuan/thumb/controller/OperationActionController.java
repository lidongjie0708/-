package com.yuyuan.thumb.controller;

import com.baomidou.mybatisplus.core.conditions.query.QueryWrapper;
import com.yuyuan.thumb.common.BaseResponse;
import com.yuyuan.thumb.common.ResultUtils;
import com.yuyuan.thumb.model.dto.agent.ApproveOperationActionRequest;
import com.yuyuan.thumb.model.dto.agent.CreateOperationActionRequest;
import com.yuyuan.thumb.model.entity.OperationAction;
import com.yuyuan.thumb.model.entity.User;
import com.yuyuan.thumb.service.OperationActionService;
import com.yuyuan.thumb.service.UserService;
import com.yuyuan.thumb.service.impl.OperationActionException;
import jakarta.validation.Valid;
import lombok.RequiredArgsConstructor;
import org.springframework.http.HttpStatus;
import org.springframework.security.core.context.SecurityContextHolder;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestHeader;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

@RestController
@RequestMapping("/agent/operations/actions")
@RequiredArgsConstructor
public class OperationActionController {
    private final OperationActionService operationActionService;
    private final UserService userService;

    @PostMapping
    public BaseResponse<?> create(@Valid @RequestBody CreateOperationActionRequest request,
                                  @RequestHeader(value = "Idempotency-Key", required = false) String idempotencyKey) {
        User actor = requireAdmin();
        if (actor == null) return ResultUtils.error(HttpStatus.FORBIDDEN.value(), "NO_PERMISSION");
        try {
            return ResultUtils.success(operationActionService.create(request, idempotencyKey, actor.getId()));
        } catch (OperationActionException e) {
            return error(e);
        }
    }

    @PostMapping("/{id}/approve")
    public BaseResponse<?> approve(@PathVariable String id, @Valid @RequestBody ApproveOperationActionRequest request) {
        User actor = requireAdmin();
        if (actor == null) return ResultUtils.error(HttpStatus.FORBIDDEN.value(), "NO_PERMISSION");
        try {
            return ResultUtils.success(operationActionService.approve(id, request.getDecision(), request.getReason(), actor.getId()));
        } catch (OperationActionException e) {
            return error(e);
        }
    }

    @GetMapping("/{id}")
    public BaseResponse<?> get(@PathVariable String id) {
        if (requireAdmin() == null) return ResultUtils.error(HttpStatus.FORBIDDEN.value(), "NO_PERMISSION");
        OperationAction action = operationActionService.getById(id);
        return action == null ? ResultUtils.error(HttpStatus.NOT_FOUND.value(), "Action not found") : ResultUtils.success(action);
    }

    private User requireAdmin() {
        if (SecurityContextHolder.getContext().getAuthentication() == null) {
            return null;
        }
        String username = SecurityContextHolder.getContext().getAuthentication().getName();
        User user = userService.getOne(new QueryWrapper<User>().eq("username", username), false);
        return user != null && "ADMIN".equalsIgnoreCase(user.getRole()) ? user : null;
    }

    private BaseResponse<?> error(OperationActionException e) {
        int status = switch (e.getErrorCode()) {
            case "NOT_FOUND" -> HttpStatus.NOT_FOUND.value();
            case "NO_PERMISSION" -> HttpStatus.FORBIDDEN.value();
            case "ACTION_SCHEMA_INVALID" -> HttpStatus.BAD_REQUEST.value();
            default -> HttpStatus.CONFLICT.value();
        };
        return ResultUtils.error(status, e.getErrorCode() + ": " + e.getMessage());
    }
}
