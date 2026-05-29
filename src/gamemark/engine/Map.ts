/**
 * 地图系统 - 瓦片地图渲染和管理
 */

import { GameMap, MapLayer, MapEvent, Exit, TileSet } from '../types';
import { Camera } from './Camera';

export class MapRenderer {
  private canvas: HTMLCanvasElement;
  private ctx: CanvasRenderingContext2D;
  
  // 当前地图
  currentMap: GameMap | null = null;
  
  // 瓦片集
  private tileSets: Map<string, TileSet> = new Map();
  private tileImages: Map<string, HTMLImageElement> = new Map();
  
  // 碰撞层（用于快速查询）
  private collisionGrid: boolean[][] = [];
  
  // 事件层
  private eventGrid: Map<string, MapEvent> = new Map();
  
  // 传送点
  private exitGrid: Map<string, Exit> = new Map();
  
  // 渲染层缓存
  private layerCanvases: Map<string, HTMLCanvasElement> = new Map();
  
  constructor(canvas: HTMLCanvasElement) {
    this.canvas = canvas;
    this.ctx = canvas.getContext('2d')!;
  }
  
  // ========== 加载地图 ==========
  
  async loadMap(map: GameMap): Promise<void> {
    this.currentMap = map;
    
    // 预加载瓦片集
    const loadImagePromises: Promise<void>[] = [];
    
    // 检查是否有 tileset 需要加载
    for (const _layer of map.layers) {
      // 这里简化处理，假设所有瓦片都来自同一个 tileset
      // 实际实现可以根据瓦片 ID 区分不同的 tileset
    }
    
    await Promise.all(loadImagePromises);
    
    // 初始化碰撞网格
    this.collisionGrid = map.collisions.map(row => [...row]);
    
    // 初始化事件网格
    this.eventGrid.clear();
    for (const event of map.events) {
      this.eventGrid.set(`${event.x},${event.y}`, event);
    }
    
    // 初始化传送点网格
    this.exitGrid.clear();
    for (const exit of map.exits) {
      this.exitGrid.set(`${exit.x},${exit.y}`, exit);
    }
    
    // 清除层缓存
    this.layerCanvases.clear();
    
    console.log(`[Map] Loaded: ${map.name} (${map.width}x${map.height})`);
  }
  
  // ========== 加载瓦片集 ==========
  
  async loadTileSet(tileSet: TileSet): Promise<void> {
    this.tileSets.set(tileSet.id, tileSet);
    
    return new Promise((resolve, reject) => {
      const img = new Image();
      img.onload = () => {
        this.tileImages.set(tileSet.id, img);
        resolve();
      };
      img.onerror = () => reject(new Error(`Failed to load tileset: ${tileSet.image}`));
      img.src = tileSet.image;
    });
  }
  
  // ========== 渲染 ==========
  
  render(camera: Camera): void {
    if (!this.currentMap) return;
    
    const map = this.currentMap;
    const tileSize = map.tileSize;
    
    // 获取可见范围
    const range = camera.getVisibleTileRange(tileSize);
    
    // 清空画布
    this.ctx.clearRect(0, 0, this.canvas.width, this.canvas.height);
    
    // 按层级渲染
    const sortedLayers = [...map.layers].sort((a, b) => a.zIndex - b.zIndex);
    
    for (const layer of sortedLayers) {
      this.renderLayer(layer, range, camera, tileSize);
    }
  }
  
  private renderLayer(
    layer: MapLayer,
    range: { startX: number; startY: number; endX: number; endY: number },
    camera: Camera,
    tileSize: number
  ): void {
    if (!this.currentMap) return;
    
    // 限制范围
    const startX = Math.max(0, range.startX);
    const startY = Math.max(0, range.startY);
    const endX = Math.min(this.currentMap.width, range.endX);
    const endY = Math.min(this.currentMap.height, range.endY);
    
    for (let y = startY; y < endY; y++) {
      for (let x = startX; x < endX; x++) {
        const tileId = layer.tiles[y]?.[x];
        if (tileId === undefined || tileId === 0) continue;
        
        this.renderTile(tileId, x, y, camera, tileSize);
      }
    }
  }
  
