package com.yuyuan.thumb.mapper;

import com.baomidou.mybatisplus.core.mapper.BaseMapper;
import com.yuyuan.thumb.model.entity.OutboxEvent;
import org.apache.ibatis.annotations.Mapper;

@Mapper
public interface OutboxEventMapper extends BaseMapper<OutboxEvent> {
}
