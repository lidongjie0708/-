package com.yuyuan.thumb.model.dto.agent;

import com.fasterxml.jackson.databind.JsonNode;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotNull;
import lombok.Data;

import java.time.LocalDateTime;

@Data
public class CreateOperationActionRequest {
    private String findingId;
    @NotBlank private String actionType;
    @NotBlank private String targetType;
    @NotBlank private String targetId;
    @NotBlank private String reason;
    @NotNull private JsonNode proposedPayload;
    private JsonNode evidence;
    private LocalDateTime expiresAt;
}
