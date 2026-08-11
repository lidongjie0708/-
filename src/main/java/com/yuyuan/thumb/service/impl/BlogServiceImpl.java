package com.yuyuan.thumb.service.impl;

import cn.hutool.core.bean.BeanUtil;
import cn.hutool.core.util.ObjUtil;
import com.baomidou.mybatisplus.core.conditions.query.QueryWrapper;
import com.baomidou.mybatisplus.core.conditions.update.LambdaUpdateWrapper;
import com.baomidou.mybatisplus.extension.plugins.pagination.Page;
import com.baomidou.mybatisplus.extension.service.impl.ServiceImpl;
import com.yuyuan.thumb.config.RabbitMQAgentConfig;
import com.yuyuan.thumb.listener.agent.msg.BlogAgentEvent;
import com.yuyuan.thumb.model.dto.blog.PageRequest;
import com.yuyuan.thumb.model.entity.Blog;
import com.yuyuan.thumb.model.entity.User;
import com.yuyuan.thumb.model.vo.BlogVO;
import com.yuyuan.thumb.service.BlogService;
import com.yuyuan.thumb.mapper.BlogMapper;
import com.yuyuan.thumb.mapper.UserMapper;
import com.yuyuan.thumb.service.OutboxEventService;
import com.yuyuan.thumb.service.ThumbService;
import com.yuyuan.thumb.service.UserService;
import com.yuyuan.thumb.util.RedisKeyUtil;
import jakarta.annotation.Resource;
import jakarta.servlet.http.HttpServletRequest;
import org.springframework.stereotype.Service;
import org.springframework.context.annotation.Lazy;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.beans.factory.annotation.Qualifier;
import org.springframework.data.redis.core.RedisTemplate;

import java.time.LocalDateTime;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;
import java.util.Map;

import lombok.extern.slf4j.Slf4j;

/**
 * @author pine
 */
