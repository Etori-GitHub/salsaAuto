# 补采购功能设计文档

## 概述

补采购功能用于自动调整采购明细，使实际采购金额接近目标金额。

## 问题背景

采购明细 API 只支持按"创建时间"查询，不支持按"进货时间"查询。但补采购需要按进货时间来计算金额。

## 解决方案：本地建库

### 数据流程

```
┌─────────────────────────────────────────────────────────────┐
│                      开始补采购任务                          │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│  1. 同步采购明细到本地库 (API 调用 1 次)                      │
│     POST /api/purchase/sync-details                         │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│  2. 遍历所有日期，逐个执行补采购                              │
│     - 从本地库查询目标日期的明细（按进货时间）                  │
│     - 计算差额                                               │
│     - 差额 > 0：创建明细 + 入库                              │
│     - 差额 < 0：关闭明细                                     │
│     - 同步更新本地库                                         │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│  3. 校对：重新同步采购明细 (API 调用 1 次)                    │
│     - 覆盖本地库                                             │
│     - 检查有问题的日期                                       │
└─────────────────────────────────────────────────────────────┘
```

### 数据库设计

**表名**: `purchase_details`

| 字段 | 类型 | 说明 |
|------|------|------|
| id | INTEGER | 明细 ID (主键) |
| detail_code | TEXT | 明细编号 |
| purchase_code | TEXT | 采购单号 |
| supplier_code | TEXT | 供应商编码 |
| supplier_name | TEXT | 供应商名称 |
| product_id | INTEGER | 商品 ID |
| product_name | TEXT | 商品名称 |
| category_name | TEXT | 分类名称 |
| sub_category_name | TEXT | 子分类名称 |
| quantity | INTEGER | 数量 |
| unit_price | REAL | 单价 |
| total_price | REAL | 金额 |
| purchase_time | TEXT | 进货时间 |
| purchaser | TEXT | 采购人 |
| can_show | INTEGER | 显示状态 (0=隐藏, 1=显示) |
| inbound_status | INTEGER | 入库状态 |
| create_time | TEXT | 创建时间 |
| updated_at | TEXT | 更新时间 |

### API 设计

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/purchase/sync-details` | 同步采购明细到本地库 |
| POST | `/api/purchase/adjust-day` | 执行单日补采购 |

## 补采购算法

### 1. 计算差额

```python
# 从本地库查询目标日期的明细
valid_details = db.get_purchase_details_by_date(date_str, entity_supplier_codes)
valid_details = [d for d in valid_details if d.get("can_show", 1) == 1]

# 计算当前总金额
current_amount = sum(d.get("total_price", 0) for d in valid_details)

# 计算差额
diff_amount = target_amount - current_amount
```

### 2. 差额 < 0：关闭明细

- 从最接近差额的明细开始关闭
- 关闭时调用 API 更新服务器，同时更新本地库
- 直到当前金额 <= 目标金额

### 3. 差额 > 0：创建明细

**商品筛选规则**：
- 排除分类为"现采"的商品
- 排除分类为"加工品"的商品
- 排除档口分类包含"现采"的商品（如"石家庄现采入库"）

**贪心算法**：
- 从大到小选择商品
- 每个商品记录数量，而非重复添加
- 返回格式：`{商品ID: {"goods": 商品对象, "quantity": 数量}}`

**创建流程**：
1. 检查是否已有当天该供应商的采购单
2. 如有则复用，否则创建新采购单
3. 创建采购明细（指定数量）
4. 入库处理
5. 同步更新本地库

## 使用方式

### 前置条件

1. 同步供应商信息
2. 同步商品库
3. 同步采购明细到本地库

### 执行步骤

```bash
# 1. 同步采购明细
POST /api/purchase/sync-details

# 2. 执行补采购任务
POST /api/purchase/adjust-day
{
    "date": "2026-04-01",
    "summary_entity": "外部供应商",
    "target_amount": 1000.00,
    "purchase_time": "2026-04-01 12:00:00",
    "purchaser": "system"
}

# 3. 完成后校对
POST /api/purchase/sync-details
```

## 注意事项

1. **API 调用次数优化**：理论上只需要 2 次完整拉取（开始 + 结束）
2. **数据一致性**：每次关闭/创建明细后立即更新本地库
3. **错误处理**：校对时发现问题的日期需要单独处理
4. **字段映射**：
   - API 返回驼峰命名（`totalPrice`, `supplierCode`）
   - 数据库使用下划线命名（`total_price`, `supplier_code`）

## 文件路径

- 数据库服务：`src/services/database.py`
- 补采购 API：`web/server.py` 的 `adjust_purchase_day` 函数
- 采购明细服务：`src/services/base_library.py`
