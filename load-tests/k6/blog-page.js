import http from 'k6/http';
import { check } from 'k6';
import { JAVA_BASE, jsonHeaders, registerAndLogin } from './common.js';

export const options = {
  scenarios: {
    browse: {
      executor: 'ramping-vus',
      stages: [
        { duration: __ENV.RAMP_UP || '10s', target: Number(__ENV.VUS || '50') },
        { duration: __ENV.HOLD || '30s', target: Number(__ENV.VUS || '50') },
        { duration: __ENV.RAMP_DOWN || '10s', target: 0 },
      ],
    },
  },
  thresholds: {
    http_req_failed: ['rate<0.05'],
  },
};

export function setup() {
  const run = Date.now();
  const user = registerAndLogin(`lt_browse_${run}_0`);
  return { user };
}

export default function (data) {
  // 带 token 访问博客分页：每个博客会触发 hasThumb -> cacheManager.get，
  // 高频访问同一批博客即可驱动 Caffeine 本地缓存与 HeavyKeeper 热 key 检测。
  const res = http.get(
    `${JAVA_BASE}/blog/page?pageNum=1&pageSize=20&sortField=createTime&sortOrder=desc`,
    jsonHeaders(data.user.token),
  );
  check(res, { 'blog page ok': (r) => r.status === 200 });
}
