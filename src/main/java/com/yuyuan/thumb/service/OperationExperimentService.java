package com.yuyuan.thumb.service;

import com.baomidou.mybatisplus.extension.service.IService;
import com.yuyuan.thumb.model.entity.OperationExperiment;

import java.util.List;

public interface OperationExperimentService extends IService<OperationExperiment> {
    List<OperationExperiment> listByActionId(String actionId);
}
