package com.yuyuan.thumb.listener.thumb;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.yuyuan.thumb.config.RabbitMQConfig;
import com.yuyuan.thumb.listener.thumb.msg.ThumbEvent;
import org.junit.jupiter.api.Test;
import org.springframework.amqp.core.Message;
import org.springframework.amqp.core.MessageBuilder;

import java.time.LocalDateTime;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertThrows;

class ThumbEventDecoderTest {

    private final ObjectMapper objectMapper = new RabbitMQConfig().objectMapper();
    private final ThumbEventDecoder decoder = new ThumbEventDecoder(objectMapper);

    @Test
    void decodesCurrentJsonObjectPayload() throws Exception {
        ThumbEvent expected = ThumbEvent.builder().eventId("event-1").userId(1L).blogId(2L)
                .desiredLiked(true).version(3L).eventTime(LocalDateTime.now()).build();
        Message message = MessageBuilder.withBody(objectMapper.writeValueAsBytes(expected)).build();

        ThumbEvent actual = decoder.decode(message);

        assertEquals(expected.getEventId(), actual.getEventId());
        assertEquals(expected.getUserId(), actual.getUserId());
        assertEquals(expected.getBlogId(), actual.getBlogId());
    }

    @Test
    void decodesLegacyJsonStringPayload() throws Exception {
        String legacyBody = objectMapper.writeValueAsString(ThumbEvent.builder().eventId("event-2").userId(1L)
                .blogId(2L).desiredLiked(false).build());
        Message message = MessageBuilder.withBody(objectMapper.writeValueAsBytes(legacyBody)).build();

        assertEquals("event-2", decoder.decode(message).getEventId());
    }

    @Test
    void rejectsMalformedOrIncompletePayload() {
        Message message = MessageBuilder.withBody("{\"eventId\":\"missing-fields\"}".getBytes()).build();

        assertThrows(IllegalArgumentException.class, () -> decoder.decode(message));
    }
}
