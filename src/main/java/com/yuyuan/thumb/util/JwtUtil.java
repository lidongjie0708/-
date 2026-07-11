package com.yuyuan.thumb.util;

import io.jsonwebtoken.Jwts;
import io.jsonwebtoken.security.Keys;
import jakarta.servlet.http.HttpServletRequest;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Component;
import org.springframework.util.StringUtils;

import javax.crypto.SecretKey;
import java.util.Base64;
import java.util.Date;
import java.util.HashMap;
import java.util.Map;

/**
 * JWT工具类
 * <p>
 * 密钥通过环境变量注入，杜绝每次重启随机生成导致旧 Token 失效的问题。
 * 生产环境启动前必须设置 JWT_SECRET 环境变量。
 */
@Component
public class JwtUtil {

    private final SecretKey secretKey;

    private final long expiration;

    /**
     * 从 Spring 配置（底层是环境变量 $JWT_SECRET）读取密钥，
     * 保证每次启动解密签名用的是同一个密钥，Token 重启不失效。
     */
    public JwtUtil(
            @Value("${jwt.secret}") String secretBase64,
            @Value("${jwt.expiration:86400000}") long expiration) {
        byte[] keyBytes = Base64.getDecoder().decode(secretBase64);
        this.secretKey = Keys.hmacShaKeyFor(keyBytes);
        this.expiration = expiration;
    }

    /**
     * 生成token
     */
    public String generateToken(String username) {
        return Jwts.builder()
                .setSubject(username)
                .setIssuedAt(new Date())
                .setExpiration(new Date(System.currentTimeMillis() + expiration))
                .signWith(secretKey)
                .compact();
    }

    /**
     * 生成短期 AI Token，供前端直连 Python Agent 流式接口使用。
     */
    public String generateAiToken(String username, Long userId, String role, long ttlMillis) {
        Map<String, Object> claims = new HashMap<>();
        claims.put("typ", "AI_AGENT");
        claims.put("userId", userId);
        claims.put("role", role);
        claims.put("scope", "agent:stream");
        return Jwts.builder()
                .setClaims(claims)
                .setSubject(username)
                .setIssuedAt(new Date())
                .setExpiration(new Date(System.currentTimeMillis() + ttlMillis))
                .signWith(secretKey)
                .compact();
    }

    /**
     * 从token中获取用户名
     */
    public String getUsernameFromToken(String token) {
        return Jwts.parserBuilder()
                .setSigningKey(secretKey)
                .build()
                .parseClaimsJws(token)
                .getBody()
                .getSubject();
    }

    /**
     * 验证token
     */
    public boolean validateToken(String token) {
        try {
            Jwts.parserBuilder()
                    .setSigningKey(secretKey)
                    .build()
                    .parseClaimsJws(token);
            return true;
        } catch (Exception e) {
            return false;
        }
    }

    /**
     * 从请求头中提取token
     */
    public String getTokenFromRequest(HttpServletRequest request) {
        String bearerToken = request.getHeader("Authorization");
        if (StringUtils.hasText(bearerToken) && bearerToken.startsWith("Bearer ")) {
            return bearerToken.substring(7);
        }
        return null;
    }

    /**
     * 获取token过期时间
     */
    public Date getExpirationDateFromToken(String token) {
        return Jwts.parserBuilder()
                .setSigningKey(secretKey)
                .build()
                .parseClaimsJws(token)
                .getBody()
                .getExpiration();
    }
}
