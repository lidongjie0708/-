package com.yuyuan.thumb.service.impl;

import com.baomidou.mybatisplus.core.conditions.query.QueryWrapper;
import com.baomidou.mybatisplus.extension.plugins.pagination.Page;
import com.baomidou.mybatisplus.extension.service.impl.ServiceImpl;
import com.yuyuan.thumb.config.RabbitMQAgentConfig;
import com.yuyuan.thumb.listener.agent.msg.CommentAgentEvent;
import com.yuyuan.thumb.mapper.UserMapper;
import com.yuyuan.thumb.model.dto.blog.PageRequest;
import com.yuyuan.thumb.model.dto.comment.CommentDto;
import com.yuyuan.thumb.model.entity.Comments;
import com.yuyuan.thumb.model.entity.User;
import com.yuyuan.thumb.service.CommentService;
import com.yuyuan.thumb.mapper.CommentsMapper;
import com.yuyuan.thumb.model.vo.CommentVo;
import lombok.extern.slf4j.Slf4j;
import org.redisson.api.RRateLimiter;
import org.redisson.api.RateIntervalUnit;
import org.redisson.api.RateType;
import org.redisson.api.RedissonClient;
import org.springframework.amqp.rabbit.core.RabbitTemplate;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Service;

import java.time.LocalDateTime;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;
import java.util.Map;

/**
 * 评论Service实现
 */
