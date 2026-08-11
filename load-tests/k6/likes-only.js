import http from 'k6/http';
import { JAVA_BASE, createBlog, jsonHeaders, ok, registerAndLogin } from './common.js';

export const options = {
  scenarios: {
    likesOnly: {
      executor: 'per-vu-iterations',
      vus: Number(__ENV.VUS || '30'),
      iterations: Number(__ENV.ITER || '40'),
      maxDuration: '3m',
    },
  },
  thresholds: {
    http_req_failed: ['rate<0.05'],
  },
};

export function setup() {
  const run = Date.now();
  const userCount = Number(__ENV.USERS || __ENV.VUS || '30');
  const blogCount = Number(__ENV.BLOGS || String(userCount));
  const users = [];
  for (let i = 0; i < userCount; i += 1) {
    users.push(registerAndLogin(`lt_only_${run}_${i}`));
  }
  const blogs = [];
  for (let i = 0; i < blogCount; i += 1) {
    blogs.push(createBlog(users[i % users.length], i));
  }
  return { users, blogs };
}

export default function (data) {
  // Each VU likes a rotating blog: every (user, blog) pair is used at most once
  // (no duplicate-like noise), while many users share the same blog so the
  // per-blog delta hash and the flush batch see real contention.
  const vu = __VU - 1;
  const iteration = __ITER;
  const user = data.users[vu % data.users.length];
  const blog = data.blogs[(vu + iteration) % data.blogs.length];
  const res = http.post(
    `${JAVA_BASE}/thumb/do`,
    JSON.stringify({ blogId: String(blog.id) }),
    jsonHeaders(user.token),
  );
  ok(res, 'thumb /thumb/do');
}
