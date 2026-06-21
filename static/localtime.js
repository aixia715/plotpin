// 把页面上的 UTC 时间转换为访问者浏览器的本地时间。
// 约定：用 <time class="local-time" datetime="{UTC ISO}">{UTC ISO}</time> 承载时间，
// 文本初始为原始 ISO 字符串,无 JS 时优雅降级为 UTC 原文,有 JS 时转成本地时间。
function fmtLocal(iso) {
  const d = new Date(iso);
  if (isNaN(d)) return iso; // 解析失败保留原文
  return d.toLocaleString(); // 浏览器本地时区 + 本地区域格式
}

document.addEventListener("DOMContentLoaded", () => {
  document.querySelectorAll("time.local-time[datetime]").forEach((el) => {
    el.textContent = fmtLocal(el.getAttribute("datetime"));
  });
});
