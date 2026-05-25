# salsaAuto

餐饮管理系统自动化工具 - 重构版

## 功能

- **Web UI 界面**：现代化的 Web 管理界面
- **Chrome 驱动管理**：自动检测版本、一键更新驱动
- **Token 管理**：自动保存/加载认证 Token
- **会员管理**：会员数据存储在数据库，支持类型分类
- **订单管理**：支持单个订单、按金额刷单、按数量刷单、一纸满刷单
- **刷单计算器**：根据总金额自动计算每日商品配比
- **任务系统**：保存计算结果，一键执行刷单任务
- **基础库管理**：商品库、商品分类、档口分类、供应商管理
- **数据校准**：要货任务计算器、补要货、采购任务计算器、补采购
- **数据分析**：订单查询、菜品分析、档口分析、要货查询、采购查询、月订货统计

## 快速开始

### 安装依赖

```bash
pip install -r requirements.txt
```

### 启动服务

双击 `start_web.bat` 或运行：

```bash
python -m src web
```

服务启动后会自动打开浏览器访问 `http://127.0.0.1:8080`

### CLI 模式

```bash
python -m src
```

## 功能说明

### 概览页面

- **Chrome 驱动状态**：显示 Chrome 浏览器版本和 ChromeDriver 版本
- **版本检测**：自动检测版本是否匹配
- **一键更新**：点击更新按钮自动下载并更新 ChromeDriver
- **Token 状态**：显示认证状态
- **今日刷单统计**：按门店显示今日刷单金额

### 门店管理

显示所有门店信息，配置在 `config/settings.json`

### 菜品管理

- 显示所有菜品信息
- 支持添加、更新、删除菜品
- 配置商品可用时间范围（用于任务刷单）

### 会员管理

- 查看会员列表
- 同步会员余额（从 API）
- 设置会员类型（通用/一纸满）
- 会员数据存储在数据库 `members` 表

### 订单管理

支持五种刷单方式：

1. **单个订单**：创建单个订单
2. **按金额刷单**：指定总金额，随机数量刷单
3. **按数量刷单**：指定总数量，随机数量刷单
4. **一纸满刷单**：专用一纸满门店刷单
5. **任务刷单**：选择已保存的任务执行刷单

### 刷单计算器

**功能**：根据总金额、日期范围、商品配比，自动计算每日刷单方案

**输入参数**：
- 门店选择
- 支付方式（会员支付/现金支付）
- 开始日期、结束日期
- 总金额
- 每日浮动百分比
- 商品选择（可多选）

**算法特点**：
- 高价商品（≥15元）数量平衡：每天数量相近，最多 20% 差距
- 贪心算法：从贵到便宜填满每日目标金额
- 精度处理：所有金额转为"分"计算，避免浮点数精度问题
- 最后一天精确匹配：确保总金额完美匹配

**输出**：
- 每日商品数量分配表
- 导出 CSV 功能
- 保存为任务

### 任务系统

**任务保存**：
- 计算器计算完成后，可保存为任务 JSON 文件
- 任务文件保存在 `data/tasks/` 目录
- 任务命名格式：`{门店}_{支付方式}_{日期区间}_{时间戳}`

**任务刷单**：
- 选择任务后显示详情（每日商品配比）
- 支持会员类型选择（通用/一纸满）
- 执行时自动拼接日期 + 商品时间上界作为交易时间

### 数据校准

**要货任务计算器** (`/supply-calculator`)
- 根据总金额和日期范围，计算每日要货金额
- 支持浮动百分比设置
- 任务保存到 `data/supply-tasks/` 目录

**补要货** (`/supply-adjust`)
- 选择门店、日期、目标金额
- 自动查询现有要货明细
- 计算差额并添加补差价商品
- 补差价商品：8919(1元)、8917(1角)、8918(1分)
- 自动修改新添加明细的创建时间

**采购任务计算器** (`/purchase-task`)
- 根据总金额和日期范围，计算每日采购金额
- 支持浮动百分比设置
- 选择汇总主体（供应商分组）
- 设置采购人
- 自动生成随机采购时间
- 导出 CSV 功能
- 保存为采购任务

