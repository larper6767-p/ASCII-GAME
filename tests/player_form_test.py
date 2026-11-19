"""Player form tests: slime morphs, 1/2/3 switching and bow/gun projectiles.

Run from the repo root with ``python tests/player_form_test.py``.
"""
import os

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import pygame

pygame.init()

from emberfall import combat, config
from emberfall.entities import Crawler, Player
from emberfall.input import InputState, KeyboardInput
from emberfall.projectiles import ProjectileSystem
from emberfall.renderer import Renderer
from emberfall.boss import BossState
from emberfall.session import GameSession
from emberfall.world import Level

CHECKS = 0
FAILURES = []


def check(name, condition, detail=""):
    global CHECKS
    CHECKS += 1
    if not condition:
        FAILURES.append(f"{name}: {detail}" if detail else name)
    return bool(condition)


def flat_level():
    width, height = 60, 14
    rows = []
    for y in range(height):
        rows.append("#" * width if y >= 12 else "." * width)
    return Level(rows, [], player_spawn=(5.0, 9.0))


def settled_session():
    session = GameSession(seed=21, level=flat_level())
    inp = InputState()
    for _ in range(6):
        session.update(config.FIXED_DT, inp)
    return session, inp


def advance(session, inp, frames=1):
    for _ in range(frames):
        session.update(config.FIXED_DT, inp)
        inp.clear_edges()


def test_forms_and_switching():
    print("Forms and 1/2/3 switching:")
    ok = True
    player = Player(5.0, 9.0)
    ok &= check("player starts as the sword form",
                player.weapon == "sword", player.weapon)
    ok &= check("bow form morphs", player.set_weapon("bow"))
    ok &= check("unknown form is refused", not player.set_weapon("cannon"))
    ok &= check("gun form morphs", player.set_weapon("gun"))

    session, inp = settled_session()
    inp.set_held({"weapon_bow"})
    advance(session, inp, 1)
    ok &= check("2 key switches the session to bow",
                session.weapon == "bow" and session.player.weapon == "bow",
                session.weapon)
    inp.set_held({"attack"})
    advance(session, inp, 1)
    ok &= check("attack starts in the selected form",
                session.player.attacking and session.player.weapon == "bow")
    inp.set_held({"weapon_sword"})
    advance(session, inp, 1)
    ok &= check("form cannot change mid-swing",
                session.player.weapon == "bow",
                session.player.weapon)
    inp.set_held(set())
    for _ in range(80):
        advance(session, inp, 1)
        if not session.player.attacking:
            break
    inp.set_held({"weapon_sword"})
    advance(session, inp, 1)
    ok &= check("1 key returns to sword",
                session.weapon == "sword" and session.player.weapon == "sword",
                session.weapon)

    session.weapon = "gun"
    session.player.weapon = "gun"
    session.reset()
    ok &= check("selected form survives death/reset",
                session.weapon == "gun" and session.player.weapon == "gun",
                session.weapon)

    keyboard = KeyboardInput()
    keyboard.handle_events([pygame.event.Event(pygame.KEYDOWN, key=pygame.K_3)])
    advance(session, keyboard, 1)
    ok &= check("physical 3 key selects gun", session.player.weapon == "gun",
                session.player.weapon)
    keyboard.handle_events([pygame.event.Event(pygame.KEYUP, key=pygame.K_3)])
    keyboard.handle_events([pygame.event.Event(pygame.KEYDOWN, key=pygame.K_1)])
    advance(session, keyboard, 1)
    ok &= check("physical 1 key selects sword",
                session.player.weapon == "sword", session.player.weapon)
    return ok


def test_hitboxes_and_pogo():
    print("Sword-only hitbox and pogo:")
    ok = True
    sword = Player(5.0, 9.0, weapon="sword")
    sword.attack_t = config.ATTACK_STARTUP + 0.01
    ok &= check("sword has a melee hitbox",
                combat.attack_hitbox(sword) is not None)
    bow = Player(5.0, 9.0, weapon="bow")
    bow.attack_t = config.ATTACK_STARTUP + 0.01
    ok &= check("bow has no melee hitbox",
                combat.attack_hitbox(bow) is None)
    gun = Player(5.0, 9.0, weapon="gun")
    gun.attack_t = config.ATTACK_STARTUP + 0.01
    ok &= check("gun has no melee hitbox",
                combat.attack_hitbox(gun) is None)

    airborne = Player(5.0, 5.0, weapon="sword")
    airborne.on_ground = False
    airborne.start_attack(True)
    ok &= check("sword keeps the pogo form", airborne.pogo)
    ranged = Player(5.0, 5.0, weapon="bow")
    ranged.on_ground = False
    ranged.start_attack(True)
    ok &= check("bow does not pogo", not ranged.pogo)
    return ok


def fire_once(weapon, enemy=None):
    """Run one ranged swing; return the session, input and player."""
    session, inp = settled_session()
    session.enemies = []
    player = session.player
    player.inv = 999.0
    player.facing = 1
    player.weapon = weapon
    if enemy is not None:
        enemy.stun = 99.0
        session.enemies = [enemy]
    player.start_attack()
    for _ in range(20):
        advance(session, inp, 1)
        if session.projectiles.items:
            break
    return session, inp, player


