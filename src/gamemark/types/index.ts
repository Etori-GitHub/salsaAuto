/**
 * GameMark 引擎类型定义
 */

// ========== 基础类型 ==========

export type Direction = 'up' | 'down' | 'left' | 'right';

export type MapType = 'world' | 'area' | 'room';

export type Quality = 'common' | 'uncommon' | 'rare' | 'epic' | 'legendary';

export type ElementType = 'physical' | 'fire' | 'ice' | 'lightning' | 'earth' | 'light' | 'dark';

// ========== 属性系统 ==========

export interface Stats {
  hp: number;
  maxHp: number;
  mp: number;
  maxMp: number;
  atk: number;
  def: number;
  spd: number;
  mag: number;
}

export type PartialStats = Partial<Stats>;

// ========== 能量系统 ==========

export interface EnergySystem {
  type: 'mp' | 'energy' | 'rage' | 'custom';
  name: string;
  current: number;
  max: number;
  regen: EnergyRegen;
}

export interface EnergyRegen {
  perTurn: number;
  onAttack: number;
  onHit: number;
  onCast: number;
  onKill: number;
}

// ========== 角色 ==========

export interface Character {
  id: string;
  name: string;
  level: number;
  exp: number;
  stats: Stats;
  energy: EnergySystem;
  skills: Skill[];
  magics: Magic[];
  passives: Passive[];
  equippedPassives: Passive[];
  inventory: Item[];
  equipment: EquipmentSlots;
}

export interface EquipmentSlots {
  weapon?: Equipment;
  armor?: Equipment;
  helmet?: Equipment;
  accessory?: Equipment;
}

// ========== 技能系统 ==========

export interface Skill {
  id: string;
  name: string;
  description: string;
  cost: number;
  costType: 'energy' | 'rage' | 'custom';
  effects: SkillEffect[];
  cooldown: number;
  currentCooldown: number;
  learnCondition?: Condition;
}

export interface SkillEffect {
  type: 'damage' | 'heal' | 'buff' | 'debuff';
  target: 'single' | 'all' | 'self';
  value: number | string;
  element?: ElementType;
}

export interface Magic {
  id: string;
  name: string;
  description: string;
  mpCost: number;
  effects: MagicEffect[];
  learnCondition?: Condition;
}

export interface MagicEffect {
  type: 'damage' | 'heal' | 'buff' | 'debuff' | 'dot';
  target: 'single' | 'all' | 'self';
  value: number | string;
  element?: ElementType;
  duration?: number;
}

export interface Passive {
  id: string;
  name: string;
  description: string;
  effects: PassiveEffect[];
  source: 'level' | 'npc' | 'item';
  unlockLevel?: number;
  npcId?: string;
  itemId?: string;
}

export interface PassiveEffect {
  type: 'stat_mod' | 'trigger' | 'aura';
  statMod?: PartialStats;
  trigger?: TriggerEffect;
  aura?: AuraEffect;
}

export interface TriggerEffect {
  event: 'on_attack' | 'on_hit' | 'on_kill' | 'on_turn_start' | 'on_turn_end';
  action: SkillEffect;
}

export interface AuraEffect {
  range: number;
  effect: SkillEffect;
  targetFilter?: 'all' | 'party' | 'enemy';
}

// ========== 装备系统 ==========

export interface Equipment {
  id: string;
  name: string;
  description: string;
  type: 'weapon' | 'armor' | 'helmet' | 'accessory';
  level: number;
  quality: Quality;
  stats: PartialStats;
  effects: EquipmentEffect[];
  activeSkill?: Skill;
  passiveSkill?: Passive;
  sockets: Socket[];
  maxSockets: number;
  enchant?: Enchant;
  upgradeLevel?: number;
  upgradeExp?: number;
}

export interface EquipmentEffect {
  type: 'stat_bonus' | 'trigger' | 'special';
  value: number | string;
  condition?: Condition;
}

export interface Socket {
  type: 'gem' | 'rune';
  item?: Gem | Rune;
}

export interface Gem {
  id: string;
  name: string;
  stats: PartialStats;
  quality: Quality;
}

export interface Rune {
  id: string;
  name: string;
  effect: RuneEffect;
}

export interface RuneEffect {
  type: 'stat_mod' | 'trigger' | 'special';
  value: number | string;
}

export interface Enchant {
  id: string;
  name: string;
  stats: PartialStats;
  effects: EquipmentEffect[];
}

// ========== 物品 ==========

export interface Item {
  id: string;
  name: string;
  description: string;
  type: 'consumable' | 'material' | 'key';
  effects?: ItemEffect[];
  stackable: boolean;
  quantity: number;
}

export interface ItemEffect {
  type: 'heal' | 'restore' | 'buff' | 'give_item' | 'teleport';
  value: number | string;
  target?: 'hp' | 'mp' | 'energy';
}

// ========== 地图系统 ==========

export interface GameMap {
  id: string;
  name: string;
  type: MapType;
  width: number;
  height: number;
  tileSize: number;
  layers: MapLayer[];
  collisions: boolean[][];
  events: MapEvent[];
  exits: Exit[];
  encounters?: Encounter[];
  background?: string;
}

export interface MapLayer {
  name: string;
  tiles: number[][];
  zIndex: number;
}

export interface Exit {
  x: number;
  y: number;
  targetMap: string;
  targetX: number;
  targetY: number;
  direction?: Direction;
}

