import http from 'k6/http';
import { check, sleep } from 'k6';
import { Trend } from 'k6/metrics';

const base = __ENV.AGENT_BASE_URL || 'http://127.0.0.1:8001/api/agent';
const firstResponse = new Trend('agent_total_response_ms');

export const options = {
  scenarios: {
    agent_low_concurrency: {
      executor: 'constant-vus',
      vus: 2,
      duration: '2m',
    },
  },
  thresholds: {
    http_req_failed: ['rate<0.03'],
    agent_total_response_ms: ['p(95)<30000'],
  },
};

const prompts = [
  ['chat', '解释一下 RAG 是什么'],
  ['rag', '博客知识库中有哪些关于 Redis 的内容？'],
  ['auto', '根据博客内容总结点赞系统的设计'],
];

export default function () {
  const [mode, message] = prompts[Math.floor(Math.random() * prompts.length)];
  const started = Date.now();
  const response = http.post(`${base}/chat`, JSON.stringify({
    message,
    mode,
    sessionId: `k6-${__VU}-${__ITER}`,
  }), {
    headers: {
      Authorization: `Bearer ${__ENV.AGENT_TOKEN}`,
      'Content-Type': 'application/json',
    },
    timeout: '60s',
  });
  firstResponse.add(Date.now() - started);
  check(response, {
    'agent HTTP 200': (r) => r.status === 200,
    'agent business response': (r) => {
      try { return [0, 403].includes(r.json().code); } catch (_) { return false; }
    },
  });
  sleep(2 + Math.random() * 3);
}

