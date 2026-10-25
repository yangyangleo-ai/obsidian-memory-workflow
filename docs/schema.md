# 最小属性规范

新资料／知识卡显式采用 `management_schema: obs-v1`。旧项目档案不必批量补齐。所有字段是扁平 YAML，同名字段保持同一类型；空白代表未知，不能填 0 或今天冒充已核实。

| 字段 | 含义 |
| --- | --- |
| type | reference-note / knowledge-card；项目和报告使用各自类型 |
| status | 资料：captured / triaged / retained / promoted / rejected；卡片：draft / active / needs-review / superseded |
| evidence_status | unverified / verified / user-decision / inferred / contested / superseded |
| project | 关联入口，文本或带引号双链 |
| source_url / source_version | 公开无凭据 URL 与版次／commit；没有就留空 |
| source_accessed / source_published | YYYY-MM-DD 日期；访问日期不是事实发生日期 |
| source_sha256 | 只对应实际计算过的单个本地文件，不能套给整篇结论或多个来源 |
| source_of_truth / promoted_to | 权威记录／提炼去向，文本或带引号双链 |
| last_verified / review_after | 日期或空；核实范围写正文；复查提醒不是到期自动失效 |
| sensitivity / publish | 示例均为 private / false；只是标记，不是访问权限 |

`active` 表示采用，不等于效果经过实验；`user-decision` 表示用户决定，不等于已执行；`promoted` 表示有提炼去向，不等于来源中每个论断都证实。

Bases 只纳入两个目录的**直接子文件**：`07-收件箱/资料`、`05-复盘/知识卡`，且要同时满足类型、schema、private、布尔 false。历史、模板、staging、附件和缺字段文件不自动纳入。若调整目录，要同步改 `.base` 和测试。
