package com.yuyuan.thumb.service.agent;

import com.yuyuan.thumb.config.AgentConfig;
import com.yuyuan.thumb.model.dto.agent.AgentRequest;
import com.yuyuan.thumb.model.dto.agent.AgentResponse;
import com.yuyuan.thumb.model.entity.Blog;
import com.yuyuan.thumb.model.entity.Comments;
import com.yuyuan.thumb.model.enums.AuditStatusEnum;
import com.yuyuan.thumb.model.enums.EmbeddingStatusEnum;
import com.yuyuan.thumb.service.BlogService;
import com.yuyuan.thumb.service.CommentService;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Service;

import java.util.HashMap;
import java.util.List;
import java.util.Map;

/**
 * Agent 业务编排服务
 * <p>
 * 负责编排 Agent 调用流程，处理结果回写，以及降级策略。
 * 所有 Agent 相关的业务逻辑集中在此，不污染现有 Service。
 */
@Slf4j
@Service
@RequiredArgsConstructor
public class AgentService {

    private final AgentClient agentClient;
    private final AgentConfig agentConfig;
    private final BlogService blogService;
    private final CommentService commentService;

    // ========== 博客相关 Agent 任务 ==========

    /**
     * 触发博客摘要生成 + 标签推荐 + 向量化
     * 在博客创建/更新后异步调用
     */
    public void processBlogAsync(Blog blog) {
        if (!agentConfig.isEnabled()) {
            log.debug("Agent 已禁用，跳过博客处理: blogId={}", blog.getId());
            return;
        }

        doProcessBlog(blog);
    }

    /**
     * 同步处理博客（用于 RabbitMQ 消费者调用）
     */
    public void processBlogSync(Blog blog) {
        if (!agentConfig.isEnabled()) {
            log.debug("Agent 宸茬鐢紝璺宠繃鍗氬澶勭悊: blogId={}", blog.getId());
            return;
        }
        doProcessBlog(blog);
    }

    private void doProcessBlog(Blog blog) {
        try {
            // 1. 标记为处理中
            blog.setEmbeddingStatus(EmbeddingStatusEnum.PROCESSING.getCode());
            blogService.updateByIdWithoutAgent(blog);

            AgentResponse response = callBlogProcessAgent(blog);
            String summary = response.getSummary();
            List<String> tags = response.getTags();
            Boolean embedSuccess = response.getEmbedSuccess();

            // 5. 回写结果
            blog.setSummary(summary);
            if (tags != null && !tags.isEmpty()) {
                blog.setTags(String.join(",", tags));
            }
            blog.setEmbeddingStatus(Boolean.TRUE.equals(embedSuccess)
                    ? EmbeddingStatusEnum.COMPLETED.getCode()
                    : EmbeddingStatusEnum.FAILED.getCode());
            blogService.updateByIdWithoutAgent(blog);

            log.info("博客 Agent 处理完成: blogId={}, summaryLen={}, tags={}, embedSuccess={}",
                    blog.getId(), summary != null ? summary.length() : 0, tags, embedSuccess);

        } catch (Exception e) {
            log.error("博客 Agent 处理异常: blogId={}", blog.getId(), e);
            blog.setEmbeddingStatus(EmbeddingStatusEnum.FAILED.getCode());
            blogService.updateByIdWithoutAgent(blog);
        }
    }

    // ========== 评论相关 Agent 任务 ==========

    /**
     * 触发评论审核 + 情感分析
     * 在评论创建后异步调用
     */
    public void processCommentAsync(Comments comment) {
        if (!agentConfig.isEnabled()) {
            log.debug("Agent 已禁用，跳过评论处理: commentId={}", comment.getId());
            return;
        }
        doProcessComment(comment);
    }

    /**
     * 同步处理评论（用于 RabbitMQ 消费者调用）
     */
    public void processCommentSync(Comments comment) {
        if (!agentConfig.isEnabled()) {
            log.debug("Agent 宸茬鐢紝璺宠繃璇勮澶勭悊: commentId={}", comment.getId());
            return;
        }
        doProcessComment(comment);
    }

