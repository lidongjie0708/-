package com.yuyuan.thumb.listener.thumb.msg;

import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

import java.time.LocalDateTime;

@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
public class ThumbEvent {
    /** Globally unique event identifier used for consumer-side idempotency. */
    private String eventId;
    private Long userId;
    private Long blogId;
    /** The desired final state, rather than a non-idempotent increment/decrement. */
    private Boolean desiredLiked;
    /** Monotonically increasing version for one user/blog state machine. */
    private Long version;
    private LocalDateTime eventTime;
}
