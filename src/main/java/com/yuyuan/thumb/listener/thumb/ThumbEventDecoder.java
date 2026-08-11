package com.yuyuan.thumb.listener.thumb;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.yuyuan.thumb.listener.thumb.msg.ThumbEvent;
import lombok.RequiredArgsConstructor;
import org.springframework.amqp.core.Message;
import org.springframework.stereotype.Component;

import java.nio.charset.StandardCharsets;

/**
 * Decodes both the current ThumbEvent JSON envelope and legacy messages whose
 * JSON payload was published as a String. Keeping this at the queue boundary
 * prevents a conversion exception from bypassing the listener and repeatedly
 * redelivering an otherwise inspectable DLQ message.
 */
@Component
@RequiredArgsConstructor
public class ThumbEventDecoder {

    private final ObjectMapper objectMapper;

    public ThumbEvent decode(Message message) {
        try {
            String body = new String(message.getBody(), StandardCharsets.UTF_8);
            JsonNode node = objectMapper.readTree(body);
            if (node != null && node.isTextual()) {
                node = objectMapper.readTree(node.textValue());
            }
            ThumbEvent event = objectMapper.treeToValue(node, ThumbEvent.class);
            if (event == null || event.getEventId() == null || event.getUserId() == null || event.getBlogId() == null
                    || event.getDesiredLiked() == null) {
                throw new IllegalArgumentException("thumb event misses required fields");
            }
            return event;
        } catch (Exception exception) {
            throw new IllegalArgumentException("Unable to decode thumb event JSON", exception);
        }
    }
}
