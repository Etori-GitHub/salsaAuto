/**
 * RPG Demo - 示例游戏
 */

import { Game, GameConfig } from '../../gamemark';

class RPGDemo {
  private game: Game;
  
  constructor(canvas: HTMLCanvasElement) {
    const config: GameConfig = {
      title: 'RPG Demo',
      canvas,
      tileSize: 16,
      fps: 60,
      debug: true,
      initialMap: 'test',
      initialX: 10,
      initialY: 10,
    };
    
    this.game = new Game(config);
  }
  
  async start(): Promise<void> {
    await this.game.init();
    this.game.start();
    console.log('[RPG Demo] Game started');
  }
}

// 初始化
document.addEventListener('DOMContentLoaded', async () => {
  const canvas = document.getElementById('game-canvas') as HTMLCanvasElement;
  if (!canvas) {
    console.error('Canvas not found');
    return;
  }
  
  // 设置画布尺寸
  canvas.width = 640;
  canvas.height = 480;
  
  // 启动游戏
  const demo = new RPGDemo(canvas);
  await demo.start();
});

export { RPGDemo };
