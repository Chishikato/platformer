# Get Slimed

**Get Slimed** is a vertical platformer written in Python with Pygame.  
You play as a slime on an adventure (or a fever dream lol)

---

## Features

- Single-player endless run
- Local 2-player modes (co-op and versus)
- Optional LAN multiplayer with UDP host discovery
- Shop with permanent upgrades (speed, jump, HP, slam/dash cooldown)
- Boss arena with a multi-phase Necromancer fight and portal system
- Parallax backgrounds, particles, and flashy retro UI
- Persistent save data and leaderboards stored in `data/save/`

---

## Controls

### Single Player / Networked Local Player

- **Move left**: `A` or `←`
- **Move right**: `D` or `→`
- **Jump**: `W`, `↑`, or `Space`
- **Use skill (slam / dash)**: `Left Shift`, `S`, or `↓`
- **Pause / exit run**: `ESC`

> Keybinds can be changed in the in-game settings menu.

---

### Local 2-Player (Play Local mode)

**Player 1**

- **Left**: `A`
- **Right**: `D`
- **Jump**: `W` or `Space`
- **Skill**: `Left Shift` or `S`

**Player 2**

- **Left**: `J`
- **Right**: `L`
- **Jump**: `I`
- **Skill**: `Right Shift` or `K`

---

## How to Run

1. Install **Python 3.8+**.
2. Install Pygame:

   ```bash
   pip install pygame-ce

Make sure platformer.py and the data/ folder stay in the same directory.

From that directory, run:

    python platformer.py

That’s it! The main menu will walk you through single-player, local co-op/versus, and LAN play.
