package com.yuyuan.thumb.service;

import com.baomidou.mybatisplus.extension.plugins.pagination.Page;
import com.yuyuan.thumb.model.dto.blog.PageRequest;
import com.yuyuan.thumb.model.entity.Blog;
import com.baomidou.mybatisplus.extension.service.IService;
import com.yuyuan.thumb.model.entity.User;
import com.yuyuan.thumb.model.vo.BlogVO;
import jakarta.servlet.http.HttpServletRequest;

import java.util.List;

/**
 * 博客Service接口
 * @author pine
 */
public interface BlogService extends IService<Blog> {
    Page<BlogVO> pageBlogs(PageRequest pageRequest, HttpServletRequest request);
    Page<BlogVO> pageMyBlogs(PageRequest pageRequest, HttpServletRequest request);

    BlogVO getBlogVOById(long blogId, HttpServletRequest request);

    BlogVO getBlogVO(Blog blog, User loginUser);

    List<BlogVO> getBlogVOList(List<Blog> blogList, HttpServletRequest request);
    
    List<Blog> getByUsername(String username);

    /**
     * Fills thumbCount with the exact real-time value (MySQL base + pending Redis delta),
     * so the displayed count is fresh even before the next flush batch.
     */
    void fillRealTimeThumbCount(Blog blog);

    void fillRealTimeThumbCounts(List<Blog> blogs);
    
    boolean isAuthor(Long id, String username);

    boolean updateByIdWithoutAgent(Blog blog);

    /**
     * 只更新 Agent 负责的字段（summary/tags/embedding_status），
     * 避免整行回写覆盖并发修改的其他字段（如 thumbCount）。
     *
     * @param summary 摘要，null 表示不更新
     * @param tags    标签（逗号分隔），null 表示不更新
     */
    void updateAgentFields(Long blogId, String summary, String tags, Integer embeddingStatus);
}
