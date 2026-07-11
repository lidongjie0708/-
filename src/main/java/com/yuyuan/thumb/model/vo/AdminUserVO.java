package com.yuyuan.thumb.model.vo;

import lombok.Data;

import java.util.Date;

@Data
public class AdminUserVO {
    private Long id;
    private String username;
    private String email;
    private String fullName;
    private Integer enabled;
    private String role;
    private Date createdAt;
    private Date updatedAt;
}
