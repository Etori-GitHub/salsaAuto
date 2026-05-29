# GameMark 引擎设计文档

> 复古像素风 RPG 游戏引擎，FC 勇者斗恶龙风格

## 项目架构

```
salsaAuto/
├── src/
│   ├── gamemark/                  # 游戏引擎（通用）
│   │   ├── engine/
│   │   │   ├── Game.ts           # 主循环、场景管理
│   │   │   ├── Map.ts            # 地图渲染、碰撞
│   │   │   ├── Sprite.ts         # 精灵系统
│   │   │   ├── Input.ts          # 输入处理（手柄+键盘）
│   │   │   ├── Camera.ts         # 视口相机
│   │   │   └── Event.ts          # 事件系统
│   │   ├── entity/
│   │   │   ├── Character.ts      # 角色基类
│   │   │   ├── Player.ts         # 玩家
│   │   │   ├── NPC.ts            # NPC
│   │   │   └── Enemy.ts          # 敌人
│   │   ├── combat/
│   │   │   ├── Battle.ts         # 战斗管理
│   │   │   ├── TurnQueue.ts      # 回合队列（行动条）
│   │   │   ├── Buff.ts           # Buff/Debuff/DoT
│   │   │   ├── Skill.ts          # 主动技能
│   │   │   ├── Magic.ts          # 魔法
│   │   │   ├── Passive.ts        # 被动技能
│   │   │   └── Energy.ts         # 能量系统
│   │   ├── equipment/
│   │   │   ├── Equipment.ts      # 装备基类
│   │   │   ├── Socket.ts         # 镶孔系统
│   │   │   └── Enchant.ts        # 附魔系统
│   │   ├── editor/
│   │   │   ├── MapEditor.ts      # 地图编辑器
│   │   │   ├── DialogueEditor.ts # 剧情编辑器
│   │   │   └── AssetManager.ts   # 素材管理
│   │   └── types/
│   │       └── index.ts          # 类型定义
│   │
│   └── game/                      # 游戏集合
│       ├── rpg-demo/              # 示例游戏
│       │   ├── data/
│       │   │   ├── maps/
│       │   │   ├── sprites/
│       │   │   ├── skills/
│       │   │   ├── magics/
│       │   │   ├── passives/
│       │   │   ├── items/
│       │   │   └── dialogues/
│       │   └── index.ts
│       └── [game-name]/           # 其他游戏独立文件夹
│
└── web/
    └── templates/
        └── game.html             # 游戏页面
```

---

## 一、角色系统

### 1.1 基础属性

```typescript
interface Stats {
  hp: number;        // 生命
  maxHp: number;
  mp: number;        // 魔法值（通用）
  maxMp: number;
  atk: number;       // 攻击
  def: number;       // 防御
  spd: number;       // 速度（影响行动条累积）
  mag: number;       // 魔力
}
```

### 1.2 角色结构

```typescript
interface Character {
  id: string;
  name: string;
  level: number;
  exp: number;
  
  stats: Stats;
  
  // 能量系统（每个角色可能不同）
  energy: EnergySystem;
  
  // 技能系统
  skills: Skill[];           // 主动技能（消耗角色特有能量）
  magics: Magic[];           // 魔法（消耗通用MP）
  passives: Passive[];       // 已习得的被动技能
  equippedPassives: Passive[]; // 当前装备的被动技能
  
  // 物品
  inventory: Item[];
  equipment: EquipmentSlots;
}

interface EquipmentSlots {
  weapon?: Equipment;
  armor?: Equipment;
  helmet?: Equipment;
  accessory?: Equipment;
}
```

---

## 二、能量系统

每个角色拥有独立的能量机制，可能不同：

```typescript
interface EnergySystem {
  type: 'mp' | 'energy' | 'rage' | 'custom';
  name: string;              // 显示名称（能量/怒气/灵力...）
  current: number;
  max: number;
  
  // 回复规则
  regen: {
    perTurn: number;         // 每回合自然回复（可为负数）
    onAttack: number;        // 普攻时增加
    onHit: number;           // 被攻击时增加
    onCast: number;          // 施法时增加
    onKill: number;          // 击杀时增加
  };
}
```

