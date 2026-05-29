/**
 * 精灵系统 - 像素精灵渲染和动画
 */

import { SpriteSheet, SpriteAnimation, Direction } from '../types';

export class Sprite {
  // 精灵图
  private image: HTMLImageElement | null = null;
  private sheet: SpriteSheet | null = null;
  
  // 当前状态
  private currentAnimation: string = 'idle';
  private currentFrame: number = 0;
  private frameTime: number = 0;
  
  // 动画数据
  private animations: Record<string, SpriteAnimation> = {};
  
  // 位置
  x: number = 0;
  y: number = 0;
  
  // 尺寸
  width: number = 16;
  height: number = 16;
  
  // 方向（用于方向相关动画）
  direction: Direction = 'down';
  
  // 是否播放动画
  playing: boolean = true;
  
  // 渲染缩放
  scale: number = 1;
  
  // 偏移（用于对齐）
  offsetX: number = 0;
  offsetY: number = 0;
  
  constructor() {}
  
  // ========== 加载 ==========
  
  load(sheet: SpriteSheet): Promise<void> {
    this.sheet = sheet;
    this.animations = sheet.animations;
    this.width = sheet.frameWidth;
    this.height = sheet.frameHeight;
    
    return new Promise((resolve, reject) => {
      this.image = new Image();
      this.image.onload = () => resolve();
      this.image.onerror = () => reject(new Error(`Failed to load sprite: ${sheet.image}`));
      this.image.src = sheet.image;
    });
  }
  
  loadFromUrl(url: string, frameWidth: number, frameHeight: number): Promise<void> {
    this.width = frameWidth;
    this.height = frameHeight;
    
    return new Promise((resolve, reject) => {
      this.image = new Image();
      this.image.onload = () => resolve();
      this.image.onerror = () => reject(new Error(`Failed to load sprite: ${url}`));
      this.image.src = url;
    });
  }
  
  // ========== 动画控制 ==========
  
  play(name: string, reset: boolean = false): void {
    if (this.currentAnimation === name && !reset) return;
    
    const anim = this.animations[name];
    if (!anim) {
      console.warn(`[Sprite] Animation not found: ${name}`);
      return;
    }
    
    this.currentAnimation = name;
    this.currentFrame = reset ? 0 : this.currentFrame;
    this.frameTime = 0;
    this.playing = true;
  }
  
  stop(): void {
    this.playing = false;
  }
  
  resume(): void {
    this.playing = true;
  }
  
  reset(): void {
    this.currentFrame = 0;
    this.frameTime = 0;
  }
  
  // ========== 方向相关动画 ==========
  
  playDirection(baseName: string, direction: Direction): void {
    this.direction = direction;
    
    // 方向命名约定: walk_up, walk_down, walk_left, walk_right
    const animName = `${baseName}_${direction}`;
    
    // 如果没有方向动画，使用默认动画
    if (this.animations[animName]) {
      this.play(animName);
    } else if (this.animations[baseName]) {
      this.play(baseName);
    } else if (this.animations[direction]) {
      this.play(direction);
    }
  }
  
  // ========== 更新 ==========
  
  update(deltaTime: number): void {
    if (!this.playing || !this.image) return;
    
    const anim = this.animations[this.currentAnimation];
    if (!anim) return;
    
    // 更新帧时间
    this.frameTime += deltaTime;
    
    // 检查是否需要切换帧
    if (this.frameTime >= anim.frameDuration) {
      this.frameTime -= anim.frameDuration;
      this.currentFrame++;
      
      // 检查是否到达最后一帧
      if (this.currentFrame >= anim.frames.length) {
        if (anim.loop) {
          this.currentFrame = 0;
        } else {
          this.currentFrame = anim.frames.length - 1;
          this.playing = false;
        }
      }
    }
  }
  
  // ========== 渲染 ==========
  
  render(ctx: CanvasRenderingContext2D, cameraX: number = 0, cameraY: number = 0): void {
    if (!this.image) return;
    
    const anim = this.animations[this.currentAnimation];
    if (!anim) {
      // 没有动画，直接渲染整张图的第一帧
      ctx.drawImage(
        this.image,
        0, 0, this.width, this.height,
        this.x - cameraX + this.offsetX,
        this.y - cameraY + this.offsetY,
        this.width * this.scale,
        this.height * this.scale
      );
      return;
    }
    
    const frame = anim.frames[this.currentFrame];
    
    ctx.drawImage(
      this.image,
      frame.x, frame.y, frame.width || this.width, frame.height || this.height,
      this.x - cameraX + this.offsetX,
      this.y - cameraY + this.offsetY,
      (frame.width || this.width) * this.scale,
      (frame.height || this.height) * this.scale
    );
  }
  
  // ========== 状态查询 ==========
  
  getAnimation(): string {
    return this.currentAnimation;
  }
  
  getFrame(): number {
    return this.currentFrame;
  }
  
  isPlaying(): boolean {
    return this.playing;
  }
  
  isAnimation(name: string): boolean {
    return this.currentAnimation === name;
  }
  
  // ========== 位置设置 ==========
  
  setPosition(x: number, y: number): void {
    this.x = x;
    this.y = y;
  }
  
  setTilePosition(tileX: number, tileY: number, tileSize: number): void {
    this.x = tileX * tileSize;
    this.y = tileY * tileSize;
  }
  
