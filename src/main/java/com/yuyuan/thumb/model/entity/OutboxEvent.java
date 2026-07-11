package com.yuyuan.thumb.model.entity;

import com.baomidou.mybatisplus.annotation.IdType;
import com.baomidou.mybatisplus.annotation.TableField;
import com.baomidou.mybatisplus.annotation.TableId;
import com.baomidou.mybatisplus.annotation.TableName;
import lombok.Data;

import java.time.LocalDateTime;

@Data
@TableName("outbox_event")
public class OutboxEvent {

    @TableId(type = IdType.ASSIGN_ID)
    private Long id;

    private String eventType;

    private String aggregateType;

    private String aggregateId;

    @TableField("exchange_name")
    private String exchangeName;

    private String routingKey;

    private String payload;

    private String status;

    private Integer retryCount;

    private LocalDateTime nextRetryTime;

    private String lastError;

    private LocalDateTime createdAt;

    private LocalDateTime updatedAt;
}
