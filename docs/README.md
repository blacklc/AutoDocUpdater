# AutoDocUpdater 流程图

本文档使用 Mermaid 源文本维护，便于随代码同步更新。旧的 PNG 流程图已移除。

## 主流程

```mermaid
flowchart TD
    A[开始] --> B[使用 exporting-doc 导出 51upload 文章]
    B --> C[使用 optimizing-markdown 优化 Markdown]
    C --> D[使用 uploading-2-51cto 发布到 51CTO]
    D --> E[汇总各步骤结果]
    E --> F[结束]
```

## 备忘录导出

```mermaid
flowchart TD
    A[用户提供 tag 或文章名称] --> B[解析并校验参数]
    B --> C[查询标签/文件夹或名称]
    C --> C1{查询成功?}
    C1 -- 否 --> C2[返回查询超时或 AppleScript 错误]
    C1 -- 是 --> D{导出格式}
    D -- Markdown --> E[HTML 转 Markdown]
    D -- PDF --> F{桌面存在同名 PDF?}
    F -- 是 --> F1[安全拒绝，不覆盖]
    F -- 否 --> G[等待 Notes 保存面板并自动保存]
    E --> H[写入目标目录]
    G --> I[从桌面移动到目标目录]
    H --> J[返回结构化结果]
    I --> J
```

说明：主导出器不在导出阶段移除 base64 图片，base64 清理由优化阶段完成。

## Markdown 优化

```mermaid
flowchart TD
    A[用户提供 Markdown 路径] --> B[检查 AUTODOC_LLM_* 环境变量]
    B --> B1{配置完整?}
    B1 -- 否 --> B2[输出配置引导并退出]
    B1 -- 是 --> C[删除原文第一行]
    C --> D[移除 base64 图片]
    D --> E{文章长度}
    E -- 短文章 --> F[单次正文优化]
    E -- 长文章 --> G[按标题分块并逐块优化]
    F --> H[生成摘要]
    G --> H
    H --> I[生成前言和总结]
    I --> J[组装前言、目录、正文和总结]
    J --> K[覆盖保存原文件]
```

## 51CTO 上传与重试

```mermaid
flowchart TD
    A[用户提供 Markdown 文件或目录] --> B[打开发布页并检查登录]
    B --> B1{已登录?}
    B1 -- 否 --> B2[提示用户登录或报告登录失败]
    B1 -- 是 --> C[遍历文件]
    C --> D[执行上传尝试]
    D --> E{发布成功?}
    E -- 是 --> F[删除本地文件]
    E -- 最终提交前失败 --> G{还有即时重试次数?}
    G -- 是 --> D
    G -- 否 --> H[暂时保留文件并写入重试清单]
    E -- 最终提交后状态未知 --> H
    H --> I[报告失败原因并询问用户是否重传]
    I --> J{用户选择}
    J -- 重传 --> K[使用 --retry-manifest 再次上传]
    J -- 放弃 --> L[使用 --discard-manifest 删除保留文件]
    K --> E
```

说明：

- 默认即时重试 1 次，仅用于最终提交前的可恢复失败。
- 最终提交后状态未知时不会自动重试，避免重复发布。
- 用户未确认前保留文件。
