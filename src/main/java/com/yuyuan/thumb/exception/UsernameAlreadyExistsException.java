package com.yuyuan.thumb.exception;

/**
 * 自定义异常：用户名已存在
 */
public class UsernameAlreadyExistsException extends RuntimeException {
    public UsernameAlreadyExistsException(String message) {
        super(message);
    }
}
