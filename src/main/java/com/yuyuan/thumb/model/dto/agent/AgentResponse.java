package com.yuyuan.thumb.model.dto.agent;

import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

import java.util.List;
import java.util.Map;

/**
 * Python Agent 服务返回的响应体
 * <p>
 * 统一响应结构，所有 Agent 接口返回此格式。
 */
@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
public class AgentResponse {

    /** 是否成功 */
    private boolean success;

    /** 任务类型，与请求中的 action 对应 */
    private String action;

    /** 处理结果，不同 action 对应不同结构 */
    private Map<String, Object> result;

    /** 错误信息（success=false 时） */
    private String errorMessage;

    // ========== 便捷提取方法 ==========

    /** 提取摘要 */
    public String getSummary() {
        return result != null ? (String) result.get("summary") : null;
    }

    /** 提取标签列表 */
    @SuppressWarnings("unchecked")
    public List<String> getTags() {
        return result != null ? (List<String>) result.get("tags") : null;
    }

    /** 提取情感得分 */
    public Double getSentimentScore() {
        return result != null ? (Double) result.get("sentiment_score") : null;
    }

    /** 提取审核是否通过 */
    public Boolean getIsApproved() {
        return result != null ? (Boolean) result.get("is_approved") : null;
    }

    public Boolean getEmbedSuccess() {
        return result != null ? (Boolean) result.get("embed_success") : null;
    }
}
