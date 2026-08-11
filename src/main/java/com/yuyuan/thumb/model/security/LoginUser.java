package com.yuyuan.thumb.model.security;

/**
 * Lightweight authenticated principal backed by JWT claims; avoids per-request DB lookups.
 */
public record LoginUser(Long userId, String username, String role) implements java.security.Principal {

    @Override
    public String getName() {
        return username;
    }
}
