/**
 * 游戏主循环 - 核心引擎
 */

import { 
  GameConfig, 
  GameMap, 
  GameEvent, 
  GameEventType, 
  EventCallback,
  Character,
  GlobalState,
} from '../types';
import { InputManager } from './Input';
import { Camera } from './Camera';
import { MapRenderer, MapGenerator } from './Map';
import { Sprite, SpriteManager, PixelSpriteGenerator } from './Sprite';

export type GameScene = 'map' | 'battle' | 'dialogue' | 'menu';

export interface GameState {
  scene: GameScene;
  paused: boolean;
  debug: boolean;
  globalState: GlobalState;
}

export class Game {
  // 配置
  private config: GameConfig;
  
  // 画布
  private canvas: HTMLCanvasElement;
  private ctx: CanvasRenderingContext2D;
  
  // 核心
  private input: InputManager;
  private camera: Camera;
  private mapRenderer: MapRenderer;
  private spriteManager: SpriteManager;
  
  // 玩家
  private playerSprite: Sprite | null = null;
  private playerTileX: number = 0;
  private playerTileY: number = 0;
  private playerMoving: boolean = false;
  private playerMoveProgress: number = 0;
  private playerTargetX: number = 0;
  private playerTargetY: number = 0;
  private moveSpeed: number = 0.15;  // 移动一格所需时间（秒）
  
  // 状态
  private state: GameState;
  private running: boolean = false;
  private lastTime: number = 0;
  private deltaTime: number = 0;
  private fps: number = 0;
  private fpsCounter: number = 0;
  private fpsTime: number = 0;
  
  // 地图
  private maps: Map<string, GameMap> = new Map();
  private currentMapId: string = '';
  
  // 事件系统
  private eventListeners: Map<GameEventType, EventCallback[]> = new Map();
  
  // 当前对话/消息
  private currentMessage: string | null = null;
  private messageTimeout: number = 0;
  
  constructor(config: GameConfig) {
    this.config = config;
    this.canvas = config.canvas;
    this.ctx = this.canvas.getContext('2d')!;
    
    // 初始化核心组件
    this.input = new InputManager();
    this.camera = new Camera({
      viewportWidth: this.canvas.width,
      viewportHeight: this.canvas.height,
      smoothing: 0.1,
    });
    this.mapRenderer = new MapRenderer(this.canvas);
    this.spriteManager = new SpriteManager();
    
    // 初始化状态
    this.state = {
      scene: 'map',
      paused: false,
      debug: config.debug,
      globalState: {
        storyProgress: 0,
        unlockedMaps: [],
        npcStates: {},
        flags: {},
        variables: {},
        strings: {},
      },
    };
    
    // 初始位置
    this.playerTileX = config.initialX;
    this.playerTileY = config.initialY;
    this.currentMapId = config.initialMap;
    
    // 设置键盘事件
    this.setupKeyboardEvents();
  }
  
  // ========== 初始化 ==========
  
  async init(): Promise<void> {
    console.log(`[Game] Initializing: ${this.config.title}`);
    
    // 生成测试精灵
    const playerSheet = PixelSpriteGenerator.generateDirectionSheet('#4A90D9', 16);
    await this.spriteManager.preload([playerSheet]);
    
    // 创建玩家精灵
    this.playerSprite = this.spriteManager.get(playerSheet.id);
    if (this.playerSprite) {
      this.playerSprite.play('idle_down');
    }
    
    // 生成测试地图
    const testMap = MapGenerator.createTestMap();
    this.maps.set(testMap.id, testMap);
    
    // 加载初始地图
    await this.loadMap(this.currentMapId);
    
    // 设置玩家初始位置
    this.updatePlayerPosition();
    
    console.log('[Game] Initialized');
  }
  
  private setupKeyboardEvents(): void {
    window.addEventListener('keydown', (e) => {
      this.input.handleKeyDown(e.code);
      
      // 阻止默认行为
      if (['ArrowUp', 'ArrowDown', 'ArrowLeft', 'ArrowRight', 'Space'].includes(e.code)) {
        e.preventDefault();
      }
    });
    
    window.addEventListener('keyup', (e) => {
      this.input.handleKeyUp(e.code);
    });
  }
  
