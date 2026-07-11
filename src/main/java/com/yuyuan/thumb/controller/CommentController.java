package com.yuyuan.thumb.controller;

import com.baomidou.mybatisplus.extension.plugins.pagination.Page;
import com.yuyuan.thumb.common.BaseResponse;
import com.yuyuan.thumb.common.ResultUtils;
import com.yuyuan.thumb.model.dto.blog.PageRequest;
import com.yuyuan.thumb.model.dto.blog.PageResponse;
import com.yuyuan.thumb.model.dto.comment.CommentDto;
import com.yuyuan.thumb.model.dto.comment.ReplyDto;
import com.yuyuan.thumb.model.entity.Comments;
import com.yuyuan.thumb.model.vo.CommentVo;
import com.yuyuan.thumb.service.CommentService;
import com.yuyuan.thumb.service.UserService;
import jakarta.validation.Valid;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.security.core.context.SecurityContextHolder;
import org.springframework.web.bind.annotation.*;

import java.util.List;

/**
 * 评论控制器
 */
@RestController
@RequestMapping("/comment")
public class CommentController {

    @Autowired
    private CommentService commentService;

    @Autowired
    private UserService userService;

    @PostMapping
    public BaseResponse<Comments> addComment(@Valid @RequestBody CommentDto commentDto) {
        String username = SecurityContextHolder.getContext().getAuthentication().getName();
        Long userId = userService.getUserIdByUsername(username);
        
        Comments savedComment = commentService.createComment(commentDto, userId);
        if (savedComment == null) {
            return ResultUtils.error(400, "文章不存在");
        }
        return ResultUtils.success(savedComment);
    }

    @PostMapping("/{commentId}/replies")
    public BaseResponse<Comments> addReply(@PathVariable Long commentId,
                                           @Valid @RequestBody ReplyDto replyDto) {
        String username = SecurityContextHolder.getContext().getAuthentication().getName();
        Long userId = userService.getUserIdByUsername(username);
        return ResultUtils.success(commentService.createReply(commentId, replyDto.getContent(), userId));
    }

    @GetMapping("/blog/{blogId}")
    public BaseResponse<List<CommentVo>> getCommentsByBlogId(@PathVariable String blogId) {
        List<CommentVo> commentVoList = commentService.getCommentsByBlogId(blogId);
        return ResultUtils.success(commentVoList);
    }

    @GetMapping("/blog/{blogId}/page")
    public BaseResponse<PageResponse<CommentVo>> pageCommentsByBlogId(
            @PathVariable String blogId,
            @Valid PageRequest pageRequest) {
        Page<CommentVo> commentPage = commentService.pageCommentsByBlogId(blogId, pageRequest);
        
        PageResponse<CommentVo> response = new PageResponse<>();
        response.setRecords(commentPage.getRecords());
        response.setTotal(commentPage.getTotal());
        response.setPageNum((int) commentPage.getCurrent());
        response.setPageSize((int) commentPage.getSize());
        response.setTotalPages((int) commentPage.getPages());
        
        return ResultUtils.success(response);
    }

    @DeleteMapping("/{commentId}")
    public BaseResponse<String> deleteComment(@PathVariable Long commentId) {
        String username = SecurityContextHolder.getContext().getAuthentication().getName();
        Long userId = userService.getUserIdByUsername(username);
        
        boolean success = commentService.deleteComment(userId, commentId);
        if (success) {
            return ResultUtils.success("删除成功");
        }
        return ResultUtils.error(500, "删除失败");
    }

    @GetMapping("/count/{blogId}")
    public BaseResponse<Long> countComments(@PathVariable String blogId) {
        Long count = commentService.countCommentsByBlogId(blogId);
        return ResultUtils.success(count);
    }
}