@Slf4j
@Service
public class CommentServiceImpl extends ServiceImpl<CommentsMapper, Comments>
        implements CommentService {

    @Autowired
    private CommentsMapper commentsMapper;

    @Autowired
    private UserMapper userMapper;
    @Autowired
    private RedissonClient redissonClient;
    @Autowired
    private RabbitTemplate rabbitTemplate;

    @Override
    public Comments createComment(CommentDto commentDto, Long userId) {
        String blogId = commentDto.getBlogId();
        if (blogId == null) {
            return null;
        }

        Long parentId = commentDto.getParentId();
        if (parentId != null && parentId > 0) {
            Comments parentComment = commentsMapper.selectById(parentId);
            if (parentComment == null) {
                throw new IllegalArgumentException("父评论不存在");
            }
        }

        // ========== 限流检查 ==========

        // 1. 用户级限流：每分钟最多10次评论（包括一级和子评论）
        String userRateLimitKey = "comment:ratelimit:user:" + userId;
        RRateLimiter userRateLimiter = redissonClient.getRateLimiter(userRateLimitKey);
        userRateLimiter.setRate(RateType.OVERALL, 10, 1, RateIntervalUnit.MINUTES);

        if (!userRateLimiter.tryAcquire()) {
            throw new RuntimeException("评论过于频繁，请稍后重试（每分钟最多10次）");
        }

        // 2. 博客级限流：每分钟对同一博客最多5条一级评论
        if (parentId == null || parentId == 0) {
            String blogRateLimitKey = "comment:ratelimit:blog:" + blogId;
            RRateLimiter blogRateLimiter = redissonClient.getRateLimiter(blogRateLimitKey);
            blogRateLimiter.setRate(RateType.OVERALL, 5, 1, RateIntervalUnit.MINUTES);

            if (!blogRateLimiter.tryAcquire()) {
                throw new RuntimeException("该博客的评论过于频繁，请稍后重试（每分钟最多5条一级评论）");
            }
        }

        // 子评论不限流，允许正常讨论交流
        // ========== 限流检查结束 ==========

        Comments comment = new Comments();
        comment.setBlogId(commentDto.getBlogId());
        comment.setUserId(userId);
        comment.setContent(commentDto.getContent());

        if (parentId != null && parentId > 0) {
            comment.setParentId(parentId);
        } else {
            comment.setParentId(0L);
        }

        comment.setIsDeleted(0);
        commentsMapper.insert(comment);
        publishCommentAgentEvent(comment);
        return comment;
    }

    @Override
    public Comments createReply(Long parentId, String content, Long userId) {
        Comments parent = commentsMapper.selectById(parentId);
        if (parent == null || Integer.valueOf(1).equals(parent.getIsDeleted())) {
            throw new IllegalArgumentException("父评论不存在");
        }
        CommentDto dto = new CommentDto();
        dto.setBlogId(parent.getBlogId());
        dto.setParentId(parentId);
        dto.setContent(content.trim());
        return createComment(dto, userId);
    }

    private void publishCommentAgentEvent(Comments comment) {
        try {
            CommentAgentEvent event = CommentAgentEvent.builder()
                    .commentId(comment.getId())
                    .blogId(comment.getBlogId())
                    .userId(comment.getUserId())
                    .eventTime(LocalDateTime.now())
                    .build();
            rabbitTemplate.convertAndSend(
                    RabbitMQAgentConfig.AGENT_EXCHANGE,
                    RabbitMQAgentConfig.COMMENT_AGENT_ROUTING_KEY,
                    event
            );
        } catch (Exception e) {
            log.error("发送评论 Agent 事件失败: commentId={}", comment.getId(), e);
        }
    }


    @Override
    public Page<CommentVo> pageCommentsByBlogId(String blogId, PageRequest pageRequest) {
        Page<Comments> page = new Page<>(pageRequest.getPageNum(), pageRequest.getPageSize());
        
        QueryWrapper<Comments> queryWrapper = new QueryWrapper<>();
        queryWrapper.eq("blog_id", blogId)
                    .eq("parent_id", 0)
                    .eq("is_deleted", 0);
        
        if (pageRequest.getSortField() != null && !pageRequest.getSortField().isEmpty()) {
            String sortOrder = "desc".equalsIgnoreCase(pageRequest.getSortOrder()) ? "DESC" : "ASC";
            queryWrapper.orderBy(true, "ASC".equals(sortOrder), pageRequest.getSortField());
        } else {
            queryWrapper.orderByAsc("created_at");
        }
        
        Page<Comments> commentPage = commentsMapper.selectPage(page, queryWrapper);
        
        List<Long> rootCommentIds = commentPage.getRecords().stream()
                .map(Comments::getId)
                .toList();
        
        QueryWrapper<Comments> childQueryWrapper = new QueryWrapper<>();
        childQueryWrapper.eq("blog_id", blogId)
                        .in("parent_id", rootCommentIds)
                        .eq("is_deleted", 0)
                        .orderByAsc("created_at");
        List<Comments> childComments = commentsMapper.selectList(childQueryWrapper);
        
        Map<Long, CommentVo> commentVoMap = new HashMap<>();
        List<CommentVo> rootComments = new ArrayList<>();
        
        for (Comments comment : commentPage.getRecords()) {
            CommentVo vo = new CommentVo();
            vo.setId(comment.getId());
            vo.setContent(comment.getContent());
            vo.setCreatedAt(comment.getCreatedAt());
            vo.setUserId(comment.getUserId());
            vo.setParentId(comment.getParentId());
            
            User user = userMapper.selectById(comment.getUserId());
            vo.setUsername(user != null ? user.getUsername() : "未知用户");
            vo.setChildren(new ArrayList<>());
            
            commentVoMap.put(vo.getId(), vo);
            rootComments.add(vo);
        }
        
        for (Comments comment : childComments) {
            CommentVo vo = new CommentVo();
            vo.setId(comment.getId());
            vo.setContent(comment.getContent());
            vo.setCreatedAt(comment.getCreatedAt());
            vo.setUserId(comment.getUserId());
            vo.setParentId(comment.getParentId());
            
            User user = userMapper.selectById(comment.getUserId());
            vo.setUsername(user != null ? user.getUsername() : "未知用户");
            vo.setChildren(new ArrayList<>());
            
            commentVoMap.put(vo.getId(), vo);
        }
        
        for (CommentVo vo : commentVoMap.values()) {
            if (vo.getParentId() != 0) {
                CommentVo parentVo = commentVoMap.get(vo.getParentId());
                if (parentVo != null) {
                    parentVo.getChildren().add(vo);
                }
            }
        }
        
        Page<CommentVo> result = new Page<>(commentPage.getCurrent(), commentPage.getSize(), commentPage.getTotal());
        result.setRecords(rootComments);
        
        return result;
    }

    @Override
    public List<CommentVo> getCommentsByBlogId(String blogId) {
        List<Comments> comments = commentsMapper.selectCommentsByBlogId(blogId);
        if (comments.isEmpty()) {
            return new ArrayList<>();
        }

        Map<Long, CommentVo> commentVoMap = new HashMap<>();
        List<CommentVo> rootComments = new ArrayList<>();

        for (Comments comment : comments) {
            CommentVo vo = new CommentVo();
            vo.setId(comment.getId());
            vo.setContent(comment.getContent());
            vo.setCreatedAt(comment.getCreatedAt());
            vo.setUserId(comment.getUserId());

            User user = userMapper.selectById(comment.getUserId());
            vo.setUsername(user != null ? user.getUsername() : "未知用户");
            vo.setParentId(comment.getParentId());
            vo.setChildren(new ArrayList<>());
            commentVoMap.put(vo.getId(), vo);
        }

        for (CommentVo vo : commentVoMap.values()) {
            if (vo.getParentId() == 0) {
                rootComments.add(vo);
            } else {
                CommentVo parentVo = commentVoMap.get(vo.getParentId());
                if (parentVo != null) {
                    parentVo.getChildren().add(vo);
                }
            }
        }

        return rootComments;
    }

    @Override
    public boolean deleteComment(Long userId, Long commentId) {
        Comments comments = commentsMapper.selectById(commentId);
        if (comments == null) {
            throw new RuntimeException("评论不存在");
        }
        if (!comments.getUserId().equals(userId)) {
            throw new RuntimeException("需要本人操作");
        }
        return commentsMapper.deleteById(commentId) > 0;
    }

    @Override
    public Long countCommentsByBlogId(String blogId) {
        return commentsMapper.countCommentsByBlogId(blogId);
    }
}