  // ========== 静态工厂方法 ==========
  
  static async create(sheet: SpriteSheet): Promise<Sprite> {
    const sprite = new Sprite();
    await sprite.load(sheet);
    return sprite;
  }
  
  static async createSimple(url: string, width: number, height: number): Promise<Sprite> {
    const sprite = new Sprite();
    await sprite.loadFromUrl(url, width, height);
    return sprite;
  }
}

// ========== 精灵管理器 ==========

export class SpriteManager {
  private sprites: Map<string, Sprite> = new Map();
  private sheets: Map<string, SpriteSheet> = new Map();
  private loaded: boolean = false;
  
  // 预加载精灵表
  async preload(sheets: SpriteSheet[]): Promise<void> {
    const promises = sheets.map(async (sheet) => {
      this.sheets.set(sheet.id, sheet);
      const sprite = await Sprite.create(sheet);
      this.sprites.set(sheet.id, sprite);
    });
    
    await Promise.all(promises);
    this.loaded = true;
  }
  
  // 获取精灵（克隆一个新的实例）
  get(sheetId: string): Sprite | null {
    const template = this.sprites.get(sheetId);
    if (!template) return null;
    
    // 创建克隆
    const clone = new Sprite();
    clone['image'] = template['image'];
    clone['sheet'] = template['sheet'];
    clone['animations'] = template['animations'];
    clone.width = template.width;
    clone.height = template.height;
    
    return clone;
  }
  
  // 获取精灵表
  getSheet(sheetId: string): SpriteSheet | null {
    return this.sheets.get(sheetId) || null;
  }
  
  // 添加精灵表
  addSheet(sheet: SpriteSheet): void {
    this.sheets.set(sheet.id, sheet);
  }
  
  isLoaded(): boolean {
    return this.loaded;
  }
}

// ========== 像素精灵生成器（用于测试） ==========

export class PixelSpriteGenerator {
  // 生成简单的像素精灵（用于测试）
  static generateCharacter(color: string, size: number = 16): HTMLCanvasElement {
    const canvas = document.createElement('canvas');
    canvas.width = size;
    canvas.height = size;
    const ctx = canvas.getContext('2d')!;
    
    // 简单的人形像素图
    ctx.fillStyle = 'transparent';
    ctx.fillRect(0, 0, size, size);
    
    // 头部
    ctx.fillStyle = '#FFE4C4';
    ctx.fillRect(4, 2, 8, 6);
    
    // 身体
    ctx.fillStyle = color;
    ctx.fillRect(4, 8, 8, 6);
    
    // 腿部
    ctx.fillStyle = '#333';
    ctx.fillRect(4, 14, 3, 2);
    ctx.fillRect(9, 14, 3, 2);
    
    return canvas;
  }
  
  // 生成方向动画精灵表
  static generateDirectionSheet(color: string, size: number = 16): SpriteSheet {
    const canvas = document.createElement('canvas');
    canvas.width = size * 4;  // 4 方向
    canvas.height = size * 2; // 2 帧
    const ctx = canvas.getContext('2d')!;
    
    for (let d = 0; d < 4; d++) {
      for (let f = 0; f < 2; f++) {
        const x = d * size;
        const y = f * size;
        
        // 头部
        ctx.fillStyle = '#FFE4C4';
        ctx.fillRect(x + 4, y + 2, 8, 6);
        
        // 身体
        ctx.fillStyle = color;
        ctx.fillRect(x + 4, y + 8, 8, 6);
        
        // 腿部（行走动画）
        ctx.fillStyle = '#333';
        if (f === 0) {
          ctx.fillRect(x + 4, y + 14, 3, 2);
          ctx.fillRect(x + 9, y + 14, 3, 2);
        } else {
          ctx.fillRect(x + 3, y + 14, 3, 2);
          ctx.fillRect(x + 10, y + 14, 3, 2);
        }
      }
    }
    
    const dataUrl = canvas.toDataURL();
    
    return {
      id: `character_${color}`,
      image: dataUrl,
      frameWidth: size,
      frameHeight: size,
      animations: {
        'idle_down': {
          name: 'idle_down',
          frames: [{ x: 0, y: 0, width: size, height: size }],
          frameDuration: 200,
          loop: true,
        },
        'walk_down': {
          name: 'walk_down',
          frames: [
            { x: 0, y: 0, width: size, height: size },
            { x: 0, y: size, width: size, height: size },
          ],
          frameDuration: 150,
          loop: true,
        },
        'walk_left': {
          name: 'walk_left',
          frames: [
            { x: size, y: 0, width: size, height: size },
            { x: size, y: size, width: size, height: size },
          ],
          frameDuration: 150,
          loop: true,
        },
        'walk_right': {
          name: 'walk_right',
          frames: [
            { x: size * 2, y: 0, width: size, height: size },
            { x: size * 2, y: size, width: size, height: size },
          ],
          frameDuration: 150,
          loop: true,
        },
        'walk_up': {
          name: 'walk_up',
          frames: [
            { x: size * 3, y: 0, width: size, height: size },
            { x: size * 3, y: size, width: size, height: size },
          ],
          frameDuration: 150,
          loop: true,
        },
      },
    };
  }
}