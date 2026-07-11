import http from 'k6/http';
import { JAVA_BASE, createBlog, jsonHeaders, ok, registerAndLogin, shortThink } from './common.js';

export const options = {
  scenarios: {
    likes: {
      executor: 'ramping-vus',
      stages: [
        { duration: __ENV.RAMP_UP || '30s', target: Number(__ENV.VUS || '10') },
        { duration: __ENV.HOLD || '1m', target: Number(__ENV.VUS || '10') },
        { duration: __ENV.RAMP_DOWN || '20s', target: 0 },
      ],
    },
  },
  thresholds: {
    http_req_failed: ['rate<0.05'],
    http_req_duration: ['p(95)<800'],
  },
};

export function setup() {
  const run = Date.now();
  const userCount = Number(__ENV.USERS || __ENV.VUS || '10');
  const blogCount = Number(__ENV.BLOGS || String(userCount));
  const users = [];
  for (let i = 0; i < userCount; i += 1) {
    users.push(registerAndLogin(`lt_like_${run}_${i}`));
  }
  const blogs = [];
  for (let i = 0; i < blogCount; i += 1) {
    blogs.push(createBlog(users[i % users.length], i));
  }
  return { users, blogs };
}

export default function (data) {
  const index = (__VU - 1) % data.users.length;
  const user = data.users[index];
  const blog = data.blogs[index % data.blogs.length];
  const payload = JSON.stringify({ blogId: String(blog.id) });

  const doRes = http.post(
    `${JAVA_BASE}/thumb/do`,
    payload,
    jsonHeaders(user.token),
  );
  ok(doRes, 'thumb /thumb/do');

  const undoRes = http.post(
    `${JAVA_BASE}/thumb/undo`,
    payload,
    jsonHeaders(user.token),
  );
  ok(undoRes, 'thumb /thumb/undo');
  shortThink();
}
