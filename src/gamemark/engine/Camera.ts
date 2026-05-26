/**
 * 相机系统 - 视口管理
 */

export interface CameraConfig {
  viewportWidth: number;
  viewportHeight: number;
  smoothing?: number;  // 0 = 无平滑, 1 = 最大平滑
  deadzone?: number;   // 死区大小
}

export class Camera {
  // 视口尺寸
  viewportWidth: number;
  viewportHeight: number;
  
  // 当前位置（左上角）
  x: number = 0;
  y: number = 0;
  
  // 目标位置（用于平滑跟随）
  targetX: number = 0;
  targetY: number = 0;
  
  // 跟随目标
  followTarget: { x: number; y: number } | null = null;
  
  // 配置
  smoothing: number;
  deadzone: number;
  
  // 边界限制
  bounds: { left: number; top: number; right: number; bottom: number } | null = null;
  
  // 缩放
  zoom: number = 1;
  
  constructor(config: CameraConfig) {
    this.viewportWidth = config.viewportWidth;
    this.viewportHeight = config.viewportHeight;
    this.smoothing = config.smoothing ?? 0.1;
    this.deadzone = config.deadzone ?? 0;
  }
  
  // ========== 更新 ==========
  
  update(deltaTime: number): void {
    if (this.followTarget) {
      // 计算目标位置（居中）
      const centerX = this.followTarget.x - this.viewportWidth / 2;
      const centerY = this.followTarget.y - this.viewportHeight / 2;
      
      // 应用死区
      if (this.deadzone > 0) {
        const dx = centerX - this.targetX;
        const dy = centerY - this.targetY;
        
        if (Math.abs(dx) > this.deadzone) {
          this.targetX = centerX - Math.sign(dx) * this.deadzone;
        }
        if (Math.abs(dy) > this.deadzone) {
          this.targetY = centerY - Math.sign(dy) * this.deadzone;
        }
      } else {
        this.targetX = centerX;
        this.targetY = centerY;
      }
    }
    
    // 平滑移动
    if (this.smoothing > 0) {
      this.x += (this.targetX - this.x) * this.smoothing;
      this.y += (this.targetY - this.y) * this.smoothing;
    } else {
      this.x = this.targetX;
      this.y = this.targetY;
    }
    
    // 应用边界限制
    this.applyBounds();
  }
  
  // ========== 跟随 ==========
  
  follow(target: { x: number; y: number }): void {
    this.followTarget = target;
  }
  
  stopFollow(): void {
    this.followTarget = null;
  }
  
  // ========== 边界 ==========
  
  setBounds(width: number, height: number): void {
    this.bounds = {
      left: 0,
      top: 0,
      right: Math.max(0, width - this.viewportWidth),
      bottom: Math.max(0, height - this.viewportHeight),
    };
    this.applyBounds();
  }
  
  clearBounds(): void {
    this.bounds = null;
  }
  
  private applyBounds(): void {
    if (!this.bounds) return;
    
    this.x = Math.max(this.bounds.left, Math.min(this.bounds.right, this.x));
    this.y = Math.max(this.bounds.top, Math.min(this.bounds.bottom, this.y));
    this.targetX = Math.max(this.bounds.left, Math.min(this.bounds.right, this.targetX));
    this.targetY = Math.max(this.bounds.top, Math.min(this.bounds.bottom, this.targetY));
  }
  
  // ========== 位置控制 ==========
  
  setPosition(x: number, y: number, immediate: boolean = false): void {
    this.targetX = x;
    this.targetY = y;
    
    if (immediate) {
      this.x = x;
      this.y = y;
    }
  }
  
  lookAt(x: number, y: number): void {
    this.setPosition(x - this.viewportWidth / 2, y - this.viewportHeight / 2);
  }
  
  // ========== 缩放 ==========
  
  setZoom(zoom: number): void {
    this.zoom = Math.max(0.5, Math.min(3, zoom));
  }
  
  // ========== 坐标转换 ==========
  
  // 屏幕坐标 -> 世界坐标
  screenToWorld(screenX: number, screenY: number): { x: number; y: number } {
    return {
      x: (screenX / this.zoom) + this.x,
      y: (screenY / this.zoom) + this.y,
    };
  }
  
  // 世界坐标 -> 屏幕坐标
  worldToScreen(worldX: number, worldY: number): { x: number; y: number } {
    return {
      x: (worldX - this.x) * this.zoom,
      y: (worldY - this.y) * this.zoom,
    };
  }
  
  // 格子坐标 -> 世界坐标（格子中心）
  tileToWorld(tileX: number, tileY: number, tileSize: number): { x: number; y: number } {
    return {
      x: tileX * tileSize + tileSize / 2,
      y: tileY * tileSize + tileSize / 2,
    };
  }
  
  // 世界坐标 -> 格子坐标
  worldToTile(worldX: number, worldY: number, tileSize: number): { x: number; y: number } {
    return {
      x: Math.floor(worldX / tileSize),
      y: Math.floor(worldY / tileSize),
    };
  }
  
  // 屏幕坐标 -> 格子坐标
  screenToTile(screenX: number, screenY: number, tileSize: number): { x: number; y: number } {
    const world = this.screenToWorld(screenX, screenY);
    return this.worldToTile(world.x, world.y, tileSize);
  }
  
  // ========== 可见性检测 ==========
  
  isVisible(x: number, y: number, width: number, height: number): boolean {
    return (
      x + width > this.x &&
      x < this.x + this.viewportWidth &&
      y + height > this.y &&
      y < this.y + this.viewportHeight
    );
  }
  
  isTileVisible(tileX: number, tileY: number, tileSize: number): boolean {
    const x = tileX * tileSize;
    const y = tileY * tileSize;
    return this.isVisible(x, y, tileSize, tileSize);
  }
  
  // ========== 视口信息 ==========
  
  getViewport(): { x: number; y: number; width: number; height: number } {
    return {
      x: this.x,
      y: this.y,
      width: this.viewportWidth,
      height: this.viewportHeight,
    };
  }
  
  getVisibleTileRange(tileSize: number): { startX: number; startY: number; endX: number; endY: number } {
    return {
      startX: Math.floor(this.x / tileSize),
      startY: Math.floor(this.y / tileSize),
      endX: Math.ceil((this.x + this.viewportWidth) / tileSize),
      endY: Math.ceil((this.y + this.viewportHeight) / tileSize),
    };
  }
  
  // ========== 调整尺寸 ==========
  
  resize(width: number, height: number): void {
    this.viewportWidth = width;
    this.viewportHeight = height;
    
    // 重新应用边界
    if (this.bounds) {
      this.setBounds(
        this.bounds.right + this.viewportWidth,
        this.bounds.bottom + this.viewportHeight
      );
    }
  }
}