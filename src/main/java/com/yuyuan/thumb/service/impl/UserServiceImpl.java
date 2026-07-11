package com.yuyuan.thumb.service.impl;

import com.baomidou.mybatisplus.core.conditions.query.QueryWrapper;
import com.baomidou.mybatisplus.extension.service.impl.ServiceImpl;
import com.yuyuan.thumb.exception.UsernameAlreadyExistsException;
import com.yuyuan.thumb.mapper.UserMapper;
import com.yuyuan.thumb.model.dto.user.RegisterDto;
import com.yuyuan.thumb.model.dto.user.UpdateProfileDto;
import com.yuyuan.thumb.model.entity.User;
import com.yuyuan.thumb.service.UserService;
import com.yuyuan.thumb.util.JwtUtil;
import jakarta.servlet.http.HttpServletRequest;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.data.redis.core.RedisTemplate;
import org.springframework.security.core.userdetails.UserDetails;
import org.springframework.security.core.userdetails.UsernameNotFoundException;
import org.springframework.security.core.Authentication;
import org.springframework.security.core.context.SecurityContextHolder;
import org.springframework.security.crypto.password.PasswordEncoder;
import org.springframework.stereotype.Service;

import java.util.Date;
import java.util.concurrent.TimeUnit;

/**
 * 用户Service实现
 * @author pine
 */
@Slf4j
@Service
public class UserServiceImpl extends ServiceImpl<UserMapper, User>
        implements UserService {

    @Autowired
    private UserMapper userMapper;

    @Autowired
    private PasswordEncoder passwordEncoder;

    @Autowired
    private RedisTemplate<String, Object> redisTemplate;

    @Autowired
    private JwtUtil jwtUtil;

    @Override
    public User getLoginUser(HttpServletRequest request) {
        Authentication authentication = SecurityContextHolder.getContext().getAuthentication();
        if (authentication == null || !authentication.isAuthenticated()
                || "anonymousUser".equals(authentication.getPrincipal())) {
            return null;
        }
        return userMapper.selectOne(
                new QueryWrapper<User>().eq("username", authentication.getName())
        );
    }

    @Override
    public UserDetails loadUserByUsername(String username) throws UsernameNotFoundException {
        QueryWrapper<User> wrapper = new QueryWrapper<>();
        wrapper.eq("username", username);
        User user = userMapper.selectOne(wrapper);

        if (user == null) {
            throw new UsernameNotFoundException("用户不存在: " + username);
        }

        boolean enabled = user.getEnabled() != null && user.getEnabled() == 1;

        String role = user.getRole() == null || user.getRole().isBlank() ? "USER" : user.getRole();

        return org.springframework.security.core.userdetails.User.builder()
                .username(user.getUsername())
                .password(user.getPassword())
                .disabled(!enabled)
                .authorities(role)
                .build();
    }

    @Override
    public void logout(String token) {
        if (token != null) {
            Date expiration = jwtUtil.getExpirationDateFromToken(token);
            long expireTime = expiration.getTime() - System.currentTimeMillis();

            if (expireTime > 0) {
                redisTemplate.opsForValue().set(
                        "blacklist:" + token,
                        "invalid",
                        expireTime,
                        TimeUnit.MILLISECONDS
                );
            }
        }
    }

    @Override
    public User login(String username, String password) {
        QueryWrapper<User> wrapper = new QueryWrapper<>();
        wrapper.eq("username", username);
        User user = userMapper.selectOne(wrapper);

        if (user != null && passwordEncoder.matches(password, user.getPassword())) {
            return user;
        }
        return null;
    }

    @Override
    public void register(RegisterDto registerDto) {
        QueryWrapper<User> queryWrapper = new QueryWrapper<>();
        queryWrapper.eq("username", registerDto.getUsername());
        User existUser = userMapper.selectOne(queryWrapper);

        if (existUser != null) {
            throw new UsernameAlreadyExistsException("用户名已存在：" + registerDto.getUsername());
        }

        String encryptedPassword = passwordEncoder.encode(registerDto.getPassword());

        User newUser = new User();
        newUser.setUsername(registerDto.getUsername());
        newUser.setPassword(encryptedPassword);
        newUser.setEmail(registerDto.getEmail());
        newUser.setEnabled(1);
        newUser.setRole("USER");
        newUser.setCreatedAt(new Date());
        userMapper.insert(newUser);
    }

    @Override
    public Long getUserIdByUsername(String username) {
        return userMapper.selectByUsername(username);
    }

    @Override
    public User updateProfile(String username, UpdateProfileDto profile) {
        User current = userMapper.selectOne(new QueryWrapper<User>().eq("username", username));
        if (current == null) {
            throw new UsernameNotFoundException("用户不存在");
        }
        current.setEmail(profile.getEmail().trim());
        current.setFullName(profile.getFullName() == null ? null : profile.getFullName().trim());
        current.setUpdatedAt(new Date());
        userMapper.updateById(current);
        current.setPassword(null);
        return current;
    }
}