  private renderTile(
    tileId: number,
    tileX: number,
    tileY: number,
    camera: Camera,
    tileSize: number
  ): void {
    // 找到对应的瓦片集
    let tileSet: TileSet | null = null;
    let img: HTMLImageElement | null = null;
    
    // 遍历所有瓦片集找到包含该 ID 的
    for (const [id, set] of this.tileSets) {
      // 简化：假设瓦片 ID 就是瓦片在瓦片集中的索引
      const maxTileId = set.columns * Math.ceil(set.tiles.length / set.columns);
      if (tileId > 0 && tileId <= maxTileId) {
        tileSet = set;
        img = this.tileImages.get(id) || null;
        break;
      }
    }
    
    if (!tileSet || !img) {
      // 没有瓦片集，绘制占位符
      this.renderPlaceholder(tileX, tileY, camera, tileSize);
      return;
    }
    
    // 计算瓦片在瓦片集中的位置
    const tileIndex = tileId - 1; // 假设瓦片 ID 从 1 开始
    const srcX = (tileIndex % tileSet.columns) * tileSet.tileWidth;
    const srcY = Math.floor(tileIndex / tileSet.columns) * tileSet.tileHeight;
    
    // 计算屏幕位置
    const screenPos = camera.worldToScreen(
      tileX * tileSize,
      tileY * tileSize
    );
    
    this.ctx.drawImage(
      img,
      srcX, srcY, tileSet.tileWidth, tileSet.tileHeight,
      screenPos.x, screenPos.y,
      tileSize * camera.zoom, tileSize * camera.zoom
    );
  }
  
  private renderPlaceholder(
    tileX: number,
    tileY: number,
    camera: Camera,
    tileSize: number
  ): void {
    const screenPos = camera.worldToScreen(
      tileX * tileSize,
      tileY * tileSize
    );
    
    // 绘制棋盘格占位符
    const isLight = (tileX + tileY) % 2 === 0;
    this.ctx.fillStyle = isLight ? '#444' : '#333';
    this.ctx.fillRect(
      screenPos.x, screenPos.y,
      tileSize * camera.zoom, tileSize * camera.zoom
    );
    
    // 绘制瓦片 ID
    const tileId = this.currentMap?.layers[0]?.tiles[tileY]?.[tileX] || 0;
    this.ctx.fillStyle = '#888';
    this.ctx.font = '10px monospace';
    this.ctx.fillText(
      tileId.toString(),
      screenPos.x + 4,
      screenPos.y + tileSize * camera.zoom / 2
    );
  }
  
  // ========== 碰撞检测 ==========
  
  isCollidable(x: number, y: number): boolean {
    if (!this.currentMap) return true;
    
    const tileX = Math.floor(x / this.currentMap.tileSize);
    const tileY = Math.floor(y / this.currentMap.tileSize);
    
    // 边界检测
    if (tileX < 0 || tileX >= this.currentMap.width ||
        tileY < 0 || tileY >= this.currentMap.height) {
      return true;
    }
    
    return this.collisionGrid[tileY]?.[tileX] ?? false;
  }
  
  isTileCollidable(tileX: number, tileY: number): boolean {
    if (!this.currentMap) return true;
    
    if (tileX < 0 || tileX >= this.currentMap.width ||
        tileY < 0 || tileY >= this.currentMap.height) {
      return true;
    }
    
    return this.collisionGrid[tileY]?.[tileX] ?? false;
  }
  
  // ========== 事件查询 ==========
  
  getEventAt(x: number, y: number): MapEvent | null {
    if (!this.currentMap) return null;
    
    const tileX = Math.floor(x / this.currentMap.tileSize);
    const tileY = Math.floor(y / this.currentMap.tileSize);
    
    return this.eventGrid.get(`${tileX},${tileY}`) || null;
  }
  
  getEventAtTile(tileX: number, tileY: number): MapEvent | null {
    return this.eventGrid.get(`${tileX},${tileY}`) || null;
  }
  
  // ========== 传送点查询 ==========
  
  getExitAt(x: number, y: number): Exit | null {
    if (!this.currentMap) return null;
    
    const tileX = Math.floor(x / this.currentMap.tileSize);
    const tileY = Math.floor(y / this.currentMap.tileSize);
    
    return this.exitGrid.get(`${tileX},${tileY}`) || null;
  }
  
  getExitAtTile(tileX: number, tileY: number): Exit | null {
    return this.exitGrid.get(`${tileX},${tileY}`) || null;
  }
  
  // ========== 地图信息 ==========
  
  getMapSize(): { width: number; height: number } {
    if (!this.currentMap) return { width: 0, height: 0 };
    return {
      width: this.currentMap.width * this.currentMap.tileSize,
      height: this.currentMap.height * this.currentMap.tileSize,
    };
  }
  
  getTileSize(): number {
    return this.currentMap?.tileSize || 16;
  }
  
  // ========== 调试渲染 ==========
  