**示例**：
- **魔法师**：MP系统，每回合回复少量，普攻不增加
- **战士**：怒气系统，每回合衰减，被打/打人增加，消耗释放大招
- **刺客**：能量系统，每回合回复，普攻增加，连击消耗

---

## 三、技能系统

### 3.1 主动技能

```typescript
interface Skill {
  id: string;
  name: string;
  description: string;
  
  // 消耗角色的特有能量
  cost: number;
  costType: 'energy' | 'rage' | 'custom';
  
  // 效果
  effects: SkillEffect[];
  
  // 冷却
  cooldown: number;
  currentCooldown: number;
  
  // 学习条件
  learnCondition?: Condition;
}

interface SkillEffect {
  type: 'damage' | 'heal' | 'buff' | 'debuff';
  target: 'single' | 'all' | 'self';
  value: number | string;    // 数值或公式
  element?: string;          // 火/冰/雷等
}
```

### 3.2 魔法

```typescript
interface Magic {
  id: string;
  name: string;
  description: string;
  
  // 消耗通用MP
  mpCost: number;
  
  // 效果
  effects: MagicEffect[];
  
  // 学习条件
  learnCondition?: Condition;
}
```

### 3.3 被动技能

```typescript
interface Passive {
  id: string;
  name: string;
  description: string;
  
  // 效果
  effects: PassiveEffect[];
  
  // 习得方式
  source: 'level' | 'npc' | 'item';
  unlockLevel?: number;
  npcId?: string;
  itemId?: string;
}

interface PassiveEffect {
  type: 'stat_mod' | 'trigger' | 'aura';
  // stat_mod: 属性修正
  // trigger: 触发效果（如被攻击时反击）
  // aura: 光环效果
}
```

**被动装备系统**：
- 角色习得的被动技能需要"装备"才能生效
- 装备槽位数量有限（随等级增加）
- 玩家可以自由搭配组合

---

## 四、装备系统

### 4.1 装备结构

```typescript
interface Equipment {
  id: string;
  name: string;
  description: string;
  
  // 基础信息
  type: 'weapon' | 'armor' | 'helmet' | 'accessory';
  level: number;              // 装备等级（未来可升级）
  quality: 'common' | 'uncommon' | 'rare' | 'epic' | 'legendary';
  
  // 基础属性加成
  stats: Partial<Stats>;
  
  // 特效
  effects: EquipmentEffect[];
  
  // 附带技能
  activeSkill?: Skill;        // 装备附带的主动技能
  passiveSkill?: Passive;     // 装备附带的被动技能
  
  // 镶孔
  sockets: Socket[];
  maxSockets: number;
  
  // 附魔
  enchant?: Enchant;
  
  // 升级信息（未来版本）
  upgradeLevel?: number;
  upgradeExp?: number;
}

type Quality = {
  name: string;
  color: string;
  multiplier: number;         // 属性倍率
};
```

### 4.2 镶孔系统

```typescript
interface Socket {
  type: 'gem' | 'rune';
  item?: Gem | Rune;
}

interface Gem {
  id: string;
  name: string;
  stats: Partial<Stats>;
  quality: Quality;
}

interface Rune {
  id: string;
  name: string;
  effect: RuneEffect;         // 特殊效果
}
```

### 4.3 附魔系统

```typescript
interface Enchant {
  id: string;
  name: string;
  stats: Partial<Stats>;
  effects: EquipmentEffect[];
}
```

---

## 五、地图系统

### 5.1 地图层级

```
大地图（World Map）
  └── 子地图（Area）
        └── 房间（Room）
```

- **大地图**：世界地图，视觉无缝（相机滚动），多张地图传送切换
- **子地图**：城市、村庄、迷宫等
- **房间**：建筑内部、迷宫房间

### 5.2 地图结构

