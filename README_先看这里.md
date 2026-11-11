# Group 4 — Web Dashboard V1 (2026-11-11)

**这不是第二套后端。** 已部署的 `group4-mfg-stack`（10资源）不需要更改。压缩包含：

- `web/`：已经有的 Streamlit MVP（本地演示 + AWS 云端模式）及9项离线单元测试
- `infra/group4_web_api.yaml`：独立的CloudFormation Web API附加栈模板
- `aws_artifacts/web-api-v1.zip`：新增Lambda代码（部署用，入口lambda_function.lambda_handler）
- `docs/DEPLOY_CN.md`：逐步部署指南（先Web，再API接AWS）

## 你现在只做的事情

1. 解压本包，把 **web/** 文件夹上传到 `fengzhibin-web/group4-aws-manufacturing` GitHub 仓库；建议也上传 `infra/`、`aws_artifacts/` 和 `docs/`。
2. 打开 https://share.streamlit.io ，Connect with GitHub → Create app，Repository选择该仓库，Branch=main，Main file=`web/app.py`。
3. **不连接AWS时即可使用本地演示模式**，上传 `web/data/sample_valid.csv`，点击“本地执行分析”。
4. 要连接真实AWS，再按 `docs/DEPLOY_CN.md` 部署 `group4-web-api` 附加栈，并通过Streamlit Secrets配置 URL 和随机秘密。

本地演示成功并不证明真实AWS已连接；AWS模式需要CloudFormation附加栈 `CREATE_COMPLETE`、API调用验证和端到端上传测试。

⚠ 仓库目前是Public。绝对不要提交AWS临时密钥、AWS session token、`.streamlit/secrets.toml` 或实际的DemoApiKey。在线云端模式启用前必须在Streamlit的Secrets中设置不同的 `APP_PASSWORD` 和 `DEMO_API_KEY`。密码保护仅适合课程内演示，不是生产级用户认证。
