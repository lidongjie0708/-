package com.yuyuan.thumb.model.enums;

import lombok.Getter;

/**
 * 内容审核状态枚举
 * Agent 自动审核标记，用于内容安全管控
 */
@Getter
public enum AuditStatusEnum {
    /**
     * 待审核（尚未处理）
     */
    PENDING(0, "待审核"),
    /**
     * 审核通过
     */
    APPROVED(1, "审核通过"),
    /**
     * 审核拒绝（违规内容）
     */
    REJECTED(2, "审核拒绝");

    private final int code;
    private final String desc;

    AuditStatusEnum(int code, String desc) {
        this.code = code;
        this.desc = desc;
    }
}