```typescript
interface GameMap {
  id: string;
  name: string;
  type: 'world' | 'area' | 'room';
  
  // 尺寸
  width: number;              // 格子数
  height: number;
  tileSize: number;           // 瓦片尺寸（16px）
  
  // 多层渲染
  layers: MapLayer[];
  
  // 碰撞矩阵
  collisions: boolean[][];
  
  // 事件
  events: MapEvent[];
  
  // 传送点
  exits: Exit[];
  
  // 遇敌配置（迷宫）
  encounters?: Encounter[];
}

interface MapLayer {
  name: string;
  tiles: number[][];          // 瓦片ID矩阵
  zIndex: number;             // 渲染层级
}

interface Exit {
  x: number;
  y: number;
  targetMap: string;
  targetX: number;
  targetY: number;
  direction?: 'up' | 'down' | 'left' | 'right';
}
```

### 5.3 地图事件

```typescript
interface MapEvent {
  id: string;
  x: number;
  y: number;
  trigger: 'touch' | 'interact' | 'auto';
  conditions: Condition[];
  actions: Action[];
}

interface Action {
  type: 'dialogue' | 'teleport' | 'battle' | 'give_item' | 'set_flag' | 'play_sound';
  params: Record<string, any>;
}

interface Condition {
  type: 'flag' | 'item' | 'level' | 'quest';
  operator: 'eq' | 'gt' | 'lt' | 'has';
  value: any;
}
```

---

## 六、战斗系统

### 6.1 回合制行动条

```typescript
interface TurnQueue {
  participants: Combatant[];
  actionBarThreshold: number;  // 100
  standardSpeed: number;       // 25
}

interface Combatant {
  character: Character;
  actionBar: number;           // 0-100
  buffs: Buff[];
  isPlayer: boolean;
}

// 行动条累积公式
// 每帧: actionBar += (spd / standardSpeed) * deltaTime
// 当 actionBar >= 100 时可行动
```

**速度设计**：
- 标准速度 25，行动阈值 100
- 初期速度差异不大，不影响平衡
- 后期速度累积后，可以利用机制多行动

### 6.2 Buff/Debuff/DoT

```typescript
interface Buff {
  id: string;
  name: string;
  type: 'buff' | 'debuff' | 'dot';
  
  // 持续时间（标准回合数）
  duration: number;
  remainingDuration: number;
  
  // 效果
  effects: BuffEffect[];
  
  // 触发时机
  trigger: 'on_turn_start' | 'on_turn_end' | 'on_action' | 'on_hit' | 'custom';
}

interface BuffEffect {
  type: 'stat_mod' | 'dot' | 'shield' | 'special';
  value: number | string;
  element?: string;
}
```

**DoT 触发时机**：
- 施法者行动时触发
- 标准回合触发（全局计时器）
- 承受者行动时触发
- 条件触发（如移动、攻击）

### 6.3 战斗视角

- 我方角色在右侧
- 敌方角色在左侧
- 八方旅人风格

```typescript
interface BattleScene {
  position: {
    player: { x: number; y: number }[];   // 我方位置（右侧）
    enemy: { x: number; y: number }[];    // 敌方位置（左侧）
  };
  
  // 背景根据地图类型变化
  background: string;
}
```

---

## 七、对话剧情系统

### 7.1 对话结构

```typescript
interface Dialogue {
  id: string;
  nodes: DialogueNode[];
}

interface DialogueNode {
  id: string;
  speaker?: string;           // 说话人（null = 旁白）
  text: string;
  portrait?: string;          // 立绘
  
  // 分支选项
  choices?: DialogueChoice[];
  
  // 单线下一个节点
  next?: string;
  
  // 执行动作
  actions?: Action[];
  
  // 条件
  condition?: Condition;
}

interface DialogueChoice {
  text: string;
  next: string;
  condition?: Condition;
  actions?: Action[];
}
```

### 7.2 立绘系统

- 立绘素材在剧情编辑器中管理
- 支持多个表情/姿态
- 支持立绘位置（左/中/右）

