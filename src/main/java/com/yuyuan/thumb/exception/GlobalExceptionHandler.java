package com.yuyuan.thumb.exception;

import com.yuyuan.thumb.common.BaseResponse;
import com.yuyuan.thumb.common.ErrorCode;
import com.yuyuan.thumb.common.ResultUtils;
import io.swagger.v3.oas.annotations.Hidden;
import lombok.extern.slf4j.Slf4j;
import org.springframework.http.HttpStatus;
import org.springframework.security.access.AccessDeniedException;
import org.springframework.security.authentication.BadCredentialsException;
import org.springframework.security.authentication.DisabledException;
import org.springframework.security.core.userdetails.UsernameNotFoundException;
import org.springframework.validation.FieldError;
import org.springframework.web.bind.MethodArgumentNotValidException;
import org.springframework.web.bind.annotation.ExceptionHandler;
import org.springframework.web.bind.annotation.RestControllerAdvice;
import org.springframework.web.method.annotation.MethodArgumentTypeMismatchException;

import java.util.HashMap;
import java.util.Map;

/**
 * 全局异常处理器
 *
 * @author pine
 */
@RestControllerAdvice
@Slf4j
@Hidden
public class GlobalExceptionHandler {

    @ExceptionHandler(MethodArgumentNotValidException.class)
    public BaseResponse<?> handleValidationException(MethodArgumentNotValidException e) {
        Map<String, String> errorMap = new HashMap<>();
        e.getBindingResult().getAllErrors().forEach(error -> {
            String fieldName = ((FieldError) error).getField();
            String errorMsg = error.getDefaultMessage();
            errorMap.put(fieldName, errorMsg);
        });
        log.warn("参数校验失败：{}", errorMap);
        return ResultUtils.error(HttpStatus.BAD_REQUEST.value(), "请求参数校验失败");
    }

    @ExceptionHandler(UsernameNotFoundException.class)
    public BaseResponse<?> handleUsernameNotFound(UsernameNotFoundException e) {
        log.warn("认证失败：{}", e.getMessage());
        return ResultUtils.error(HttpStatus.UNAUTHORIZED.value(), e.getMessage());
    }

    @ExceptionHandler(BadCredentialsException.class)
    public BaseResponse<?> handleBadCredentials(BadCredentialsException e) {
        log.warn("认证失败：用户名或密码错误");
        return ResultUtils.error(HttpStatus.UNAUTHORIZED.value(), "用户名或密码错误");
    }

    @ExceptionHandler(DisabledException.class)
    public BaseResponse<?> handleDisabled(DisabledException e) {
        log.warn("认证失败：账号已被禁用");
        return ResultUtils.error(HttpStatus.FORBIDDEN.value(), "账号已被禁用，请联系管理员");
    }

    @ExceptionHandler(UsernameAlreadyExistsException.class)
    public BaseResponse<?> handleUsernameExistsException(UsernameAlreadyExistsException e) {
        return ResultUtils.error(HttpStatus.CONFLICT.value(), e.getMessage());
    }

    @ExceptionHandler(AccessDeniedException.class)
    public BaseResponse<?> handleAccessDenied(AccessDeniedException e) {
        log.warn("权限不足：{}", e.getMessage());
        return ResultUtils.error(HttpStatus.FORBIDDEN.value(), "没有权限访问该接口");
    }

    @ExceptionHandler(MethodArgumentTypeMismatchException.class)
    public BaseResponse<?> handleTypeMismatch(MethodArgumentTypeMismatchException e) {
        String msg = String.format("参数类型错误：%s 应是 %s 类型",
                e.getName(), e.getRequiredType().getSimpleName());
        log.warn("参数异常：{}", msg);
        return ResultUtils.error(HttpStatus.BAD_REQUEST.value(), msg);
    }

    @ExceptionHandler(RuntimeException.class)
    public BaseResponse<?> runtimeExceptionHandler(RuntimeException e) {
        log.error(e.getMessage(), e);
        return ResultUtils.error(ErrorCode.OPERATION_ERROR, e.getMessage());
    }

    @ExceptionHandler(Exception.class)
    public BaseResponse<?> handleUnknownException(Exception e) {
        log.error("系统异常：{}", e.getMessage(), e);
        return ResultUtils.error(HttpStatus.INTERNAL_SERVER_ERROR.value(), "系统繁忙，请稍后再试");
    }
}
