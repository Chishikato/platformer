"""
Data persistence functions for save files and leaderboards.
"""
import os
import json
import time

from config.constants import LEADERBOARD_FILE, SAVE_FILE


UPGRADE_INFO = {
    "speed": {"name": "Agility", "base_cost": 50, "cost_mult": 1.5, "max": 10, "desc": "+5% Move Speed"},
    "jump":  {"name": "Rocket Boots", "base_cost": 60, "cost_mult": 1.6, "max": 10, "desc": "+3% Jump Height"},
    "hp":    {"name": "Iron Heart", "base_cost": 200, "cost_mult": 2.0, "max": 5,  "desc": "+1 Max HP"},
    "slam":  {"name": "Graviton", "base_cost": 80, "cost_mult": 1.4, "max": 10, "desc": "-8% Slam/Dash Cooldown"}
}


def ensure_save_dir():
    save_dir = os.path.dirname(SAVE_FILE)
    if not os.path.exists(save_dir):
        try:
            os.makedirs(save_dir)
        except OSError as e:
            print(f"Error creating save directory: {e}")


def load_leaderboard():
    ensure_save_dir()
    if not os.path.exists(LEADERBOARD_FILE):
        return {"single": [], "coop": [], "versus": []}
    try:
        with open(LEADERBOARD_FILE, "r") as f:
            data = json.load(f)
        for key in ("single", "coop", "versus"):
            data.setdefault(key, [])
        return data
    except Exception:
        return {"single": [], "coop": [], "versus": []}


def save_leaderboard(lb):
    ensure_save_dir()
    try:
        with open(LEADERBOARD_FILE, "w") as f:
            json.dump(lb, f, indent=2)
    except Exception:
        pass


def add_score(lb, mode, name, score):
    entry = {"name": name, "score": int(score), "time": time.time()}
    lb[mode].append(entry)
    lb[mode] = sorted(lb[mode], key=lambda e: e["score"], reverse=True)[:10]
    save_leaderboard(lb)


def load_save_data():
    ensure_save_dir()
    data = {
        "credits": 0.0,
        "upgrades": {"speed": 0, "jump": 0, "hp": 0, "slam": 0}
    }
    if os.path.exists(SAVE_FILE):
        try:
            with open(SAVE_FILE, "r") as f:
                saved = json.load(f)
                if "coins" in saved:
                    data["credits"] = float(saved["coins"])
                else:
                    data["credits"] = float(saved.get("credits", 0))
                    
                if "upgrades" in saved:
                    for k in data["upgrades"]:
                        data["upgrades"][k] = saved["upgrades"].get(k, 0)
        except Exception:
            pass
    return data


def save_save_data(data):
    ensure_save_dir()
    try:
        with open(SAVE_FILE, "w") as f:
            json.dump(data, f, indent=2)
    except Exception as e:
        print(f"Failed to save data: {e}")


def get_upgrade_cost(key, current_level):
    info = UPGRADE_INFO[key]
    if current_level >= info["max"]: 
        return 999999
    return int(info["base_cost"] * (info["cost_mult"] ** current_level))
