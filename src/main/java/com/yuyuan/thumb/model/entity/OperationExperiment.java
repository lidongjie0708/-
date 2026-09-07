package com.yuyuan.thumb.model.entity;

import com.baomidou.mybatisplus.annotation.IdType;
import com.baomidou.mybatisplus.annotation.TableField;
import com.baomidou.mybatisplus.annotation.TableId;
import com.baomidou.mybatisplus.annotation.TableName;
import lombok.Data;

import java.time.LocalDateTime;

@Data
@TableName("operation_experiment")
public class OperationExperiment {
    @TableId(type = IdType.INPUT)
    private String id;
    private String actionId;
    private String metricKey;
    private String metricVersion;
    @TableField("baseline_snapshot_json")
    private String baselineSnapshotJson;
    @TableField("post_snapshot_json")
    private String postSnapshotJson;
    private LocalDateTime observationFrom;
    private LocalDateTime observationTo;
    private String status;
    private String attributionResult;
    private String notAttributableReason;
    private LocalDateTime createdAt;
    private LocalDateTime updatedAt;
}
