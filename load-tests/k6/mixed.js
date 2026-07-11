import http from 'k6/http';
import { AGENT_BASE, JAVA_BASE, createBlog, getAgentToken, jsonHeaders, ok, registerAndLogin, shortThink } from './common.js';

export const options = {
  scenarios: {
    mixed: {
      executor: 'ramping-vus',
      stages: [
        { duration: __ENV.RAMP_UP || '30s', target: Number(__ENV.VUS || '10') },
        { duration: __ENV.HOLD || '2m', target: Number(__ENV.VUS || '10') },
        { duration: __ENV.RAMP_DOWN || '30s', target: 0 },
      ],
    },
  },
  thresholds: {
    http_req_failed: ['rate<0.08'],
    http_req_duration: ['p(95)<5000'],
  },
};

export function setup() {
  const run = Date.now();
  const users = [];
  for (let i = 0; i < Number(__ENV.USERS || __ENV.VUS || '10'); i += 1) {
    users.push(registerAndLogin(`lt_mix_${run}_${i}`));
  }
  const blogs = [];
  for (let i = 0; i < Number(__ENV.BLOGS || '8'); i += 1) {
    blogs.push(createBlog(users[i % users.length], i));
  }
  const agentToken = getAgentToken(users[0]);
  return { users, blogs, agentToken };
}

export default function (data) {
  const user = data.users[(__VU - 1) % data.users.length];
  const blog = data.blogs[__ITER % data.blogs.length];
  const bucket = __ITER % 10;

  if (bucket < 5) {
    const payload = JSON.stringify({ blogId: String(blog.id) });
    ok(http.post(`${JAVA_BASE}/thumb/do`, payload, jsonHeaders(user.token)), 'mixed thumb do');
    ok(http.post(`${JAVA_BASE}/thumb/undo`, payload, jsonHeaders(user.token)), 'mixed thumb undo');
  } else if (bucket < 8) {
    ok(http.get(`${JAVA_BASE}/blog/page?pageNum=1&pageSize=20&sortField=createTime&sortOrder=desc`), 'mixed blog page');
  } else if (bucket === 8) {
    ok(http.post(
      `${AGENT_BASE}/api/agent/rag/ask`,
      JSON.stringify({ question: 'Redis 缓存如何提升博客系统性能？', sessionId: `lt-mix-${__VU}`, visibleScopes: ['PUBLIC'] }),
      jsonHeaders(data.agentToken),
    ), 'mixed rag');
  } else {
    ok(http.post(
      `${AGENT_BASE}/api/agent/analytics/query`,
      JSON.stringify({ question: '统计博客和评论的运营概览', role: 'USER' }),
      jsonHeaders(data.agentToken),
    ), 'mixed analytics');
  }
  shortThink();
}
