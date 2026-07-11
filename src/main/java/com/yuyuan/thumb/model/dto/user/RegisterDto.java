package com.yuyuan.thumb.model.dto.user;

import jakarta.validation.constraints.Email;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.Size;
import lombok.Data;

/**
 * 注册请求DTO
 */
@Data
public class RegisterDto {
    @NotBlank(message = "用户名不为空")
    @Size(min = 2, message = "用户名不少于2个字符")
    private String username;

    @NotBlank(message = "密码不为空")
    @Size(min = 2, message = "密码不少于2个字符")
    private String password;

    @NotBlank(message = "邮箱不能为空")
    @Email(message = "邮箱格式不正确")
    private String email;
}
