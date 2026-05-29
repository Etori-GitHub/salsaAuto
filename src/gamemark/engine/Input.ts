/**
 * 输入系统 - 支持手柄和键盘
 */

import { GamepadButton, GamepadAxis, InputState, Direction } from '../types';

// 默认键盘映射
const DEFAULT_KEY_MAPPING: Record<GamepadButton, string> = {
  // 移动（十字键）
  'A': 'Space',
  'B': 'Escape',
  'X': 'KeyX',
  'Y': 'KeyY',
  'LB': 'KeyQ',
  'RB': 'KeyE',
  'LT': 'KeyW',
  'RT': 'KeyR',
  'LS': 'KeyZ',
  'RS': 'KeyC',
  'START': 'Enter',
  'SELECT': 'Tab',
};

// 手柄按键映射（标准 Gamepad API）
const GAMEPAD_BUTTON_MAP: Record<GamepadButton, number> = {
  'A': 0,
  'B': 1,
  'X': 2,
  'Y': 3,
  'LB': 4,
  'RB': 5,
  'LT': 6,
  'RT': 7,
  'SELECT': 8,
  'START': 9,
  'LS': 10,
  'RS': 11,
};

// 手柄轴映射
const GAMEPAD_AXIS_MAP: Record<GamepadAxis, number> = {
  'LEFT_X': 0,
  'LEFT_Y': 1,
  'RIGHT_X': 2,
  'RIGHT_Y': 3,
  'DPAD_X': 4,  // 某些手柄的十字键是轴
  'DPAD_Y': 5,
};

export class InputManager {
  private keyMapping: Record<GamepadButton, string>;
  private gamepadIndex: number | null = null;
  private previousButtonState: Record<GamepadButton, boolean> = {} as any;
  private previousKeyState: Record<string, boolean> = {};
  private axisDeadzone = 0.3;
  
  // 当前状态
  private state: InputState = {
    buttons: {} as any,
    axes: {} as any,
    justPressed: [],
    justReleased: [],
  };
  
  // 回调
  private onGamepadConnectedCallbacks: (() => void)[] = [];
  private onGamepadDisconnectedCallbacks: (() => void)[] = [];
  
  constructor(customKeyMapping?: Partial<Record<GamepadButton, string>>) {
    this.keyMapping = { ...DEFAULT_KEY_MAPPING, ...customKeyMapping };
    this.initButtonState();
    this.setupGamepadListeners();
  }
  
  // ========== 初始化 ==========
  
  private initButtonState(): void {
    const buttons: GamepadButton[] = ['A', 'B', 'X', 'Y', 'LB', 'RB', 'LT', 'RT', 'LS', 'RS', 'START', 'SELECT'];
    for (const btn of buttons) {
      this.state.buttons[btn] = false;
      this.previousButtonState[btn] = false;
    }
    
    const axes: GamepadAxis[] = ['LEFT_X', 'LEFT_Y', 'RIGHT_X', 'RIGHT_Y', 'DPAD_X', 'DPAD_Y'];
    for (const axis of axes) {
      this.state.axes[axis] = 0;
    }
  }
  
  private setupGamepadListeners(): void {
    window.addEventListener('gamepadconnected', (e) => {
      this.gamepadIndex = e.gamepad.index;
      console.log(`[Input] Gamepad connected: ${e.gamepad.id}`);
      this.onGamepadConnectedCallbacks.forEach(cb => cb());
    });
    
    window.addEventListener('gamepaddisconnected', (e) => {
      if (this.gamepadIndex === e.gamepad.index) {
        this.gamepadIndex = null;
        console.log(`[Input] Gamepad disconnected`);
        this.onGamepadDisconnectedCallbacks.forEach(cb => cb());
      }
    });
  }
  
  // ========== 更新 ==========
  
  update(): void {
    this.state.justPressed = [];
    this.state.justReleased = [];
    
    // 更新键盘状态
    this.updateKeyboard();
    
    // 更新手柄状态
    this.updateGamepad();
    
    // 检测刚按下/刚释放
    this.detectButtonChanges();
  }
  
  private updateKeyboard(): void {
    for (const [btn, key] of Object.entries(this.keyMapping)) {
      const isPressed = this.isKeyPressed(key);
      // 键盘输入覆盖手柄输入（如果键盘按下，则按钮状态为按下）
      if (isPressed) {
        this.state.buttons[btn as GamepadButton] = true;
      }
      // 注意：不设置 false，因为手柄可能还在按下
    }
  }
  
  private updateGamepad(): void {
    if (this.gamepadIndex === null) return;
    
    const gamepads = navigator.getGamepads();
    const gamepad = gamepads[this.gamepadIndex];
    if (!gamepad) return;
    
    // 更新按钮状态
    for (const [btn, index] of Object.entries(GAMEPAD_BUTTON_MAP)) {
      if (index < gamepad.buttons.length) {
        const pressed = gamepad.buttons[index].pressed;
        // 手柄状态直接设置（不覆盖键盘）
        if (!this.isKeyPressed(this.keyMapping[btn as GamepadButton])) {
          this.state.buttons[btn as GamepadButton] = pressed;
        }
      }
    }
    
    // 更新轴状态
    for (const [axis, index] of Object.entries(GAMEPAD_AXIS_MAP)) {
      if (index < gamepad.axes.length) {
        let value = gamepad.axes[index];
        // 应用死区
        if (Math.abs(value) < this.axisDeadzone) {
          value = 0;
        }
        this.state.axes[axis as GamepadAxis] = value;
      }
    }
    
    // 某些手柄的十字键是按钮而不是轴
    this.handleDpadButtons(gamepad);
  }
  
