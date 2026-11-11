# Group 4 — Manufacturing CSV 数据规范 v1（拟冻结）

> 本规范对齐已运行的 AWS 版本的 **7 个必需字段**，并扩展“前端质量预警”和“报告分析”。
> **重要：这不是声明 AWS 当前已实现全部规则。** 当前已部署 AWS `group4-validate` 主要验证文件大小、编码、必需列和非空；`group4-process` 清洗空格/精确重复、缺失值、0/1缺陷标签及按机器统计。更严格字段值检查和分组报告需要后续升级云端代码后才可声称已经在AWS实施。

## 1. 文件级要求（Hard error：INVALID_INPUT）

| 项目 | 规范 | 当前AWS适配情况 |
|---|---|---|
| 文件格式 | `.csv`，逗号分隔，首行为列名 | 已按上传路径 `.csv` 过滤 |
| 编码 | UTF-8 或 UTF-8 BOM | 已支持 |
| 大小 | 不超过10 MiB | 已支持 |
| 行数 | 至少1行数据，最多50,000行 | AWS目前**尚未强制50,000行上限** |
| 列名 | 7个必需列，名称完全一致、区分大小写 | 已支持必需列 |
| 列数 | 每行列数必须等于表头 | 前端已校验，AWS需补强 |
| 原始文件 | 禁止改变原始上传对象 | AWS保留在 `raw/` |

### 七个必需列（顺序推荐，AWS按名称识别）

```csv
timestamp,machine_id,shift,product_id,supplier_batch,temperature,defect_label
```

| 字段 | 类型 | 推荐合法格式 | 示例 | 不合规时的建议 |
|---|---|---|---|---|
| `timestamp` | 文本时间戳 | ISO 8601 `YYYY-MM-DDTHH:MM:SS`，注明工厂所在时区 | `2026-09-01T08:00:00` | 行级警告，不直接删除 |
| `machine_id` | 机器编号 | 现有模拟清单 `M01–M04` | `M03` | 不认识的编号标记复核 |
| `shift` | 班次枚举 | 约定 `Day` / `Evening` / `Night` | `Night` | 标记复核；命名由小组最终确认 |
| `product_id` | 产品编号 | `P` + 两位或更多数字 | `P02` | 行级警告 |
| `supplier_batch` | 供应商批次 | `SB-` + 数字 | `SB-204` | 行级警告 |
| `temperature` | 浮点数字，单位°C | 非空且可转换为有限数字 | `91.3` | 空值/非数字/异常数值仅标记 |
| `defect_label` | 二元标签 | `0`=合格，`1`=缺陷 | `1` | 其他值不参与缺陷率分母，标记复核 |

**可选扩展字段**：`batch_id`（生产批次）、`defect_type`（缺陷类别）。现有云端代码支持保留额外列，但尚未对这些字段作完整业务分析。

## 2. 异常值不能当错误直接删除

- **结构性错误**：缺少必需列、格式不符合要求、非UTF-8、空文件、超出大小/行数限制 → 拒绝整个文件。
- **质量问题**：机器编号未知、温度缺失或异常、缺陷标签未知、供应商批次不规范 → 文件可以进入处理，但是该行需要被 **flagged**。
- **低风险清洗**：去除前后空格、完全相同的记录去重（注意保留计数），不修改异常温度。
- **示例温度预警区间**：60–90 °C，仅供界面演示；这不是工程上已批准的缺陷阈值，应按实际工艺数据确认。

## 3. 分析指标的数学定义

- `input_rows`：CSV总数据行数（不计表头）。
- `cleaned_rows`：移除完全重复记录后行数（空格两端先标准化）。
- `exact_duplicates_removed`：`input_rows - cleaned_rows`。
- `valid_labeled_rows`：去重后、`defect_label` 恰为 `0` 或 `1` 的记录数。
- `defects`：上述记录中标签为 `1` 的数量。
- **缺陷率**：`defects / valid_labeled_rows`；无有效标签时显示 `N/A`，绝不按0%报告。
- 按机器、班次、产品、供应商批次、日期的比率，都以**对应分组有效标签记录数**为分母。
- 统计图只揭示相关性/分布，不声称已证明 M03 或 SB-204 是缺陷根因。

## 4. 内容级去重规则

`sha256(file_bytes)` + `processing_version=v1` → `sha256("<digest>:v1")[:16]` 作为Job ID。

相同字节、不同文件名的CSV会得到相同Job ID；只改空格/换行也可能改变哈希。
现有实现可跳过已完成的重复任务，尚不代表所有并发与失败情况下的严格 exactly-once 处理。

## 5. 任务状态及页面用词

`CREATED` → `UPLOADED` → `VALIDATING` → `QUEUED` → `PROCESSING` → `COMPLETED`；
错误可能为 `INVALID_INPUT` 或 `FAILED`，AI非关键错误可用 `COMPLETED_WITH_WARNING`。

**当前云端真实实现**：主要是 `VALIDATED` / `QUEUED` / `PROCESSING` / `COMPLETED` / `INVALID_INPUT`；`FAILED` 的DLQ状态核对、`CREATED/UPLOADED/VALIDATING` 细粒度记录仍待实现。不要把 UI 文案或规划状态描述为现有AWS数据事实。

## 6. 测试样本

- `data/sample_valid.csv`：6行，含1条完全重复，正确结果：5条去重、3个缺陷、总体缺陷率60%。
- `data/sample_invalid.csv`：缺少 `supplier_batch`，应返回 INVALID_INPUT。
- `data/manufacturing_6000.csv`：6000行可重复生成的模拟制造数据，包含M03夜班/供应商批次异常、重复行、少量无效标签和温度缺失；不涉及真实工业数据。
