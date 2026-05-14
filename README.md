# salsaAuto

餐饮管理系统自动化工具 - 重构版

## 功能

- **Web UI 界面**：现代化的 Web 管理界面
- **Chrome 驱动管理**：自动检测版本、一键更新驱动
- **Token 管理**：自动保存/加载认证 Token
- **会员管理**：本地存储会员信息，支持类型分类
- **订单管理**：支持单个订单、按金额刷单、按数量刷单、一纸满刷单
- **刷单计算器**：根据总金额自动计算每日商品配比
- **任务系统**：保存计算结果，一键执行刷单任务

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
- 会员数据保存在 `config/member.json`

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

### config/member.json

会员数据，包含：
- `phone`: 手机号
- `username`: 用户名
- `balance`: 余额
- `type`: 类型（None=通用, yizhiman=一纸满）

### config/token.json

Token 缓存，包含：
- `token`: 认证 Token
- `updated_at`: 更新时间

### data/tasks/

任务文件夹，存储计算器生成的刷单任务

### data/orders.db

SQLite 数据库，存储刷单记录

## 项目结构

```
salsaAuto/
├── src/                    # 源代码
│   ├── api/               # API 客户端
│   ├── auth/              # 认证服务
│   ├── cli/               # CLI 界面
│   ├── services/          # 业务服务
│   │   ├── member.py      # 会员服务
│   │   ├── order.py       # 订单服务（含 execute_task）
│   │   └── database.py    # 数据库服务
│   ├── config.py          # 配置管理
│   └── __main__.py        # 入口
├── web/                    # Web UI
│   ├── server.py          # FastAPI 服务
│   ├── static/            # CSS/JS
│   └── templates/         # HTML 模板
├── config/
│   ├── settings.json      # 配置
│   ├── member.json        # 会员数据
│   └── token.json         # Token 缓存
├── data/
│   ├── orders.db          # 刷单记录数据库
│   └── tasks/             # 任务文件夹
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
- **数据库**: SQLite + JSON 文件

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
| POST | `/api/token/start` | 启动登录流程 |
| POST | `/api/token/submit` | 提交验证码 |
| POST | `/api/chromedriver/update` | 更新 ChromeDriver |

## 注意事项

1. **Chrome 驱动**：首次使用前确保 ChromeDriver 版本与 Chrome 浏览器版本匹配
2. **Token 获取**：需要先启动 Chrome 调试模式（端口 9222）
3. **会员类型**：会员类型是本地手动划分的，不会从 API 同步
4. **商品时间**：任务刷单时会使用商品配置的 `time_range` 字段拼接交易时间

## 更新日志

### v2.1.0 (2026-05-14)

- 新增刷单计算器（自动计算每日商品配比）
- 新增任务系统（保存计算结果，一键执行）
- 新增商品时间配置（`time_range` 字段）
- 优化计算器算法（浮点数精度、高价商品平衡）
- Token 自动加载（服务启动时）
- 任务刷单功能（订单页面新增 Tab）

### v2.0.0 (2026-05-14)

- 完全重构项目结构
- 新增 Web UI 界面
- 新增 Chrome 驱动自动检测和更新
- 新增今日刷单统计
- 优化会员管理，支持本地类型划分
- 统一 OpenClaw 设计风格