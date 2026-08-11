package com.yuyuan.thumb.constant;

/**
 * @author pine
 */
public interface ThumbConstant {

    /**
     * 用户点赞 hash key
     */
    String USER_THUMB_KEY_PREFIX = "thumb:";

    Long UN_THUMB_CONSTANT = 0L;

    /**
     * 临时 点赞记录 key
     */
    String TEMP_THUMB_KEY_PREFIX = "thumb:temp:%s";

    String BLOG_DELTA_KEY = "thumb:blog:delta";

    String BLOG_DELTA_FLUSHING_KEY = "thumb:blog:delta:flushing";

    String BLOG_DELTA_FLUSHING_BATCH_KEY = "thumb:blog:delta:flushing:batch";

}
