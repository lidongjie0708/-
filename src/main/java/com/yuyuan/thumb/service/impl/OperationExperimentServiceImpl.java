package com.yuyuan.thumb.service.impl;

import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.baomidou.mybatisplus.extension.service.impl.ServiceImpl;
import com.yuyuan.thumb.mapper.OperationExperimentMapper;
import com.yuyuan.thumb.model.entity.OperationExperiment;
import com.yuyuan.thumb.service.OperationExperimentService;
import org.springframework.stereotype.Service;

import java.util.List;

@Service
public class OperationExperimentServiceImpl extends ServiceImpl<OperationExperimentMapper, OperationExperiment>
        implements OperationExperimentService {
    @Override
    public List<OperationExperiment> listByActionId(String actionId) {
        return list(new LambdaQueryWrapper<OperationExperiment>()
                .eq(OperationExperiment::getActionId, actionId)
                .orderByDesc(OperationExperiment::getCreatedAt));
    }
}
