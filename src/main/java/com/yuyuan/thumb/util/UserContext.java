package com.yuyuan.thumb.util;

import com.yuyuan.thumb.model.security.LoginUser;
import org.springframework.security.core.Authentication;
import org.springframework.security.core.context.SecurityContextHolder;

/**
 * Reads the current user id from the SecurityContext principal (JWT claims), no DB involved.
 */
public final class UserContext {

    private UserContext() {
    }

    public static Long getCurrentUserId() {
        Authentication authentication = SecurityContextHolder.getContext().getAuthentication();
        if (authentication == null || !authentication.isAuthenticated()
                || !(authentication.getPrincipal() instanceof LoginUser loginUser)) {
            return null;
        }
        return loginUser.userId();
    }
}