  renderDebug(camera: Camera): void {
    if (!this.currentMap) return;
    
    const tileSize = this.currentMap.tileSize;
    const range = camera.getVisibleTileRange(tileSize);
    
    // 渲染碰撞网格
    this.ctx.strokeStyle = 'rgba(255, 0, 0, 0.3)';
    this.ctx.lineWidth = 1;
    
    for (let y = Math.max(0, range.startY); y < Math.min(this.currentMap.height, range.endY); y++) {
      for (let x = Math.max(0, range.startX); x < Math.min(this.currentMap.width, range.endX); x++) {
        if (this.collisionGrid[y]?.[x]) {
          const screenPos = camera.worldToScreen(x * tileSize, y * tileSize);
          this.ctx.strokeRect(
            screenPos.x, screenPos.y,
            tileSize * camera.zoom, tileSize * camera.zoom
          );
        }
      }
    }
    
    // 渲染事件标记
    this.ctx.fillStyle = 'rgba(0, 255, 0, 0.5)';
    for (const [key, _event] of this.eventGrid) {
      const [x, y] = key.split(',').map(Number);
      if (camera.isTileVisible(x, y, tileSize)) {
        const screenPos = camera.worldToScreen(x * tileSize, y * tileSize);
        this.ctx.fillRect(
          screenPos.x + tileSize * camera.zoom / 4,
          screenPos.y + tileSize * camera.zoom / 4,
          tileSize * camera.zoom / 2,
          tileSize * camera.zoom / 2
        );
      }
    }
    
    // 渲染传送点标记
    this.ctx.fillStyle = 'rgba(0, 0, 255, 0.5)';
    for (const [key, _exit] of this.exitGrid) {
      const [x, y] = key.split(',').map(Number);
      if (camera.isTileVisible(x, y, tileSize)) {
        const screenPos = camera.worldToScreen(x * tileSize, y * tileSize);
        this.ctx.beginPath();
        this.ctx.arc(
          screenPos.x + tileSize * camera.zoom / 2,
          screenPos.y + tileSize * camera.zoom / 2,
          tileSize * camera.zoom / 4,
          0, Math.PI * 2
        );
        this.ctx.fill();
      }
    }
  }
}

// ========== 地图生成器（用于测试） ==========

export class MapGenerator {
  // 生成空白地图
  static createEmptyMap(
    id: string,
    name: string,
    width: number,
    height: number,
    tileSize: number = 16
  ): GameMap {
    const groundLayer: MapLayer = {
      name: 'ground',
      tiles: Array(height).fill(null).map(() => Array(width).fill(1)),
      zIndex: 0,
    };
    
    return {
      id,
      name,
      type: 'area',
      width,
      height,
      tileSize,
      layers: [groundLayer],
      collisions: Array(height).fill(null).map(() => Array(width).fill(false)),
      events: [],
      exits: [],
    };
  }
  
  // 生成带边界的房间地图
  static createRoomMap(
    id: string,
    name: string,
    width: number,
    height: number,
    tileSize: number = 16
  ): GameMap {
    const map = MapGenerator.createEmptyMap(id, name, width, height, tileSize);
    
    // 设置边界碰撞
    for (let x = 0; x < width; x++) {
      map.collisions[0][x] = true;
      map.collisions[height - 1][x] = true;
    }
    for (let y = 0; y < height; y++) {
      map.collisions[y][0] = true;
      map.collisions[y][width - 1] = true;
    }
    
    // 设置边界瓦片（假设 2 是墙）
    for (let x = 0; x < width; x++) {
      map.layers[0].tiles[0][x] = 2;
      map.layers[0].tiles[height - 1][x] = 2;
    }
    for (let y = 0; y < height; y++) {
      map.layers[0].tiles[y][0] = 2;
      map.layers[0].tiles[y][width - 1] = 2;
    }
    
    return map;
  }
  
  // 生成测试地图
  static createTestMap(): GameMap {
    const map = MapGenerator.createRoomMap('test', '测试地图', 20, 15, 16);
    
    // 添加一些障碍物
    map.collisions[5][5] = true;
    map.layers[0].tiles[5][5] = 3;
    
    map.collisions[5][6] = true;
    map.layers[0].tiles[5][6] = 3;
    
    map.collisions[8][10] = true;
    map.layers[0].tiles[8][10] = 3;
    
    // 添加传送点
    map.exits.push({
      x: 10,
      y: 14,
      targetMap: 'test2',
      targetX: 10,
      targetY: 1,
      direction: 'down',
    });
    
    // 添加事件
    map.events.push({
      id: 'sign_1',
      x: 3,
      y: 3,
      trigger: 'interact',
      conditions: [],
      actions: [
        {
          type: 'show_message',
          params: { message: '欢迎来到测试地图！' },
        },
      ],
    });
    
    return map;
  }
}