```typescript
interface Portrait {
  id: string;
  characterId: string;
  expressions: {
    [key: string]: string;    // 表情名 -> 图片路径
  };
  position: 'left' | 'center' | 'right';
}
```

---

## 八、输入系统

### 8.1 手柄适配

支持：Xbox、PlayStation、Switch Pro 手柄

```typescript
type GamepadButton = 
  | 'A' | 'B' | 'X' | 'Y'      // 右侧四键（Xbox命名）
  | 'LB' | 'RB' | 'LT' | 'RT'  // L1 L2 R1 R2
  | 'LS' | 'RS'                // 摇杆按下
  | 'START' | 'SELECT';        // 开始/选择

type GamepadAxis = 
  | 'LEFT_X' | 'LEFT_Y'        // 左摇杆
  | 'RIGHT_X' | 'RIGHT_Y'      // 右摇杆
  | 'DPAD_X' | 'DPAD_Y';       // 十字键
```

### 8.2 键盘映射

```typescript
const defaultKeyMapping: Record<string, string> = {
  // 移动
  'DPAD_UP': 'ArrowUp',
  'DPAD_DOWN': 'ArrowDown',
  'DPAD_LEFT': 'ArrowLeft',
  'DPAD_RIGHT': 'ArrowRight',
  
  // 功能键
  'A': 'Space',           // 确认
  'B': 'Escape',          // 取消
  'X': 'KeyX',            // 交互
  'Y': 'KeyY',            // 菜单
  
  // 肩键
  'LB': 'KeyQ',
  'RB': 'KeyE',
  'LT': 'KeyW',
  'RT': 'KeyR',
  
  // 系统
  'START': 'Enter',
  'SELECT': 'Tab',
  
  // 摇杆按下
  'LS': 'KeyZ',
  'RS': 'KeyC',
};
```

### 8.3 输入管理器

```typescript
class InputManager {
  private gamepad: Gamepad | null;
  private keyMapping: Record<string, string>;
  
  // 获取输入状态
  getButton(button: GamepadButton): boolean;
  getAxis(axis: GamepadAxis): number;
  
  // 检测手柄连接
  onGamepadConnected(callback: () => void);
  onGamepadDisconnected(callback: () => void);
}
```

---

## 九、编辑器系统

### 9.1 地图编辑器

```
┌─────────────────────────────────────────────┐
│  素材面板  │      地图画布      │  属性面板  │
│           │                   │           │
│  [瓦片列表] │  [网格编辑区]      │  [选中格子] │
│  [事件列表] │                   │  [事件配置] │
│           │                   │           │
└─────────────────────────────────────────────┘
```

**功能**：
1. 瓦片绘制（选择素材 → 点击放置）
2. 多层编辑（地面、建筑、装饰）
3. 碰撞编辑（标记不可通行格子）
4. 事件编辑（触发器 + 动作）
5. 传送点配置
6. 导入/导出 JSON

### 9.2 剧情编辑器

可视化节点编辑器，类似流程图：

```
[node1] → [node2] → [node3]
              ↓
           [node4] → [node5]
```

**功能**：
1. 节点创建/删除/连接
2. 对话文本编辑
3. 立绘选择和位置
4. 条件分支配置
5. 动作配置
6. 素材管理（立绘、背景）

### 9.3 素材管理器

```typescript
interface AssetManager {
  // 瓦片素材
  tiles: Map<string, TileSet>;
  
  // 精灵素材
  sprites: Map<string, SpriteSheet>;
  
  // 立绘素材
  portraits: Map<string, Portrait>;
  
  // 音效素材
  sounds: Map<string, Sound>;
  
  // 背景音乐
  bgms: Map<string, BGM>;
}
```

---

## 十、全局变量系统

用于控制剧情进度、地图状态、NPC状态等：

```typescript
interface GlobalState {
  // 剧情进度
  storyProgress: number;
  
  // 地图开放状态
  unlockedMaps: string[];
  
  // NPC 状态
  npcStates: Record<string, NPCState>;
  
  // 自定义标志
  flags: Record<string, boolean>;
  
  // 数值变量
  variables: Record<string, number>;
  
  // 字符串变量
  strings: Record<string, string>;
}
```