**补采购** (`/purchase-adjust`)
- 选择已保存的采购任务
- 显示任务详情（每日目标金额）
- 执行单日补采购

**补采购流程**:
1. 读取任务配置（汇总主体、目标金额、日期等）
2. 同步采购明细到本地库
3. 查询指定日期、汇总主体、显示状态的采购明细总金额
4. 计算差额（目标金额 - 当前金额）
5. 如果差额 < 0：关闭部分明细（从最接近差额的开始）
6. 如果差额 > 0：贪心算法选择商品
   - 只使用贸易品（排除现采、加工品）
   - 排除 G00003、G00004 供应商
   - 只取上架状态的商品
   - 两阶段贪心：大金额商品填大部分，小金额商品（0.1元、0.01元）补零头
7. 按供应商分组，查找/创建采购订单
8. 添加采购明细并入库
9. 验算最终金额，返回结果

**补采购算法特点**:
- 精确补齐到 0.01 元级别（需要汇总主体包含 0.1元、0.01元商品）
- 按供应商分组处理，每个供应商单独创建/查找采购订单
- 验算步骤确保最终金额准确

### 数据分析

**订单查询** (`/order-query`)
- 从平台 API 实时查询订单
- 筛选条件：门店、时间范围、订单号、菜品名称

**菜品分析** (`/product-analysis`)
- 按菜品汇总销量数据
- 支持导出 Excel

**档口分析** (`/category-analysis`)
- 按档口汇总数据
- 支持导出 Excel

**要货查询** (`/supply-query`)
- 查询门店要货记录
- 支持切换 canShow 状态

## 配置文件

### config/settings.json

```json
{
  "api": {
    "base_url": "https://shasha.tjxuechuang.com",
    "endpoints": {
      "login": "/thinker/tkadmin/login",
      "members": "/restful/shasha/orders/members",
      "orders": "/restful/shasha/orders/orderinfo"
    }
  },
  "user": {
    "username": "admin",
    "password": "***"
  },
  "stores": {
    "13": { "name": "丰台店" },
    "8": { "name": "一号仓" },
    "16": { "name": "宾西楼" },
    "11": { "name": "测试店" },
    "32": { "name": "一纸满" }
  },
  "dishes": {
    "28": { "name": "自助餐", "price": 17.6, "time_range": "11:00-20:00" },
    "73": { "name": "自助餐", "price": 19.9, "time_range": "11:00-14:00" },
    "77": { "name": "烤肉", "price": 49.9, "time_range": "16:00-23:00" },
    "511": { "name": "康师傅纯净水", "price": 1.0, "time_range": "11:30-21:30" },
    "512": { "name": "大窑", "price": 5.0, "time_range": "11:30-21:30" },
    "513": { "name": "塑料袋", "price": 0.1, "time_range": "11:30-21:30" },
    "57": { "name": "测试菜品", "price": 1.0, "time_range": "00:00-23:59" }
  }
}
```

### config/token.json

Token 缓存，包含：
- `token`: 认证 Token
- `updated_at`: 更新时间

### data/tasks/

任务文件夹，存储计算器生成的刷单任务

### data/supply-tasks/

要货任务文件夹，存储要货任务

### data/purchase-tasks/

采购任务文件夹，存储采购任务

### data/orders.db

SQLite 数据库，包含以下表：
- `order_records` - 刷单记录
- `goods` - 商品库
- `goods_sub_cate` - 商品分类
- `cang_sub_cate` - 档口分类
- `members` - 会员数据
- `suppliers` - 供应商数据
- `purchase_details` - 采购明细缓存

## 项目结构

```
salsaAuto/
├── src/                    # 源代码
│   ├── api/               # API 客户端
│   ├── auth/              # 认证服务
│   ├── cli/               # CLI 界面
│   ├── services/          # 业务服务
│   │   ├── member.py      # 会员服务（数据库）
│   │   ├── order.py       # 订单服务
│   │   ├── supply_adjust.py  # 补要货服务
│   │   ├── supply_query.py   # 要货查询服务
│   │   └── database.py    # 数据库服务
│   ├── config.py          # 配置管理
│   └── __main__.py        # 入口
├── web/                    # Web UI
│   ├── server.py          # FastAPI 服务
│   ├── static/            # CSS/JS
│   └── templates/         # HTML 模板
├── config/
│   ├── settings.json      # 配置
│   └── token.json         # Token 缓存
├── data/
│   ├── orders.db          # 数据库
│   ├── tasks/             # 刷单任务
│   ├── supply-tasks/      # 要货任务
│   └── purchase-tasks/    # 采购任务
├── chromedriver-win64/     # ChromeDriver
├── docs/
│   └── CHANGELOG.md       # 更新日志
├── start_web.bat          # 启动脚本
├── requirements.txt
└── README.md
```

