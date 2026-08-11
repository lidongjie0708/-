package com.yuyuan.thumb.mapper;

import com.baomidou.mybatisplus.core.mapper.BaseMapper;
import com.yuyuan.thumb.model.entity.ThumbFlushBatch;
import org.apache.ibatis.annotations.Delete;
import org.apache.ibatis.annotations.Insert;
import org.apache.ibatis.annotations.Mapper;
import org.apache.ibatis.annotations.Param;

import java.time.LocalDateTime;

@Mapper
public interface ThumbFlushBatchMapper extends BaseMapper<ThumbFlushBatch> {

    /** Returns 1 when the batch was newly recorded, 0 when it was applied before. */
    @Insert("INSERT IGNORE INTO thumb_flush_batch (batch_id) VALUES (#{batchId})")
    int insertIgnore(@Param("batchId") String batchId);

    @Delete("DELETE FROM thumb_flush_batch WHERE created_at < #{before}")
    int deleteOlderThan(@Param("before") LocalDateTime before);
}
