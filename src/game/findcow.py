"""
找牛游戏服务 - 逻辑推理游戏
"""
import random
from typing import Optional

# 日系小清新配色
COW_COLORS = [
    "#ffb3ba",  # 樱花粉
    "#bae1ff",  # 天空蓝
    "#baffc9",  # 薄荷绿
    "#ffffba",  # 柠檬黄
    "#e0bbff",  # 薰衣草紫
    "#ffcba4",  # 杏子橙
    "#c9baff",  # 紫藤紫
    "#bae0ff",  # 水色蓝
    "#ffdfba",  # 奶油橙
    "#baffba",  # 青草绿
]


def generate_puzzle(size: int = 6) -> dict:
    """
    生成找牛关卡
    
    Args:
        size: 网格大小 (6-10)
        
    Returns:
        关卡数据 {"size": int, "colors": [...], "cows": [...]}
    """
    size = max(6, min(10, size))  # 限制范围 6-10
    
    # 初始化网格
    grid = [[0 for _ in range(size)] for _ in range(size)]
    
    # 使用 BFS 洪水填充生成连通颜色区域
    _generate_color_regions(grid, size)
    
    # 放置牛
    cows = _place_cows(grid, size)
    
    # 如果放置失败，重新生成
    attempts = 0
    while cows is None and attempts < 50:
        grid = [[0 for _ in range(size)] for _ in range(size)]
        _generate_color_regions(grid, size)
        cows = _place_cows(grid, size)
        attempts += 1
    
    if cows is None:
        # 强制放置
        cows = _force_place_cows(grid, size)
    
    return {
        "size": size,
        "grid": grid,
        "colors": COW_COLORS[:size],
        "cows": cows,
        "cowCount": len(cows)
    }


def _generate_color_regions(grid: list, size: int):
    """BFS 洪水填充生成连通颜色区域"""
    seeds = []
    used_positions = set()
    
    # 为每种颜色选择种子点
    for color in range(1, size + 1):
        attempts = 0
        while attempts < 100:
            r = random.randint(0, size - 1)
            c = random.randint(0, size - 1)
            if (r, c) not in used_positions:
                break
            attempts += 1
        else:
            # 找第一个空位
            for i in range(size):
                for j in range(size):
                    if (i, j) not in used_positions:
                        r, c = i, j
                        break
        
        seeds.append({"r": r, "c": c, "color": color})
        used_positions.add((r, c))
        grid[r][c] = color
    
    # BFS 扩展
    queues = [[s] for s in seeds]
    
    while len(used_positions) < size * size:
        expanded = False
        
        for i in range(size):
            queue = queues[i]
            if not queue:
                continue
            
            # 随机选择一个点扩展
            idx = random.randint(0, len(queue) - 1)
            point = queue[idx]
            r, c = point["r"], point["c"]
            color = i + 1
            
            # 随机方向
            dirs = [(0, 1), (0, -1), (1, 0), (-1, 0)]
            random.shuffle(dirs)
            
            for dr, dc in dirs:
                nr, nc = r + dr, c + dc
                if 0 <= nr < size and 0 <= nc < size and (nr, nc) not in used_positions:
                    grid[nr][nc] = color
                    used_positions.add((nr, nc))
                    queue.append({"r": nr, "c": nc})
                    expanded = True
                    break
        
        if not expanded:
            # 清理无法扩展的队列
            for i in range(size):
                queues[i] = [p for p in queues[i] if _can_expand(p["r"], p["c"], grid, size, used_positions)]
            
            # 强制填充
            if len(used_positions) < size * size:
                for r in range(size):
                    for c in range(size):
                        if grid[r][c] == 0:
                            for dr, dc in [(0, 1), (0, -1), (1, 0), (-1, 0)]:
                                nr, nc = r + dr, c + dc
                                if 0 <= nr < size and 0 <= nc < size and grid[nr][nc] != 0:
                                    grid[r][c] = grid[nr][nc]
                                    used_positions.add((r, c))
                                    break


def _can_expand(r: int, c: int, grid: list, size: int, used: set) -> bool:
    """检查位置是否还能扩展"""
    for dr, dc in [(0, 1), (0, -1), (1, 0), (-1, 0)]:
        nr, nc = r + dr, c + dc
        if 0 <= nr < size and 0 <= nc < size and (nr, nc) not in used:
            return True
    return False


def _place_cows(grid: list, size: int) -> Optional[list]:
    """放置牛，满足约束条件"""
    cows = []
    
    for color in range(1, size + 1):
        # 找到该颜色的所有格子
        color_cells = []
        for r in range(size):
            for c in range(size):
                if grid[r][c] == color:
                    color_cells.append((r, c))
        
        random.shuffle(color_cells)
        
        # 找一个满足条件的位置
        placed = False
        for r, c in color_cells:
            if _is_valid_cow_position(r, c, cows, size):
                cows.append([r, c])
                placed = True
                break
        
        if not placed:
            return None
    
    return cows


def _force_place_cows(grid: list, size: int) -> list:
    """强制放置牛（放宽约束）"""
    cows = []
    
    for color in range(1, size + 1):
        for r in range(size):
            for c in range(size):
                if grid[r][c] == color:
                    # 只检查行列约束
                    conflict = False
                    for cr, cc in cows:
                        if cr == r or cc == c:
                            conflict = True
                            break
                    if not conflict:
                        cows.append([r, c])
                        break
    
    return cows


def _is_valid_cow_position(r: int, c: int, cows: list, size: int) -> bool:
    """检查位置是否有效"""
    for cr, cc in cows:
        # 同一行或同一列
        if cr == r or cc == c:
            return False
        # 周围8格
        if abs(cr - r) <= 1 and abs(cc - c) <= 1:
            return False
    return True


def verify_cow(puzzle: dict, row: int, col: int) -> dict:
    """
    验证用户猜测的牛位置
    
    Args:
        puzzle: 关卡数据
        row: 行坐标
        col: 列坐标
        
    Returns:
        验证结果 {"correct": bool, "cow": bool}
    """
    cows = puzzle["cows"]
    is_cow = [row, col] in cows or (row, col) in [(c[0], c[1]) for c in cows]
    
    return {
        "correct": is_cow,
        "cow": is_cow
    }
