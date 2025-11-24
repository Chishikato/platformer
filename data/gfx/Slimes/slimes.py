import pygame
import os

# --- Constants ---
SCREEN_WIDTH = 800
SCREEN_HEIGHT = 600
FPS = 10
BG_COLOR = (255, 255, 255)  # White background
SCALE_FACTOR = 6  # Scale up pixel art so it's big enough to see

# Position for the ground (Y-coordinate)
GROUND_Y = 450 

# --- Animation Settings ---
# The sprites assume 7 rows of colors.
# Row 0: Pink, 1: Red, 2: Orange, 3: Blue, 4: Green, 5: Brown, 6: Grey
SELECTED_COLOR_ROW = 0 

# Define animations that should play forward then backward (ping-pong)
PING_PONG_ANIMS = ["Jump"]

class SpriteSheet:
    def __init__(self, filename):
        try:
            # convert_alpha() is crucial for loading transparent PNGs correctly
            self.sheet = pygame.image.load(filename).convert_alpha()
            self.width = self.sheet.get_width()
            self.height = self.sheet.get_height()
            
            # Calculate frame dimensions assuming standard 7-row sprite sheet layout
            self.frame_height = self.height // 7
            
            # Assume frames are square (standard for this art style)
            # If your sprites look cut off, we might need to adjust this to hardcoded values
            self.frame_width = self.frame_height 
            
            self.columns = self.width // self.frame_width
            
        except pygame.error as e:
            print(f"Unable to load sprite sheet image: {filename}")
            raise SystemExit(e)

    def get_frames(self, row):
        """Extracts all frames from a specific row (color variant)"""
        frames = []
        for col in range(self.columns):
            # Create a surface for the single frame with per-pixel alpha transparency
            frame = pygame.Surface((self.frame_width, self.frame_height), pygame.SRCALPHA)
            
            # Calculate position on the sheet
            x = col * self.frame_width
            y = row * self.frame_height
            
            # Blit the specific chunk of the sheet onto the frame surface
            frame.blit(self.sheet, (0, 0), (x, y, self.frame_width, self.frame_height))
            
            # Scale it up
            scaled_width = self.frame_width * SCALE_FACTOR
            scaled_height = self.frame_height * SCALE_FACTOR
            scale_frame = pygame.transform.scale(frame, (scaled_width, scaled_height))
            
            frames.append(scale_frame)
        return frames

def main():
    pygame.init()
    screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
    pygame.display.set_caption("Slime Sprite Animator")
    clock = pygame.time.Clock()

    # --- Load Assets ---
    # Dictionary mapping keys to animation data
    animations = {}
    
    # List of your files
    files = {
        "Idle 1": "slime_idle1.png",
        "Idle 2": "slime_idle2.png",
        "Idle 3": "slime_idle3.png",
        "Move": "slime_move.png",
        "Jump": "slime_jump.png",
        "Swallow": "slime_swallow.png",
        "Die": "slime_die.png",
        "Hit": "slime_hit.png"
    }

    print("Loading sprite sheets...")
    for name, filename in files.items():
        if os.path.exists(filename):
            sheet = SpriteSheet(filename)
            # Get frames for the selected color row
            frames = sheet.get_frames(SELECTED_COLOR_ROW)
            animations[name] = frames
            print(f"Loaded {name}: {len(frames)} frames")
        else:
            print(f"Warning: File {filename} not found.")

    if not animations:
        print("No images found! Make sure png files are in the same folder.")
        return

    # --- State Management ---
    animation_keys = list(animations.keys())
    current_anim_name = "Idle 1" if "Idle 1" in animations else animation_keys[0]
    current_frames = animations[current_anim_name]
    
    frame_index = 0
    anim_direction = 1 # 1 for forward, -1 for backward
    paused = False # Allow manual control
    last_update = pygame.time.get_ticks()
    animation_cooldown = 100 # Milliseconds per frame

    running = True
    while running:
        # --- Event Handling ---
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            
            # Key bindings to switch animations
            if event.type == pygame.KEYDOWN:
                new_anim = None
                if event.key == pygame.K_1: new_anim = "Idle 1"
                elif event.key == pygame.K_2: new_anim = "Idle 2"
                elif event.key == pygame.K_3: new_anim = "Idle 3"
                elif event.key == pygame.K_4: new_anim = "Move"
                elif event.key == pygame.K_5: new_anim = "Jump"
                elif event.key == pygame.K_6: new_anim = "Swallow"
                elif event.key == pygame.K_7: new_anim = "Die"
                elif event.key == pygame.K_8: new_anim = "Hit"
                
                # Manual Step Controls
                elif event.key == pygame.K_RIGHT:
                    paused = True
                    frame_index = (frame_index + 1) % len(current_frames)
                elif event.key == pygame.K_LEFT:
                    paused = True
                    frame_index = (frame_index - 1) % len(current_frames)
                elif event.key == pygame.K_SPACE:
                    paused = not paused

                if new_anim and new_anim in animations:
                    current_anim_name = new_anim
                    current_frames = animations[new_anim]
                    frame_index = 0 # Reset to start of animation
                    anim_direction = 1 # Reset direction for new anim
                    paused = False # Unpause when switching animations

        # --- Update Animation ---
        current_time = pygame.time.get_ticks()
        if not paused and current_time - last_update >= animation_cooldown:
            # Update logic based on animation type
            if current_anim_name in PING_PONG_ANIMS and len(current_frames) > 1:
                frame_index += anim_direction
                
                # Reached the end, reverse direction
                if frame_index >= len(current_frames):
                    frame_index = len(current_frames) - 2
                    anim_direction = -1
                # Reached the beginning, reverse direction
                elif frame_index < 0:
                    frame_index = 1
                    anim_direction = 1
            else:
                # Standard looping animation
                frame_index += 1
                if frame_index >= len(current_frames):
                    frame_index = 0
            
            last_update = current_time

        # --- Drawing ---
        screen.fill(BG_COLOR)

        # Draw a simple floor line so you can see the "ground" (Darker now for white bg)
        pygame.draw.line(screen, (50, 50, 50), (0, GROUND_Y), (SCREEN_WIDTH, GROUND_Y), 2)

        # Draw Text Info (Black text for white bg)
        font = pygame.font.SysFont("Arial", 24)
        status_text = "PAUSED" if paused else "PLAYING"
        text_surf = font.render(f"{current_anim_name} [{status_text}] Frame {frame_index+1}/{len(current_frames)}", True, (0, 0, 0))
        help_surf = font.render("1-8: Switch | Arrows: Step Frame | Space: Pause", True, (100, 100, 100))
        screen.blit(text_surf, (10, 10))
        screen.blit(help_surf, (10, 40))

        # Draw Slime anchored to the ground
        if current_frames:
            # Ensure frame_index is within bounds (useful when switching anims of different lengths)
            frame_index = frame_index % len(current_frames)
            img = current_frames[frame_index]
            # Use 'midbottom' to anchor the feet to the ground
            # This behaves like a game character (feet stay planted even if sprite size changes)
            rect = img.get_rect(midbottom=(SCREEN_WIDTH // 2, GROUND_Y))
            screen.blit(img, rect)

        pygame.display.flip()
        clock.tick(FPS)

    pygame.quit()

if __name__ == "__main__":
    main()