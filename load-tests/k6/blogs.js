import http from 'k6/http';
import { JAVA_BASE, createBlog, jsonHeaders, ok, registerAndLogin, shortThink } from './common.js';

export const options = {
  scenarios: {
    blogs: {
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
    http_req_duration: ['p(95)<1000'],
  },
};

export function setup() {
  const run = Date.now();
  const user = registerAndLogin(`lt_blog_${run}`);
  const blogs = [];
  for (let i = 0; i < Number(__ENV.SEED_BLOGS || '10'); i += 1) {
    blogs.push(createBlog(user, i));
  }
  return { user, blogs };
}

export default function (data) {
  const action = __ITER % 4;
  if (action === 0) {
    createBlog(data.user, __ITER);
  } else if (action === 1) {
    const res = http.get(`${JAVA_BASE}/blog/page?pageNum=1&pageSize=20&sortField=createTime&sortOrder=desc`);
    ok(res, 'blog page');
  } else {
    const blog = data.blogs[__ITER % data.blogs.length];
    const res = http.get(`${JAVA_BASE}/blog/${blog.id}`);
    ok(res, 'blog detail');
  }
  shortThink();
}
