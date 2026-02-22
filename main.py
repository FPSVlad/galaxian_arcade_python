import argparse
import math
import random
from array import array
from dataclasses import dataclass

import pygame

SCREEN_W = 480
SCREEN_H = 640
FPS = 60

PLAYER_SPEED = 260
BULLET_SPEED = -420
ENEMY_BULLET_SPEED = 220
DIVE_SPEED = 170
FORMATION_DROP_SPEED = 14

DIVE_CHANCE_BASE = 0.0010
DIVE_CHANCE_PER_LEVEL = 0.00015
ENEMY_SHOT_CHANCE_BASE = 0.008
ENEMY_SHOT_CHANCE_PER_LEVEL = 0.0012


@dataclass
class Bullet:
    x: float
    y: float
    dy: float
    from_enemy: bool


class Sfx:
    def __init__(self, enabled: bool = True):
        self.enabled = enabled
        self.sounds = {}
        if not enabled:
            return
        try:
            if not pygame.mixer.get_init():
                pygame.mixer.init(frequency=22050, size=-16, channels=1, buffer=256)
            self.sounds["shoot"] = self._tone(880, 0.05)
            self.sounds["boom"] = self._noise(0.18)
            self.sounds["coin"] = self._tone(1200, 0.08)
            self.sounds["start"] = self._tone(620, 0.12)
            self.sounds["hit"] = self._tone(240, 0.12)
        except pygame.error:
            self.enabled = False

    def _tone(self, freq: float, sec: float, volume: float = 0.35):
        rate = 22050
        n = int(rate * sec)
        data = array("h")
        for i in range(n):
            t = i / rate
            sample = int(32767 * volume * math.sin(2 * math.pi * freq * t))
            data.append(sample)
        return pygame.mixer.Sound(buffer=data)

    def _noise(self, sec: float, volume: float = 0.35):
        rate = 22050
        n = int(rate * sec)
        data = array("h")
        last = 0
        for _ in range(n):
            last = int(last * 0.72 + random.randint(-14000, 14000) * 0.28)
            data.append(int(last * volume))
        return pygame.mixer.Sound(buffer=data)

    def play(self, name: str):
        if self.enabled and name in self.sounds:
            self.sounds[name].play()


