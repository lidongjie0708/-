package com.yuyuan.thumb.controller;

import com.yuyuan.thumb.common.BaseResponse;
import com.yuyuan.thumb.common.ResultUtils;
import com.yuyuan.thumb.model.dto.user.LoginDto;
import com.yuyuan.thumb.model.dto.user.RegisterDto;
import com.yuyuan.thumb.model.dto.user.UpdateProfileDto;
import com.yuyuan.thumb.model.entity.User;
import com.yuyuan.thumb.service.UserService;
import com.yuyuan.thumb.util.JwtUtil;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.validation.Valid;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.security.authentication.AuthenticationManager;
import org.springframework.security.authentication.BadCredentialsException;
import org.springframework.security.authentication.UsernamePasswordAuthenticationToken;
import org.springframework.security.core.Authentication;
import org.springframework.security.core.context.SecurityContextHolder;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PutMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import java.util.HashMap;
import java.util.Map;

/**
 * 登录控制器
 */
@Slf4j
@RestController
@RequestMapping
public class LoginController {

    @Autowired
    private UserService userService;

    @Autowired
    private JwtUtil jwtUtil;

    @Autowired
    private AuthenticationManager authenticationManager;

    @PostMapping("/login")
    public BaseResponse<Map<String, Object>> login(@RequestBody LoginDto loginDto) {
        log.info("=== 登录请求开始 ===");
        log.info("用户名: {}", loginDto.getUsername());
        
        try {
            Authentication authentication = authenticationManager.authenticate(
                    new UsernamePasswordAuthenticationToken(loginDto.getUsername(), loginDto.getPassword())
            );
            log.info("认证成功: {}", authentication.getName());
            SecurityContextHolder.getContext().setAuthentication(authentication);

            User user = userService.login(loginDto.getUsername(), loginDto.getPassword());
            user.setPassword(null);
            String token = jwtUtil.generateToken(user.getUsername(), user.getId(), user.getRole());

            Map<String, Object> data = new HashMap<>();
            data.put("token", token);
            data.put("user", user);
            data.put("expiresIn", jwtUtil.getExpirationDateFromToken(token));

            return ResultUtils.success(data);
        } catch (BadCredentialsException e) {
            return ResultUtils.error(401, "用户名或密码错误");
        } catch (Exception e) {
            return ResultUtils.error(500, "登录失败: " + e.getMessage());
        }
    }

    @PostMapping("/register")
    public BaseResponse<String> register(@Valid @RequestBody RegisterDto registerDto) {
        userService.register(registerDto);
        return ResultUtils.success("注册成功");
    }

    @PostMapping("/logout")
    public BaseResponse<String> logout(HttpServletRequest request) {
        String token = jwtUtil.getTokenFromRequest(request);
        userService.logout(token);
        return ResultUtils.success("登出成功");
    }

    @GetMapping("/user/profile")
    public BaseResponse<User> getProfile(HttpServletRequest request) {
        User user = userService.getLoginUser(request);
        if (user == null) {
            return ResultUtils.error(401, "请先登录");
        }
        user.setPassword(null);
        return ResultUtils.success(user);
    }

    @PutMapping("/user/profile")
    public BaseResponse<User> updateProfile(@Valid @RequestBody UpdateProfileDto profile) {
        String username = SecurityContextHolder.getContext().getAuthentication().getName();
        return ResultUtils.success(userService.updateProfile(username, profile));
    }
}
