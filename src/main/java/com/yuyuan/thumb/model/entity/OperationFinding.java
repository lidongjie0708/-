package com.yuyuan.thumb.model.entity;

import com.baomidou.mybatisplus.annotation.IdType;
import com.baomidou.mybatisplus.annotation.TableField;
import com.baomidou.mybatisplus.annotation.TableId;
import com.baomidou.mybatisplus.annotation.TableName;
import lombok.Data;

import java.math.BigDecimal;
import java.time.LocalDateTime;

@Data
@TableName("operation_finding")
public class OperationFinding {
    @TableId(type = IdType.INPUT)
    private String id;
    private String findingType;
    private String status;
    private String targetType;
    private String targetId;
    private String metricKey;
    private String metricVersion;
    private BigDecimal currentValue;
    private BigDecimal baselineValue;
    private BigDecimal anomalyScore;
    private BigDecimal confidence;
    private Integer sampleSize;
    private LocalDateTime observedFrom;
    private LocalDateTime observedTo;
    private LocalDateTime dataFreshAt;
    @TableField("evidence_json")
    private String evidenceJson;
    @TableField("limitations_json")
    private String limitationsJson;
    private Long analysisLogId;
    private Long createdBy;
    private LocalDateTime createdAt;
    private LocalDateTime updatedAt;
}
