import http from 'k6/http';
import { check, sleep } from 'k6';

export const JAVA_BASE = __ENV.JAVA_BASE || 'http://host.docker.internal:9199/api';
export const AGENT_BASE = __ENV.AGENT_BASE || 'http://host.docker.internal:8081';
export const PASSWORD = __ENV.TEST_PASSWORD || 'LoadPass123';

export function jsonHeaders(token) {
  const headers = { 'Content-Type': 'application/json' };
  if (token) headers.Authorization = `Bearer ${token}`;
  return { headers };
}

export function ok(res, name) {
  return check(res, {
    [`${name}: http 2xx`]: (r) => r.status >= 200 && r.status < 300,
    [`${name}: app code 0`]: (r) => {
      try {
        const body = r.json();
        return body.code === 0 || body.success === true;
      } catch (_) {
        return false;
      }
    },
  });
}

export function registerAndLogin(username) {
  const payload = JSON.stringify({
    username,
    password: PASSWORD,
    email: `${username}@load.test`,
  });
  http.post(`${JAVA_BASE}/register`, payload, jsonHeaders());

  const login = http.post(
    `${JAVA_BASE}/login`,
    JSON.stringify({ username, password: PASSWORD }),
    jsonHeaders(),
  );
  ok(login, 'login');
  const body = login.json();
  return {
    username,
    token: body.data.token,
    userId: body.data.user.id,
  };
}

export function createBlog(user, index) {
  const res = http.post(
    `${JAVA_BASE}/blog/create`,
    JSON.stringify({
      title: `Load Blog ${index}`,
      content: `# Load Test\n\nRedis 8, RabbitMQ, RAG and analytics test content ${index}.`,
      contentFormat: 'MARKDOWN',
    }),
    jsonHeaders(user.token),
  );
  ok(res, 'create blog');
  return res.json().data;
}

export function getAgentToken(user) {
  const res = http.post(`${JAVA_BASE}/agent/token`, null, {
    headers: { Authorization: `Bearer ${user.token}` },
  });
  ok(res, 'agent token');
  return res.json().data.token;
}

export function shortThink() {
  sleep(Number(__ENV.THINK_SECONDS || '0.2'));
}
