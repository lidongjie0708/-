package com.yuyuan.thumb;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.yuyuan.thumb.model.entity.Blog;
import com.yuyuan.thumb.model.entity.Comments;
import com.yuyuan.thumb.model.entity.User;
import com.yuyuan.thumb.service.BlogService;
import com.yuyuan.thumb.service.CommentService;
import com.yuyuan.thumb.service.UserService;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.condition.EnabledIfEnvironmentVariable;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.AutoConfigureMockMvc;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.http.MediaType;
import org.springframework.security.crypto.password.PasswordEncoder;
import org.springframework.test.web.servlet.MockMvc;

import java.time.Duration;
import java.time.Instant;
import java.util.UUID;

import static org.assertj.core.api.Assertions.assertThat;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.*;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

@SpringBootTest(properties = {
        "spring.datasource.url=${E2E_DB_URL:jdbc:mysql://127.0.0.1:13306/thumb_e2e?useSSL=false&allowPublicKeyRetrieval=true}",
        "spring.datasource.username=root",
        "spring.datasource.password=${E2E_DB_PASSWORD:e2e_root}",
        "spring.data.redis.host=127.0.0.1",
        "spring.data.redis.port=${E2E_REDIS_PORT:16379}",
        "spring.data.redis.database=15",
        "spring.rabbitmq.host=127.0.0.1",
        "spring.rabbitmq.port=${E2E_RABBIT_PORT:25672}",
        "spring.rabbitmq.username=${E2E_RABBIT_USERNAME:e2e}",
        "spring.rabbitmq.password=${E2E_RABBIT_PASSWORD:e2e}",
        "spring.rabbitmq.virtual-host=${E2E_RABBIT_VHOST:blogslike-e2e}",
        "agent.base-url=${E2E_AGENT_BASE_URL:http://127.0.0.1:8001}",
        "server.port=0"
})
@AutoConfigureMockMvc
@EnabledIfEnvironmentVariable(named = "JAVA_E2E_ENABLED", matches = "true")
class JavaFullChainE2ETest {

    @Autowired MockMvc mvc;
    @Autowired ObjectMapper objectMapper;
    @Autowired UserService userService;
    @Autowired BlogService blogService;
    @Autowired CommentService commentService;
    @Autowired PasswordEncoder passwordEncoder;

    @Test
    void authenticatedBusinessFlowAndAsyncAgentCallback() throws Exception {
        String suffix = UUID.randomUUID().toString().substring(0, 8);
        String username = "e2e_" + suffix;
        String password = "E2ePass!123";
        Long blogId = null;
        Long commentId = null;
        Long replyId = null;
        Long userId = null;

        try {
            User user = new User();
            user.setUsername(username);
            user.setPassword(passwordEncoder.encode(password));
            user.setEmail(username + "@example.test");
            user.setEnabled(1);
            user.setRole("ADMIN");
            userService.save(user);
            userId = user.getId();

            String token = login(username, password);
            String auth = "Bearer " + token;

            assertSuccess(getJson("/user/profile", auth));

            JsonNode createdBlog = postJson("/blog/create", auth, """
                    {"title":"Java E2E","content":"# Full chain\\n\\nRedis RabbitMQ RAG","contentFormat":"MARKDOWN"}
                    """);
            assertSuccess(createdBlog);
            blogId = createdBlog.path("data").path("id").asLong();

            JsonNode detail = getJson("/blog/" + blogId, null);
            assertThat(detail.path("data").path("contentFormat").asText()).isEqualTo("MARKDOWN");

            JsonNode comment = postJson("/comment", auth,
                    "{\"blogId\":\"" + blogId + "\",\"content\":\"Java E2E comment\"}");
            assertSuccess(comment);
            commentId = comment.path("data").path("id").asLong();

            JsonNode reply = postJson("/comment/" + commentId + "/replies", auth,
                    "{\"content\":\"Java E2E reply\"}");
            assertSuccess(reply);
            replyId = reply.path("data").path("id").asLong();

            assertSuccess(postJson("/thumb/do", auth, "{\"blogId\":\"" + blogId + "\"}"));
            assertSuccess(postJson("/thumb/undo", auth, "{\"blogId\":\"" + blogId + "\"}"));
            assertSuccess(getJson("/admin/overview", auth));
            assertSuccess(postJson("/agent/token", auth, null));

            Blog processedBlog = awaitBlogAgent(blogId, Duration.ofSeconds(45));
            assertThat(processedBlog.getEmbeddingStatus()).isIn(2, 3);

            Comments processedComment = awaitCommentAgent(commentId, Duration.ofSeconds(30));
            assertThat(processedComment.getSentimentScore()).isNotNull();
        } finally {
            if (replyId != null) commentService.removeById(replyId);
            if (commentId != null) commentService.removeById(commentId);
            if (blogId != null) blogService.removeById(blogId);
            if (userId != null) userService.removeById(userId);
        }
    }

    private String login(String username, String password) throws Exception {
        JsonNode response = postJson("/login", null,
                "{\"username\":\"" + username + "\",\"password\":\"" + password + "\"}");
        assertSuccess(response);
        return response.path("data").path("token").asText();
    }

    private JsonNode getJson(String path, String authorization) throws Exception {
        var request = get(path).accept(MediaType.APPLICATION_JSON);
        if (authorization != null) request.header("Authorization", authorization);
        String body = mvc.perform(request).andExpect(status().isOk()).andReturn().getResponse().getContentAsString();
        return objectMapper.readTree(body);
    }

    private JsonNode postJson(String path, String authorization, String body) throws Exception {
        var request = post(path).contentType(MediaType.APPLICATION_JSON);
        if (authorization != null) request.header("Authorization", authorization);
        if (body != null) request.content(body);
        String response = mvc.perform(request).andExpect(status().isOk()).andReturn().getResponse().getContentAsString();
        return objectMapper.readTree(response);
    }

    private void assertSuccess(JsonNode response) {
        assertThat(response.path("code").asInt()).withFailMessage(response.toPrettyString()).isZero();
    }

    private Blog awaitBlogAgent(Long blogId, Duration timeout) throws InterruptedException {
        Instant deadline = Instant.now().plus(timeout);
        Blog blog;
        do {
            blog = blogService.getById(blogId);
            if (blog != null && blog.getEmbeddingStatus() != null && blog.getEmbeddingStatus() >= 2) return blog;
            Thread.sleep(500);
        } while (Instant.now().isBefore(deadline));
        return blog;
    }

    private Comments awaitCommentAgent(Long commentId, Duration timeout) throws InterruptedException {
        Instant deadline = Instant.now().plus(timeout);
        Comments comment;
        do {
            comment = commentService.getById(commentId);
            if (comment != null && comment.getSentimentScore() != null) return comment;
            Thread.sleep(500);
        } while (Instant.now().isBefore(deadline));
        return comment;
    }
}
