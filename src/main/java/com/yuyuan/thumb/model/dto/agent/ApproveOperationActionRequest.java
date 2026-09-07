package com.yuyuan.thumb.model.dto.agent;

import jakarta.validation.constraints.NotBlank;
import lombok.Data;

@Data
public class ApproveOperationActionRequest {
    /** APPROVE or REJECT */
    @NotBlank private String decision;
    private String reason;
}
