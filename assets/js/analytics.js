/* 确实在审 · 访问统计（默认关闭，不收集个人身份信息）
 *
 * 启用方法：在下方填入百度统计的 HM 号（tongji.baidu.com 建站后获取，
 * 形如 "xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"），保存并重新部署即可。
 * 未填写时本脚本不做任何网络请求，也不采集任何数据。
 *
 * 说明：百度统计为标准站点访问量统计（页面浏览量、访问时长、来源等），
 * 不收集求职者姓名、电话、简历等个人身份信息。
 */
(function () {
  "use strict";
  var TONGJI_ID = ""; // TODO: 填入百度统计 HM 号后启用

  if (!TONGJI_ID) return;

  window._hmt = window._hmt || [];
  var hm = document.createElement("script");
  hm.async = true;
  hm.src = "https://hm.baidu.com/hm.js?" + encodeURIComponent(TONGJI_ID);
  var s = document.getElementsByTagName("script")[0];
  s.parentNode.insertBefore(hm, s);
})();
