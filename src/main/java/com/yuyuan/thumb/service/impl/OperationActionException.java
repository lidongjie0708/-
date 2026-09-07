package com.yuyuan.thumb.service.impl;

import lombok.Getter;

@Getter
public class OperationActionException extends RuntimeException {
    private final String errorCode;
    public OperationActionException(String errorCode, String message) { super(message); this.errorCode = errorCode; }
}