  // ========== 地图管理 ==========
  
  async loadMap(mapId: string): Promise<void> {
    const map = this.maps.get(mapId);
    if (!map) {
      console.error(`[Game] Map not found: ${mapId}`);
      return;
    }
    
    await this.mapRenderer.loadMap(map);
    this.currentMapId = mapId;
    
    // 设置相机边界
    const mapSize = this.mapRenderer.getMapSize();
    this.camera.setBounds(mapSize.width, mapSize.height);
    
    // 生成瓦片占位符纹理
    await this.generatePlaceholderTiles(map);
    
    this.emit({ type: 'map_loaded', data: { mapId } });
    console.log(`[Game] Map loaded: ${mapId}`);
  }
  
  private async generatePlaceholderTiles(map: GameMap): Promise<void> {
    // 为测试生成简单的瓦片纹理
    const tileSize = map.tileSize;
    const colors = ['#4a5568', '#718096', '#48bb78', '#ed8936'];
    
    const canvas = document.createElement('canvas');
    canvas.width = tileSize * 4;
    canvas.height = tileSize;
    const ctx = canvas.getContext('2d')!;
    
    for (let i = 0; i < 4; i++) {
      const x = i * tileSize;
      
      // 绘制瓦片
      ctx.fillStyle = colors[i];
      ctx.fillRect(x, 0, tileSize, tileSize);
      
      // 添加边框
      ctx.strokeStyle = 'rgba(0,0,0,0.3)';
      ctx.strokeRect(x + 0.5, 0.5, tileSize - 1, tileSize - 1);
      
      // 添加纹理效果
      if (i === 0) {
        // 地面：点状纹理
        ctx.fillStyle = 'rgba(255,255,255,0.1)';
        for (let py = 2; py < tileSize; py += 4) {
          for (let px = 2; px < tileSize; px += 4) {
            ctx.fillRect(x + px, py, 1, 1);
          }
        }
      } else if (i === 1) {
        // 砖块纹理
        ctx.strokeStyle = 'rgba(0,0,0,0.2)';
        for (let py = 0; py < tileSize; py += 4) {
          ctx.beginPath();
          ctx.moveTo(x, py);
          ctx.lineTo(x + tileSize, py);
          ctx.stroke();
        }
      }
    }
    
    // 加载为瓦片集
    await this.mapRenderer.loadTileSet({
      id: 'placeholder',
      image: canvas.toDataURL(),
      tileWidth: tileSize,
      tileHeight: tileSize,
      columns: 4,
      tiles: [
        { id: 1 }, // 地面
        { id: 2, collision: true }, // 墙
        { id: 3, collision: true }, // 障碍物
        { id: 4 }, // 装饰
      ],
    });
  }
  
  // ========== 主循环 ==========
  
  start(): void {
    if (this.running) return;
    
    this.running = true;
    this.lastTime = performance.now();
    
    console.log('[Game] Starting game loop');
    requestAnimationFrame(this.loop.bind(this));
  }
  
  stop(): void {
    this.running = false;
    console.log('[Game] Stopped');
  }
  
  private loop(currentTime: number): void {
    if (!this.running) return;
    
    // 计算 deltaTime
    this.deltaTime = (currentTime - this.lastTime) / 1000;
    this.lastTime = currentTime;
    
    // 限制 deltaTime（防止标签页切换后的大跳跃）
    if (this.deltaTime > 0.1) this.deltaTime = 0.1;
    
    // FPS 计算
    this.fpsCounter++;
    this.fpsTime += this.deltaTime;
    if (this.fpsTime >= 1) {
      this.fps = this.fpsCounter;
      this.fpsCounter = 0;
      this.fpsTime = 0;
    }
    
    // 更新
    if (!this.state.paused) {
      this.update(this.deltaTime);
    }
    
    // 渲染
    this.render();
    
    // 继续循环
    requestAnimationFrame(this.loop.bind(this));
  }
  
  // ========== 更新 ==========
  
