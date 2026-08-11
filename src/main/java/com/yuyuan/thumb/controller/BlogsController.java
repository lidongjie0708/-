package com.yuyuan.thumb.controller;

import com.baomidou.mybatisplus.extension.plugins.pagination.Page;
import com.yuyuan.thumb.common.BaseResponse;
import com.yuyuan.thumb.common.ResultUtils;
import com.yuyuan.thumb.model.dto.blog.PageRequest;
import com.yuyuan.thumb.model.dto.blog.PageResponse;
import com.yuyuan.thumb.model.entity.Blog;
import com.yuyuan.thumb.model.vo.BlogVO;
import com.yuyuan.thumb.service.BlogService;
import com.yuyuan.thumb.service.UserService;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.validation.Valid;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.security.core.context.SecurityContextHolder;
import org.springframework.web.bind.annotation.*;

import java.util.Date;
import java.util.List;

/**
 * 博客控制器
 */
@RestController
@RequestMapping("/blog")
public class BlogsController {

    @Autowired
    private BlogService blogService;

    @Autowired
    private UserService userService;

    @GetMapping("/all")
    public BaseResponse<List<Blog>> getAllBlogs() {
        List<Blog> blogs = blogService.list();
        blogService.fillRealTimeThumbCounts(blogs);
        return ResultUtils.success(blogs);
    }

    @GetMapping("/my")
    public BaseResponse<List<Blog>> getMyBlogs() {
        String username = SecurityContextHolder.getContext().getAuthentication().getName();
        List<Blog> blogs = blogService.getByUsername(username);
        blogService.fillRealTimeThumbCounts(blogs);
        return ResultUtils.success(blogs);
    }

    @GetMapping("/{blogId}")
    public BaseResponse<Blog> getBlogById(@PathVariable Long blogId) {
        Blog blog = blogService.getById(blogId);
        if (blog == null) {
            return ResultUtils.error(404, "博客不存在");
        }
        blogService.fillRealTimeThumbCount(blog);
        return ResultUtils.success(blog);
    }

    @PostMapping("/create")
    public BaseResponse<Blog> createBlog(@RequestBody Blog blog) {
        normalizeAndValidateContentFormat(blog);
        String username = SecurityContextHolder.getContext().getAuthentication().getName();
        Long userId = userService.getUserIdByUsername(username);
        
        blog.setUserId(userId);
        blog.setCreateTime(new Date());
        blog.setUpdateTime(new Date());
        blog.setThumbCount(0);
        
        boolean saved = blogService.save(blog);
        if (!saved) {
            return ResultUtils.error(500, "创建失败");
        }
        return ResultUtils.success(blog);
    }

    @PutMapping("/{blogId}")
    public BaseResponse<Blog> updateBlog(@PathVariable Long blogId, @RequestBody Blog blog) {
        String username = SecurityContextHolder.getContext().getAuthentication().getName();
        if (!blogService.isAuthor(blogId, username)) {
            return ResultUtils.error(403, "无权限");
        }
        
        normalizeAndValidateContentFormat(blog);
        blog.setId(blogId);
        blog.setUpdateTime(new Date());
        boolean updated = blogService.updateById(blog);
        
        return updated ? ResultUtils.success(blog) : ResultUtils.error(500, "更新失败");
    }

    private void normalizeAndValidateContentFormat(Blog blog) {
        String format = blog.getContentFormat();
        format = format == null || format.isBlank() ? "PLAIN" : format.trim().toUpperCase();
        if (!"PLAIN".equals(format) && !"MARKDOWN".equals(format)) {
            throw new IllegalArgumentException("contentFormat 仅支持 PLAIN 或 MARKDOWN");
        }
        blog.setContentFormat(format);
    }

    @DeleteMapping("/{blogId}")
    public BaseResponse<String> deleteBlog(@PathVariable Long blogId) {
        String username = SecurityContextHolder.getContext().getAuthentication().getName();
        if (!blogService.isAuthor(blogId, username)) {
            return ResultUtils.error(403, "无权限");
        }
        
        boolean deleted = blogService.removeById(blogId);
        if (!deleted) {
            return ResultUtils.error(500, "删除失败");
        }
        return ResultUtils.success("删除成功");
    }

    @GetMapping("/page")
    public BaseResponse<PageResponse<BlogVO>> pageBlogs(
            @Valid PageRequest pageRequest,
            HttpServletRequest request) {
        Page<BlogVO> blogPage = blogService.pageBlogs(pageRequest, request);
        
        PageResponse<BlogVO> response = new PageResponse<>();
        response.setRecords(blogPage.getRecords());
        response.setTotal(blogPage.getTotal());
        response.setPageNum((int) blogPage.getCurrent());
        response.setPageSize((int) blogPage.getSize());
        response.setTotalPages((int) blogPage.getPages());
        
        return ResultUtils.success(response);
    }

    @GetMapping("/my/page")
    public BaseResponse<PageResponse<BlogVO>> pageMyBlogs(
            @Valid PageRequest pageRequest,
            HttpServletRequest request) {
        Page<BlogVO> blogPage = blogService.pageMyBlogs(pageRequest, request);
        
        PageResponse<BlogVO> response = new PageResponse<>();
        response.setRecords(blogPage.getRecords());
        response.setTotal(blogPage.getTotal());
        response.setPageNum((int) blogPage.getCurrent());
        response.setPageSize((int) blogPage.getSize());
        response.setTotalPages((int) blogPage.getPages());
        
        return ResultUtils.success(response);
    }
}
