from __future__ import annotations

import random
import tkinter as tk
from dataclasses import dataclass
from heapq import heappop, heappush


CELL_SIZE = 48
GRID_WIDTH = 12
GRID_HEIGHT = 14
HUD_HEIGHT = 120
WINDOW_WIDTH = GRID_WIDTH * CELL_SIZE
WINDOW_HEIGHT = GRID_HEIGHT * CELL_SIZE + HUD_HEIGHT

BG_COLOR = "#0a1017"
FLOOR_COLOR = "#d6d4ca"
FLOOR_ACCENT = "#c1c0b6"
WALL_COLOR = "#37483f"
CRATE_COLOR = "#b56135"
CRATE_SHADOW = "#814124"
PLAYER_COLOR = "#2aa85a"
PLAYER_ACCENT = "#1f6f3d"
GUARD_COLOR = "#f0f0f0"
GUARD_ACCENT = "#2b2b2b"
TARGET_COLOR = "#ffd44a"
VISION_COLOR = "#ffb342"
ROUTE_COLOR = "#f4c542"
TEXT_COLOR = "#eef4ff"
ACCENT_COLOR = "#6fd3ff"
DANGER_COLOR = "#ff6e5e"
SUCCESS_COLOR = "#77e08e"
PLAYER_MAX_HEALTH = 120
SHOT_DAMAGE = 15
SHOT_COOLDOWN_TICKS = 14
SHOT_FLASH_TICKS = 4

LAYOUT = [
    "############",
    "#..........#",
    "#..##...#..#",
    "#..##...#..#",
    "#..........#",
    "#.###..###.#",
    "#..........#",
    "#..#....#..#",
    "#..#....#..#",
    "#..........#",
    "#.###..###.#",
    "#..........#",
    "#..##....#.#",
    "############",
]


@dataclass(frozen=True)
class Point:
    x: int
    y: int


@dataclass
class Guard:
    guard_id: int
    pos: Point
    facing: tuple[int, int]
    alive: bool = True
    move_timer: int = 0
    shot_cooldown: int = 0


