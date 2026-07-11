package com.yuyuan.thumb.service.impl;

import com.baomidou.mybatisplus.extension.service.impl.ServiceImpl;
import com.yuyuan.thumb.mapper.AgentAnalysisLogMapper;
import com.yuyuan.thumb.model.entity.AgentAnalysisLog;
import com.yuyuan.thumb.service.AgentAnalysisLogService;
import org.springframework.stereotype.Service;

@Service
public class AgentAnalysisLogServiceImpl extends ServiceImpl<AgentAnalysisLogMapper, AgentAnalysisLog>
        implements AgentAnalysisLogService {
}