    private void doProcessComment(Comments comment) {
        try {
            AgentRequest request = AgentRequest.builder()
                    .action("audit-comment")
                    .content(comment.getContent())
                    .contentId(String.valueOf(comment.getId()))
                    .extra(buildExtra(comment))
                    .build();

            AgentResponse response = agentClient.execute(request);

            if (response.isSuccess()) {
                // 情感得分
                Double sentimentScore = response.getSentimentScore();
                if (sentimentScore != null) {
                    // 情感得分范围 -1.0~1.0，转为数据库 -100~100 整数存储
                    comment.setSentimentScore((int) (sentimentScore * 100));
                }

                // 审核结果
                Boolean isApproved = response.getIsApproved();
                if (isApproved != null) {
                    comment.setIsFlagged(isApproved ? 0 : 1);
                }

                commentService.updateById(comment);
                log.info("评论 Agent 处理完成: commentId={}, sentiment={}, approved={}",
                        comment.getId(), sentimentScore, response.getIsApproved());
            } else {
                log.warn("评论 Agent 处理失败: commentId={}, error={}",
                        comment.getId(), response.getErrorMessage());
            }
        } catch (Exception e) {
            log.error("评论 Agent 处理异常: commentId={}", comment.getId(), e);
        }
    }

    // ========== 私有方法 ==========

    private String callSummaryAgent(Blog blog) {
        AgentRequest request = AgentRequest.builder()
                .action("summary")
                .title(blog.getTitle())
                .content(blog.getContent())
                .contentId(String.valueOf(blog.getId()))
                .build();
        AgentResponse response = agentClient.execute(request);
        return response.isSuccess() ? response.getSummary() : null;
    }

    private List<String> callTagsAgent(Blog blog) {
        AgentRequest request = AgentRequest.builder()
                .action("tags")
                .title(blog.getTitle())
                .content(blog.getContent())
                .contentId(String.valueOf(blog.getId()))
                .build();
        AgentResponse response = agentClient.execute(request);
        return response.isSuccess() ? response.getTags() : null;
    }

    private boolean callEmbedAgent(Blog blog, String summary, List<String> tags) {
        Map<String, Object> extra = new HashMap<>();
        extra.put("summary", summary != null ? summary : "");
        extra.put("tags", tags != null && !tags.isEmpty() ? String.join(",", tags) : "");
        extra.put("userId", blog.getUserId());
        extra.put("visibility", "PUBLIC");
        extra.put("status", buildRagStatus(blog));

        AgentRequest request = AgentRequest.builder()
                .action("embed")
                .title(blog.getTitle())
                .content(blog.getContent() != null ? blog.getContent() : "")
                .contentId(String.valueOf(blog.getId()))
                .extra(extra)
                .build();
        AgentResponse response = agentClient.execute(request);
        return response.isSuccess();
    }

    private AgentResponse callBlogProcessAgent(Blog blog) {
        Map<String, Object> extra = new HashMap<>();
        extra.put("userId", blog.getUserId());
        extra.put("visibility", "PUBLIC");
        extra.put("status", buildRagStatus(blog));

        AgentRequest request = AgentRequest.builder()
                .action("blog-process")
                .title(blog.getTitle())
                .content(blog.getContent() != null ? blog.getContent() : "")
                .contentId(String.valueOf(blog.getId()))
                .extra(extra)
                .build();
        return agentClient.execute(request);
    }

    private String buildRagStatus(Blog blog) {
        if (blog.getAuditStatus() != null && blog.getAuditStatus() == AuditStatusEnum.REJECTED.getCode()) {
            return "REJECTED";
        }
        if (blog.getAuditStatus() == null || blog.getAuditStatus() != AuditStatusEnum.APPROVED.getCode()) {
            return "DRAFT";
        }
        return "PUBLISHED";
    }

    private Map<String, Object> buildExtra(Comments comment) {
        Map<String, Object> extra = new HashMap<>();
        extra.put("userId", comment.getUserId());
        extra.put("blogId", comment.getBlogId());
        return extra;
    }
}