class Player:
    def __init__(self):
        self.w = 28
        self.h = 16
        self.x = SCREEN_W // 2
        self.y = SCREEN_H - 56
        self.cooldown = 0.0

    def update(self, dt: float, keys):
        move = 0
        if keys[pygame.K_LEFT] or keys[pygame.K_a]:
            move -= 1
        if keys[pygame.K_RIGHT] or keys[pygame.K_d]:
            move += 1
        self.x += move * PLAYER_SPEED * dt
        self.x = max(self.w // 2 + 4, min(SCREEN_W - self.w // 2 - 4, self.x))
        self.cooldown = max(0.0, self.cooldown - dt)

    def draw(self, surf):
        px = int(self.x)
        py = int(self.y)
        body = [
            (px, py - 8),
            (px - 12, py + 6),
            (px - 5, py + 2),
            (px + 5, py + 2),
            (px + 12, py + 6),
        ]
        pygame.draw.polygon(surf, (80, 255, 120), body)
        pygame.draw.rect(surf, (160, 255, 180), (px - 2, py - 2, 4, 10))

    def shoot(self):
        if self.cooldown > 0:
            return None
        self.cooldown = 0.24
        return Bullet(self.x, self.y - 10, BULLET_SPEED, False)


class Enemy:
    def __init__(self, gx: int, gy: int, etype: int):
        self.gx = gx
        self.gy = gy
        self.etype = etype
        self.alive = True
        self.diving = False
        self.x = 0.0
        self.y = 0.0
        self.dive_phase = random.random() * 2 * math.pi

    def points(self):
        if self.etype == 0:
            return 40
        if self.etype == 1:
            return 30
        return 20

    def draw(self, surf, t: float):
        if not self.alive:
            return
        x = int(self.x)
        y = int(self.y)
        wing = int(4 * math.sin(t * 8 + self.gx))
        if self.etype == 0:
            c1, c2 = (255, 90, 90), (255, 190, 120)
        elif self.etype == 1:
            c1, c2 = (120, 180, 255), (180, 230, 255)
        else:
            c1, c2 = (255, 220, 90), (255, 255, 180)

        pygame.draw.circle(surf, c1, (x, y), 6)
        pygame.draw.polygon(
            surf,
            c2,
            [(x - 10, y + wing), (x - 2, y + 2), (x - 6, y + 8)],
        )
        pygame.draw.polygon(
            surf,
            c2,
            [(x + 10, y + wing), (x + 2, y + 2), (x + 6, y + 8)],
        )


class Game:
    def __init__(self, headless: bool = False):
        pygame.init()
        flags = 0
        if headless:
            flags |= pygame.HIDDEN
        self.screen = pygame.display.set_mode((SCREEN_W, SCREEN_H), flags)
        pygame.display.set_caption("Galaxian-like Arcade")
        self.clock = pygame.time.Clock()
        self.font = pygame.font.SysFont("consolas", 20)
        self.small = pygame.font.SysFont("consolas", 16)

        self.sfx = Sfx(enabled=True)

        self.credits = 0
        self.high_score = 0
        self.reset_to_attract()

    def reset_to_attract(self):
        self.state = "ATTRACT"
        self.player = Player()
        self.bullets = []
        self.enemy_bullets = []
        self.level = 1
        self.score = 0
        self.lives = 3
        self._spawn_wave()
        self.formation_x = 60.0
        self.formation_y = 90.0
        self.form_dir = 1
        self.time = 0.0
        self.flash = 0.0
        self.dive_cooldown = 0.0

    def _spawn_wave(self):
        self.enemies = []
        rows = 5
        cols = 10
        for y in range(rows):
            for x in range(cols):
                et = 0 if y == 0 else (1 if y < 3 else 2)
                self.enemies.append(Enemy(x, y, et))

    def start_game(self):
        self.state = "PLAY"
        self.player = Player()
        self.bullets = []
        self.enemy_bullets = []
        self.level = 1
        self.score = 0
        self.lives = 3
        self.formation_x = 60.0
        self.formation_y = 90.0
        self.form_dir = 1
        self.time = 0.0
        self._spawn_wave()
        self.dive_cooldown = 0.0
        self.sfx.play("start")

    def alive_enemies(self):
        return [e for e in self.enemies if e.alive]

    def _update_enemies(self, dt: float):
        self.formation_x += self.form_dir * 55 * dt
        if self.formation_x < 30:
            self.formation_x = 30
            self.form_dir = 1
            self.formation_y += FORMATION_DROP_SPEED
        if self.formation_x > SCREEN_W - 30 - 9 * 36:
            self.formation_x = SCREEN_W - 30 - 9 * 36
            self.form_dir = -1
            self.formation_y += FORMATION_DROP_SPEED

        self.dive_cooldown = max(0.0, self.dive_cooldown - dt)
        diving_now = sum(1 for e in self.enemies if e.alive and e.diving)
        max_divers = 1 + (1 if self.level >= 5 else 0)

        for e in self.enemies:
            if not e.alive:
                continue
            if not e.diving:
                e.x = self.formation_x + e.gx * 36
                e.y = self.formation_y + e.gy * 30
                if (
                    diving_now < max_divers
                    and self.dive_cooldown <= 0.0
                    and random.random() < DIVE_CHANCE_BASE + self.level * DIVE_CHANCE_PER_LEVEL
                ):
                    e.diving = True
                    e.dive_phase = random.random() * math.pi
                    diving_now += 1
                    self.dive_cooldown = random.uniform(0.45, 1.05)
            else:
                e.y += DIVE_SPEED * dt
                e.x += math.sin(e.dive_phase + e.y * 0.04) * 130 * dt
                if random.random() < 0.006:
                    self.enemy_bullets.append(Bullet(e.x, e.y + 8, ENEMY_BULLET_SPEED, True))
                if e.y > SCREEN_H + 20:
                    e.diving = False

    @staticmethod
    def _hit(ax, ay, aw, ah, bx, by, bw, bh):
        return (abs(ax - bx) * 2 < (aw + bw)) and (abs(ay - by) * 2 < (ah + bh))

    def _update_bullets(self, dt: float):
        for b in self.bullets:
            b.y += b.dy * dt
        for b in self.enemy_bullets:
            b.y += b.dy * dt

        self.bullets = [b for b in self.bullets if -20 < b.y < SCREEN_H + 20]
        self.enemy_bullets = [b for b in self.enemy_bullets if -20 < b.y < SCREEN_H + 20]

        for b in list(self.bullets):
            for e in self.enemies:
                if e.alive and self._hit(b.x, b.y, 3, 8, e.x, e.y, 16, 16):
                    e.alive = False
                    self.score += e.points()
                    self.high_score = max(self.high_score, self.score)
                    self.sfx.play("boom")
                    if b in self.bullets:
                        self.bullets.remove(b)
                    break

        for b in list(self.enemy_bullets):
            if self._hit(b.x, b.y, 3, 8, self.player.x, self.player.y, self.player.w, self.player.h):
                self.enemy_bullets.remove(b)
                self.lives -= 1
                self.flash = 0.24
                self.sfx.play("hit")
                if self.lives <= 0:
                    self.state = "GAMEOVER"

    def _draw_starfield(self):
        for i in range(80):
            x = (i * 71 + int(self.time * (20 + i % 7))) % SCREEN_W
            y = (i * 137 + int(self.time * (12 + i % 5))) % SCREEN_H
            c = 120 + (i * 17) % 120
            self.screen.fill((c, c, c), (x, y, 2, 2))

    def _draw_hud(self):
        self.screen.blit(self.small.render(f"SCORE {self.score:05d}", True, (255, 255, 255)), (12, 8))
        self.screen.blit(self.small.render(f"HI {self.high_score:05d}", True, (255, 200, 80)), (180, 8))
        self.screen.blit(self.small.render(f"LIVES {self.lives}", True, (120, 255, 120)), (360, 8))
        self.screen.blit(self.small.render(f"CREDITS {self.credits}", True, (120, 200, 255)), (12, SCREEN_H - 24))

    def update(self, dt, keys):
        self.time += dt
        self.flash = max(0.0, self.flash - dt)

        if self.state == "PLAY":
            self.player.update(dt, keys)
            self._update_enemies(dt)
            self._update_bullets(dt)

            if random.random() < ENEMY_SHOT_CHANCE_BASE + self.level * ENEMY_SHOT_CHANCE_PER_LEVEL:
                shooters = [e for e in self.alive_enemies() if not e.diving]
                if shooters:
                    s = random.choice(shooters)
                    self.enemy_bullets.append(Bullet(s.x, s.y + 8, ENEMY_BULLET_SPEED, True))

            if not self.alive_enemies():
                self.level += 1
                self.formation_y = 80
                self._spawn_wave()
                self.sfx.play("start")

        elif self.state == "ATTRACT":
            self._update_enemies(dt)
            if random.random() < 0.012:
                shooters = [e for e in self.alive_enemies() if e.alive]
                if shooters:
                    s = random.choice(shooters)
                    self.enemy_bullets.append(Bullet(s.x, s.y + 8, ENEMY_BULLET_SPEED, True))
            self._update_bullets(dt)

            if not self.alive_enemies():
                self._spawn_wave()
                self.formation_y = 90

    def draw(self):
        base = (8, 8, 22) if self.flash <= 0 else (40, 10, 10)
        self.screen.fill(base)
        self._draw_starfield()

        for e in self.enemies:
            e.draw(self.screen, self.time)

        for b in self.bullets:
            pygame.draw.rect(self.screen, (140, 255, 140), (int(b.x) - 1, int(b.y) - 6, 3, 8))
        for b in self.enemy_bullets:
            pygame.draw.rect(self.screen, (255, 120, 120), (int(b.x) - 1, int(b.y), 3, 8))

        if self.state in ("PLAY", "GAMEOVER"):
            self.player.draw(self.screen)

        self._draw_hud()

        if self.state == "ATTRACT":
            t = self.font.render("GALAXIAN-LIKE ARCADE", True, (255, 220, 110))
            self.screen.blit(t, ((SCREEN_W - t.get_width()) // 2, 190))
            tip = self.small.render("PRESS 5 TO INSERT COIN", True, (180, 230, 255))
            self.screen.blit(tip, ((SCREEN_W - tip.get_width()) // 2, 250))
            tip2 = self.small.render("PRESS 1 TO START", True, (180, 230, 255))
            self.screen.blit(tip2, ((SCREEN_W - tip2.get_width()) // 2, 274))

        if self.state == "GAMEOVER":
            g = self.font.render("GAME OVER", True, (255, 90, 90))
            self.screen.blit(g, ((SCREEN_W - g.get_width()) // 2, 280))
            r = self.small.render("PRESS 1 TO START (CREDIT REQUIRED)", True, (255, 230, 180))
            self.screen.blit(r, ((SCREEN_W - r.get_width()) // 2, 314))

        pygame.display.flip()

    def run(self, max_frames: int = 0):
        running = True
        frames = 0
        while running:
            dt = min(0.033, self.clock.tick(FPS) / 1000.0)
            keys = pygame.key.get_pressed()

            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
                if event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_ESCAPE:
                        running = False
                    elif event.key == pygame.K_5:
                        self.credits += 1
                        self.sfx.play("coin")
                    elif event.key == pygame.K_1:
                        if self.credits > 0:
                            self.credits -= 1
                            self.start_game()
                    elif event.key == pygame.K_SPACE and self.state == "PLAY":
                        b = self.player.shoot()
                        if b:
                            self.bullets.append(b)
                            self.sfx.play("shoot")

            self.update(dt, keys)
            self.draw()

            frames += 1
            if max_frames and frames >= max_frames:
                break

        pygame.quit()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--headless", action="store_true")
    parser.add_argument("--max-frames", type=int, default=0)
    args = parser.parse_args()

    game = Game(headless=args.headless)
    game.run(max_frames=args.max_frames)


if __name__ == "__main__":
    main()
