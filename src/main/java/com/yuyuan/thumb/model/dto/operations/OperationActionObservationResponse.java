package com.yuyuan.thumb.model.dto.operations;

import com.yuyuan.thumb.model.entity.OperationExperiment;
import lombok.Data;

import java.util.List;

/** Read-only observation payload; a result is never presented as causal proof. */
@Data
public class OperationActionObservationResponse {
    private String actionId;
    private List<OperationExperiment> experiments;
}