  private update(dt: number): void {
    // 更新输入
    this.input.update();
    
    // 根据场景更新
    switch (this.state.scene) {
      case 'map':
        this.updateMapScene(dt);
        break;
      case 'dialogue':
        this.updateDialogueScene(dt);
        break;
      case 'battle':
        this.updateBattleScene(dt);
        break;
      case 'menu':
        this.updateMenuScene(dt);
        break;
    }
    
    // 更新相机
    this.camera.update(dt);
    
    // 更新精灵动画
    if (this.playerSprite) {
      this.playerSprite.update(dt);
    }
    
    // 更新消息
    if (this.currentMessage) {
      this.messageTimeout -= dt;
      if (this.messageTimeout <= 0) {
        this.currentMessage = null;
      }
    }
  }
  
  private updateMapScene(dt: number): void {
    // 玩家移动
    if (this.playerMoving) {
      this.updatePlayerMovement(dt);
    } else {
      // 检查输入
      this.handleMovementInput();
      this.handleInteractionInput();
    }
  }
  
  private handleMovementInput(): void {
    const direction = this.input.getMovementDirection();
    if (!direction) return;
    
    let dx = 0, dy = 0;
    switch (direction) {
      case 'up': dy = -1; break;
      case 'down': dy = 1; break;
      case 'left': dx = -1; break;
      case 'right': dx = 1; break;
    }
    
    const targetX = this.playerTileX + dx;
    const targetY = this.playerTileY + dy;
    
    // 检查碰撞
    if (this.mapRenderer.isTileCollidable(targetX, targetY)) {
      // 更新方向但不移动
      if (this.playerSprite) {
        this.playerSprite.playDirection('idle', direction);
      }
      return;
    }
    
    // 开始移动
    this.playerMoving = true;
    this.playerMoveProgress = 0;
    this.playerTargetX = targetX;
    this.playerTargetY = targetY;
    
    // 更新精灵动画
    if (this.playerSprite) {
      this.playerSprite.playDirection('walk', direction);
    }
  }
  
  private updatePlayerMovement(dt: number): void {
    this.playerMoveProgress += dt / this.moveSpeed;
    
    if (this.playerMoveProgress >= 1) {
      // 移动完成
      this.playerTileX = this.playerTargetX;
      this.playerTileY = this.playerTargetY;
      this.playerMoving = false;
      this.playerMoveProgress = 0;
      
      // 更新精灵位置
      this.updatePlayerPosition();
      
      // 检查传送点
      this.checkExit();
      
      // 检查事件
      this.checkTouchEvent();
    } else {
      // 插值位置
      this.updatePlayerPosition();
    }
  }
  
  private updatePlayerPosition(): void {
    if (!this.playerSprite || !this.mapRenderer.currentMap) return;
    
    const tileSize = this.mapRenderer.getTileSize();
    
    let x = this.playerTileX;
    let y = this.playerTileY;
    
    if (this.playerMoving) {
      // 插值
      x = this.playerTileX + (this.playerTargetX - this.playerTileX) * this.playerMoveProgress;
      y = this.playerTileY + (this.playerTargetY - this.playerTileY) * this.playerMoveProgress;
    }
    
    // 设置精灵位置（格子中心）
    this.playerSprite.x = x * tileSize;
    this.playerSprite.y = y * tileSize;
    
    // 更新相机跟随
    this.camera.follow({
      x: x * tileSize + tileSize / 2,
      y: y * tileSize + tileSize / 2,
    });
  }
  
  private handleInteractionInput(): void {
    if (this.input.isJustPressed('A')) {
      // 检查面前的交互事件
      const direction = this.playerSprite?.direction || 'down';
      let checkX = this.playerTileX;
      let checkY = this.playerTileY;
      
      switch (direction) {
        case 'up': checkY--; break;
        case 'down': checkY++; break;
        case 'left': checkX--; break;
        case 'right': checkX++; break;
      }
      
      const event = this.mapRenderer.getEventAtTile(checkX, checkY);
      if (event && event.trigger === 'interact') {
        this.triggerEvent(event);
      }
    }
  }
  