def test_ranged_attacks():
    print("Bow/gun firing and friendly projectiles:")
    ok = True
    bow_session, bow_inp, bow_player = fire_once("bow")
    shot = bow_session.projectiles.items[0] if bow_session.projectiles.items else None
    ok &= check("bow fires one arrow", shot is not None and shot.kind == "arrow",
                str(getattr(shot, "kind", None)))
    if shot is not None:
        ok &= check("bow arrow is friendly",
                    shot.friendly and shot.damage == 1
                    and shot.vx > config.WEAPON_DATA["bow"]["projectile_speed"] - 0.01,
                    f"vx={shot.vx}")
        ok &= check("bow arrow moves right", shot.vx > 0.0, f"{shot.vx}")
    hp_before = bow_player.hp
    for _ in range(20):
        advance(bow_session, bow_inp, 1)
    ok &= check("friendly arrow never hurts the player",
                bow_player.hp == hp_before, f"{bow_player.hp}")

    gun_session, _, _ = fire_once("gun")
    shot = gun_session.projectiles.items[0] if gun_session.projectiles.items else None
    ok &= check("gun fires one bullet", shot is not None and shot.kind == "bullet",
                str(getattr(shot, "kind", None)))
    if shot is not None:
        ok &= check("gun bullet is faster than the bow arrow",
                    shot.vx > config.WEAPON_DATA["bow"]["projectile_speed"],
                    f"{shot.vx}")

    # One swing never queues a second shot after the first active frame.
    bow_session, bow_inp, _ = fire_once("bow")
    for _ in range(30):
        advance(bow_session, bow_inp, 1)
        if not bow_session.player.attacking:
            break
    ok &= check("one projectile per swing",
                len(bow_session.projectiles.items) <= 1,
                str(len(bow_session.projectiles.items)))

    # Friendly arrows damage an enemy and are consumed by the hit.
    crawler = Crawler(14.0, 10.0, bow_session.rng)
    session, inp, _ = fire_once("bow", enemy=crawler)
    for _ in range(60):
        advance(session, inp, 1)
        if crawler.hp < crawler.max_hp:
            break
    ok &= check("friendly arrow damages an enemy",
                crawler.hp == crawler.max_hp - 1, f"hp={crawler.hp}")
    ok &= check("friendly arrow is consumed by the hit",
                not session.projectiles.items,
                str(len(session.projectiles.items)))
    ok &= check("ranged hit triggers hit-stop", session.hitstop.active)

    # Friendly shots die on walls like hostile ones.
    wall_session, wall_inp, wall_player = fire_once("gun")
    wall_player.x = 58.0
    wall_player.facing = 1
    wall_player.attack_t = -1.0
    wall_player.ranged_fired = False
    wall_session.projectiles.clear()
    wall_player.start_attack()
    for _ in range(10):
        advance(wall_session, wall_inp, 1)
    ok &= check("friendly bullet dies in a wall",
                not wall_session.projectiles.items,
                str(len(wall_session.projectiles.items)))
    return ok


def test_renderer_art():
    print("Slime/weapon rendering:")
    ok = True
    renderer = Renderer()
    renderer.begin_frame(camera_offset=0.0)
    for weapon in config.WEAPON_DATA:
        for facing in (1, -1):
            player = Player(10.0, 9.0, weapon=weapon)
            player.facing = facing
            player.vx = 12.0 * facing
            player.on_ground = True
            renderer.stats["sprite_cells"] = 0
            renderer._fg_batch.clear()
            renderer.draw_player(player, 0.0, 0.0)
            cells = renderer.stats["sprite_cells"]
            ok &= check(
                f"{weapon}/{'right' if facing > 0 else 'left'} slime art draws",
                cells > 20, f"{cells} cells",
            )
            renderer.draw_slash(player, 0.0)

    # An active sword swing still draws its long blade without errors.
    player = Player(10.0, 9.0, weapon="sword")
    player.facing = 1
    player.attack_t = config.ATTACK_STARTUP + 0.02
    renderer.stats["sprite_cells"] = 0
    renderer._fg_batch.clear()
    renderer.draw_player(player, 0.0, 0.0)
    ok &= check("sword swing draws extra art",
                renderer.stats["sprite_cells"] > 20,
                str(renderer.stats["sprite_cells"]))
    renderer.draw_slash(player, 0.0)

    shots = ProjectileSystem()
    shots.spawn(10.0, 9.0, 24.0, 0.0, color=(155, 232, 255), char=">",
                lifetime=4.0, kind="arrow", friendly=True)
    shots.spawn(12.0, 9.0, 44.0, 0.0, color=(255, 208, 120), char="*",
                lifetime=2.5, kind="bullet", friendly=True)
    before = len(renderer._fg_batch)
    renderer.draw_projectiles(shots, 0.0)
    ok &= check("friendly projectiles draw arrow/bullet art",
                len(renderer._fg_batch) > before, str(len(renderer._fg_batch)))

    # The renderer must not mutate the simulation it is drawing.
    before_state = (player.x, player.y, player.vx, player.vy,
                    player.attack_t, player.on_ground)
    renderer.draw_player(player, 0.0, 1.0)
    after_state = (player.x, player.y, player.vx, player.vy,
                   player.attack_t, player.on_ground)
    ok &= check("drawing leaves player physics untouched",
                before_state == after_state, f"{before_state} != {after_state}")
    return ok


