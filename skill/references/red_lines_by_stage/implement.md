# 实现阶段红线（implement）

> 加载时机：进入「实现」阶段时
> 违反后果：污染工程规范，代码风格不一致

---

## RL-S01：UI 改动必须比对语义桥

### 规则

> 禁止硬编码字号/颜色，参照 L3 naming-conventions.md

### 错误示例

```objc
// ❌ 硬编码字号 + 颜色
self.titleLabel.font = [UIFont systemFontOfSize:15];
self.titleLabel.textColor = [UIColor colorWithRed:0.1 green:0.1 blue:0.1 alpha:1.0];
```

### 正确示例

```objc
// ✅ 按映射规则翻译 Figma Token
self.titleLabel = [UILabel xyz_styledLabel:@"callout"]; // Mobile/callout
self.titleLabel.textColor = XYZColor(base_gray_100);   // Base/base_gray_100
self.titleLabel.text = R_NSSTRING(XYZ::XXX::TITLE_KEY); // i18n
```

### 语义桥位置

- `docs/knowledge-base/L3-语义桥/naming-conventions.md`
- `docs/knowledge-base/L3-语义桥/figma_token_mapping.md`

---

## RL-S02：禁止语义联想扩大范围

### 规则

> 任何"点击 X → 触发 Y"类拦截，X 必须有**具体引用依据**

### 允许的引用来源（仅三种）

1. **设计稿标注**：PNG 上的连接线/箭头从 X 指向 Y（必须有 nodeId）
2. **文档原文**：TAPD/企微文档的**直接引用原句**
3. **用户消息**：用户原话引用

### 禁止的语义联想

- "Z 看起来也属于这类功能"
- "为了一致性应该也拦一下"
- "属于同类功能行为"

### 正确示例

```markdown
拦截点：邮件列表点击 → 跳转详情页

引用依据：
- 设计稿 nodeId 153:74521 标注：从"邮件列表"指向"邮件详情"
- TAPD 原文："点击邮件列表项，跳转至邮件详情页"

禁止项：
- ✗ "点击Tab也拦截"（无引用依据）
- ✗ "未读状态也要拦截"（无引用依据）
```

### 禁止示例

```markdown
拦截点：点击小红条 → 跳转管理页

判断："根据一致性原则，角标点击也应该跳转"

⛔ 这是语义联想，禁止实施
```

### 触发报告模板

```markdown
⛔ 触发红线 RL-S02：禁止语义联想扩大范围

当前情形：
- 新增拦截：{new_interception}
- 引用依据：{reference}
- 判断方式：{reasoning}

建议处理：
1. 删除无引用依据的拦截点
2. 仅保留有设计稿/文档/用户消息支撑的拦截点
3. 如确实需要，补充对应引用依据
```