  private checkExit(): void {
    const exit = this.mapRenderer.getExitAtTile(this.playerTileX, this.playerTileY);
    if (exit) {
      this.teleport(exit.targetMap, exit.targetX, exit.targetY);
    }
  }
  
  private checkTouchEvent(): void {
    const event = this.mapRenderer.getEventAtTile(this.playerTileX, this.playerTileY);
    if (event && event.trigger === 'touch') {
      this.triggerEvent(event);
    }
  }
  
  private triggerEvent(event: any): void {
    console.log(`[Game] Event triggered: ${event.id}`);
    
    for (const action of event.actions) {
      switch (action.type) {
        case 'show_message':
          this.currentMessage = action.params.message;
          this.messageTimeout = 3;
          break;
        case 'teleport':
          this.teleport(
            action.params.targetMap,
            action.params.targetX,
            action.params.targetY
          );
          break;
        // 其他动作类型...
      }
    }
  }
  
  // ========== 场景更新 ==========
  
  private updateDialogueScene(dt: number): void {
    // 对话场景更新
    if (this.input.isJustPressed('A') || this.input.isJustPressed('B')) {
      this.state.scene = 'map';
    }
  }
  
  private updateBattleScene(dt: number): void {
    // 战斗场景更新
  }
  
  private updateMenuScene(dt: number): void {
    // 菜单场景更新
    if (this.input.isJustPressed('B') || this.input.isJustPressed('START')) {
      this.state.scene = 'map';
    }
  }
  
  // ========== 渲染 ==========
  
  private render(): void {
    // 清空画布
    this.ctx.fillStyle = '#1a1a2e';
    this.ctx.fillRect(0, 0, this.canvas.width, this.canvas.height);
    
    // 根据场景渲染
    switch (this.state.scene) {
      case 'map':
        this.renderMapScene();
        break;
      case 'dialogue':
        this.renderDialogueScene();
        break;
      case 'battle':
        this.renderBattleScene();
        break;
      case 'menu':
        this.renderMenuScene();
        break;
    }
    
    // 渲染消息
    this.renderMessage();
    
    // 渲染调试信息
    if (this.state.debug) {
      this.renderDebug();
    }
  }
  
  private renderMapScene(): void {
    // 渲染地图
    this.mapRenderer.render(this.camera);
    
    // 渲染玩家
    if (this.playerSprite) {
      this.playerSprite.render(this.ctx, this.camera.x, this.camera.y);
    }
    
    // 调试渲染
    if (this.state.debug) {
      this.mapRenderer.renderDebug(this.camera);
    }
  }
  
  private renderDialogueScene(): void {
    // 先渲染地图背景
    this.renderMapScene();
    
    // 渲染对话框
    const boxHeight = 120;
    const boxY = this.canvas.height - boxHeight - 20;
    
    this.ctx.fillStyle = 'rgba(0, 0, 0, 0.8)';
    this.ctx.fillRect(20, boxY, this.canvas.width - 40, boxHeight);
    
    this.ctx.strokeStyle = '#fff';
    this.ctx.lineWidth = 2;
    this.ctx.strokeRect(20, boxY, this.canvas.width - 40, boxHeight);
  }
  
  private renderBattleScene(): void {
    // 战斗场景渲染
    this.ctx.fillStyle = '#2d3748';
    this.ctx.fillRect(0, 0, this.canvas.width, this.canvas.height);
    
    // 战斗 UI 占位
    this.ctx.fillStyle = '#fff';
    this.ctx.font = '24px sans-serif';
    this.ctx.textAlign = 'center';
    this.ctx.fillText('战斗场景', this.canvas.width / 2, this.canvas.height / 2);
  }
  
