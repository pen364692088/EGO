# Contract Versioning Rules

> 版本: 1.0.0
> 日期: 2026-03-16

## 概述

本文档定义 EgoCore 与 OpenEmotion 之间契约的版本治理规则。

## 版本号格式

使用语义化版本 (SemVer)：`MAJOR.MINOR.PATCH`

- **MAJOR**: 破坏性变更
- **MINOR**: 向后兼容的新增功能
- **PATCH**: 文档/描述修正

## 变更分类

### MAJOR 变更（破坏性）

以下变更必须升级主版本号：

1. **必填字段移除**
   - 移除 `required` 数组中的字段

2. **必填字段重命名**
   - 改变必填字段的名称

3. **类型变更**
   - `string` → `number`
   - `object` → `array`
   - 等等

4. **枚举值移除**
   - 从 `enum` 中移除现有值

5. **约束收紧**
   - `minimum` 值增大
   - `maximum` 值减小
   - `pattern` 更严格

### MINOR 变更（向后兼容）

以下变更可以升级次版本号：

1. **新增可选字段**
   - 在 `properties` 中添加新字段，但不加入 `required`

2. **枚举值扩展**
   - 在 `enum` 中添加新值

3. **约束放宽**
   - `minimum` 值减小
   - `maximum` 值增大

4. **新增可选属性**
   - 在嵌套对象中添加可选属性

### PATCH 变更

以下变更可以升级修订号：

1. **描述修正**
   - 修改 `description` 内容

2. **标题修正**
   - 修改 `title` 内容

3. **示例更新**
   - 添加或修改示例

4. **默认值修正**
   - 修改 `default` 值（不影响必填字段）

## 兼容性检查规则

### 检查时机

1. **Adapter 初始化时**
   - 检查本地 schema 版本与预期版本

2. **处理事件前**
   - 检查输入事件的 schema_version

3. **处理输出前**
   - 检查 OpenEmotion 输出的 schema_version

### 兼容性判定

```
if major_version相同:
    兼容
elif major_version不同:
    不兼容，fail-fast
```

### 错误处理

当检测到不兼容版本时：

1. **记录错误日志**
   ```json
   {
     "error": "INCOMPATIBLE_SCHEMA_VERSION",
     "expected": "1.0.0",
     "received": "2.0.0",
     "schema_name": "event_input"
   }
   ```

2. **阻断处理**
   - 不尝试静默转换
   - 不跳过字段

3. **返回错误输出**
   - 使用标准错误输出格式

## 版本协商

如果未来需要支持多版本共存：

1. **声明支持版本范围**
   ```json
   {
     "supported_versions": ["1.0.0", "1.1.0"]
   }
   ```

2. **客户端指定版本**
   ```json
   {
     "schema_version": "1.0.0"
   }
   ```

3. **服务端选择最高兼容版本**

## 契约注册表

所有契约应在 `contracts/registry.json` 中注册：

```json
{
  "contracts": {
    "event_input": {
      "current_version": "1.0.0",
      "file": "contracts/event_input.schema.json",
      "compatible_versions": ["1.0.0"]
    },
    "openemotion_output": {
      "current_version": "1.0.0",
      "file": "contracts/openemotion_output.schema.json",
      "compatible_versions": ["1.0.0"]
    }
  }
}
```

## Replay Artifact 要求

所有 replay artifact 必须记录使用的 schema 版本：

```json
{
  "chain_id": "chain_xxx",
  "schema_versions": {
    "event_input": "1.0.0",
    "openemotion_output": "1.0.0"
  },
  "steps": [...]
}
```

## 变更日志

| 版本 | 日期 | 变更说明 |
|------|------|---------|
| 1.0.0 | 2026-03-16 | 初始版本，添加 schema_version 字段 |
