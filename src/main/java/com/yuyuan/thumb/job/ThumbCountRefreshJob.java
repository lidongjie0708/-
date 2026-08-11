package com.yuyuan.thumb.job;

import com.yuyuan.thumb.mapper.BlogMapper;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.stereotype.Component;

/**
 * Periodically rebuilds blog.thumbCount from the thumb table, keeping the DB as the source of truth.
 */
@Slf4j
@Component
@RequiredArgsConstructor
public class ThumbCountRefreshJob {

    private final BlogMapper blogMapper;

    @Scheduled(cron = "${thumb.refresh.cron:0 30 3 * * ?}")
    public void refresh() {
        blogMapper.refreshAllThumbCount();
        log.info("All blog thumb counts rebuilt from thumb table");
    }
}
