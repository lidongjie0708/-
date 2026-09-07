import http from 'k6/http';
import { check } from 'k6';
import { AGENT_BASE, JAVA_BASE, PASSWORD, getAgentToken, jsonHeaders, registerAndLogin, shortThink } from './common.js';

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
  const adminUser = __ENV.ADMIN_USERNAME;
  if (adminUser) {
    const login = http.post(
      `${JAVA_BASE}/login`,
      JSON.stringify({ username: adminUser, password: __ENV.ADMIN_PASSWORD || PASSWORD }),
      jsonHeaders(),
    );
    check(login, { 'admin login: http 2xx': (r) => r.status >= 200 && r.status < 300 });
    const body = login.json();
    const token = body.data.token;
    return {
      token: getAgentToken({ token }),
      userId: body.data.user.id,
      role: 'ADMIN',
    };
  }
  const user = registerAndLogin(`lt_ops_${Date.now()}`);
  return { token: getAgentToken(user), userId: user.userId, role: 'USER' };
}

export default function (data) {
  const questions = [
    '按点赞数统计热门博客，返回前 10 篇',
    '最近内容发布趋势如何？按日期统计博客数量',
    '统计博客标签分布，看看哪些标签最多',
  ];
  const res = http.post(
    `${AGENT_BASE}/api/agent/analytics/query`,
    JSON.stringify({
      question: questions[__ITER % questions.length],
      userId: data.userId,
      role: data.role,
    }),
    jsonHeaders(data.token),
  );
  let body = {};
  try {
    body = res.json();
  } catch (_) {
    body = {};
  }
  const dataBody = (body && body.data) || {};
  check(res, {
    'analytics: http 2xx': (r) => r.status >= 200 && r.status < 300,
    'analytics: app code 0': () => body.code === 0 || body.success === true,
    'analytics: success': () => dataBody.status === 'SUCCESS' || dataBody.status === 'DENIED',
    'analytics: no error': () => !dataBody.error,
  });
  shortThink();
}