export interface MapEvent {
  id: string;
  x: number;
  y: number;
  trigger: 'touch' | 'interact' | 'auto';
  conditions: Condition[];
  actions: Action[];
}

export interface Encounter {
  enemies: string[];
  rate: number;
}

// ========== 条件与动作 ==========

export interface Condition {
  type: 'flag' | 'item' | 'level' | 'quest' | 'variable';
  key: string;
  operator: 'eq' | 'gt' | 'lt' | 'gte' | 'lte' | 'has' | 'not_has';
  value: any;
}

export interface Action {
  type: 'dialogue' | 'teleport' | 'battle' | 'give_item' | 'take_item' | 'set_flag' | 'set_variable' | 'play_sound' | 'show_message' | 'wait';
  params: ActionParams;
}

export type ActionParams = {
  dialogueId?: string;
  targetMap?: string;
  targetX?: number;
  targetY?: number;
  enemies?: string[];
  itemId?: string;
  quantity?: number;
  flagKey?: string;
  flagValue?: boolean;
  variableKey?: string;
  variableValue?: number;
  soundId?: string;
  message?: string;
  duration?: number;
};

// ========== 对话系统 ==========

export interface Dialogue {
  id: string;
  nodes: DialogueNode[];
}

export interface DialogueNode {
  id: string;
  speaker?: string;
  text: string;
  portrait?: PortraitConfig;
  choices?: DialogueChoice[];
  next?: string;
  actions?: Action[];
  condition?: Condition;
}

export interface DialogueChoice {
  text: string;
  next: string;
  condition?: Condition;
  actions?: Action[];
}

export interface PortraitConfig {
  characterId: string;
  expression: string;
  position: 'left' | 'center' | 'right';
}

export interface Portrait {
  id: string;
  characterId: string;
  expressions: Record<string, string>;
}

// ========== 战斗系统 ==========

export interface Combatant {
  character: Character;
  actionBar: number;
  buffs: Buff[];
  isPlayer: boolean;
  position: { x: number; y: number };
}

export interface Buff {
  id: string;
  name: string;
  type: 'buff' | 'debuff' | 'dot';
  duration: number;
  remainingDuration: number;
  effects: BuffEffect[];
  trigger: BuffTrigger;
  sourceId?: string;
}

export interface BuffEffect {
  type: 'stat_mod' | 'dot' | 'shield' | 'special';
  statMod?: PartialStats;
  dotValue?: number;
  dotElement?: ElementType;
  shieldValue?: number;
  special?: string;
}

export type BuffTrigger = 'on_turn_start' | 'on_turn_end' | 'on_action' | 'on_hit' | 'standard_tick' | 'custom';

export interface BattleState {
  participants: Combatant[];
  turnQueue: Combatant[];
  currentTurn: Combatant | null;
  actionBarThreshold: number;
  standardSpeed: number;
  standardTickCount: number;
  background: string;
  isOver: boolean;
  result?: 'win' | 'lose' | 'flee';
}

// ========== 输入系统 ==========

export type GamepadButton = 
  | 'A' | 'B' | 'X' | 'Y'
  | 'LB' | 'RB' | 'LT' | 'RT'
  | 'LS' | 'RS'
  | 'START' | 'SELECT';

export type GamepadAxis = 
  | 'LEFT_X' | 'LEFT_Y'
  | 'RIGHT_X' | 'RIGHT_Y'
  | 'DPAD_X' | 'DPAD_Y';

export interface InputState {
  buttons: Record<GamepadButton, boolean>;
  axes: Record<GamepadAxis, number>;
  justPressed: GamepadButton[];
  justReleased: GamepadButton[];
}

export interface KeyMapping {
  button: GamepadButton;
  key: string;
}

// ========== 全局状态 ==========

export interface GlobalState {
  storyProgress: number;
  unlockedMaps: string[];
  npcStates: Record<string, NPCState>;
  flags: Record<string, boolean>;
  variables: Record<string, number>;
  strings: Record<string, string>;
}

export interface NPCState {
  visible: boolean;
  position?: { x: number; y: number };
  dialogueId?: string;
}

// ========== 渲染相关 ==========

export interface SpriteFrame {
  x: number;
  y: number;
  width: number;
  height: number;
}

export interface SpriteAnimation {
  name: string;
  frames: SpriteFrame[];
  frameDuration: number;
  loop: boolean;
}

export interface SpriteSheet {
  id: string;
  image: string;
  frameWidth: number;
  frameHeight: number;
  animations: Record<string, SpriteAnimation>;
}

export interface TileSet {
  id: string;
  image: string;
  tileWidth: number;
  tileHeight: number;
  columns: number;
  tiles: TileInfo[];
}

export interface TileInfo {
  id: number;
  collision?: boolean;
  animated?: boolean;
  frames?: number[];
}

// ========== 游戏配置 ==========

export interface GameConfig {
  title: string;
  canvas: HTMLCanvasElement;
  tileSize: number;
  fps: number;
  debug: boolean;
  initialMap: string;
  initialX: number;
  initialY: number;
}

// ========== 引擎事件 ==========

export type GameEventType = 
  | 'map_loaded'
  | 'map_changed'
  | 'battle_start'
  | 'battle_end'
  | 'dialogue_start'
  | 'dialogue_end'
  | 'item_pickup'
  | 'level_up'
  | 'game_saved'
  | 'game_loaded';

export interface GameEvent {
  type: GameEventType;
  data?: any;
}

export type EventCallback = (event: GameEvent) => void;