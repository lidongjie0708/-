package com.yuyuan.thumb.service.agent;

import com.yuyuan.thumb.config.AgentConfig;
import com.yuyuan.thumb.model.dto.agent.AgentRequest;
import com.yuyuan.thumb.model.dto.agent.AgentResponse;
import com.yuyuan.thumb.model.entity.Blog;
import com.yuyuan.thumb.service.BlogService;
import com.yuyuan.thumb.service.CommentService;
import org.junit.jupiter.api.Test;

import java.util.List;
import java.util.Map;

import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

/**
 * Regression guard: blog agent processing must write back only the fields it
 * owns (summary/tags/embedding_status) and never do a whole-row update that
 * could overwrite concurrently modified counters such as thumbCount.
 */
class AgentServiceTest {

    private AgentService newAgentService(BlogService blogService, AgentClient agentClient) {
        AgentConfig agentConfig = new AgentConfig();
        agentConfig.setEnabled(true);
        return new AgentService(agentClient, agentConfig, blogService, mock(CommentService.class));
    }

    @Test
    void processBlogSyncWritesOnlyAgentOwnedFields() {
        BlogService blogService = mock(BlogService.class);
        AgentClient agentClient = mock(AgentClient.class);
        AgentService agentService = newAgentService(blogService, agentClient);

        Blog blog = new Blog();
        blog.setId(999L);

        AgentResponse response = AgentResponse.builder()
                .success(true)
                .result(Map.of(
                        "summary", "test summary",
                        "tags", List.of("a", "b"),
                        "embed_success", true
                ))
                .build();
        when(agentClient.execute(any(AgentRequest.class))).thenReturn(response);

        agentService.processBlogSync(blog);

        // PROCESSING then COMPLETED, both through the field-scoped update.
        verify(blogService).updateAgentFields(999L, null, null, 1);
        verify(blogService).updateAgentFields(999L, "test summary", "a,b", 2);
        // The whole-row update path must never be used by the blog agent flow.
        verify(blogService, never()).updateByIdWithoutAgent(any());
    }

    @Test
    void processBlogSyncMarksFailedWithoutWholeRowWrite() {
        BlogService blogService = mock(BlogService.class);
        AgentClient agentClient = mock(AgentClient.class);
        AgentService agentService = newAgentService(blogService, agentClient);

        Blog blog = new Blog();
        blog.setId(999L);
        when(agentClient.execute(any(AgentRequest.class))).thenThrow(new RuntimeException("agent down"));

        agentService.processBlogSync(blog);

        verify(blogService).updateAgentFields(999L, null, null, 3); // FAILED
        verify(blogService, never()).updateByIdWithoutAgent(any());
    }
}
