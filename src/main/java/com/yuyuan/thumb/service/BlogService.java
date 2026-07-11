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
    
    boolean isAuthor(Long id, String username);

    boolean updateByIdWithoutAgent(Blog blog);
}
