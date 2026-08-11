package com.yuyuan.thumb.model.entity;

import com.baomidou.mybatisplus.annotation.IdType;
import com.baomidou.mybatisplus.annotation.TableId;
import com.baomidou.mybatisplus.annotation.TableName;
import lombok.Data;

import java.time.LocalDateTime;

/**
 * Ledger row for a thumb-count flush batch. The batch_id is the idempotency
 * anchor: INSERT IGNORE + PRIMARY KEY makes re-applying the same batch a no-op.
 */
@TableName(value = "thumb_flush_batch")
@Data
public class ThumbFlushBatch {

    @TableId(value = "batch_id", type = IdType.INPUT)
    private String batchId;

    private LocalDateTime createdAt;
}
