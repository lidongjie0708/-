package com.yuyuan.thumb.model.entity;

import com.baomidou.mybatisplus.annotation.IdType;
import com.baomidou.mybatisplus.annotation.TableField;
import com.baomidou.mybatisplus.annotation.TableId;
import com.baomidou.mybatisplus.annotation.TableName;
import lombok.Data;

import java.time.LocalDateTime;

/** A proposal only. It never represents a direct modification of blog data. */
@Data
@TableName("operation_action")
public class OperationAction {
    @TableId(type = IdType.INPUT)
    private String id;
    private String findingId;
    private String actionType;
    private String targetType;
    private String targetId;
    private String reason;
    @TableField("proposed_payload_json")
    private String proposedPayloadJson;
    private String payloadHash;
    private String payloadSchemaVersion;
    private String evidenceJson;
    private String riskLevel;
    private Boolean approvalRequired;
    private String status;
    private String idempotencyKey;
    private Long createdBy;
    private Long approvedBy;
    private LocalDateTime approvedAt;
    private String rejectionReason;
    private Long executedBy;
    private String executionJson;
    private LocalDateTime expiresAt;
    private LocalDateTime createdAt;
    private LocalDateTime updatedAt;
    private LocalDateTime executedAt;
}
