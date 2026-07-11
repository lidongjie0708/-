import http from 'k6/http';
import { check, sleep } from 'k6';
import { Rate } from 'k6/metrics';

const errors = new Rate('business_errors');
const base = __ENV.API_BASE_URL || 'http://127.0.0.1:9199/api';

export const options = {
  stages: [
    { duration: '30s', target: 10 },
    { duration: '1m', target: 20 },
    { duration: '2m', target: 50 },
    { duration: '30s', target: 0 },
  ],
  thresholds: {
    http_req_failed: ['rate<0.01'],
    business_errors: ['rate<0.01'],
    http_req_duration: ['p(95)<500', 'p(99)<1200'],
  },
};

function businessCheck(response, name) {
  let body = {};
  try { body = response.json(); } catch (_) {}
  const ok = check(response, {
    [`${name}: HTTP 200`]: (r) => r.status === 200,
    [`${name}: business success`]: () => body.code === 0,
  });
  errors.add(!ok);
}

export default function () {
  businessCheck(http.get(`${base}/blog/page?pageNum=1&pageSize=12`), 'blog page');
  businessCheck(http.get(`${base}/blog/all`), 'blog all');
  sleep(Math.random() * 1.2 + 0.3);
}
