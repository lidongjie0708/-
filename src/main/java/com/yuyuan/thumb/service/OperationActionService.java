package com.yuyuan.thumb.service;

import com.baomidou.mybatisplus.extension.service.IService;
import com.yuyuan.thumb.model.dto.agent.CreateOperationActionRequest;
import com.yuyuan.thumb.model.entity.OperationAction;

public interface OperationActionService extends IService<OperationAction> {
    OperationAction create(CreateOperationActionRequest request, String idempotencyKey, Long actorId);
    OperationAction approve(String actionId, String decision, String reason, Long actorId);
}
