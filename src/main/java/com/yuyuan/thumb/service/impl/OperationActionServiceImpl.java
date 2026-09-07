package com.yuyuan.thumb.service.impl;

import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.baomidou.mybatisplus.core.conditions.update.LambdaUpdateWrapper;
import com.baomidou.mybatisplus.extension.service.impl.ServiceImpl;
import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.databind.node.ObjectNode;
import com.yuyuan.thumb.config.RabbitMQAgentConfig;
import com.yuyuan.thumb.mapper.OperationActionMapper;
import com.yuyuan.thumb.model.dto.agent.CreateOperationActionRequest;
import com.yuyuan.thumb.model.entity.OperationAction;
import com.yuyuan.thumb.service.OperationActionService;
import com.yuyuan.thumb.service.OutboxEventService;
import lombok.RequiredArgsConstructor;
import org.springframework.dao.DuplicateKeyException;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.time.LocalDateTime;
import java.util.Locale;
import java.util.Map;
import java.util.UUID;

@Service
@RequiredArgsConstructor
public class OperationActionServiceImpl extends ServiceImpl<OperationActionMapper, OperationAction>
        implements OperationActionService {
    private final ObjectMapper objectMapper;
    private final OutboxEventService outboxEventService;

    @Override
    @Transactional
    public OperationAction create(CreateOperationActionRequest request, String idempotencyKey, Long actorId) {
        if (idempotencyKey == null || idempotencyKey.isBlank() || idempotencyKey.length() > 128) {
            throw new OperationActionException("IDEMPOTENCY_CONFLICT", "A valid Idempotency-Key is required");
        }
        ActionPolicy policy = ActionPolicy.forType(request.getActionType());
        JsonNode payload = sanitizePayload(policy, request.getProposedPayload());
        String payloadJson = writeJson(payload);
        String payloadHash = sha256(payloadJson);
        OperationAction existing = getOne(new LambdaQueryWrapper<OperationAction>()
                .eq(OperationAction::getIdempotencyKey, idempotencyKey), false);
        if (existing != null) {
            if (sameRequest(existing, request, payloadHash)) return existing;
            throw new OperationActionException("IDEMPOTENCY_CONFLICT", "Idempotency-Key was used for a different action");
        }
        OperationAction action = new OperationAction();
        action.setId(UUID.randomUUID().toString());
        action.setFindingId(request.getFindingId());
        action.setActionType(policy.type());
        action.setTargetType(request.getTargetType().trim());
        action.setTargetId(request.getTargetId().trim());
        action.setReason(request.getReason().trim());
        action.setProposedPayloadJson(payloadJson);
        action.setPayloadHash(payloadHash);
        action.setPayloadSchemaVersion("v1");
        action.setEvidenceJson(request.getEvidence() == null ? null : writeJson(request.getEvidence()));
        action.setRiskLevel(policy.riskLevel());
        action.setApprovalRequired(policy.approvalRequired());
        action.setStatus(policy.approvalRequired() ? "PENDING_APPROVAL" : "APPROVED");
        action.setIdempotencyKey(idempotencyKey);
        action.setCreatedBy(actorId);
        action.setExpiresAt(request.getExpiresAt());
        if (request.getExpiresAt() != null && !request.getExpiresAt().isAfter(LocalDateTime.now())) {
            throw new OperationActionException("ACTION_EXPIRED", "expiresAt must be in the future");
        }
        try {
            save(action);
        } catch (DuplicateKeyException e) {
            OperationAction concurrent = getOne(new LambdaQueryWrapper<OperationAction>()
                    .eq(OperationAction::getIdempotencyKey, idempotencyKey), false);
            if (concurrent != null && sameRequest(concurrent, request, payloadHash)) return concurrent;
            throw new OperationActionException("IDEMPOTENCY_CONFLICT", "Idempotency-Key was used for a different action");
        }
        if (!policy.approvalRequired()) createApprovedOutbox(action);
        return action;
    }

    @Override
    @Transactional
    public OperationAction approve(String actionId, String decision, String reason, Long actorId) {
        OperationAction action = getById(actionId);
        if (action == null) throw new OperationActionException("NOT_FOUND", "Action not found");
        if (actorId.equals(action.getCreatedBy())) throw new OperationActionException("NO_PERMISSION", "Creator cannot approve their own action");
        if (!"PENDING_APPROVAL".equals(action.getStatus())) {
            throw new OperationActionException("APPROVAL_CONFLICT", "Action is not pending approval");
        }
        if (action.getExpiresAt() != null && !action.getExpiresAt().isAfter(LocalDateTime.now())) {
            update(new LambdaUpdateWrapper<OperationAction>().eq(OperationAction::getId, actionId)
                    .eq(OperationAction::getStatus, "PENDING_APPROVAL").set(OperationAction::getStatus, "EXPIRED"));
            throw new OperationActionException("ACTION_EXPIRED", "Action has expired");
        }
        String normalized = decision.trim().toUpperCase(Locale.ROOT);
        if (!"APPROVE".equals(normalized) && !"REJECT".equals(normalized)) {
            throw new OperationActionException("APPROVAL_CONFLICT", "decision must be APPROVE or REJECT");
        }
        if ("REJECT".equals(normalized) && (reason == null || reason.isBlank())) {
            throw new OperationActionException("APPROVAL_CONFLICT", "A rejection reason is required");
        }
        boolean updated = update(new LambdaUpdateWrapper<OperationAction>().eq(OperationAction::getId, actionId)
                .eq(OperationAction::getStatus, "PENDING_APPROVAL")
                .set(OperationAction::getStatus, "APPROVE".equals(normalized) ? "APPROVED" : "REJECTED")
                .set(OperationAction::getApprovedBy, actorId)
                .set(OperationAction::getApprovedAt, LocalDateTime.now())
                .set(OperationAction::getRejectionReason, "REJECT".equals(normalized) ? truncate(reason.trim(), 500) : null));
        if (!updated) throw new OperationActionException("APPROVAL_CONFLICT", "Action was already decided");
        action = getById(actionId);
        if ("APPROVED".equals(action.getStatus())) createApprovedOutbox(action);
        return action;
    }

    private void createApprovedOutbox(OperationAction action) {
        outboxEventService.create("OPERATION_ACTION_APPROVED", "OPERATION_ACTION", action.getId(),
                RabbitMQAgentConfig.AGENT_EXCHANGE, RabbitMQAgentConfig.OPERATION_ACTION_ROUTING_KEY,
                Map.of("actionId", action.getId(), "idempotencyKey", action.getIdempotencyKey(), "actionType", action.getActionType()));
    }

    private boolean sameRequest(OperationAction action, CreateOperationActionRequest request, String hash) {
        return action.getActionType().equalsIgnoreCase(request.getActionType().trim())
                && action.getTargetType().equals(request.getTargetType().trim())
                && action.getTargetId().equals(request.getTargetId().trim()) && action.getPayloadHash().equals(hash);
    }
    /** Keep only the contract fields; model-supplied extras never reach a command consumer. */
    private JsonNode sanitizePayload(ActionPolicy policy, JsonNode payload) {
        if (!payload.isObject()) throw new OperationActionException("ACTION_SCHEMA_INVALID", "proposedPayload must be an object");
        if ("SEO_REWRITE_DRAFT".equals(policy.type()) && (!payload.path("title").isTextual() || !payload.path("summary").isTextual()))
            throw new OperationActionException("ACTION_SCHEMA_INVALID", "SEO_REWRITE_DRAFT requires title and summary");
        ObjectNode allowed = objectMapper.createObjectNode();
        switch (policy.type()) {
            case "SEO_REWRITE_DRAFT" -> {
                allowed.put("title", payload.path("title").asText());
                allowed.put("summary", payload.path("summary").asText());
                if (payload.path("keywords").isArray()) allowed.set("keywords", payload.path("keywords"));
            }
            case "CREATE_OPERATION_TODO" -> copyTextFields(payload, allowed, "title", "description", "dueAt");
            case "REQUEST_MANUAL_REVIEW" -> copyTextFields(payload, allowed, "reviewReason", "queue");
            default -> throw new OperationActionException("ACTION_SCHEMA_INVALID", "Action type is not allowed");
        }
        return allowed;
    }
    private void copyTextFields(JsonNode source, ObjectNode target, String... fields) {
        for (String field : fields) if (source.path(field).isTextual()) target.put(field, source.path(field).asText());
    }
    private String writeJson(JsonNode value) { try { return objectMapper.writeValueAsString(value); } catch (JsonProcessingException e) { throw new OperationActionException("ACTION_SCHEMA_INVALID", "Invalid JSON payload"); } }
    private String sha256(String value) { try { byte[] bytes = MessageDigest.getInstance("SHA-256").digest(value.getBytes(StandardCharsets.UTF_8)); StringBuilder b = new StringBuilder(64); for (byte x : bytes) b.append(String.format("%02x", x)); return b.toString(); } catch (Exception e) { throw new IllegalStateException("SHA-256 unavailable", e); } }
    private String truncate(String value, int maxLength) { return value.length() <= maxLength ? value : value.substring(0, maxLength); }

    private record ActionPolicy(String type, String riskLevel, boolean approvalRequired) {
        static ActionPolicy forType(String actionType) {
            String type = actionType == null ? "" : actionType.trim().toUpperCase(Locale.ROOT);
            return switch (type) {
                case "CREATE_OPERATION_TODO" -> new ActionPolicy(type, "LOW", false);
                case "SEO_REWRITE_DRAFT", "REQUEST_MANUAL_REVIEW" -> new ActionPolicy(type, "MEDIUM", true);
                default -> throw new OperationActionException("ACTION_SCHEMA_INVALID", "Action type is not allowed");
            };
        }
    }
}
