# Group 4 — Web ↔ AWS API 合约（API实现已准备，需通过独立附加Stack部署）

## 背景

AWS现有：`S3 raw/` → `group4-validate` → `SQS group4-mfg-jobs` → `group4-process` → `S3 cleaned/reports/`，DynamoDB `group4-mfg-jobs` 记录状态。
Web目前不存在可安全直接调用的后台API。**不能把 AWS Academy 的临时访问密钥写入前端、GitHub或公开的Streamlit secrets。**

## 推荐对接：API Gateway HTTP API + 一个轻量 Lambda

新建 `group4-web-api`，把两条HTTP API route接入它：

### `POST /uploads`

Request body:

```json
{"filename":"factory.csv","sha256":"<64 hex chars>","size_bytes":360,"processing_version":"v1"}
```

成功返回：

```json
{"job_id":"<16hex>","key":"raw/uploads/<uuid>/factory.csv","upload_url":"<S3 presigned HTTPS PUT URL>","upload_headers":{"Content-Type":"text/csv"}}
```

前端随后向`upload_url`发起 `PUT`，其中请求头必须匹配。**上传文件字节本身不会经过API Gateway或本API Lambda**。S3的 `raw/`对象创建事件会自动触发原有Validation Lambda。

### `GET /jobs/{job_id}`

上传完到S3，但验证事件可能还未处理，初期可能返回404。前端将其视为短暂 `AWAITING_EVENT`，由用户点击“刷新任务状态”。

任务处理成功示例：

```json
{"job_id":"<16hex>","status":"COMPLETED","created_at":"...","updated_at":"...","validation_errors":[],"report_url":"<5 min presigned GET>","cleaned_url":"<5 min presigned GET>"}
```

无效输入返回 `status=INVALID_INPUT`，并附 `validation_errors` 和 `validation_url`。

前端从 `report_url` 读取AWS生成的 `report.json`，从 `cleaned_url` 读取 `cleaned.csv` 用于二级图表。**目前按班次/产品/日期的扩展图表是Streamlit基于云端清洗文件计算；尚未由现有Processing Lambda计算。**

## AWS资源与权限（Learner Lab恢复后）

| 资源 | 操作 |
|---|---|
| `group4-web-api`（新增） | Python 3.12，x86_64，建议内存128MB/超时10s，执行角色按Lab可用权限设定 |
| 环境变量 | `BUCKET_NAME=group4-mfg-data-20261110`；`JOB_TABLE_NAME=group4-mfg-jobs`；`PROCESS_VERSION=v1`；`DEMO_API_KEY=<random secret>` |
| API Gateway HTTP API | `POST /uploads`、`GET /jobs/{job_id}` 两个Route接同一个Lambda，使用 `$default` stage；payload格式2.0 |
| IAM | API Lambda只应被授予 `s3:PutObject` (raw/), `s3:GetObject` (reports/, cleaned/) , `dynamodb:GetItem` (指定Table)，及CloudWatch日志 |
| S3 | 保持Block Public Access，事件规则限制`raw/`且仅处理`.csv` |
| Web | `.streamlit/secrets.toml` 配`AWS_API_BASE_URL`和`DEMO_API_KEY`，不得提交到GitHub |

## 安全限制与正式部署升级

- 示例代码的 `x-demo-key` 只是小组演示的额外服务端秘密校验，不是多用户授权机制。正式分享前，优先配置 **API Gateway IAM/JWT/Lambda authorizer**，限制谁能发起任务并查看报告。
- 公开Streamlit页面的访客会借由页面间接触发后端操作，因此公开展示前还需要页面访问控制、限流及预算控制。
- `PUT` 预签名URL 有效期5分钟；API本身必须先授权，云端Lambda的最小权限限制依然有效。
- API对上传信息中的 `sha256` 暂时做格式检查，真正的SHA由Validation Lambda读取S3实际文件重新计算。上传大小上限仍必须由Validation Lambda执行；目前使用的PUT方式本身不强制Content-Length上限。
- 若 API Gateway 在 Learner Lab 不可用：先在本地演示Streamlit界面，云端仍可用AWS Console手动上传CSV。不要为了UI去公开S3，或把临时AWS密钥放进公开站点。
- 该API服务**尚未由我们在真实AWS控制台部署并验证**。不能将示例API地址当成有效服务。
