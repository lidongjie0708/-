package com.yuyuan.thumb.model.dto.comment;

import jakarta.validation.constraints.NotBlank;
import lombok.Data;

/**
 * 评论请求DTO
 */
@Data
public class CommentDto {
    @NotBlank(message = "博客ID不能为空")
    private String blogId;
    
    @NotBlank(message = "评论内容不能为空")
    private String content;
    
    private Long parentId;
}
