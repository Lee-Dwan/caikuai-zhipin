# 每周招聘来源发现报告

- 探测时间：2026-11-27T15:10:21+08:00（北京时间）
- 汇总：可访问且疑似社招 3；可访问待确认 0；仅校招 0；不可访问 4

| 来源 | 类别 | 状态 | 说明 |
| --- | --- | --- | --- |
| 国聘（央企国企招聘平台） | 国企/央企 | 疑似有社招 | - |
| 中智招聘 | 国企/上市公司 | 疑似有社招 | - |
| 华兴会计师事务所（广东） | 会计师事务所 | 不可访问 | ConnectionError: HTTPSConnectionPool(host='www.gdhxcpa.com.cn', port=443): Max retries exceeded with url: / (Caused by NameResolutionError("HTTPSConnection(host='www.gdhxcpa.com.cn', port=443): Failed to resolve 'www.gdhxcpa.com.cn' ([Errno -2] Name or service not known)")) |
| 希格玛会计师事务所 | 会计师事务所 | 疑似有社招 | - |
| 中兴财光华会计师事务所 | 会计师事务所 | 不可访问 | ConnectionError: HTTPSConnectionPool(host='www.zqftcpa.com', port=443): Max retries exceeded with url: / (Caused by NameResolutionError("HTTPSConnection(host='www.zqftcpa.com', port=443): Failed to resolve 'www.zqftcpa.com' ([Errno -2] Name or service not known)")) |
| 京洲联信税务师事务所 | 税务师事务所 | 不可访问 | SSLError: HTTPSConnectionPool(host='www.jzlx.com.cn', port=443): Max retries exceeded with url: / (Caused by SSLError(SSLCertVerificationError(1, '[SSL: CERTIFICATE_VERIFY_FAILED] certificate verify failed: certificate has expired (_ssl.c:1011)'))) |
| 中瑞岳华税务师事务所 | 税务师事务所 | 不可访问 | HTTP 403 |

> 以上仅为基础探测信号，不直接上线。确认「疑似有社招」的来源后，需人工核对其官方公开招聘渠道
> 与数据接口，再按 `scripts/collectors/` 现有模式新增采集器；验证通过前不会写入任何岗位数据。
