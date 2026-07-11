import http from 'k6/http';
import { AGENT_BASE, getAgentToken, jsonHeaders, ok, registerAndLogin, shortThink } from './common.js';

export const options = {
  scenarios: {
    rag: {
      executor: 'ramping-vus',
      stages: [
        { duration: __ENV.RAMP_UP || '20s', target: Number(__ENV.VUS || '3') },
        { duration: __ENV.HOLD || '1m', target: Number(__ENV.VUS || '3') },
        { duration: __ENV.RAMP_DOWN || '20s', target: 0 },
      ],
    },
  },
  thresholds: {
    http_req_failed: ['rate<0.10'],
    http_req_duration: ['p(95)<15000'],
  },
};

export function setup() {
  const user = registerAndLogin(`lt_rag_${Date.now()}`);
  return { token: getAgentToken(user), userId: user.userId };
}

export default function (data) {
  const questions = [
    'Redis 缓存是怎么工作的？',
    '点赞系统如何避免重复点赞？',
    '博客系统有哪些核心功能？',
  ];
  const res = http.post(
    `${AGENT_BASE}/api/agent/rag/ask`,
    JSON.stringify({
      question: questions[__ITER % questions.length],
      sessionId: `lt-rag-${__VU}`,
      userId: data.userId,
      role: 'USER',
      visibleScopes: ['PUBLIC'],
    }),
    jsonHeaders(data.token),
  );
  ok(res, 'rag ask');
  shortThink();
}