  private handleDpadButtons(gamepad: Gamepad): void {
    // 标准 Gamepad API 没有统一的十字键处理
    // 某些手柄用按钮 12-15 表示上下左右
    if (gamepad.buttons.length >= 16) {
      const up = gamepad.buttons[12]?.pressed || false;
      const down = gamepad.buttons[13]?.pressed || false;
      const left = gamepad.buttons[14]?.pressed || false;
      const right = gamepad.buttons[15]?.pressed || false;
      
      if (up) this.state.axes['DPAD_Y'] = -1;
      if (down) this.state.axes['DPAD_Y'] = 1;
      if (left) this.state.axes['DPAD_X'] = -1;
      if (right) this.state.axes['DPAD_X'] = 1;
    }
  }
  
  private detectButtonChanges(): void {
    for (const btn of Object.keys(this.state.buttons) as GamepadButton[]) {
      const current = this.state.buttons[btn];
      const previous = this.previousButtonState[btn];
      
      if (current && !previous) {
        this.state.justPressed.push(btn);
      } else if (!current && previous) {
        this.state.justReleased.push(btn);
      }
      
      this.previousButtonState[btn] = current;
    }
  }
  
  private isKeyPressed(key: string): boolean {
    // 使用 KeyboardEvent 的 code 而不是 key
    // 这里需要维护一个键盘状态
    return this.previousKeyState[key] || false;
  }
  
  // 键盘事件处理（需要外部调用）
  handleKeyDown(code: string): void {
    this.previousKeyState[code] = true;
    
    // 同步到按钮状态
    for (const [btn, key] of Object.entries(this.keyMapping)) {
      if (key === code) {
        this.state.buttons[btn as GamepadButton] = true;
      }
    }
  }
  
  handleKeyUp(code: string): void {
    this.previousKeyState[code] = false;
    
    // 同步到按钮状态
    for (const [btn, key] of Object.entries(this.keyMapping)) {
      if (key === code) {
        this.state.buttons[btn as GamepadButton] = false;
      }
    }
  }
  
  // ========== 查询 ==========
  
  getButton(button: GamepadButton): boolean {
    return this.state.buttons[button];
  }
  
  getAxis(axis: GamepadAxis): number {
    return this.state.axes[axis];
  }
  
  isJustPressed(button: GamepadButton): boolean {
    return this.state.justPressed.includes(button);
  }
  
  isJustReleased(button: GamepadButton): boolean {
    return this.state.justReleased.includes(button);
  }
  
  // 获取移动方向（基于十字键或左摇杆）
  getMovementDirection(): Direction | null {
    const dx = this.state.axes['DPAD_X'] || this.state.axes['LEFT_X'];
    const dy = this.state.axes['DPAD_Y'] || this.state.axes['LEFT_Y'];
    
    // 键盘方向覆盖
    if (this.isKeyPressed('ArrowUp') || this.isKeyPressed('KeyW')) return 'up';
    if (this.isKeyPressed('ArrowDown') || this.isKeyPressed('KeyS')) return 'down';
    if (this.isKeyPressed('ArrowLeft') || this.isKeyPressed('KeyA')) return 'left';
    if (this.isKeyPressed('ArrowRight') || this.isKeyPressed('KeyD')) return 'right';
    
    if (Math.abs(dx) < 0.1 && Math.abs(dy) < 0.1) return null;
    
    if (Math.abs(dx) > Math.abs(dy)) {
      return dx > 0 ? 'right' : 'left';
    } else {
      return dy > 0 ? 'down' : 'up';
    }
  }
  
  // 获取移动向量（用于摇杆）
  getMovementVector(): { x: number; y: number } {
    let x = this.state.axes['DPAD_X'] || this.state.axes['LEFT_X'];
    let y = this.state.axes['DPAD_Y'] || this.state.axes['LEFT_Y'];
    
    // 键盘方向覆盖
    if (this.isKeyPressed('ArrowLeft') || this.isKeyPressed('KeyA')) x = -1;
    if (this.isKeyPressed('ArrowRight') || this.isKeyPressed('KeyD')) x = 1;
    if (this.isKeyPressed('ArrowUp') || this.isKeyPressed('KeyW')) y = -1;
    if (this.isKeyPressed('ArrowDown') || this.isKeyPressed('KeyS')) y = 1;
    
    return { x, y };
  }
  
  // ========== 回调注册 ==========
  
  onGamepadConnected(callback: () => void): void {
    this.onGamepadConnectedCallbacks.push(callback);
  }
  
  onGamepadDisconnected(callback: () => void): void {
    this.onGamepadDisconnectedCallbacks.push(callback);
  }
  
  // ========== 配置 ==========
  
  setKeyMapping(mapping: Partial<Record<GamepadButton, string>>): void {
    this.keyMapping = { ...this.keyMapping, ...mapping };
  }
  
  setAxisDeadzone(deadzone: number): void {
    this.axisDeadzone = deadzone;
  }
  
  hasGamepad(): boolean {
    return this.gamepadIndex !== null;
  }
  
  getState(): InputState {
    return { ...this.state };
  }
}