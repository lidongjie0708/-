package com.yuyuan.thumb.model.dto.comment;

import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.Size;
import lombok.Data;

@Data
public class ReplyDto {

    @NotBlank(message = "回复内容不能为空")
    @Size(max = 1000, message = "回复内容不能超过 1000 个字符")
    private String content;
}
