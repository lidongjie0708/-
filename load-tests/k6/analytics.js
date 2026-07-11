import http from 'k6/http';
import { AGENT_BASE, getAgentToken, jsonHeaders, ok, registerAndLogin, shortThink } from './common.js';

export const options = {
  scenarios: {
    analytics: {
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
  const user = registerAndLogin(`lt_ops_${Date.now()}`);
  return { token: getAgentToken(user), userId: user.userId };
}

export default function (data) {
  const questions = [
    '统计当前博客数量和用户数量',
    '最近创建的博客数量是多少？',
    '评论数量和点赞相关数据概览',
  ];
  const res = http.post(
    `${AGENT_BASE}/api/agent/analytics/query`,
    JSON.stringify({
      question: questions[__ITER % questions.length],
      userId: data.userId,
      role: 'USER',
    }),
    jsonHeaders(data.token),
  );
  ok(res, 'analytics query');
  shortThink();
}
