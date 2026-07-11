package com.yuyuan.thumb.service;

import com.baomidou.mybatisplus.extension.plugins.pagination.Page;
import com.yuyuan.thumb.model.dto.blog.PageRequest;
import com.yuyuan.thumb.model.dto.comment.CommentDto;
import com.yuyuan.thumb.model.entity.Comments;
import com.baomidou.mybatisplus.extension.service.IService;
import com.yuyuan.thumb.model.vo.CommentVo;

import java.util.List;

/**
 * 评论Service接口
 */
public interface CommentService extends IService<Comments> {

    Comments createComment(CommentDto commentDto, Long userId);

    Comments createReply(Long parentId, String content, Long userId);

    List<CommentVo> getCommentsByBlogId(String blogId);

    Page<CommentVo> pageCommentsByBlogId(String blogId, PageRequest pageRequest);

    boolean deleteComment(Long userId, Long commentId);

    Long countCommentsByBlogId(String blogId);
}