---

## 开发计划

### Phase 1: 引擎核心 ✅
- [x] 类型定义
- [x] 游戏主循环（Game.ts）
- [x] 输入系统（Input.ts）
- [x] 地图渲染（Map.ts）
- [x] 相机系统（Camera.ts）
- [x] 精灵系统（Sprite.ts）
- [x] 示例游戏（rpg-demo）

### Phase 2: 地图编辑器
- [ ] 素材管理
- [ ] 瓦片绘制
- [ ] 碰撞编辑
- [ ] 事件系统
- [ ] 导入/导出

### Phase 3: 角色系统
- [ ] 角色基类
- [ ] 玩家控制
- [ ] NPC 行为
- [ ] 敌人 AI

### Phase 4: 战斗系统
- [ ] 回合队列
- [ ] 行动条
- [ ] 技能系统
- [ ] Buff 系统
- [ ] 战斗 UI

### Phase 5: 剧情系统
- [ ] 对话系统
- [ ] 剧情编辑器
- [ ] 立绘系统
- [ ] 分支剧情

### Phase 6: 装备系统
- [ ] 装备基础
- [ ] 镶孔系统
- [ ] 附魔系统
- [ ] 装备升级

---

## 技术栈

- **语言**: TypeScript
- **渲染**: Canvas 2D
- **打包**: Vite
- **样式**: 原生 CSS（编辑器 UI）

---

*文档创建时间: 2026-05-26*
*最后更新: 2026-05-26*

---

## 开发进度记录

**2026-05-26 - Phase 1 引擎核心完成 + 编辑器完成 ✅**

**已完成模块**:
| 模块 | 文件 | 功能 |
|------|------|------|
| 类型定义 | `types/index.ts` | 角色、技能、装备、地图、战斗等完整类型 |
| 输入系统 | `engine/Input.ts` | 手柄+键盘支持，可配置映射 |
| 相机系统 | `engine/Camera.ts` | 视口管理、平滑跟随、边界限制 |
| 精灵系统 | `engine/Sprite.ts` | 动画播放、方向动画、像素生成器 |
| 地图渲染 | `engine/Map.ts` | 瓦片地图、碰撞检测、事件触发、传送点 |
| 游戏主循环 | `engine/Game.ts` | 场景切换、玩家移动、事件系统 |

**编辑器**:
| 编辑器 | 文件 | 功能 |
|--------|------|------|
| 地图编辑器 | `web/templates/editor.html` | 瓦片绘制、碰撞、事件、传送点、JSON导入导出 |
| 剧情编辑器 | `web/templates/editor.html` | 节点编辑、对话配置、分支选项 |

**示例游戏**:
- 位置: `src/game/rpg-demo/`
- 访问: http://127.0.0.1:8080/rpg
- 操作: 方向键移动，Space 确认/交互，Esc 取消

**目录结构**:
```
salsaAuto/
├── src/
│   ├── gamemark/              # 游戏引擎（通用）
│   │   ├── engine/           # 核心引擎
│   │   │   ├── Game.ts
│   │   │   ├── Input.ts
│   │   │   ├── Camera.ts
│   │   │   ├── Map.ts
│   │   │   └── Sprite.ts
│   │   ├── types/            # 类型定义
│   │   └── index.ts
│   │
│   └── game/                 # 游戏集合
│       └── rpg-demo/          # 示例游戏
│           └── index.ts
│
├── web/
│   ├── templates/game.html   # 游戏页面
│   └── static/game/           # 构建输出
│
├── docs/RPG-ENGINE-DESIGN.md # 引擎设计文档
├── vite.config.ts
├── tsconfig.json
└── package.json
```

**开发命令**:
```bash
# 构建游戏
npm run build

# 运行服务
python -m src web

# 访问
http://127.0.0.1:8080/moyu      # 摸鱼入口
http://127.0.0.1:8080/editor    # 游戏编辑器
http://127.0.0.1:8080/rpg       # RPG Demo
```
