package com.yuyuan.thumb.mapper;

import com.yuyuan.thumb.model.entity.Comments;
import com.baomidou.mybatisplus.core.mapper.BaseMapper;
import org.apache.ibatis.annotations.Mapper;
import org.apache.ibatis.annotations.Select;

import java.util.List;

/**
 * 评论Mapper
 */
@Mapper
public interface CommentsMapper extends BaseMapper<Comments> {

    @Select("SELECT * FROM comments WHERE blog_id = #{blogId} AND is_deleted = 0 ORDER BY created_at ASC")
    List<Comments> selectCommentsByBlogId(String blogId);

    @Select("SELECT COUNT(*) FROM comments WHERE blog_id = #{blogId} AND is_deleted = 0")
    Long countCommentsByBlogId(String blogId);
}
