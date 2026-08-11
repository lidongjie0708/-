package com.yuyuan.thumb.listener.thumb.msg;

import org.junit.jupiter.api.Test;

import java.time.LocalDateTime;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;

/**
 * Locks the message contract to a desired-state event. Consumers can therefore
 * converge after duplicate delivery or reordering instead of applying +/- deltas.
 */
class ThumbEventTest {

    @Test
    void retainsTheDesiredStateAndMonotonicVersionForAnUnlikeEvent() {
        LocalDateTime eventTime = LocalDateTime.of(2026, 8, 6, 10, 30);

        ThumbEvent event = ThumbEvent.builder()
                .eventId("thumb-1001-2001-42")
                .userId(1001L)
                .blogId(2001L)
                .desiredLiked(false)
                .version(42L)
                .eventTime(eventTime)
                .build();

        assertEquals("thumb-1001-2001-42", event.getEventId());
        assertEquals(1001L, event.getUserId());
        assertEquals(2001L, event.getBlogId());
        assertFalse(event.getDesiredLiked());
        assertEquals(42L, event.getVersion());
        assertEquals(eventTime, event.getEventTime());
    }
}
