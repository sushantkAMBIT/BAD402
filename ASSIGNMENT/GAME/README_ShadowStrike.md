# 1. Name of the Game

`Shadow Strike: AI Maze Assassin`

# 2. AI Methods Used

- `A* Pathfinding`
  Used for shortest-path movement when the player clicks a destination tile.

- `Stealth-Aware Path Planning`
  The route system tries to choose paths that avoid guard vision tiles whenever possible.

- `Target Lock and Dynamic Replanning`
  When a guard is clicked, the assassin keeps tracking that same guard and recalculates the route as the guard moves.

- `Enemy Vision and Facing Logic`
  Guards turn toward the player and detect or shoot when the player enters their visible area.

- `Random Patrol Movement`
  Guards move unpredictably through the maze, which makes the stealth challenge different each time.

# 3. Brief Explanation of the Game

`Shadow Strike` is a top-down stealth maze game. The player controls an assassin inside a maze filled with moving guards.

- Clicking any free tile makes the player move there using the shortest path.
- Clicking a guard locks that target, and the assassin keeps chasing that guard until the player clicks somewhere else.
- Guards can shoot the player if they see him.
- The player must move carefully and kill guards from behind.
- The game includes health, lives, multiple waves, and pause support.

This game demonstrates AI concepts through pathfinding, target tracking, enemy vision, and safe route selection.

# 4. How to Run

Make sure Python is installed, then run:

```bash
python shadow_strike_assassin.py
```

# Controls

- `Mouse Click on Tile` - move to that location
- `Mouse Click on Guard` - lock target and chase for backstab
- `P` or `Pause Button` - pause or resume the game
- `Enter` - start or restart
- `R` - reset the game