class ShadowStrikeGame:
    def __init__(self) -> None:
        self.root = tk.Tk()
        self.root.title("Shadow Strike: AI Maze Assassin")
        self.root.resizable(False, False)
        self.canvas = tk.Canvas(
            self.root,
            width=WINDOW_WIDTH,
            height=WINDOW_HEIGHT,
            bg=BG_COLOR,
            highlightthickness=0,
        )
        self.canvas.pack()

        self.root.bind("<Button-1>", self.on_click)
        self.root.bind("<Return>", self.handle_enter)
        self.root.bind("r", self.restart_game)
        self.root.bind("p", self.toggle_pause)

        self.showing_title = True
        self.after_id = None
        self.best_score = 0
        self.build_board()
        self.reset_game()
        self.draw_title()

    def build_board(self) -> None:
        self.walkable = set()
        self.grid = []
        for y, row in enumerate(LAYOUT):
            grid_row = []
            for x, cell in enumerate(row):
                blocked = 1 if cell == "#" else 0
                grid_row.append(blocked)
                if not blocked:
                    self.walkable.add(Point(x, y))
            self.grid.append(grid_row)

        self.player_spawn = Point(1, GRID_HEIGHT - 2)
        self.guard_spawn_candidates = [
            Point(10, 1),
            Point(9, 4),
            Point(10, 8),
            Point(7, 11),
            Point(2, 1),
            Point(5, 6),
            Point(9, 9),
        ]

    def reset_game(self) -> None:
        self.score = 0
        self.wave = 1
        self.lives = 4
        self.player_health = PLAYER_MAX_HEALTH
        self.safe_ticks = 0
        self.kill_flash_ticks = 0
        self.is_paused = False
        self.game_over = False
        self.victory = False
        self.message = "Click a tile to move or click a guard to plan a backstab."
        self.selected_guard_id = None
        self.move_target = None
        self.player_path = []
        self.player_move_tick = 0
        self.shot_flash = None
        self.player = self.player_spawn
        self.spawn_wave()

    def spawn_wave(self) -> None:
        self.player = self.player_spawn
        self.safe_ticks = 28
        self.kill_flash_ticks = 0
        self.selected_guard_id = None
        self.move_target = None
        self.player_path = []
        self.player_move_tick = 0

        count = 4 if self.wave == 1 else 5
        chosen_spawns = random.sample(self.guard_spawn_candidates, count)
        self.guards = []
        base_speed = max(6, 10 - min(3, self.wave - 1))
        for idx, spawn in enumerate(chosen_spawns):
            timer = random.randint(0, base_speed)
            facing = random.choice([(1, 0), (-1, 0), (0, 1), (0, -1)])
            self.guards.append(Guard(idx, spawn, facing, True, timer, 0))

    def on_click(self, event: tk.Event) -> None:
        if self.showing_title:
            self.showing_title = False
            self.loop()
            return

        if self.game_over or self.victory:
            self.reset_game()
            self.showing_title = False
            self.loop()
            return

        if self.in_pause_button(event.x, event.y):
            self.toggle_pause()
            return

        if self.is_paused:
            return

        if event.y >= GRID_HEIGHT * CELL_SIZE:
            return

        clicked = Point(event.x // CELL_SIZE, event.y // CELL_SIZE)
        target = self.guard_at(clicked)
        if target and target.alive:
            self.selected_guard_id = target.guard_id
            self.move_target = None
            self.recalculate_player_path()
            if self.player_path:
                self.message = "Target locked. Assassin will chase this guard until you click elsewhere."
            else:
                self.message = "Target locked. Waiting for a better backstab route."
            return

        destination = clicked if self.is_walkable(clicked) else self.nearest_walkable_to(clicked)
        if destination is None:
            self.message = "That area is blocked."
            return

        self.selected_guard_id = None
        self.move_target = destination
        self.recalculate_player_path()
        if self.player == destination:
            self.message = "Already standing there."
            self.move_target = None
        elif self.player_path:
            self.message = "Shortest path locked to the clicked tile."
        else:
            self.message = "No path found to that tile."

    def handle_enter(self, event: tk.Event | None = None) -> None:
        if self.showing_title:
            self.showing_title = False
            self.loop()
            return

        if self.game_over or self.victory:
            self.reset_game()
            self.showing_title = False
            self.loop()

    def restart_game(self, event: tk.Event | None = None) -> None:
        self.reset_game()
        self.showing_title = False
        self.loop()

    def toggle_pause(self, event: tk.Event | None = None) -> None:
        if self.showing_title or self.game_over or self.victory:
            return
        self.is_paused = not self.is_paused
        self.message = "Game paused." if self.is_paused else "Game resumed."
        self.draw()

    def guard_at(self, point: Point):
        for guard in self.guards:
            if guard.alive and guard.pos == point:
                return guard
        return None

    def loop(self) -> None:
        if self.after_id:
            self.root.after_cancel(self.after_id)
            self.after_id = None

        self.update()
        self.draw()

        if not self.showing_title:
            self.after_id = self.root.after(90, self.loop)

    def update(self) -> None:
        if self.showing_title or self.game_over or self.victory or self.is_paused:
            return

        self.safe_ticks = max(0, self.safe_ticks - 1)
        self.kill_flash_ticks = max(0, self.kill_flash_ticks - 1)
        if self.shot_flash:
            self.shot_flash["ticks"] -= 1
            if self.shot_flash["ticks"] <= 0:
                self.shot_flash = None

        self.update_guards()
        self.update_player()
        self.update_guard_fire()
        self.check_wave_clear()

    def update_guards(self) -> None:
        guard_speed = max(6, 10 - min(3, self.wave - 1))
        for guard in self.guards:
            if not guard.alive:
                continue
            guard.shot_cooldown = max(0, guard.shot_cooldown - 1)

            guard.move_timer += 1
            if guard.move_timer < guard_speed:
                continue

            guard.move_timer = 0
            next_pos, next_facing = self.random_guard_step(guard)
            guard.pos = next_pos
            guard.facing = self.direction_toward(guard.pos, self.player, fallback=next_facing)

    def random_guard_step(self, guard: Guard):
        blocked = self.occupied_guard_cells(exclude_guard_id=guard.guard_id)
        if self.player not in blocked:
            blocked.add(self.player)
        neighbors = [point for point in self.neighbors(guard.pos) if point not in blocked]
        if not neighbors:
            return guard.pos, guard.facing

        forward = Point(guard.pos.x + guard.facing[0], guard.pos.y + guard.facing[1])
        preferred = []
        if forward in neighbors:
            preferred.extend([forward, forward])
        preferred.extend(neighbors)
        chosen = random.choice(preferred)
        facing = (chosen.x - guard.pos.x, chosen.y - guard.pos.y)
        return chosen, facing

    def update_player(self) -> None:
        target = self.current_target_guard()
        if target and self.can_backstab(target):
            self.perform_backstab(target)
            return

        if not target and self.move_target is None:
            self.player_path = []
            return

        self.player_move_tick += 1
        if self.player_move_tick < 2:
            return
        self.player_move_tick = 0

        self.recalculate_player_path()
        if not self.player_path:
            if target:
                self.message = "No path behind this guard right now."
            elif self.move_target is not None and self.player == self.move_target:
                self.move_target = None
                self.message = "Position reached."
            elif self.move_target is not None:
                self.message = "No path to that tile."
            return

        next_step = self.player_path.pop(0)
        self.player = next_step

        if target and self.can_backstab(target):
            self.perform_backstab(target)
        elif self.move_target is not None and self.player == self.move_target:
            self.player_path = []
            self.move_target = None
            self.message = "Position reached."

    def current_target_guard(self):
        if self.selected_guard_id is None:
            return None
        for guard in self.guards:
            if guard.guard_id == self.selected_guard_id and guard.alive:
                return guard
        self.selected_guard_id = None
        return None

    def recalculate_player_path(self) -> None:
        target = self.current_target_guard()
        if target:
            self.player_path = self.find_guard_chase_path(target)
            return

        if self.move_target is not None:
            self.player_path = self.find_safe_path(
                self.player,
                self.move_target,
                blocked=self.occupied_guard_cells(),
                avoid=self.all_guard_vision_cells(),
            )
            return

        self.player_path = []

    def update_guard_fire(self) -> None:
        if self.safe_ticks > 0 or self.kill_flash_ticks > 0:
            return

        for guard in self.guards:
            if not guard.alive:
                continue
            if guard.shot_cooldown > 0:
                continue
            if self.player in self.guard_vision_cells(guard):
                self.player_health = max(0, self.player_health - SHOT_DAMAGE)
                guard.shot_cooldown = SHOT_COOLDOWN_TICKS
                self.shot_flash = {
                    "start": guard.pos,
                    "end": self.player,
                    "ticks": SHOT_FLASH_TICKS,
                }
                self.message = "You were seen and shot. Stay behind the guards."
                if self.player_health <= 0:
                    self.lose_life()
                return

    def check_wave_clear(self) -> None:
        alive = [guard for guard in self.guards if guard.alive]
        if alive:
            return

        if self.wave >= 2:
            self.victory = True
            self.best_score = max(self.best_score, self.score)
            self.message = "Mission complete."
            return

        self.wave += 1
        self.score += 200
        self.message = f"Wave {self.wave} unlocked. Guards are moving faster."
        self.spawn_wave()

    def lose_life(self) -> None:
        self.lives -= 1
        self.selected_guard_id = None
        self.move_target = None
        self.player_path = []
        self.player_health = PLAYER_MAX_HEALTH
        if self.lives <= 0:
            self.game_over = True
            self.best_score = max(self.best_score, self.score)
            self.message = "The guards shot you down."
            return

        self.message = "Hit badly. Repositioned to the entry point."
        self.player = self.player_spawn
        self.safe_ticks = 30

    def neighbors(self, point: Point):
        result = []
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            nxt = Point(point.x + dx, point.y + dy)
            if self.is_walkable(nxt):
                result.append(nxt)
        return result

    def is_walkable(self, point: Point) -> bool:
        if not (0 <= point.x < GRID_WIDTH and 0 <= point.y < GRID_HEIGHT):
            return False
        return self.grid[point.y][point.x] == 0

    def find_path(self, start: Point, goal: Point, blocked=None, avoid=None, avoid_cost: int = 0):
        if start == goal:
            return []

        blocked = blocked or set()
        avoid = avoid or set()
        frontier = [(0, 0, start)]
        came_from = {start: None}
        cost_so_far = {start: 0}
        order = 0

        while frontier:
            _, _, current = heappop(frontier)
            if current == goal:
                break

            for nxt in self.neighbors(current):
                if nxt in blocked and nxt != goal:
                    continue
                step_cost = 1
                if nxt in avoid and nxt != goal:
                    step_cost += avoid_cost
                new_cost = cost_so_far[current] + step_cost
                if nxt not in cost_so_far or new_cost < cost_so_far[nxt]:
                    cost_so_far[nxt] = new_cost
                    order += 1
                    priority = new_cost + self.manhattan(nxt, goal)
                    heappush(frontier, (priority, order, nxt))
                    came_from[nxt] = current

        if goal not in came_from:
            return []

        path = []
        current = goal
        while current != start:
            path.append(current)
            current = came_from[current]
        path.reverse()
        return path

    def occupied_guard_cells(self, exclude_guard_id=None):
        cells = set()
        for guard in self.guards:
            if not guard.alive:
                continue
            if exclude_guard_id is not None and guard.guard_id == exclude_guard_id:
                continue
            cells.add(guard.pos)
        return cells

    def all_guard_vision_cells(self, exclude_guard_id=None):
        cells = set()
        for guard in self.guards:
            if not guard.alive:
                continue
            if exclude_guard_id is not None and guard.guard_id == exclude_guard_id:
                continue
            cells.update(self.guard_vision_cells(guard))
        return cells

    def find_safe_path(self, start: Point, goal: Point, blocked=None, avoid=None):
        blocked = set(blocked or set())
        avoid = set(avoid or set())

        strict_blocked = blocked | (avoid - {goal})
        safe_path = self.find_path(start, goal, blocked=strict_blocked)
        if safe_path or start == goal:
            return safe_path

        return self.find_path(start, goal, blocked=blocked, avoid=avoid, avoid_cost=8)

    def nearest_walkable_to(self, point: Point):
        if self.is_walkable(point):
            return point

        checked = set()
        frontier = [point]
        while frontier:
            current = frontier.pop(0)
            if current in checked:
                continue
            checked.add(current)
            if self.is_walkable(current):
                return current
            for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                nxt = Point(current.x + dx, current.y + dy)
                if 0 <= nxt.x < GRID_WIDTH and 0 <= nxt.y < GRID_HEIGHT and nxt not in checked:
                    frontier.append(nxt)
        return None

    def backstab_tile(self, guard: Guard):
        dx, dy = guard.facing
        tile = Point(guard.pos.x - dx, guard.pos.y - dy)
        if not self.is_walkable(tile):
            return None
        if tile in self.occupied_guard_cells(exclude_guard_id=guard.guard_id):
            return None
        return tile

    def can_backstab(self, guard: Guard) -> bool:
        return self.backstab_tile(guard) == self.player

    def guard_chase_tiles(self, guard: Guard):
        blocked = self.occupied_guard_cells(exclude_guard_id=guard.guard_id)
        dx, dy = guard.facing
        behind = Point(guard.pos.x - dx, guard.pos.y - dy)
        left = Point(guard.pos.x - dy, guard.pos.y - dx)
        right = Point(guard.pos.x + dy, guard.pos.y + dx)

        ordered = [behind, left, right]
        result = []
        for tile in ordered:
            if self.is_walkable(tile) and tile not in blocked and tile not in result:
                result.append(tile)
        return result

    def find_guard_chase_path(self, guard: Guard):
        blocked = self.occupied_guard_cells(exclude_guard_id=guard.guard_id)
        vision = self.all_guard_vision_cells()
        best_path = []
        best_score = None

        for priority, tile in enumerate(self.guard_chase_tiles(guard)):
            path = self.find_safe_path(
                self.player,
                tile,
                blocked=blocked - {tile},
                avoid=vision - {tile},
            )
            if path or self.player == tile:
                score = (priority, len(path))
                if best_score is None or score < best_score:
                    best_score = score
                    best_path = path

        return best_path

    def direction_toward(self, start: Point, goal: Point, fallback=(0, 1)):
        dx = goal.x - start.x
        dy = goal.y - start.y
        if dx == 0 and dy == 0:
            return fallback
        if abs(dx) >= abs(dy):
            return (1 if dx > 0 else -1, 0)
        return (0, 1 if dy > 0 else -1)

    def perform_backstab(self, guard: Guard) -> None:
        guard.alive = False
        self.selected_guard_id = None
        self.player_path = []
        self.kill_flash_ticks = 8
        self.score += 120
        self.message = "Backstab successful. Target eliminated."

    def guard_vision_cells(self, guard: Guard):
        dx, dy = guard.facing
        if dx == dy == 0:
            return set()

        cells = set()
        for depth in range(1, 3):
            cx = guard.pos.x + dx * depth
            cy = guard.pos.y + dy * depth
            center = Point(cx, cy)
            if not self.is_walkable(center):
                break
            cells.add(center)

            if depth >= 2:
                side_offsets = [(dy, dx), (-dy, -dx)]
                for sx, sy in side_offsets:
                    flank = Point(cx + sx, cy + sy)
                    if self.is_walkable(flank):
                        cells.add(flank)
        return cells

    @staticmethod
    def manhattan(a: Point, b: Point) -> int:
        return abs(a.x - b.x) + abs(a.y - b.y)

    def draw(self) -> None:
        self.canvas.delete("all")
        self.draw_floor()
        self.draw_board()
        self.draw_route()
        self.draw_guard_vision()
        self.draw_shot_flash()
        self.draw_entities()
        self.draw_hud()

        if self.game_over:
            self.draw_end_screen("MISSION FAILED", DANGER_COLOR, "Press Enter or click to restart")
        elif self.victory:
            self.draw_end_screen("MISSION CLEARED", TARGET_COLOR, "Press Enter or click to play again")

    def draw_floor(self) -> None:
        self.canvas.create_rectangle(0, 0, WINDOW_WIDTH, WINDOW_HEIGHT, fill=BG_COLOR, outline="")
        for y in range(GRID_HEIGHT):
            for x in range(GRID_WIDTH):
                x1 = x * CELL_SIZE
                y1 = y * CELL_SIZE
                fill = FLOOR_COLOR if (x + y) % 2 == 0 else FLOOR_ACCENT
                self.canvas.create_rectangle(
                    x1,
                    y1,
                    x1 + CELL_SIZE,
                    y1 + CELL_SIZE,
                    fill=fill,
                    outline="#c7c6bc",
                )

    def draw_board(self) -> None:
        for y, row in enumerate(LAYOUT):
            for x, cell in enumerate(row):
                if cell != "#":
                    continue

                x1 = x * CELL_SIZE
                y1 = y * CELL_SIZE
                self.canvas.create_rectangle(
                    x1 + 3,
                    y1 + 3,
                    x1 + CELL_SIZE - 3,
                    y1 + CELL_SIZE - 3,
                    fill=WALL_COLOR,
                    outline="#203028",
                    width=2,
                )
                self.canvas.create_rectangle(
                    x1 + 7,
                    y1 + 7,
                    x1 + CELL_SIZE - 7,
                    y1 + CELL_SIZE - 7,
                    fill=CRATE_COLOR,
                    outline=CRATE_SHADOW,
                    width=2,
                )

    def draw_route(self) -> None:
        target = self.current_target_guard()
        destination = None
        if target:
            destination = self.backstab_tile(target)
        elif self.move_target is not None:
            destination = self.move_target

        if destination is None:
            return

        points = [self.player] + self.player_path
        if len(points) < 2:
            if target:
                self.draw_target_ring(target.pos, TARGET_COLOR)
                if destination:
                    self.draw_target_ring(destination, SUCCESS_COLOR)
            else:
                self.draw_target_ring(destination, ACCENT_COLOR)
            return

        line_points = []
        for point in points:
            line_points.extend([
                point.x * CELL_SIZE + CELL_SIZE // 2,
                point.y * CELL_SIZE + CELL_SIZE // 2,
            ])

        self.canvas.create_line(
            *line_points,
            fill=ROUTE_COLOR,
            width=6,
            smooth=True,
        )
        if target:
            self.draw_target_ring(target.pos, TARGET_COLOR)
            if destination:
                self.draw_target_ring(destination, SUCCESS_COLOR)
        else:
            self.draw_target_ring(destination, ACCENT_COLOR)

    def draw_target_ring(self, point: Point, color: str) -> None:
        x1 = point.x * CELL_SIZE + 6
        y1 = point.y * CELL_SIZE + 6
        self.canvas.create_oval(
            x1,
            y1,
            x1 + CELL_SIZE - 12,
            y1 + CELL_SIZE - 12,
            outline=color,
            width=4,
        )

    def draw_shot_flash(self) -> None:
        if not self.shot_flash:
            return
        start = self.shot_flash["start"]
        end = self.shot_flash["end"]
        self.canvas.create_line(
            start.x * CELL_SIZE + CELL_SIZE // 2,
            start.y * CELL_SIZE + CELL_SIZE // 2,
            end.x * CELL_SIZE + CELL_SIZE // 2,
            end.y * CELL_SIZE + CELL_SIZE // 2,
            fill=DANGER_COLOR,
            width=5,
        )

    def draw_guard_vision(self) -> None:
        for guard in self.guards:
            if not guard.alive:
                continue
            for cell in self.guard_vision_cells(guard):
                x1 = cell.x * CELL_SIZE + 8
                y1 = cell.y * CELL_SIZE + 8
                self.canvas.create_rectangle(
                    x1,
                    y1,
                    x1 + CELL_SIZE - 16,
                    y1 + CELL_SIZE - 16,
                    fill=VISION_COLOR,
                    outline="",
                    stipple="gray25",
                )

    def draw_entities(self) -> None:
        for guard in self.guards:
            if not guard.alive:
                continue
            self.draw_guard(guard)

        self.draw_player()

    def draw_player(self) -> None:
        px = self.player.x * CELL_SIZE + CELL_SIZE // 2
        py = self.player.y * CELL_SIZE + CELL_SIZE // 2
        if self.safe_ticks > 0:
            self.canvas.create_oval(px - 23, py - 23, px + 23, py + 23, fill="#69c7ff", outline="", stipple="gray25")
        self.canvas.create_oval(px - 16, py - 16, px + 16, py + 16, fill=PLAYER_COLOR, outline="", width=0)
        self.canvas.create_oval(px - 8, py - 18, px + 8, py - 2, fill="#f1c19b", outline="")
        self.canvas.create_arc(px - 10, py - 8, px + 10, py + 16, start=200, extent=140, style=tk.ARC, outline=PLAYER_ACCENT, width=3)
        self.canvas.create_line(px + 2, py - 2, px + 18, py - 18, fill="#d8d8d8", width=4)

    def draw_guard(self, guard: Guard) -> None:
        gx = guard.pos.x * CELL_SIZE + CELL_SIZE // 2
        gy = guard.pos.y * CELL_SIZE + CELL_SIZE // 2
        self.canvas.create_oval(gx - 15, gy - 15, gx + 15, gy + 15, fill=GUARD_COLOR, outline="")
        self.canvas.create_oval(gx - 7, gy - 17, gx + 7, gy - 3, fill="#f0c7a8", outline="")
        self.canvas.create_arc(gx - 9, gy - 8, gx + 9, gy + 14, start=200, extent=140, style=tk.ARC, outline=GUARD_ACCENT, width=3)

        dx, dy = guard.facing
        self.canvas.create_line(
            gx,
            gy,
            gx + dx * 18,
            gy + dy * 18,
            fill=DANGER_COLOR,
            width=4,
            arrow=tk.LAST,
        )

    def draw_health_bar(self, x: int, y: int, width: int, height: int, current: int, maximum: int, fill: str) -> None:
        self.canvas.create_rectangle(x, y, x + width, y + height, fill="#1f2933", outline="#5f6d7a", width=1)
        ratio = 0 if maximum <= 0 else max(0.0, min(1.0, current / maximum))
        if ratio > 0:
            self.canvas.create_rectangle(x + 2, y + 2, x + 2 + int((width - 4) * ratio), y + height - 2, fill=fill, outline="")

    def draw_hud(self) -> None:
        top = GRID_HEIGHT * CELL_SIZE
        self.canvas.create_rectangle(0, top, WINDOW_WIDTH, WINDOW_HEIGHT, fill="#08111b", outline="")
        self.canvas.create_text(
            16,
            top + 22,
            anchor="w",
            text="Shadow Strike",
            fill=TEXT_COLOR,
            font=("Consolas", 22, "bold"),
        )
        self.draw_health_bar(210, top + 14, 170, 18, self.player_health, PLAYER_MAX_HEALTH, SUCCESS_COLOR)
        self.canvas.create_text(
            390,
            top + 23,
            anchor="w",
            text=f"Health: {self.player_health}/{PLAYER_MAX_HEALTH}",
            fill=TEXT_COLOR,
            font=("Consolas", 11, "bold"),
        )
        self.canvas.create_text(
            16,
            top + 54,
            anchor="w",
            text=f"Score: {self.score}    Lives: {self.lives}    Wave: {self.wave}",
            fill=ACCENT_COLOR,
            font=("Consolas", 13, "bold"),
        )
        guards_left = sum(1 for guard in self.guards if guard.alive)
        self.canvas.create_text(
            16,
            top + 82,
            anchor="w",
            text=f"Guards Left: {guards_left}    Click tiles to move    Click guards to backstab",
            fill=TARGET_COLOR,
            font=("Consolas", 12, "bold"),
        )
        self.canvas.create_text(
            16,
            top + 104,
            anchor="w",
            text=self.message,
            fill=TEXT_COLOR,
            font=("Consolas", 11),
        )
        self.draw_pause_button(top)

    def draw_pause_button(self, top: int) -> None:
        x1, y1, x2, y2 = self.pause_button_rect(top)
        fill = "#394655" if self.is_paused else "#20364d"
        label = "Resume" if self.is_paused else "Pause"
        self.canvas.create_rectangle(x1, y1, x2, y2, fill=fill, outline=ACCENT_COLOR, width=2)
        self.canvas.create_text((x1 + x2) // 2, (y1 + y2) // 2, text=label, fill=TEXT_COLOR, font=("Consolas", 11, "bold"))

    def pause_button_rect(self, top: int):
        return (WINDOW_WIDTH - 108, top + 18, WINDOW_WIDTH - 18, top + 52)

    def in_pause_button(self, x: int, y: int) -> bool:
        top = GRID_HEIGHT * CELL_SIZE
        x1, y1, x2, y2 = self.pause_button_rect(top)
        return x1 <= x <= x2 and y1 <= y <= y2

    def draw_title(self) -> None:
        self.canvas.delete("all")
        self.draw_floor()
        self.canvas.create_rectangle(28, 68, WINDOW_WIDTH - 28, WINDOW_HEIGHT - 42, fill="#0c1824", outline=ACCENT_COLOR, width=2)
        self.canvas.create_text(
            WINDOW_WIDTH // 2,
            128,
            text="SHADOW STRIKE",
            fill=TEXT_COLOR,
            font=("Consolas", 28, "bold"),
        )
        self.canvas.create_text(
            WINDOW_WIDTH // 2,
            166,
            text="Top-Down AI Maze Assassin",
            fill=ACCENT_COLOR,
            font=("Consolas", 15, "bold"),
        )
        self.canvas.create_text(
            WINDOW_WIDTH // 2,
            252,
            text="Five guards roam randomly through the maze.",
            fill=TEXT_COLOR,
            font=("Consolas", 13),
        )
        self.canvas.create_text(
            WINDOW_WIDTH // 2,
            282,
            text="Click a tile to move with A*. Click a guard to route behind them for a backstab.",
            fill=TARGET_COLOR,
            font=("Consolas", 12),
        )
        self.canvas.create_text(
            WINDOW_WIDTH // 2,
            324,
            text="If guards see you, they shoot. Attack from behind and clear 3 waves to win.",
            fill=DANGER_COLOR,
            font=("Consolas", 12),
        )
        self.canvas.create_text(
            WINDOW_WIDTH // 2,
            398,
            text="Controls: Mouse click to move/attack    Pause button or P    Enter start/restart    R reset",
            fill=TEXT_COLOR,
            font=("Consolas", 12),
        )
        self.canvas.create_text(
            WINDOW_WIDTH // 2,
            456,
            text="Original student project inspired by stealth-maze gameplay.",
            fill=ACCENT_COLOR,
            font=("Consolas", 11),
        )
        self.canvas.create_text(
            WINDOW_WIDTH // 2,
            530,
            text="Click anywhere or press Enter to begin",
            fill=TARGET_COLOR,
            font=("Consolas", 14, "bold"),
        )




if __name__ == "__main__":
    ShadowStrikeGame().run()
