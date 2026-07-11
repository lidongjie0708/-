package com.yuyuan.thumb.service;

import com.yuyuan.thumb.model.dto.user.RegisterDto;
import com.yuyuan.thumb.model.dto.user.UpdateProfileDto;
import com.yuyuan.thumb.model.entity.User;
import com.baomidou.mybatisplus.extension.service.IService;
import jakarta.servlet.http.HttpServletRequest;
import org.springframework.security.core.userdetails.UserDetails;
import org.springframework.security.core.userdetails.UserDetailsService;

/**
 * 用户Service接口
 * @author pine
 */
public interface UserService extends IService<User>, UserDetailsService {

    User getLoginUser(HttpServletRequest request);
    
    User login(String username, String password);

    void register(RegisterDto registerDto);

    UserDetails loadUserByUsername(String username);

    void logout(String token);

    Long getUserIdByUsername(String username);

    User updateProfile(String username, UpdateProfileDto profile);
}