## 技术栈

- **后端**: FastAPI + Python 3.11
- **前端**: 原生 HTML/CSS/JS
- **样式**: OpenClaw Design System
- **浏览器自动化**: Selenium
- **数据库**: SQLite

## API 接口

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/status` | 获取系统状态 |
| GET | `/api/stores` | 获取门店列表 |
| GET | `/api/dishes` | 获取菜品列表 |
| POST | `/api/dishes/add` | 添加菜品 |
| POST | `/api/dishes/{id}/update` | 更新菜品 |
| POST | `/api/dishes/{id}/delete` | 删除菜品 |
| GET | `/api/members` | 获取会员列表 |
| POST | `/api/members/sync` | 同步会员余额 |
| POST | `/api/members/{id}/type` | 设置会员类型 |
| POST | `/api/orders/create` | 创建单个订单 |
| POST | `/api/orders/batch/amount` | 按金额刷单 |
| POST | `/api/orders/batch/quantity` | 按数量刷单 |
| GET | `/api/orders/records` | 获取刷单记录 |
| GET | `/api/orders/statistics` | 获取刷单统计 |
| POST | `/api/tasks/save` | 保存任务 |
| GET | `/api/tasks/list` | 获取任务列表 |
| GET | `/api/tasks/{id}` | 获取任务详情 |
| POST | `/api/tasks/{id}/execute` | 执行任务刷单 |
| POST | `/api/supply-tasks/save` | 保存要货任务 |
| GET | `/api/supply-tasks/list` | 获取要货任务列表 |
| POST | `/api/supply/update-can-show` | 更新要货明细显示状态 |
| GET | `/api/base/suppliers` | 查询供应商列表 |
| GET | `/api/base/suppliers/local` | 从数据库查询供应商 |
| POST | `/api/base/suppliers/update` | 同步供应商到本地库 |
| GET | `/api/summary-entities` | 获取汇总主体列表 |
| GET | `/api/purchase/orders` | 查询采购明细 |
| POST | `/api/purchase/detail/update-can-show` | 更新采购明细显示状态 |
| GET | `/api/purchase/order-list` | 查询采购订单列表 |
| POST | `/api/purchase/detail/add` | 添加采购明细 |
| POST | `/api/purchase/inbound/add` | 添加采购明细并入库 |
| POST | `/api/purchase/order/create` | 创建采购订单 |
| POST | `/api/purchase/task/save` | 保存采购任务 |
| GET | `/api/purchase/task/list` | 获取采购任务列表 |
| GET | `/api/purchase/task/{filename}` | 获取采购任务详情 |
| POST | `/api/purchase/sync-details` | 同步采购明细到本地库 |
| POST | `/api/purchase/adjust-day` | 执行单日补采购 |
| POST | `/api/token/start` | 启动登录流程 |
| POST | `/api/token/submit` | 提交验证码 |
| POST | `/api/chromedriver/update` | 更新 ChromeDriver |

## 注意事项

1. **Chrome 驱动**：首次使用前确保 ChromeDriver 版本与 Chrome 浏览器版本匹配
2. **Token 获取**：需要先启动 Chrome 调试模式（端口 9222）
3. **会员类型**：会员类型是本地手动划分的，不会从 API 同步
4. **商品时间**：任务刷单时会使用商品配置的 `time_range` 字段拼接交易时间
5. **数据库**：商品库、会员数据已迁移到数据库，可删除旧的 JSON 文件
6. **补采购**：只使用贸易品（排除现采和加工品），按汇总主体分组选择商品，排除 G00003、G00004 供应商，支持精确补齐到 0.01 元级别

## 更新日志

详见 `docs/CHANGELOG.md`
