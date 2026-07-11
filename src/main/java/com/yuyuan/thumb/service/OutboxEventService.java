package com.yuyuan.thumb.service;

import com.baomidou.mybatisplus.extension.service.IService;
import com.yuyuan.thumb.model.entity.OutboxEvent;

import java.util.List;

public interface OutboxEventService extends IService<OutboxEvent> {

    void create(String eventType, String aggregateType, String aggregateId,
                String exchangeName, String routingKey, Object payload);

    List<OutboxEvent> listReadyEvents(int limit);

    boolean markSending(Long id);

    void markSent(Long id);

    void markFailed(Long id, String errorMessage);
}
