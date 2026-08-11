package com.yuyuan.thumb.util;

import com.yuyuan.thumb.constant.ThumbConstant;

/**
 * @author pine
 */
public class RedisKeyUtil {

    public static String getUserThumbKey(Long userId) {
        return ThumbConstant.USER_THUMB_KEY_PREFIX + userId;
    }

    /**
     * 获取 临时点赞记录 key
     */
    public static String getTempThumbKey(String time) {
        return ThumbConstant.TEMP_THUMB_KEY_PREFIX.formatted(time);
    }

    public static String getBlogDeltaKey() {
        return ThumbConstant.BLOG_DELTA_KEY;
    }

    public static String getBlogDeltaFlushingKey() {
        return ThumbConstant.BLOG_DELTA_FLUSHING_KEY;
    }

    public static String getBlogDeltaFlushingBatchKey() {
        return ThumbConstant.BLOG_DELTA_FLUSHING_BATCH_KEY;
    }

}
