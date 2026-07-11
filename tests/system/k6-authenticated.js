import http from 'k6/http';
import { check, sleep } from 'k6';

const base = __ENV.API_BASE_URL || 'http://127.0.0.1:9199/api';

export const options = {
  stages: [
    { duration: '30s', target: 5 },
    { duration: '2m', target: 20 },
    { duration: '30s', target: 0 },
  ],
  thresholds: {
    http_req_failed: ['rate<0.01'],
    http_req_duration: ['p(95)<800', 'p(99)<1800'],
  },
};

export function setup() {
  const login = http.post(`${base}/login`, JSON.stringify({
    username: __ENV.TEST_USERNAME,
    password: __ENV.TEST_PASSWORD,
  }), { headers: { 'Content-Type': 'application/json' } });
  const body = login.json();
  if (login.status !== 200 || body.code !== 0) throw new Error('login failed');
  const blogs = http.get(`${base}/blog/all`).json().data || [];
  return { token: body.data.token, blogIds: blogs.map((x) => String(x.id)).slice(0, 20) };
}

export default function (data) {
  const params = { headers: { Authorization: `Bearer ${data.token}`, 'Content-Type': 'application/json' } };
  const responses = http.batch([
    ['GET', `${base}/user/profile`, null, params],
    ['GET', `${base}/blog/my/page?pageNum=1&pageSize=10`, null, params],
    ['GET', `${base}/blog/page?pageNum=1&pageSize=12`, null, params],
  ]);
  responses.forEach((r) => check(r, { 'authenticated query succeeds': (x) => x.status === 200 && x.json().code === 0 }));

  if (data.blogIds.length) {
    const blogId = data.blogIds[Math.floor(Math.random() * data.blogIds.length)];
    http.post(`${base}/thumb/do`, JSON.stringify({ blogId }), params);
    http.post(`${base}/thumb/undo`, JSON.stringify({ blogId }), params);
  }
  sleep(Math.random() * 1.5 + 0.5);
}
