"""
Game Session - main gameplay loop and game state management.
"""
import os
import random
import math
import pygame

from config.constants import (
    VIRTUAL_W, VIRTUAL_H, GROUND_LEVEL, TILE_SIZE,
    COL_BG, COL_TEXT, COL_ACCENT_1, COL_ACCENT_2, COL_ACCENT_3, COL_UI_BORDER,
    MODE_SINGLE, MODE_COOP, MODE_VERSUS, MODE_WINDOW, MODE_FULLSCREEN, MODE_BORDERLESS,
    ROLE_LOCAL_ONLY, ROLE_HOST, ROLE_CLIENT,
    SLAM_BASE_RADIUS, SLAM_RADIUS_PER_HEIGHT,
    get_asset_path
)
from core.helpers import clamp, draw_text_shadow, draw_panel
from core.data_persistence import load_save_data, save_save_data, add_score
from entities.player import Player
from entities.enemy import Enemy
from entities.level import LevelManager
from entities.boss import NecromancerBoss
from effects.particles import particles, floating_texts, Particle, FloatingText, spawn_dust, spawn_slam_impact, spawn_credit_text
from effects.background import draw_gradient_background
from assets.loaders import load_boss_sprites
from boss_room.boss_room import BossRoom


def start_game(settings, window, canvas, font_small, font_med, font_big, 
               player1_sprites, player2_sprites, enemy_sprite_dict, tile_surf, 
               wall_surf, lb, network, net_role, mode, mp_name_hint=None, 
               local_two_players=False, bg_obj=None, p1_ability="Slam", p2_ability="Slam"):
    """Main game session loop - handles gameplay, rendering, and game state."""
    
    clock = pygame.time.Clock()
    
    # --- MUSIC LOGIC ---
    pygame.mixer.music.stop()
    
    GAME_BGM_PATH = get_asset_path("data", "sfx", "pck404_lets_play.ogg")
    BOSS_BGM_PATH = get_asset_path("data", "sfx", "pck404_futuristic_run.wav")
    
    if os.path.exists(GAME_BGM_PATH):
        try:
            pygame.mixer.music.load(GAME_BGM_PATH)
            pygame.mixer.music.set_volume(settings.music_volume * settings.master_volume)
            pygame.mixer.music.play(-1)
        except Exception as e:
            print(f"Error loading Game BGM: {e}")
    else:
        print(f"Game BGM not found at: {GAME_BGM_PATH}")

    local_data = load_save_data()
    local_stats = local_data["upgrades"]

    game_seed = 0
    if net_role == ROLE_HOST or net_role == ROLE_LOCAL_ONLY:
        game_seed = random.randint(1, 999999)
        random.seed(game_seed)
    else:
        game_seed = 0 
        random.seed(game_seed)

    is_client = (net_role == ROLE_CLIENT)
    level = LevelManager(tile_surf, enemy_sprite_dict, game_seed, is_client=is_client) 
    particles.clear()
    floating_texts.clear()
    
    # Boss fight initialization
    boss_sprites = load_boss_sprites()
    in_boss_room = False
    boss_room = None
    boss = None
    boss_defeated = False
    
    # Start on the left, on ground level
    spawn_x = 100
    spawn_y = GROUND_LEVEL - 60
    
    stats_p1 = local_stats if (net_role != ROLE_CLIENT) else None 
    stats_p2 = local_stats if (net_role != ROLE_HOST) else None
    if net_role == ROLE_LOCAL_ONLY:
        stats_p1 = local_stats
        stats_p2 = local_stats

    # Pass sprites to Player Constructor
    p1 = Player(COL_ACCENT_1, spawn_x, spawn_y, stats_p1, sprite_dict=player1_sprites, ability=p1_ability)
    p2 = Player(COL_ACCENT_2, spawn_x - 30, spawn_y, stats_p2, sprite_dict=player2_sprites, ability=p2_ability)
    base_x = spawn_x

    if net_role == ROLE_CLIENT: local_player, remote_player = p2, p1
    else: local_player, remote_player = p1, p2
    
    p1_local = (net_role in (ROLE_HOST, ROLE_LOCAL_ONLY))
    p2_local = (net_role == ROLE_CLIENT) or (net_role == ROLE_LOCAL_ONLY and local_two_players)
    use_p1 = True
    use_p2 = (mode != MODE_SINGLE)

    # Initial Camera Setup
    cam_x = p1.x - 200
    cam_y = 0
    cam_x_p1, cam_x_p2 = cam_x, cam_x
    cam_y_p1, cam_y_p2 = cam_y, cam_y
    
    view1_surf = pygame.Surface((VIRTUAL_W, VIRTUAL_H // 2))
    view2_surf = pygame.Surface((VIRTUAL_W, VIRTUAL_H // 2))

    distance, elapsed = 0.0, 0.0
    running, game_over = True, False
    winner_text = ""
    p1_distance, p2_distance = 0.0, 0.0
    p1_orbs, p2_orbs = 0, 0
    lb_key = {MODE_SINGLE: "single", MODE_COOP: "coop", MODE_VERSUS: "versus"}[mode]
    screen_shake_timer = 0.0
    session_credits = 0.0
    waiting_for_seed = (net_role == ROLE_CLIENT)
    
    # Tutorial system
    tutorial_active = True
    tutorial_moved = False
    tutorial_linger_timer = 0.0
    tutorial_linger_duration = 3.0

    # === DYNAMIC KEYBIND HELPER ===
    kb = settings.keybinds
    def get_p1_inputs(keys_pressed):
        return (
            keys_pressed[kb["p1_left"]],
            keys_pressed[kb["p1_right"]],
            keys_pressed[kb["p1_jump"]],
            keys_pressed[kb["p1_slam"]]
        )
        
    def get_p2_inputs(keys_pressed):
        return (
            keys_pressed[kb["p2_left"]],
            keys_pressed[kb["p2_right"]],
            keys_pressed[kb["p2_jump"]],
            keys_pressed[kb["p2_slam"]]
        )

    def render_scene(target_surf, cam_x_now, cam_y_now, highlight_player=None):
        draw_cam_x = cam_x_now
        draw_cam_y = cam_y_now

        # 1. DRAW BACKGROUND & ENVIRONMENT
        if in_boss_room and boss_room:
            draw_cam_x = 0
            draw_cam_y = 0
            
            boss_room.draw(target_surf)
            
            # Draw boss
            if boss:
                boss.draw(target_surf)
                
                if boss.alive:
                    bar_total_width = 300
                    bar_height = 20
                    screen_center_x = target_surf.get_width() // 2
                    
                    start_x = screen_center_x - bar_total_width // 2
                    start_y = 25
                    
                    label_surf = font_med.render("NECROMANCER", False, (255, 50, 50))
                    target_surf.blit(label_surf, (screen_center_x - label_surf.get_width()//2, start_y - 22))
                    
                    pygame.draw.rect(target_surf, (40, 0, 0), (start_x, start_y, bar_total_width, bar_height))
                    pygame.draw.rect(target_surf, (150, 0, 0), (start_x, start_y, bar_total_width, bar_height), 2)
                    
                    if boss.max_hp > 0:
                        segment_width = bar_total_width / boss.max_hp
                        
                        for i in range(boss.hp):
                            seg_x = start_x + (i * segment_width)
                            draw_w = segment_width - 2
                            if draw_w < 1: draw_w = 1
                            pygame.draw.rect(target_surf, (255, 0, 0), (seg_x + 1, start_y + 2, draw_w, bar_height - 4))

        else:
            # Normal Level Draw
            if bg_obj:
                bg_obj.draw(target_surf, draw_cam_x)
            else:
                draw_gradient_background(target_surf, level.current_stage)
            
            if waiting_for_seed:
                txt = font_med.render("SYNCING MAP DATA...", False, COL_ACCENT_1)
                target_surf.blit(txt, txt.get_rect(center=(target_surf.get_width()//2, target_surf.get_height()//2)))
                return

            level.draw(target_surf, draw_cam_x, draw_cam_y)

        # DRAW PARTICLES
        for p in particles: p.draw(target_surf, draw_cam_x, draw_cam_y)

        # HELPER: DRAW FLOATING COOLDOWN BARS
        def draw_floating_cd(pl):
            cd_val = 0.0
            max_cd = 1.0
            
            if pl.ability_type == "Slam":
                cd_val = pl.slam_cooldown
                max_cd = pl.slam_cd_val
            elif pl.ability_type == "Dash":
                cd_val = pl.dash_cooldown
                max_cd = pl.dash_cd_val

            if cd_val > 0:
                sx = pl.x - draw_cam_x
                sy = pl.y - draw_cam_y
                bar_w = pl.w
                bar_h = 4
                bar_y = sy - 8 
                pygame.draw.rect(target_surf, (0,0,0), (sx, bar_y, bar_w, bar_h))
                ratio = cd_val / max_cd
                fill_w = int(bar_w * ratio)
                pygame.draw.rect(target_surf, (200, 200, 200), (sx, bar_y, fill_w, bar_h))

        # DRAW PLAYERS
        if use_p1 and p1.alive: 
            p1.draw(target_surf, draw_cam_x, draw_cam_y)
            draw_floating_cd(p1)

        if use_p2 and p2.alive: 
            p2.draw(target_surf, draw_cam_x, draw_cam_y)
            draw_floating_cd(p2)

        # DRAW FLOATING TEXT
        for ft in floating_texts: ft.draw(target_surf, draw_cam_x, draw_cam_y)
        
        p1_total = int(p1_distance / 10 + p1_orbs * 100)
        p2_total = int(p2_distance / 10 + p2_orbs * 100)
        
        if mode == MODE_COOP:
            combined_score = p1_total + p2_total
        
        # HUD Panel
        draw_panel(target_surf, pygame.Rect(5, 5, 120, 50), color=(0, 0, 0, 100))
        target_surf.blit(font_small.render(f"DIST: {int(distance/10)}m", False, COL_TEXT), (10, 10))
        target_surf.blit(font_small.render(f"STAGE: {level.current_stage}", False, COL_TEXT), (10, 28))
        
        hud_y = 65
        
        def draw_player_hud(pl, name, y_pos, is_highlighted, show_score=True):
            panel_col = (30, 30, 50) if is_highlighted else (10, 10, 20)
            draw_panel(target_surf, pygame.Rect(5, y_pos, 150, 24), color=panel_col)
            target_surf.blit(font_small.render(name, False, COL_TEXT), (10, y_pos+4))

            bar_x = 40
            bar_y = y_pos + 6
            total_bar_w = 100
            bar_h = 10
            pygame.draw.rect(target_surf, (40, 40, 40), (bar_x, bar_y, total_bar_w, bar_h))
            
            hp_col = (255, 50, 50) if pl.hp <= 1 else (50, 255, 50)
            seg_w = (total_bar_w / pl.max_hp) if pl.max_hp > 0 else total_bar_w

            for i in range(pl.hp):
                rect_x = bar_x + (i * seg_w)
                rect_w = seg_w - 1 if (i < pl.max_hp - 1) else seg_w
                if rect_w > 0:
                    pygame.draw.rect(target_surf, hp_col, (rect_x, bar_y, rect_w, bar_h))

            if show_score:
                if mode == MODE_COOP:
                    score_val = combined_score
                else:
                    score_val = p1_total if pl == p1 else p2_total
                score_str = f"PTS {score_val}"
                score_surf = font_small.render(score_str, False, COL_ACCENT_3)
                score_x = target_surf.get_width() - score_surf.get_width() - 15
                score_bg_rect = pygame.Rect(score_x - 5, y_pos, score_surf.get_width() + 10, 24)
                draw_panel(target_surf, score_bg_rect, color=(0, 0, 0, 150))
                target_surf.blit(score_surf, (score_x, y_pos + 4))

        if use_p1:
            draw_player_hud(p1, "P1", hud_y, highlight_player == 1, show_score=True)
            hud_y += 30 
        if use_p2:
            draw_player_hud(p2, "P2", hud_y, highlight_player == 2, show_score=(mode != MODE_COOP))

    # ========== MAIN GAME LOOP ==========
    while running:
        dt = clock.tick(settings.target_fps) / 1000.0
        dt = min(dt, 0.05)

        if not game_over and not waiting_for_seed: elapsed += dt
        
        # Update tutorial state
        if tutorial_active and tutorial_moved:
            tutorial_linger_timer += dt
            if tutorial_linger_timer >= tutorial_linger_duration:
                tutorial_active = False
        
        for p in particles: p.update(dt)
        particles[:] = [p for p in particles if p.life > 0]
        for ft in floating_texts: ft.update(dt)
        floating_texts[:] = [ft for ft in floating_texts if ft.life > 0]
        
        shake_x, shake_y = 0, 0
        if screen_shake_timer > 0:
            screen_shake_timer -= dt
            if screen_shake_timer > 0:
                shake_x = random.randint(-3, 3)
                shake_y = random.randint(-3, 3)

        for event in pygame.event.get():
            if event.type == pygame.QUIT: running = False; return
            elif event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                if net_role != ROLE_LOCAL_ONLY:
                    network.send_lobby_exit()
                running = False
                return
            elif event.type == pygame.VIDEORESIZE: window = pygame.display.set_mode(event.size, pygame.RESIZABLE)

        if net_role != ROLE_LOCAL_ONLY and not network.connected:
            if not game_over:
                game_over = True
                winner_text = "OPPONENT DISCONNECTED"
                running = True

        keys = pygame.key.get_pressed()
        if net_role != ROLE_LOCAL_ONLY:
            network.poll_remote_state()
            flag, text = network.consume_remote_game_over()
            if flag and not game_over: game_over = True; winner_text = text
            
            if network.check_lobby_exit():
                running = False
                return

        if not game_over:
            if net_role != ROLE_LOCAL_ONLY:
                # 1. SEND LOCAL STATE
                lt = int(p1_distance/10 + p1_orbs * 100) if local_player is p1 else int(p2_distance/10 + p2_orbs * 100)
                send_seed = game_seed if net_role == ROLE_HOST else 0
                
                network.send_local_state(
                    local_player.x, local_player.y, local_player.alive, lt, send_seed, 
                    local_player.hp, local_player.vx, local_player.vy, local_player.facing_right,
                    local_player.max_hp, local_player.slam_active, local_player.dash_active,
                    local_player.invul_timer, 
                    local_player.flash_on_invul,
                    local_player.current_action, local_player.frame_index
                )
                
                # 2. RECEIVE REMOTE STATE
                network.poll_remote_state()
                rstate = network.get_remote_state()
                
                dmg_taken = network.check_damage_received()
                if dmg_taken > 0 and local_player.alive:
                    local_player.take_damage(dmg_taken)

                target_x = rstate["x"]
                target_y = rstate["y"]
                
                dist_x = target_x - remote_player.x
                dist_y = target_y - remote_player.y
                
                if abs(dist_x) > 50 or abs(dist_y) > 50:
                    remote_player.x = target_x
                    remote_player.y = target_y
                else:
                    remote_player.x += dist_x * 0.4
                    remote_player.y += dist_y * 0.4

                remote_player.alive = rstate["alive"]
                remote_player.hp = rstate.get("hp", 3)
                remote_player.max_hp = rstate.get("max_hp", 3)
                remote_player.vx = rstate.get("vx", 0.0)
                remote_player.vy = rstate.get("vy", 0.0)
                remote_player.facing_right = rstate.get("facing_right", True)
                
                was_slamming = remote_player.slam_active
                is_slamming = rstate.get("slam_active", False)
                if was_slamming and not is_slamming:
                     spawn_slam_impact(remote_player.x + remote_player.w/2, remote_player.y + remote_player.h, 100)

                remote_player.slam_active = is_slamming
                remote_player.dash_active = rstate.get("dash_active", False)
                
                if remote_player.slam_active or remote_player.dash_active:
                    remote_player.trail.append([remote_player.x, remote_player.y, 200])

                for t in remote_player.trail:
                    t[2] -= 1000 * dt
                remote_player.trail = [t for t in remote_player.trail if t[2] > 0]

                remote_player.invul_timer = rstate.get("invul_timer", 0.0)
                remote_player.flash_on_invul = rstate.get("flash_on_invul", False)

                remote_player.current_action = rstate.get("action", "idle")
                remote_player.frame_index = rstate.get("frame", 0)
                
                remote_score = rstate.get("score", 0)
                if remote_player is p1:
                    p1_orbs = remote_score // 100
                    p1_distance = (remote_score % 100) * 10
                else:
                    p2_orbs = remote_score // 100
                    p2_distance = (remote_score % 100) * 10
                
                if waiting_for_seed and rstate["seed"] != 0:
                    game_seed = rstate["seed"]
                    level = LevelManager(tile_surf, enemy_sprite_dict, game_seed, is_client=True)
                    waiting_for_seed = False

            if not waiting_for_seed:
                distance = max(distance, p1_distance, p2_distance)
                difficulty = clamp(distance / 5000.0, 0.0, 1.0)
                
                if net_role == ROLE_HOST:
                    client_hits = network.get_remote_hits()
                    for eid, dmg in client_hits:
                        target_e = next((e for e in level.enemies if getattr(e, 'id', -1) == eid), None)
                        if target_e and target_e.alive:
                            died = target_e.take_damage(dmg)
                            if died:
                                level.spawn_credit(target_e.x, target_e.y, 1.0)
                            else:
                                spawn_dust(target_e.x + target_e.w/2, target_e.y, 3, (255, 100, 100))
                    
                    for e in level.enemies:
                        network.send_enemy_update(
                            getattr(e, 'id', -1), 
                            e.x, e.y, 
                            e.facing_right,
                            int(e.hp), 
                            not e.alive
                        )
                
                elif net_role == ROLE_CLIENT:
                    enemy_updates = network.get_enemy_updates()
                    for eid, ex, ey, facing, hp, is_dead in enemy_updates:
                        existing = next((e for e in level.enemies if getattr(e, 'id', -1) == eid), None)
                        
                        if existing:
                            existing.x = ex
                            existing.y = ey
                            existing.facing_right = facing
                            
                            if hp < existing.hp:
                                existing.current_action = "hurt"
                                existing.invul_timer = 0.2
                                spawn_dust(existing.x + existing.w/2, existing.y, 3, (255, 100, 100))
                            
                            existing.hp = hp
                            
                            if is_dead and existing.alive:
                                existing.alive = False
                                spawn_dust(existing.x + existing.w/2, existing.y, 5, (150, 150, 150))
                        else:
                            if not is_dead:
                                new_e = Enemy(level.enemy_sprites, ex, ey)
                                new_e.id = eid
                                new_e.facing_right = facing
                                new_e.hp = hp
                                new_e.max_hp = hp
                                level.enemies.append(new_e)
                                level.next_enemy_id = max(level.next_enemy_id, eid + 1)
                    
                    level.enemies = [e for e in level.enemies if e.alive]

                # --- BOSS ROOM PORTAL CHECK ---
                if not in_boss_room and level.portal and not game_over:
                    trigger_boss_fight = False

                    if net_role == ROLE_HOST:
                        if local_player.alive and level.portal.check_collision(local_player.rect()):
                            trigger_boss_fight = True
                        elif remote_player.alive and level.portal.check_collision(remote_player.rect()):
                            trigger_boss_fight = True
                    
                    elif net_role == ROLE_LOCAL_ONLY:
                        if (use_p1 and p1.alive and level.portal.check_collision(p1.rect())) or \
                           (use_p2 and p2.alive and level.portal.check_collision(p2.rect())):
                            trigger_boss_fight = True

                    elif net_role == ROLE_CLIENT:
                        rb_state = network.get_boss_state()
                        if rb_state["active"]:
                            trigger_boss_fight = True

                    if trigger_boss_fight:
                        in_boss_room = True
                        boss_room = BossRoom(tile_surf)
                        boss = NecromancerBoss(boss_sprites, boss_room.width, boss_room.height, boss_room.platforms)
                        
                        local_player.x = boss_room.width // 2 - local_player.w // 2
                        local_player.y = boss_room.height - 150
                        local_player.vx = 0
                        local_player.vy = 0

                        if os.path.exists(BOSS_BGM_PATH):
                            try:
                                pygame.mixer.music.stop()
                                pygame.mixer.music.load(BOSS_BGM_PATH)
                                pygame.mixer.music.set_volume(settings.music_volume * settings.master_volume)
                                pygame.mixer.music.play(-1)
                            except Exception as e:
                                print(f"Error loading Boss BGM: {e}")

                # --- BOSS ROOM UPDATE ---
                if in_boss_room and boss_room:
                    boss_room.update(dt)
                    
                    if boss:
                        if net_role != ROLE_CLIENT:
                            targets = []
                            if net_role == ROLE_LOCAL_ONLY:
                                if use_p1 and p1.alive: targets.append(p1)
                                if use_p2 and p2.alive: targets.append(p2)
                            else:
                                if local_player.alive: targets.append(local_player)
                                if remote_player.alive: targets.append(remote_player)
                            
                            boss_target_x = boss_room.width // 2
                            boss_target_y = boss_room.height // 2
                            boss_target_rect = pygame.Rect(0,0,0,0)

                            if targets:
                                best_target = min(targets, key=lambda p: math.hypot(p.x - boss.x, p.y - boss.y))
                                boss_target_x = best_target.x + best_target.w // 2
                                boss_target_y = best_target.y + best_target.h // 2
                                boss_target_rect = best_target.rect()
                            
                            boss.update(dt, boss_target_x, boss_target_y, boss_target_rect)

                        else:
                            rb_state = network.get_boss_state()
                            boss.hp = rb_state["hp"]
                            if not rb_state["dead"]:
                                boss.x += (rb_state["x"] - boss.x) * 0.2
                                boss.y += (rb_state["y"] - boss.y) * 0.2
                                if boss.current_action != rb_state["action"]:
                                    boss.current_action = rb_state["action"]
                                    boss.frame_index = rb_state["frame"]
                                    if boss.current_action == "cast" and boss.frame_index == 0:
                                        boss._attack_magic_arrows(local_player.x, local_player.y)
                                    if boss.current_action == "attack1" and boss.frame_index == 0:
                                        boss._attack_platform_fire()
                            
                            boss.update_visuals_only(dt)

                        # DAMAGE LOGIC
                        if boss.alive:
                            players_to_check = []
                            
                            if net_role == ROLE_LOCAL_ONLY:
                                if use_p1 and p1.alive: players_to_check.append(p1)
                                if use_p2 and p2.alive: players_to_check.append(p2)
                            elif net_role == ROLE_HOST:
                                if local_player.alive: players_to_check.append(local_player)
                                if remote_player.alive: players_to_check.append(remote_player)

                            for pl in players_to_check:
                                took_damage = False
                                
                                for proj in boss.projectiles[:]:
                                    p_rect = pygame.Rect(proj["x"]-4, proj["y"]-4, 8, 8)
                                    if p_rect.colliderect(pl.rect()):
                                        if net_role != ROLE_CLIENT:
                                            boss.projectiles.remove(proj)
                                        took_damage = True
                                        break
                                
                                if not took_damage:
                                    if boss.check_platform_fire_damage(pl.rect()):
                                        if not hasattr(pl, 'fire_timer'): pl.fire_timer = 0
                                        pl.fire_timer -= dt
                                        if pl.fire_timer <= 0:
                                            took_damage = True
                                            pl.fire_timer = 0.5
                                    else:
                                        pl.fire_timer = 0

                                if not took_damage and boss.state == "ATTACKING":
                                    if pl.rect().colliderect(boss.rect()):
                                        took_damage = True

                                if took_damage:
                                    if pl == local_player or net_role == ROLE_LOCAL_ONLY:
                                        pl.take_damage(1, source_x=boss.x + boss.w//2)
                                    
                                    elif net_role == ROLE_HOST and pl == remote_player:
                                        pl.take_damage(1, source_x=boss.x + boss.w//2)
                                        network.send_damage_to_client(1)

                        # PLAYER ATTACKING BOSS
                        if net_role != ROLE_CLIENT:
                            attackers = []
                            if net_role == ROLE_LOCAL_ONLY:
                                if use_p1 and p1.alive: attackers.append(p1)
                                if use_p2 and p2.alive: attackers.append(p2)
                            else:
                                if local_player.alive: attackers.append(local_player)
                                if remote_player.alive: attackers.append(remote_player)

                            for attacker in attackers:
                                if attacker.rect().colliderect(boss.rect()):
                                    if boss.state == "TIRED" and (attacker.slam_active or attacker.vy > 100):
                                        died = boss.take_damage(1)
                                        attacker.vy = -350
                                        if died:
                                            boss_defeated = True
                                            boss.alive = False
                                            p1_orbs += 5
                                            boss_room.activate_victory()

                        # Collect credits
                        credits_collected = boss_room.collect_credit(local_player.rect())
                        if credits_collected > 0:
                            session_credits += credits_collected
                            
                        # Check return portal
                        should_exit = False
                        
                        if boss_defeated and boss_room.check_portal_entry(local_player.rect()):
                            should_exit = True
                        
                        if net_role == ROLE_CLIENT:
                            rb_state = network.get_boss_state()
                            if not rb_state["active"]:
                                should_exit = True

                        if should_exit:
                            in_boss_room = False
                            boss_room = None
                            if boss: boss.reset_projectiles()
                            boss = None
                            boss_defeated = False
                            level.portal = None
                            local_player.x = level.return_safe_pos[0]
                            local_player.y = level.return_safe_pos[1] - local_player.h
                            local_player.vx, local_player.vy = 0, 0
                            local_player.slam_active, local_player.dash_active = False, False
                            
                            if net_role == ROLE_HOST:
                                network.remote_boss_state["active"] = False

                            if os.path.exists(GAME_BGM_PATH):
                                try:
                                    pygame.mixer.music.stop()
                                    pygame.mixer.music.load(GAME_BGM_PATH)
                                    pygame.mixer.music.set_volume(settings.music_volume * settings.master_volume)
                                    pygame.mixer.music.play(-1)
                                except: pass
                
                # --- UPDATE PLAYERS ---
                current_level = boss_room if in_boss_room else level
                
                if mode == MODE_SINGLE or net_role != ROLE_LOCAL_ONLY:
                    i_left, i_right, i_jump, i_slam = get_p1_inputs(keys)
                    
                    if tutorial_active and not tutorial_moved and (i_left or i_right or i_jump or i_slam):
                        tutorial_moved = True
                    
                    local_player.update(dt, current_level, i_left, i_right, i_jump, i_slam)
                else:
                    if p1_local and use_p1: 
                        i_left, i_right, i_jump, i_slam = get_p1_inputs(keys)
                        
                        if tutorial_active and not tutorial_moved and (i_left or i_right or i_jump or i_slam):
                            tutorial_moved = True
                        
                        p1.update(dt, current_level, i_left, i_right, i_jump, i_slam)
                    if p2_local and use_p2: 
                        i_left, i_right, i_jump, i_slam = get_p2_inputs(keys)
                        
                        if tutorial_active and not tutorial_moved and (i_left or i_right or i_jump or i_slam):
                            tutorial_moved = True
                        
                        p2.update(dt, current_level, i_left, i_right, i_jump, i_slam)

                # --- CAMERA UPDATE ---
                if mode == MODE_VERSUS and net_role == ROLE_LOCAL_ONLY and use_p1 and use_p2:
                    tx1 = p1.x if p1.alive else (p2.x if p2.alive else p1.x)
                    tx2 = p2.x if p2.alive else (p1.x if p1.alive else p2.x)
                    
                    ty1 = p1.y if p1.alive else (p2.y if p2.alive else p1.y)
                    ty2 = p2.y if p2.alive else (p1.y if p1.alive else p2.y)

                    target_cam_y1 = ty1 - (VIRTUAL_H // 4)
                    target_cam_y2 = ty2 - (VIRTUAL_H // 4)

                    cam_x_p1 += ((tx1 - 200) - cam_x_p1) * 0.1
                    cam_x_p2 += ((tx2 - 200) - cam_x_p2) * 0.1
                    
                    cam_y_p1 += (target_cam_y1 - cam_y_p1) * 0.1
                    cam_y_p2 += (target_cam_y2 - cam_y_p2) * 0.1

                    cam_x = max(cam_x_p1, cam_x_p2)
                else:
                    if mode == MODE_SINGLE: 
                        b_x = local_player.x
                    elif net_role != ROLE_LOCAL_ONLY:
                        if local_player.alive:
                            b_x = local_player.x
                        elif remote_player.alive:
                            b_x = remote_player.x
                        else:
                            b_x = local_player.x
                    else:
                        if p1.alive and p2.alive: b_x = max(p1.x, p2.x)
                        elif p1.alive: b_x = p1.x
                        elif p2.alive: b_x = p2.x
                        else: b_x = p1.x
                    
                    cam_x += ((b_x - 200) - cam_x) * 0.1
                    cam_y = 0 
                
                # --- UPDATE LEVEL ---
                cam_rect = pygame.Rect(int(cam_x), int(cam_y), VIRTUAL_W, VIRTUAL_H)
                
                gen_x = cam_x
                if net_role != ROLE_LOCAL_ONLY:
                    furthest_player_x = max(local_player.x, remote_player.x)
                    if furthest_player_x > (cam_x + 200):
                        gen_x = furthest_player_x - 200

                level.update(dt, gen_x, difficulty)
                
                is_client = (net_role == ROLE_CLIENT)
                spike_deaths, _ = level.update_enemies(dt, [p for p in [p1, p2] if (use_p1 if p==p1 else use_p2)], cam_rect, is_client=is_client)
                
                if is_client:
                    level.update_client_animations(dt)

                if net_role != ROLE_CLIENT:
                    for dx, dy in spike_deaths: level.spawn_credit(dx, dy, 0.5)
                
                # Update Distance Score
                if use_p1 and p1.alive and (net_role in (ROLE_LOCAL_ONLY, ROLE_HOST)): p1_distance = max(p1_distance, p1.x - base_x)
                if use_p2 and p2.alive and (net_role in (ROLE_LOCAL_ONLY, ROLE_CLIENT)): p2_distance = max(p2_distance, p2.x - base_x)

                players_to_check = []
                if net_role == ROLE_LOCAL_ONLY:
                    if use_p1 and p1.alive: players_to_check.append(p1)
                    if use_p2 and p2.alive: players_to_check.append(p2)
                else:
                    if local_player.alive: players_to_check.append(local_player)
                
                # Credit collection
                for credit in level.dropped_credits[:]:
                    c_rect = credit.rect()
                    for p in players_to_check:
                        if p.rect().colliderect(c_rect):
                            session_credits += credit.value
                            spawn_credit_text(credit.x, credit.y, credit.value, font_small)
                            if credit in level.dropped_credits: level.dropped_credits.remove(credit)
                            break

                for orb in level.orbs[:]:
                    if use_p1 and p1.alive and p1.rect().colliderect(orb): 
                        p1_orbs += 1
                        floating_texts.append(FloatingText(orb.x, orb.y, "+100 PTS", font_small, COL_ACCENT_3))
                        level.orbs.remove(orb)
                        continue
                    if use_p2 and p2.alive and p2.rect().colliderect(orb): 
                        p2_orbs += 1
                        floating_texts.append(FloatingText(orb.x, orb.y, "+100 PTS", font_small, COL_ACCENT_3))
                        level.orbs.remove(orb)

                for horb in level.health_orbs[:]:
                    if use_p1 and p1.alive and p1.rect().colliderect(horb): 
                        if p1.hp < p1.max_hp:
                            p1.hp += 1
                            floating_texts.append(FloatingText(horb.x, horb.y, "+1 HP", font_small, (50, 255, 50)))
                        else:
                            floating_texts.append(FloatingText(horb.x, horb.y, "MAX HP", font_small, (200, 255, 200)))
                        level.health_orbs.remove(horb)
                        continue
                    if use_p2 and p2.alive and p2.rect().colliderect(horb): 
                        if p2.hp < p2.max_hp:
                            p2.hp += 1
                            floating_texts.append(FloatingText(horb.x, horb.y, "+1 HP", font_small, (50, 255, 50)))
                        else:
                            floating_texts.append(FloatingText(horb.x, horb.y, "MAX HP", font_small, (200, 255, 200)))
                        level.health_orbs.remove(horb)

                def resolve_slam(player):
                    if not player.pending_slam_impact: return
                    player.pending_slam_impact = False
                    nonlocal screen_shake_timer
                    if player.slam_impact_power > 150: screen_shake_timer = 0.2
                    radius = SLAM_BASE_RADIUS + player.slam_impact_power * SLAM_RADIUS_PER_HEIGHT
                    cx, cy = player.x + player.w / 2, player.y + player.h
                    
                    player.invul_timer = 0.5 
                    player.flash_on_invul = False
                    
                    if net_role != ROLE_CLIENT:
                        for e in level.enemies:
                            if not e.alive: continue
                            ex, ey = e.x + e.w / 2, e.y + e.h / 2
                            if (ex - cx)**2 + (ey - cy)**2 <= radius**2: 
                                damage = 1.0
                                if not getattr(e, 'is_boss', False): damage = e.max_hp 
                                died = e.take_damage(damage)
                                if died:
                                    level.spawn_credit(e.x, e.y, 1.0)
                                else:
                                    spawn_dust(e.x + e.w/2, e.y, 3, (255, 100, 100))

                def handle_collisions_for_player(player):
                    if not player.alive or player.is_dying: return
                    
                    if player.y > VIRTUAL_H + 200: 
                        player.take_damage(1)
                        if player.alive:
                            player.x = player.last_safe_x
                            player.y = player.last_safe_y - TILE_SIZE 
                            player.vx = 0
                            player.vy = 0
                            player.slam_active = False
                            player.dash_active = False
                        return
                    
                    r = player.rect()
                    for obs in level.obstacles: 
                        if r.colliderect(obs): 
                            if player.dash_active: continue 
                            player.take_damage(1, source_x=obs.centerx) 
                            return
                    
                    for e in level.enemies: 
                        if r.colliderect(e.rect()):
                            if player.dash_active: continue 
                            
                            player_bottom = player.y + player.h
                            enemy_center = e.y + e.h * 0.5
                            is_above = player_bottom < enemy_center + 5
                            is_falling = player.vy > 0
                            
                            if player.slam_active or player.pending_slam_impact or (is_falling and is_above):
                                
                                damage = 0.5
                                if player.slam_active or player.pending_slam_impact:
                                    if not getattr(e, 'is_boss', False): damage = e.max_hp 
                                    else: damage = 1.0

                                if net_role != ROLE_CLIENT:
                                    died = e.take_damage(damage)
                                    if died: level.spawn_credit(e.x, e.y, 1.0) 
                                else:
                                    network.send_hit(e.id, damage)

                                player.vy = -700.0 
                                player.invul_timer = 0.2 
                                player.flash_on_invul = False 
                                player.slam_cooldown = 0 
                                player.slam_active = False 
                            else:
                                player.take_damage(1, source_x=(e.x + e.w/2))
                            return

                players_to_check_collision = []

                if net_role == ROLE_LOCAL_ONLY:
                    if use_p1 and p1.alive: players_to_check_collision.append(p1)
                    if use_p2 and p2.alive: players_to_check_collision.append(p2)
                elif net_role == ROLE_HOST:
                    if local_player.alive: players_to_check_collision.append(local_player)
                    if remote_player.alive: players_to_check_collision.append(remote_player)
                elif net_role == ROLE_CLIENT:
                    if local_player.alive: players_to_check_collision.append(local_player)

                for p in players_to_check_collision:
                    handle_collisions_for_player(p)
                    if net_role != ROLE_CLIENT:
                        resolve_slam(p)
                    elif p == local_player:
                        resolve_slam(p)
                
                if use_p1: resolve_slam(p1)
                if use_p2: resolve_slam(p2)
                
                # Network sync
                if net_role == ROLE_HOST:
                    for e in level.enemies:
                        network.send_enemy_update(e.id, e.x, e.y, e.facing_right, int(e.hp), not e.alive)
                
                if in_boss_room and boss:
                    if net_role == ROLE_HOST:
                        network.send_boss_state(boss.hp, boss_defeated, boss.x, boss.y, boss.current_action, boss.frame_index)
                    elif net_role == ROLE_CLIENT:
                        rb_state = network.get_boss_state()
                        boss.hp = rb_state["hp"]
                        
                        if not rb_state["dead"]:
                            boss.x += (rb_state["x"] - boss.x) * 0.2
                            boss.y += (rb_state["y"] - boss.y) * 0.2
                            boss.current_action = rb_state["action"]
                            boss.frame_index = rb_state["frame"]
                        
                        if rb_state["dead"] and not boss_defeated:
                            boss_defeated = True
                            boss.alive = False
                            boss_room.activate_victory()

                p1_total = int(p1_distance/10 + p1_orbs * 100)
                p2_total = int(p2_distance/10 + p2_orbs * 100)
                
                combined_score = p1_total + p2_total if mode == MODE_COOP else 0
                
                def finish(name, score, txt):
                    nonlocal game_over, winner_text
                    game_over = True
                    winner_text = txt
                    add_score(lb, lb_key, name, score)
                    if session_credits > 0:
                        local_data["credits"] += session_credits
                        save_save_data(local_data)
                    if net_role != ROLE_LOCAL_ONLY: network.send_game_over(winner_text)

                if mode == MODE_SINGLE and not local_player.alive:
                        finish("Player", p1_total if local_player is p1 else p2_total, "GAME OVER")
                elif mode == MODE_COOP and not p1.alive and not p2.alive:
                        finish("Team", combined_score, "MISSION FAILED")
                elif mode == MODE_VERSUS and not p1.alive and not p2.alive:
                        winner = "DRAW" if p1_total == p2_total else ("P1 WINS" if p1_total > p2_total else "P2 WINS")
                        finish(winner, max(p1_total, p2_total), winner)

        # ========== RENDERING ==========
        canvas.fill(COL_BG)
        final_cam_x = cam_x + shake_x
        final_cam_y = cam_y + shake_y

        if mode == MODE_VERSUS and net_role == ROLE_LOCAL_ONLY and use_p1 and use_p2:
            render_scene(view1_surf, cam_x_p1, cam_y_p1, highlight_player=1)
            render_scene(view2_surf, cam_x_p2, cam_y_p2, highlight_player=2)
            half_h = VIRTUAL_H // 2
            canvas.blit(view1_surf, (0, 0))
            canvas.blit(view2_surf, (0, half_h))
            pygame.draw.line(canvas, COL_UI_BORDER, (0, half_h), (VIRTUAL_W, half_h), 4)
        else:
            render_scene(canvas, final_cam_x, final_cam_y, highlight_player=None)
        
        # Draw tutorial overlay
        if tutorial_active and not waiting_for_seed and net_role == ROLE_LOCAL_ONLY:
            overlay = pygame.Surface((VIRTUAL_W, VIRTUAL_H), pygame.SRCALPHA)
            overlay.fill((0, 0, 0, 120))
            canvas.blit(overlay, (0, 0))
            
            p1_left_key = pygame.key.name(kb["p1_left"]).upper()
            p1_right_key = pygame.key.name(kb["p1_right"]).upper()
            p1_jump_key = pygame.key.name(kb["p1_jump"]).upper()
            p1_ability_key = pygame.key.name(kb["p1_slam"]).upper()
            
            p2_left_key = pygame.key.name(kb["p2_left"]).upper()
            p2_right_key = pygame.key.name(kb["p2_right"]).upper()
            p2_jump_key = pygame.key.name(kb["p2_jump"]).upper()
            p2_ability_key = pygame.key.name(kb["p2_slam"]).upper()
            
            line_spacing = 35
            
            if mode == MODE_VERSUS and use_p1 and use_p2:
                half_h = VIRTUAL_H // 2
                
                y_center_p1 = half_h // 2
                move_text = f"[{p1_left_key}] [{p1_right_key}] to move"
                draw_text_shadow(canvas, font_small, move_text, VIRTUAL_W//2, y_center_p1 - line_spacing, center=True, col=COL_ACCENT_1)
                jump_text = f"[{p1_jump_key}] to jump"
                draw_text_shadow(canvas, font_small, jump_text, VIRTUAL_W//2, y_center_p1, center=True, col=COL_ACCENT_1)
                ability_text = f"[{p1_ability_key}] for ability!"
                draw_text_shadow(canvas, font_small, ability_text, VIRTUAL_W//2, y_center_p1 + line_spacing, center=True, col=COL_ACCENT_3)
                
                y_center_p2 = half_h + half_h // 2
                move_text = f"[{p2_left_key}] [{p2_right_key}] to move"
                draw_text_shadow(canvas, font_small, move_text, VIRTUAL_W//2, y_center_p2 - line_spacing, center=True, col=COL_ACCENT_2)
                jump_text = f"[{p2_jump_key}] to jump"
                draw_text_shadow(canvas, font_small, jump_text, VIRTUAL_W//2, y_center_p2, center=True, col=COL_ACCENT_2)
                ability_text = f"[{p2_ability_key}] for ability!"
                draw_text_shadow(canvas, font_small, ability_text, VIRTUAL_W//2, y_center_p2 + line_spacing, center=True, col=COL_ACCENT_3)
                
            elif mode == MODE_COOP and use_p1 and use_p2:
                y_center = VIRTUAL_H // 2
                quarter_w = VIRTUAL_W // 4
                
                draw_text_shadow(canvas, font_small, "PLAYER 1", quarter_w, y_center - line_spacing * 2, center=True, col=COL_ACCENT_1)
                move_text = f"[{p1_left_key}] [{p1_right_key}] move"
                draw_text_shadow(canvas, font_small, move_text, quarter_w, y_center - line_spacing, center=True, col=COL_ACCENT_1)
                jump_text = f"[{p1_jump_key}] jump"
                draw_text_shadow(canvas, font_small, jump_text, quarter_w, y_center, center=True, col=COL_ACCENT_1)
                ability_text = f"[{p1_ability_key}] ability"
                draw_text_shadow(canvas, font_small, ability_text, quarter_w, y_center + line_spacing, center=True, col=COL_ACCENT_3)
                
                draw_text_shadow(canvas, font_small, "PLAYER 2", quarter_w * 3, y_center - line_spacing * 2, center=True, col=COL_ACCENT_2)
                move_text = f"[{p2_left_key}] [{p2_right_key}] move"
                draw_text_shadow(canvas, font_small, move_text, quarter_w * 3, y_center - line_spacing, center=True, col=COL_ACCENT_2)
                jump_text = f"[{p2_jump_key}] jump"
                draw_text_shadow(canvas, font_small, jump_text, quarter_w * 3, y_center, center=True, col=COL_ACCENT_2)
                ability_text = f"[{p2_ability_key}] ability"
                draw_text_shadow(canvas, font_small, ability_text, quarter_w * 3, y_center + line_spacing, center=True, col=COL_ACCENT_3)
                
            else:
                y_center = VIRTUAL_H // 2
                line_spacing = 45
                
                move_text = f"Press [{p1_left_key}] and [{p1_right_key}] to move left and right"
                draw_text_shadow(canvas, font_med, move_text, VIRTUAL_W//2, y_center - line_spacing, center=True, col=COL_ACCENT_1)
                
                jump_text = f"Press [{p1_jump_key}] to jump"
                draw_text_shadow(canvas, font_med, jump_text, VIRTUAL_W//2, y_center, center=True, col=COL_ACCENT_1)
                
                ability_text = f"Press [{p1_ability_key}] to use your ability!"
                draw_text_shadow(canvas, font_med, ability_text, VIRTUAL_W//2, y_center + line_spacing, center=True, col=COL_ACCENT_3)

        if game_over:
            overlay = pygame.Surface((VIRTUAL_W, VIRTUAL_H), pygame.SRCALPHA)
            overlay.fill((0, 0, 0, 180))
            canvas.blit(overlay, (0, 0))
            
            draw_text_shadow(canvas, font_big, winner_text, VIRTUAL_W//2, VIRTUAL_H//2 - 40, center=True, col=COL_ACCENT_3)
            draw_text_shadow(canvas, font_med, f"CREDITS EARNED: {int(session_credits)}", VIRTUAL_W//2, VIRTUAL_H//2, center=True)
            draw_text_shadow(canvas, font_small, "[ESC] Return to Menu", VIRTUAL_W//2, VIRTUAL_H//2 + 30, center=True)
            
            y = VIRTUAL_H // 2 + 60
            canvas.blit(font_small.render("LEADERBOARD:", False, (150, 150, 150)), (VIRTUAL_W // 2 - 40, y))
            y += 16
            for i, e in enumerate(lb[lb_key][:3]):
                canvas.blit(font_small.render(f"{i+1}. {e['name']} - {e['score']}", False, (200, 200, 200)), (VIRTUAL_W // 2 - 60, y))
                y += 14

        win_w, win_h = window.get_size()
        scale = min(win_w / VIRTUAL_W, win_h / VIRTUAL_H)
        scaled_w, scaled_h = int(VIRTUAL_W * scale), int(VIRTUAL_H * scale)
        offset_x, offset_y = (win_w - scaled_w) // 2, (win_h - scaled_h) // 2
        
        window.fill((0, 0, 0))
        surf_scaled = pygame.transform.scale(canvas, (scaled_w, scaled_h))
        window.blit(surf_scaled, (offset_x, offset_y))
        pygame.display.flip()
