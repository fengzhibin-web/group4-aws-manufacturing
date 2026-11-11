# Web — Group 4 Manufacturing Data Quality

保留原有Streamlit MVP并增加在线模式访问密码门禁与独立AWS API部署模板。**本地模式独立运行**，AWS模式须先部署Web API附加栈。

## 开发模式

```bash
cd web
python -m pip install -r requirements.txt
python -m streamlit run app.py
```

在浏览器打开 `http://localhost:8501`，选择“本地演示”并上传 `data/sample_valid.csv`，运行本地分析。

## 在线部署

- GitHub: `fengzhibin-web/group4-aws-manufacturing` 
- Streamlit Community Cloud Main file：`web/app.py`。
- 官方依赖文件：`web/requirements.txt`。
- 若接入真实AWS，先部署仓库 `infra/group4_web_api.yaml`，然后在Streamlit Secrets里配置`APP_PASSWORD`、`AWS_API_BASE_URL`、`DEMO_API_KEY`。
- 完整中文操作：仓库 `docs/DEPLOY_CN.md`。

## 质量约束

- 必需的7列 `timestamp, machine_id, shift, product_id, supplier_batch, temperature, defect_label`。
- 最大 10 MiB；本地演示最大50000行，云端最终验证边界以部署中后端实际行为为准。
- 本地详细警告规则与原AWS Lambda校验规则不同，不能冒充已在AWS实现。
- 同一CSV字节+处理版本 `v1` 产生同一job_id（故意去重）。
- DLQ→FAILED功能已在原AWS环境使用模拟消息验证；新Web显示FAILED状态。

## 测试

```bash
python -m unittest discover -s tests -v
```

课程演示用的访问密码并不是生产级多用户认证。绝对不要上传`.streamlit/secrets.toml`或AWS访问密钥到GitHub。
