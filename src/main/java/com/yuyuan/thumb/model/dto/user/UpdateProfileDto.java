package com.yuyuan.thumb.model.dto.user;

import jakarta.validation.constraints.Email;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.Size;
import lombok.Data;

@Data
public class UpdateProfileDto {

    @NotBlank(message = "邮箱不能为空")
    @Email(message = "邮箱格式不正确")
    @Size(max = 255, message = "邮箱不能超过 255 个字符")
    private String email;

    @Size(max = 100, message = "姓名不能超过 100 个字符")
    private String fullName;
}