def test_physics_driven_body():
    print("Physics-driven slime body:")
    renderer = Renderer()
    renderer.begin_frame(camera_offset=0.0)

    def body_bounds(player):
        renderer._fg_batch.clear()
        renderer._draw_slime_body(player, 100, 100)
        xs = [x for _surface, (x, _y) in renderer._fg_batch]
        ys = [y for _surface, (_x, y) in renderer._fg_batch]
        return (max(xs) - min(xs), max(ys) - min(ys))

    idle = Player(10.0, 9.0)
    idle.on_ground = True
    idle.vx = 0.0
    idle.vy = 0.0
    idle_w, idle_h = body_bounds(idle)

    running = Player(10.0, 9.0)
    running.on_ground = True
    running.vx = config.RUN_SPEED
    running_w, _ = body_bounds(running)

    falling = Player(10.0, 5.0)
    falling.on_ground = False
    falling.vy = config.MAX_FALL
    _, fall_h = body_bounds(falling)

    ok = True
    ok &= check("running stretches the slime horizontally",
                running_w > idle_w,
                f"{running_w} vs {idle_w}")
    ok &= check("falling stretches the slime vertically",
                fall_h > idle_h, f"{fall_h} vs {idle_h}")
    return ok


def test_stun_and_pogo():
    print("Stun and pogo by form:")
    ok = True
    for weapon in config.WEAPON_DATA:
        player = Player(5.0, 9.0, weapon=weapon)
        player.stun = 0.2
        ok &= check(f"stun blocks {weapon} attack",
                    not player.start_attack(), weapon)
    ranged = Player(5.0, 5.0, weapon="gun")
    ranged.on_ground = False
    ranged.start_attack(True)
    ok &= check("gun does not pogo", not ranged.pogo)
    return ok


def test_friendly_projectile_vs_boss_intro():
    print("Friendly projectile vs boss invulnerable intro:")
    session = GameSession(seed=7, room_id="room3")
    boss = session.enemies[0]
    boss.set_state(BossState.INTRO, boss.data["intro_time"])
    player = session.player
    player.inv = 999.0
    player.x = 68.0
    player.facing = 1
    player.weapon = "bow"
    player.start_attack()
    inp = InputState()
    for _ in range(20):
        advance(session, inp, 1)
        if session.projectiles.items:
            break
    hp_before = boss.hp
    for _ in range(20):
        advance(session, inp, 1)
    ok = True
    ok &= check("boss intro stays invulnerable to friendly fire",
                boss.hp == hp_before, f"hp={boss.hp}")
    ok &= check("friendly projectile is consumed during the intro",
                not session.projectiles.items,
                str(len(session.projectiles.items)))
    return ok


def test_projectiles_cleared_on_room_change():
    print("Projectiles cleared on room change:")
    session = GameSession(seed=5, room_id="room1")
    inp = InputState()
    player = session.player
    player.weapon = "bow"
    player.start_attack()
    for _ in range(20):
        advance(session, inp, 1)
        if session.projectiles.items:
            break
    ok = check("friendly projectile exists before transition",
               bool(session.projectiles.items),
               str(len(session.projectiles.items)))
    player.x = session.level.width - 2.0
    player.y = session.level.player_spawn[1]
    for _ in range(45):
        session.update(config.FIXED_DT, inp)
        inp.clear_edges()
        if session.transition is None:
            break
    ok &= check("room change completes",
                session.room_id == "room2", str(session.room_id))
    ok &= check("friendly projectiles are cleared on arrival",
                not session.projectiles.items,
                str(len(session.projectiles.items)))
    return ok


def test_hud_form_label():
    print("HUD form label:")
    renderer = Renderer()
    player = Player(10.0, 9.0, weapon="gun")
    renderer.draw_hud(player, [], locked=False)
    labels = [text for (text, *_rest) in renderer._text_cache]
    ok = check("HUD shows the selected weapon form",
               any("FORM [GUN]" in text for text in labels),
               "; ".join(sorted(labels)))
    return ok


def main():
    print("Emberfall player form tests")
    test_forms_and_switching()
    test_hitboxes_and_pogo()
    test_ranged_attacks()
    test_renderer_art()
    test_physics_driven_body()
    test_stun_and_pogo()
    test_friendly_projectile_vs_boss_intro()
    test_projectiles_cleared_on_room_change()
    test_hud_form_label()
    print(f"\n{CHECKS} checks, {len(FAILURES)} failures")
    for failure in FAILURES:
        print(f"  FAIL {failure}")
    if FAILURES:
        return 1
    print("player form tests passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