@Slf4j
@Service
public class BlogServiceImpl extends ServiceImpl<BlogMapper, Blog>
        implements BlogService {

    @Resource
    private UserService userService;

    @Resource
    @Lazy
    @Qualifier("thumbServiceRabbitMQ")
    private ThumbService thumbService;
    
    @Resource
    private UserMapper userMapper;
    
    @Resource
    private BlogMapper blogMapper;

    @Resource
    private OutboxEventService outboxEventService;

    @Resource
    private RedisTemplate<String, Object> redisTemplate;

    @Override
    public Page<BlogVO> pageBlogs(PageRequest pageRequest, HttpServletRequest request) {
        Page<Blog> page = new Page<>(pageRequest.getPageNum(), pageRequest.getPageSize());
        
        QueryWrapper<Blog> queryWrapper = new QueryWrapper<>();
        applyBlogFilters(queryWrapper, pageRequest);
        
        String sortField = resolveSortField(pageRequest.getSortField());
        if (sortField != null) {
            String sortOrder = "desc".equalsIgnoreCase(pageRequest.getSortOrder()) ? "DESC" : "ASC";
            queryWrapper.orderBy(true, "ASC".equals(sortOrder), sortField);
        } else {
            queryWrapper.orderByDesc("createTime");
        }
        
        Page<Blog> blogPage = this.page(page, queryWrapper);
        
        List<BlogVO> blogVOList = getBlogVOList(blogPage.getRecords(), request);
        
        Page<BlogVO> result = new Page<>(blogPage.getCurrent(), blogPage.getSize(), blogPage.getTotal());
        result.setRecords(blogVOList);
        
        return result;
    }

    @Override
    public Page<BlogVO> pageMyBlogs(PageRequest pageRequest, HttpServletRequest request) {
        User loginUser = userService.getLoginUser(request);
        if (loginUser == null) {
            throw new RuntimeException("用户未登录");
        }
        
        Page<Blog> page = new Page<>(pageRequest.getPageNum(), pageRequest.getPageSize());
        
        QueryWrapper<Blog> queryWrapper = new QueryWrapper<>();
        queryWrapper.eq("userId", loginUser.getId());
        applyBlogFilters(queryWrapper, pageRequest);
        
        String sortField = resolveSortField(pageRequest.getSortField());
        if (sortField != null) {
            String sortOrder = "desc".equalsIgnoreCase(pageRequest.getSortOrder()) ? "DESC" : "ASC";
            queryWrapper.orderBy(true, "ASC".equals(sortOrder), sortField);
        } else {
            queryWrapper.orderByDesc("createTime");
        }
        
        Page<Blog> blogPage = this.page(page, queryWrapper);
        
        List<BlogVO> blogVOList = getBlogVOList(blogPage.getRecords(), request);
        
        Page<BlogVO> result = new Page<>(blogPage.getCurrent(), blogPage.getSize(), blogPage.getTotal());
        result.setRecords(blogVOList);
        
        return result;
    }

    @Override
    public BlogVO getBlogVOById(long blogId, HttpServletRequest request) {
        Blog blog = this.getById(blogId);
        User loginUser = userService.getLoginUser(request);
        return this.getBlogVO(blog, loginUser);
    }

    @Override
    public BlogVO getBlogVO(Blog blog, User loginUser) {
        fillRealTimeThumbCount(blog);
        BlogVO blogVO = new BlogVO();
        BeanUtil.copyProperties(blog, blogVO);

        if (loginUser != null) {
            Boolean exist = thumbService.hasThumb(blog.getId(), loginUser.getId());
            blogVO.setHasThumb(exist);
        }

        return blogVO;
    }

    @Override
    public List<BlogVO> getBlogVOList(List<Blog> blogList, HttpServletRequest request) {
        fillRealTimeThumbCounts(blogList);
        User loginUser = userService.getLoginUser(request);
        Map<Long, Boolean> blogIdHasThumbMap = new HashMap<>();
        if (ObjUtil.isNotEmpty(loginUser)) {
            for (Blog blog : blogList) {
                if (thumbService.hasThumb(blog.getId(), loginUser.getId())) {
                    blogIdHasThumbMap.put(blog.getId(), true);
                }
            }
        }

        return blogList.stream()
                .map(blog -> {
                    BlogVO blogVO = BeanUtil.copyProperties(blog, BlogVO.class);
                    blogVO.setHasThumb(blogIdHasThumbMap.get(blog.getId()));
                    return blogVO;
                })
                .toList();
    }
    
    @Override
    public List<Blog> getByUsername(String username) {
        User user = userMapper.selectOne(new QueryWrapper<User>().eq("username", username));
        if (user == null) {
            return new ArrayList<>();
        }
        return blogMapper.selectByAuthorId(user.getId());
    }

    @Override
    public void fillRealTimeThumbCount(Blog blog) {
        if (blog == null || blog.getId() == null) {
            return;
        }
        fillRealTimeThumbCounts(List.of(blog));
    }

    @Override
    public void fillRealTimeThumbCounts(List<Blog> blogs) {
        if (blogs == null || blogs.isEmpty()) {
            return;
        }
        List<Object> blogIds = blogs.stream()
                .map(blog -> (Object) blog.getId().toString())
                .toList();
        List<Object> deltas = redisTemplate.opsForHash()
                .multiGet(RedisKeyUtil.getBlogDeltaKey(), blogIds);
        for (int i = 0; i < blogs.size(); i++) {
            Blog blog = blogs.get(i);
            long delta = deltas.get(i) == null ? 0L : Long.parseLong(deltas.get(i).toString());
            long base = blog.getThumbCount() == null ? 0L : blog.getThumbCount();
            blog.setThumbCount((int) Math.min(Integer.MAX_VALUE, Math.max(0L, base + delta)));
        }
    }

    private String resolveSortField(String sortField) {
        if (sortField == null || sortField.isBlank()) {
            return null;
        }
        return switch (sortField) {
            case "id" -> "id";
            case "title" -> "title";
            case "thumbCount" -> "thumbCount";
            case "createTime" -> "createTime";
            case "updateTime" -> "updateTime";
            default -> null;
        };
    }

    private void applyBlogFilters(QueryWrapper<Blog> queryWrapper, PageRequest pageRequest) {
        String keyword = pageRequest.getKeyword();
        if (keyword != null && !keyword.isBlank()) {
            String normalizedKeyword = keyword.trim();
            queryWrapper.and(wrapper -> wrapper
                    .like("title", normalizedKeyword)
                    .or()
                    .like("content", normalizedKeyword)
                    .or()
                    .like("summary", normalizedKeyword)
                    .or()
                    .like("tags", normalizedKeyword));
        }

        String contentFormat = pageRequest.getContentFormat();
        if (contentFormat != null && !contentFormat.isBlank()) {
            String normalizedFormat = contentFormat.trim().toUpperCase();
            if ("PLAIN".equals(normalizedFormat) || "MARKDOWN".equals(normalizedFormat)) {
                queryWrapper.eq("content_format", normalizedFormat);
            }
        }
    }

    @Override
    public boolean isAuthor(Long id, String username) {
        Blog blog = getById(id);
        if (blog == null) {
            return false;
        }
        Long userId = userMapper.selectByUsername(username);
        return blog.getUserId().equals(userId);
    }

    // ========== Agent 异步事件触发 ==========

    @Override
    @Transactional(rollbackFor = Exception.class)
    public boolean save(Blog entity) {
        boolean saved = super.save(entity);
        if (saved) {
            publishBlogAgentEvent(entity, BlogAgentEvent.ActionType.CREATE);
        }
        return saved;
    }

    @Override
    @Transactional(rollbackFor = Exception.class)
    public boolean updateById(Blog entity) {
        boolean updated = super.updateById(entity);
        if (updated) {
            publishBlogAgentEvent(entity, BlogAgentEvent.ActionType.UPDATE);
        }
        return updated;
    }

    @Override
    public boolean updateByIdWithoutAgent(Blog blog) {
        return super.updateById(blog);
    }

    @Override
    public void updateAgentFields(Long blogId, String summary, String tags, Integer embeddingStatus) {
        LambdaUpdateWrapper<Blog> wrapper = new LambdaUpdateWrapper<>();
        wrapper.eq(Blog::getId, blogId)
                .set(Blog::getEmbeddingStatus, embeddingStatus);
        if (summary != null) {
            wrapper.set(Blog::getSummary, summary);
        }
        if (tags != null && !tags.isBlank()) {
            wrapper.set(Blog::getTags, tags);
        }
        update(wrapper);
    }

    private void publishBlogAgentEvent(Blog blog, BlogAgentEvent.ActionType actionType) {
        BlogAgentEvent event = BlogAgentEvent.builder()
                .blogId(blog.getId())
                .userId(blog.getUserId())
                .actionType(actionType)
                .eventTime(LocalDateTime.now())
                .build();
        outboxEventService.create(
                "BLOG_AGENT",
                "BLOG",
                String.valueOf(blog.getId()),
                RabbitMQAgentConfig.AGENT_EXCHANGE,
                RabbitMQAgentConfig.BLOG_AGENT_ROUTING_KEY,
                event
        );
    }
}