  private renderMenuScene(): void {
    // 先渲染地图背景（变暗）
    this.renderMapScene();
    
    // 渲染菜单
    this.ctx.fillStyle = 'rgba(0, 0, 0, 0.5)';
    this.ctx.fillRect(0, 0, this.canvas.width, this.canvas.height);
    
    const menuWidth = 200;
    const menuHeight = 300;
    const menuX = this.canvas.width - menuWidth - 20;
    const menuY = 20;
    
    this.ctx.fillStyle = 'rgba(0, 0, 0, 0.9)';
    this.ctx.fillRect(menuX, menuY, menuWidth, menuHeight);
    
    this.ctx.strokeStyle = '#fff';
    this.ctx.lineWidth = 2;
    this.ctx.strokeRect(menuX, menuY, menuWidth, menuHeight);
    
    // 菜单项
    const items = ['状态', '装备', '技能', '道具', '设置'];
    this.ctx.fillStyle = '#fff';
    this.ctx.font = '16px sans-serif';
    this.ctx.textAlign = 'left';
    
    items.forEach((item, i) => {
      this.ctx.fillText(item, menuX + 20, menuY + 40 + i * 40);
    });
  }
  
  private renderMessage(): void {
    if (!this.currentMessage) return;
    
    const boxHeight = 80;
    const boxY = this.canvas.height - boxHeight - 20;
    
    this.ctx.fillStyle = 'rgba(0, 0, 0, 0.8)';
    this.ctx.fillRect(20, boxY, this.canvas.width - 40, boxHeight);
    
    this.ctx.strokeStyle = '#4A90D9';
    this.ctx.lineWidth = 2;
    this.ctx.strokeRect(20, boxY, this.canvas.width - 40, boxHeight);
    
    this.ctx.fillStyle = '#fff';
    this.ctx.font = '16px sans-serif';
    this.ctx.textAlign = 'left';
    this.ctx.fillText(this.currentMessage, 40, boxY + 45);
  }
  
  private renderDebug(): void {
    this.ctx.fillStyle = 'rgba(0, 0, 0, 0.7)';
    this.ctx.fillRect(5, 5, 150, 80);
    
    this.ctx.fillStyle = '#0f0';
    this.ctx.font = '12px monospace';
    this.ctx.textAlign = 'left';
    
    const lines = [
      `FPS: ${this.fps}`,
      `Map: ${this.currentMapId}`,
      `Pos: ${this.playerTileX}, ${this.playerTileY}`,
      `Scene: ${this.state.scene}`,
    ];
    
    lines.forEach((line, i) => {
      this.ctx.fillText(line, 10, 20 + i * 16);
    });
  }
  
  // ========== 公共方法 ==========
  
  teleport(mapId: string, x: number, y: number): void {
    if (mapId !== this.currentMapId) {
      this.loadMap(mapId).then(() => {
        this.setPlayerPosition(x, y);
      });
    } else {
      this.setPlayerPosition(x, y);
    }
  }
  
  setPlayerPosition(x: number, y: number): void {
    this.playerTileX = x;
    this.playerTileY = y;
    this.playerMoving = false;
    this.updatePlayerPosition();
    
    // 立即更新相机位置
    const tileSize = this.mapRenderer.getTileSize();
    this.camera.setPosition(
      x * tileSize - this.canvas.width / 2 + tileSize / 2,
      y * tileSize - this.canvas.height / 2 + tileSize / 2,
      true
    );
  }
  
  pause(): void {
    this.state.paused = true;
  }
  
  resume(): void {
    this.state.paused = false;
  }
  
  toggleDebug(): void {
    this.state.debug = !this.state.debug;
  }
  
  // ========== 事件系统 ==========
  
  on(eventType: GameEventType, callback: EventCallback): void {
    const listeners = this.eventListeners.get(eventType) || [];
    listeners.push(callback);
    this.eventListeners.set(eventType, listeners);
  }
  
  off(eventType: GameEventType, callback: EventCallback): void {
    const listeners = this.eventListeners.get(eventType);
    if (listeners) {
      const index = listeners.indexOf(callback);
      if (index >= 0) listeners.splice(index, 1);
    }
  }
  
  private emit(event: GameEvent): void {
    const listeners = this.eventListeners.get(event.type);
    if (listeners) {
      listeners.forEach(cb => cb(event));
    }
  }
  
  // ========== 获取器 ==========
  
  getState(): GameState {
    return { ...this.state };
  }
  
  getInput(): InputManager {
    return this.input;
  }
  
  getCamera(): Camera {
    return this.camera;
  }
}