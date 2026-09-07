package com.yuyuan.thumb.service.impl;

import com.baomidou.mybatisplus.extension.service.impl.ServiceImpl;
import com.yuyuan.thumb.mapper.OperationFindingMapper;
import com.yuyuan.thumb.model.entity.OperationFinding;
import com.yuyuan.thumb.service.OperationFindingService;
import org.springframework.stereotype.Service;

@Service
public class OperationFindingServiceImpl extends ServiceImpl<OperationFindingMapper, OperationFinding>
        implements OperationFindingService {
}
