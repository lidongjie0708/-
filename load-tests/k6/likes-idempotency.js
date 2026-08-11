import http from 'k6/http';
import { check } from 'k6';
import { JAVA_BASE, createBlog, jsonHeaders, registerAndLogin } from './common.js';

export const options = {
  scenarios: {
    idempotency: {
      executor: 'per-vu-iterations',
      vus: Number(__ENV.VUS || '10'),
      iterations: Number(__ENV.ITER || '5'),
      maxDuration: '2m',
    },
  },
  thresholds: {
    http_req_duration: ['p(95)<800'],
  },
};

export function setup() {
  const run = Date.now();
  const user = registerAndLogin(`lt_idem_${run}_0`);
  const blog = createBlog(user, 0);
  return { user, blog };
}

export default function (data) {
  const payload = JSON.stringify({ blogId: String(data.blog.id) });

  // 同一用户对同一博客并发连发两次 do：Lua 脚本必须保证只有一次生效。
  const first = http.post(`${JAVA_BASE}/thumb/do`, payload, jsonHeaders(data.user.token));
  const second = http.post(`${JAVA_BASE}/thumb/do`, payload, jsonHeaders(data.user.token));

  check(first, {
    'first do accepted (code=0)': (r) => r.json().code === 0,
  });
  check(second, {
    'duplicate do rejected (code=50001)': (r) => {
      try {
        return r.json().code === 50001;
      } catch (_) {
        return false;
      }
    },
  });
}
