#!/usr/bin/env python3
"""
imessage_gemini_ui.py - Pygame-based UI for iMessage Gemini Catchup

A modern desktop application for generating AI-powered summaries of iMessage group chats.
Allows selection between database mode and clipboard mode, with customizable message limits.

Usage:
  python imessage_gemini_ui.py

Requirements:
  - Python 3.10+
  - pip install google-genai python-dateutil pygame
  - Export GEMINI_API_KEY environment variable
"""

import os
import sys
import sqlite3
import subprocess
import threading
from datetime import datetime, timedelta
from dateutil import tz
from google import genai
from typing import List, Optional
import pygame

# ---------- CONFIG ----------
GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
DEFAULT_CHAT_DB = os.path.expanduser("~/Library/Messages/chat.db")
WINDOW_WIDTH = 1200
WINDOW_HEIGHT = 800
# ----------------------------

# Colors - Modern, refined palette
COLOR_BG = (13, 14, 20)           # Deep navy/black
COLOR_SURFACE = (25, 27, 38)      # Slightly lighter surface
COLOR_ACCENT = (100, 180, 255)    # Bright blue accent
COLOR_ACCENT_HOVER = (130, 200, 255)
COLOR_TEXT = (240, 242, 245)      # Almost white
COLOR_TEXT_DIM = (150, 160, 175)  # Dimmed text
COLOR_SUCCESS = (76, 175, 80)     # Green
COLOR_ERROR = (244, 67, 54)       # Red
COLOR_BORDER = (60, 68, 90)       # Border color

class UIState:
    SPLASH = "splash"
    CONFIG = "config"
    LOADING = "loading"
    SUMMARY = "summary"
    ERROR = "error"

class Button:
    def __init__(self, x, y, width, height, text, color=COLOR_ACCENT, hover_color=COLOR_ACCENT_HOVER):
        self.rect = pygame.Rect(x, y, width, height)
        self.text = text
        self.color = color
        self.hover_color = hover_color
        self.is_hovered = False
        self.is_active = True

    def draw(self, surface, font):
        color = self.hover_color if self.is_hovered else self.color
        pygame.draw.rect(surface, color, self.rect, border_radius=8)
        text_surf = font.render(self.text, True, COLOR_BG if color == COLOR_ACCENT or color == COLOR_ACCENT_HOVER else COLOR_TEXT)
        text_rect = text_surf.get_rect(center=self.rect.center)
        surface.blit(text_surf, text_rect)

    def is_clicked(self, pos):
        return self.rect.collidepoint(pos) and self.is_active

    def update_hover(self, pos):
        self.is_hovered = self.rect.collidepoint(pos) and self.is_active

class TextInput:
    def __init__(self, x, y, width, height, placeholder="", default_value=""):
        self.rect = pygame.Rect(x, y, width, height)
        self.text = default_value
        self.placeholder = placeholder
        self.is_focused = False
        self.cursor_visible = True
        self.cursor_timer = 0

    def draw(self, surface, font_small, font_regular):
        # Border
        border_color = COLOR_ACCENT if self.is_focused else COLOR_BORDER
        pygame.draw.rect(surface, border_color, self.rect, width=2, border_radius=6)
        pygame.draw.rect(surface, COLOR_SURFACE, self.rect, border_radius=6)

        # Text
        display_text = self.text if self.text else self.placeholder
        color = COLOR_TEXT if self.text else COLOR_TEXT_DIM
        text_surf = font_regular.render(display_text, True, color)
        surface.blit(text_surf, (self.rect.x + 12, self.rect.y + self.rect.height // 2 - text_surf.get_height() // 2))

        # Cursor
        if self.is_focused and self.cursor_visible:
            cursor_x = self.rect.x + 12 + font_regular.size(self.text)[0]
            pygame.draw.line(surface, COLOR_ACCENT, (cursor_x, self.rect.y + 8), (cursor_x, self.rect.y + self.rect.height - 8), 2)

    def handle_event(self, event):
        if event.type == pygame.MOUSEBUTTONDOWN:
            self.is_focused = self.rect.collidepoint(event.pos)
        elif event.type == pygame.KEYDOWN and self.is_focused:
            if event.key == pygame.K_BACKSPACE:
                self.text = self.text[:-1]
            elif event.key == pygame.K_RETURN:
                return True
            elif event.mod & pygame.KMOD_META:  # Command key on macOS
                if event.key == pygame.K_v:  # Paste
                    try:
                        applescript = 'return the clipboard'
                        p = subprocess.run(["osascript", "-e", applescript], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
                        if p.returncode == 0:
                            clipboard_text = p.stdout.strip()
                            self.text += clipboard_text
                    except Exception:
                        pass
                elif event.key == pygame.K_a:  # Select all
                    pass  # Could implement if needed
                elif event.key == pygame.K_c:  # Copy
                    try:
                        applescript = f'set the clipboard to "{self.text}"'
                        subprocess.run(["osascript", "-e", applescript], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                    except Exception:
                        pass
                elif event.key == pygame.K_x:  # Cut
                    try:
                        applescript = f'set the clipboard to "{self.text}"'
                        subprocess.run(["osascript", "-e", applescript], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                        self.text = ""
                    except Exception:
                        pass
            elif event.unicode.isprintable():
                self.text += event.unicode
        return False

    def update(self, dt):
        self.cursor_timer += dt
        if self.cursor_timer > 0.5:
            self.cursor_visible = not self.cursor_visible
            self.cursor_timer = 0

class RadioButton:
    def __init__(self, x, y, label, group_id):
        self.rect = pygame.Rect(x, y, 20, 20)
        self.label = label
        self.group_id = group_id
        self.is_selected = False

    def draw(self, surface, font_small):
        # Outer circle
        pygame.draw.circle(surface, COLOR_BORDER, self.rect.center, 10, 2)
        if self.is_selected:
            pygame.draw.circle(surface, COLOR_ACCENT, self.rect.center, 6)

        # Label
        text_surf = font_small.render(self.label, True, COLOR_TEXT)
        surface.blit(text_surf, (self.rect.x + 30, self.rect.y + 2))

    def is_clicked(self, pos):
        return self.rect.collidepoint(pos) or (pos[0] > self.rect.x and pos[0] < self.rect.x + 200 and abs(pos[1] - self.rect.centery) < 15)

class Slider:
    def __init__(self, x, y, width, min_val, max_val, default_val):
        self.rect = pygame.Rect(x, y, width, 40)
        self.min_val = min_val
        self.max_val = max_val
        self.value = default_val
        self.is_dragging = False
        self.track_rect = pygame.Rect(x, y + 15, width, 10)

    def draw(self, surface, font_small):
        # Track
        pygame.draw.rect(surface, COLOR_BORDER, self.track_rect, border_radius=5)

        # Position on track
        ratio = (self.value - self.min_val) / (self.max_val - self.min_val)
        thumb_x = self.track_rect.x + ratio * self.track_rect.width
        pygame.draw.circle(surface, COLOR_ACCENT, (thumb_x, self.track_rect.centery), 8)

        # Label
        text_surf = font_small.render(f"Messages: {int(self.value)}", True, COLOR_TEXT)
        surface.blit(text_surf, (self.rect.x, self.rect.y - 20))

    def handle_event(self, event):
        if event.type == pygame.MOUSEBUTTONDOWN:
            self.is_dragging = self.track_rect.collidepoint(event.pos)
        elif event.type == pygame.MOUSEBUTTONUP:
            self.is_dragging = False
        elif event.type == pygame.MOUSEMOTION and self.is_dragging:
            ratio = (event.pos[0] - self.track_rect.x) / self.track_rect.width
            self.value = max(self.min_val, min(self.max_val, self.min_val + ratio * (self.max_val - self.min_val)))

class App:
    def __init__(self):
        pygame.init()
        self.screen = pygame.display.set_mode((WINDOW_WIDTH, WINDOW_HEIGHT))
        pygame.display.set_caption("iMessage Gemini Catchup")
        self.clock = pygame.time.Clock()
        self.running = True

        # Fonts
        self.font_title = pygame.font.SysFont("Menlo", 32, bold=True)
        self.font_large = pygame.font.SysFont("Menlo", 18)
        self.font_regular = pygame.font.SysFont("Menlo", 14)
        self.font_small = pygame.font.SysFont("Menlo", 12)

        # State
        self.state = UIState.SPLASH
        self.mode = "db"  # 'db' or 'clipboard'
        self.error_msg = ""
        self.summary_text = ""

        # UI Elements
        self.chat_name_input = TextInput(100, 200, 400, 40, placeholder="Enter group chat name", default_value="")
        self.message_count_slider = Slider(100, 310, 400, 20, 500, 150)

        self.mode_db = RadioButton(100, 380, "Database Mode", "mode")
        self.mode_clipboard = RadioButton(100, 420, "Clipboard Mode", "mode")
        self.mode_db.is_selected = True

        self.btn_summarize = Button(100, 480, 200, 50, "Generate Catchup", COLOR_SUCCESS)
        self.btn_retry = Button(100, 480, 200, 50, "Retry", COLOR_ACCENT)
        self.btn_back = Button(100, 540, 200, 50, "Back", COLOR_TEXT_DIM, COLOR_TEXT)

        # For summary scrolling
        self.summary_scroll_offset = 0

    def draw_splash(self):
        """Draw the splash screen with introduction"""
        title = self.font_title.render("iMessage Catchup", True, COLOR_ACCENT)
        subtitle = self.font_large.render("AI-Powered Group Chat Summaries", True, COLOR_TEXT_DIM)

        self.screen.blit(title, (WINDOW_WIDTH // 2 - title.get_width() // 2, 80))
        self.screen.blit(subtitle, (WINDOW_WIDTH // 2 - subtitle.get_width() // 2, 140))

        # Features
        features = [
            "✓ Summarize group chats with Gemini AI",
            "✓ Extract action items and key decisions",
            "✓ Identify who said what",
            "✓ Both database and clipboard modes"
        ]
        y = 220
        for feat in features:
            feat_surf = self.font_regular.render(feat, True, COLOR_TEXT_DIM)
            self.screen.blit(feat_surf, (80, y))
            y += 40

        # Start button
        start_btn = Button(WINDOW_WIDTH // 2 - 100, 500, 200, 50, "Get Started", COLOR_ACCENT)
        start_btn.draw(self.screen, self.font_regular)
        return start_btn

    def draw_config(self):
        """Draw the configuration screen"""
        title = self.font_title.render("Configure", True, COLOR_ACCENT)
        self.screen.blit(title, (50, 30))

        # Chat name input
        label = self.font_regular.render("Group Chat Name:", True, COLOR_TEXT)
        self.screen.blit(label, (50, 160))
        self.chat_name_input.draw(self.screen, self.font_small, self.font_regular)

        # Message count slider
        self.message_count_slider.draw(self.screen, self.font_small)

        # Mode selection
        mode_label = self.font_regular.render("Source Mode:", True, COLOR_TEXT)
        self.screen.blit(mode_label, (50, 360))
        self.mode_db.draw(self.screen, self.font_small)
        self.mode_clipboard.draw(self.screen, self.font_small)

        # Buttons
        self.btn_summarize.draw(self.screen, self.font_regular)
        self.btn_back.draw(self.screen, self.font_regular)

    def draw_loading(self):
        """Draw loading screen"""
        loading_text = self.font_title.render("Generating Catchup...", True, COLOR_ACCENT)
        self.screen.blit(loading_text, (WINDOW_WIDTH // 2 - loading_text.get_width() // 2, WINDOW_HEIGHT // 2 - 50))

        # Spinner animation
        import math
        angle = (pygame.time.get_ticks() % 2000) / 2000 * 2 * math.pi
        spinner_x = WINDOW_WIDTH // 2 + 60 * math.cos(angle)
        spinner_y = WINDOW_HEIGHT // 2 + 20 + 60 * math.sin(angle)
        pygame.draw.circle(self.screen, COLOR_ACCENT, (int(spinner_x), int(spinner_y)), 6)

    def draw_summary(self):
        """Draw the summary screen with scrollable content"""
        title = self.font_title.render("Catchup Summary", True, COLOR_ACCENT)
        self.screen.blit(title, (50, 20))

        # Content area
        content_rect = pygame.Rect(50, 70, WINDOW_WIDTH - 100, WINDOW_HEIGHT - 180)
        pygame.draw.rect(self.screen, COLOR_SURFACE, content_rect, border_radius=8)
        pygame.draw.rect(self.screen, COLOR_BORDER, content_rect, width=2, border_radius=8)

        # Enable clipping for scrolled content
        pygame.draw.rect(self.screen, COLOR_BG, content_rect)
        self.screen.set_clip(content_rect)

        # Draw summary text with word wrapping
        y_offset = 20 - self.summary_scroll_offset
        lines = self.summary_text.split('\n')
        for line in lines:
            if y_offset > content_rect.height:
                break
            if y_offset > -20:
                # Word wrap
                words = line.split(' ')
                current_line = ""
                for word in words:
                    test_line = current_line + (" " if current_line else "") + word
                    if self.font_regular.size(test_line)[0] > content_rect.width - 40:
                        if current_line:
                            text_surf = self.font_regular.render(current_line, True, COLOR_TEXT)
                            self.screen.blit(text_surf, (content_rect.x + 20, content_rect.y + y_offset))
                            y_offset += 20
                        current_line = word
                    else:
                        current_line = test_line
                if current_line:
                    text_surf = self.font_regular.render(current_line, True, COLOR_TEXT)
                    self.screen.blit(text_surf, (content_rect.x + 20, content_rect.y + y_offset))
                    y_offset += 20
            else:
                y_offset += 20

        self.screen.set_clip(None)

        # Buttons
        self.btn_retry.draw(self.screen, self.font_regular)
        self.btn_back.draw(self.screen, self.font_regular)

    def draw_error(self):
        """Draw error screen"""
        title = self.font_title.render("Error", True, COLOR_ERROR)
        self.screen.blit(title, (50, 80))

        # Error message with wrapping
        y = 150
        words = self.error_msg.split(' ')
        current_line = ""
        for word in words:
            test_line = current_line + (" " if current_line else "") + word
            if self.font_regular.size(test_line)[0] > WINDOW_WIDTH - 100:
                if current_line:
                    text_surf = self.font_regular.render(current_line, True, COLOR_TEXT)
                    self.screen.blit(text_surf, (50, y))
                    y += 30
                current_line = word
            else:
                current_line = test_line
        if current_line:
            text_surf = self.font_regular.render(current_line, True, COLOR_TEXT)
            self.screen.blit(text_surf, (50, y))

        # Buttons
        self.btn_retry.draw(self.screen, self.font_regular)
        self.btn_back.draw(self.screen, self.font_regular)

    def handle_events(self):
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.running = False

            if self.state == UIState.SPLASH:
                if event.type == pygame.MOUSEBUTTONDOWN:
                    start_btn = self.draw_splash()
                    if start_btn.is_clicked(event.pos):
                        self.state = UIState.CONFIG

            elif self.state == UIState.CONFIG:
                self.chat_name_input.handle_event(event)
                self.message_count_slider.handle_event(event)

                if event.type == pygame.MOUSEBUTTONDOWN:
                    if self.mode_db.is_clicked(event.pos):
                        self.mode_db.is_selected = True
                        self.mode_clipboard.is_selected = False
                        self.mode = "db"
                    elif self.mode_clipboard.is_clicked(event.pos):
                        self.mode_db.is_selected = False
                        self.mode_clipboard.is_selected = True
                        self.mode = "clipboard"
                    elif self.btn_summarize.is_clicked(event.pos):
                        self.generate_summary()
                    elif self.btn_back.is_clicked(event.pos):
                        self.state = UIState.SPLASH

            elif self.state == UIState.SUMMARY:
                if event.type == pygame.MOUSEBUTTONDOWN:
                    if self.btn_retry.is_clicked(event.pos):
                        self.state = UIState.CONFIG
                    elif self.btn_back.is_clicked(event.pos):
                        self.state = UIState.SPLASH
                elif event.type == pygame.MOUSEWHEEL:
                    self.summary_scroll_offset = max(0, self.summary_scroll_offset - event.y * 30)

            elif self.state == UIState.ERROR:
                if event.type == pygame.MOUSEBUTTONDOWN:
                    if self.btn_retry.is_clicked(event.pos):
                        self.state = UIState.CONFIG
                    elif self.btn_back.is_clicked(event.pos):
                        self.state = UIState.SPLASH

    def generate_summary(self):
        if not GEMINI_API_KEY:
            self.error_msg = "ERROR: Set GEMINI_API_KEY environment variable"
            self.state = UIState.ERROR
            return

        if self.mode == "db" and not self.chat_name_input.text:
            self.error_msg = "Please enter a group chat name"
            self.state = UIState.ERROR
            return

        self.state = UIState.LOADING
        thread = threading.Thread(target=self._fetch_and_summarize)
        thread.daemon = True
        thread.start()

    def _fetch_and_summarize(self):
        try:
            if self.mode == "db":
                messages = self._fetch_from_db()
            else:
                messages = self._fetch_from_clipboard()

            if not messages:
                self.error_msg = "No messages found"
                self.state = UIState.ERROR
                return

            self.summary_text = self._call_gemini(messages)
            self.summary_scroll_offset = 0
            self.state = UIState.SUMMARY

        except Exception as e:
            self.error_msg = f"Error: {str(e)}"
            self.state = UIState.ERROR

    def _fetch_from_db(self):
        if not os.path.exists(DEFAULT_CHAT_DB):
            raise FileNotFoundError(f"Chat DB not found at {DEFAULT_CHAT_DB}")

        conn = sqlite3.connect(DEFAULT_CHAT_DB)
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()

        cur.execute("SELECT ROWID, display_name FROM chat WHERE display_name = ?", (self.chat_name_input.text,))
        chat_rows = cur.fetchall()
        if not chat_rows:
            cur.execute("SELECT ROWID, display_name FROM chat WHERE display_name LIKE ?", (f"%{self.chat_name_input.text}%",))
            chat_rows = cur.fetchall()

        if not chat_rows:
            raise ValueError(f"No chat found matching '{self.chat_name_input.text}'")

        chat_rowids = [r["ROWID"] for r in chat_rows]
        placeholders = ",".join(["?"] * len(chat_rowids))
        limit = int(self.message_count_slider.value)

        query = f"""
        SELECT m.text, m.date, m.is_from_me, h.id as handle_id, m.service
        FROM message m
        JOIN chat_message_join cmj ON cmj.message_id = m.ROWID
        LEFT JOIN handle h ON m.handle_id = h.ROWID
        WHERE cmj.chat_id IN ({placeholders})
        ORDER BY m.date DESC
        LIMIT ?
        """
        cur.execute(query, chat_rowids + [limit])
        rows = cur.fetchall()
        conn.close()

        messages = []
        for r in rows[::-1]:
            dt = self._mac_time_to_datetime(r["date"])
            messages.append({
                "text": r["text"] or "",
                "date": dt.isoformat() if dt else None,
                "is_from_me": bool(r["is_from_me"]),
                "handle": r["handle_id"] or "Unknown"
            })
        return messages

    def _fetch_from_clipboard(self):
        applescript = r'''
        tell application "System Events"
            keystroke "c" using {command down}
        end tell
        delay 0.15
        set theClipboard to the clipboard
        return theClipboard
        '''
        p = subprocess.run(["osascript", "-e", applescript], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        if p.returncode != 0:
            raise RuntimeError(f"osascript failed: {p.stderr.strip()}")

        clip = p.stdout
        messages = [{"text": line, "date": None, "is_from_me": False, "handle": "unknown"} for line in clip.splitlines() if line.strip()]
        return messages

    def _mac_time_to_datetime(self, mac_seconds):
        try:
            if mac_seconds is None:
                return None
            s = float(mac_seconds)
            if s > 1e12:
                s = s / 1_000_000
            elif s > 1e10:
                s = s / 1000
            mac_epoch = datetime(2001, 1, 1, tzinfo=tz.tzutc())
            dt = mac_epoch + timedelta(seconds=s)
            return dt.astimezone(tz.tzlocal())
        except Exception:
            return None

    def _call_gemini(self, messages):
        combined_text = ""
        for m in messages:
            ts = m.get("date") or ""
            sender = "Me" if m.get("is_from_me") else (m.get("handle") or "Unknown")
            text = m.get("text") or ""
            combined_text += f"[{ts}] {sender}: {text}\n"

        system_instruction = (
            "You are an assistant that reads an iMessage group chat export and returns a compact, bullet-point 'catch-up' summary.\n"
            "Output structure:\n"
            "1) 6-12 bullet points summarizing what happened (decisions, dates, plans, action items, drama/highlights).\n"
            "2) A short 'Who said what' section listing notable speakers and their short positions.\n"
            "3) Explicit list of action items with assignees and deadlines (if present in text).\n"
            "Be concise and only include what is contained in the messages. Use ISO dates when present."
        )

        prompt = "Here is the chat export:\n\n" + combined_text + "\n\n" + system_instruction

        client = genai.Client(api_key=GEMINI_API_KEY)
        response = client.models.generate_content(
            model=GEMINI_MODEL,
            contents=prompt,
        )
        return response.text

    def update(self):
        pass

    def draw(self):
        self.screen.fill(COLOR_BG)

        if self.state == UIState.SPLASH:
            start_btn = self.draw_splash()
            start_btn.update_hover(pygame.mouse.get_pos())
        elif self.state == UIState.CONFIG:
            self.btn_summarize.update_hover(pygame.mouse.get_pos())
            self.btn_back.update_hover(pygame.mouse.get_pos())
            self.draw_config()
        elif self.state == UIState.LOADING:
            self.draw_loading()
        elif self.state == UIState.SUMMARY:
            self.btn_retry.update_hover(pygame.mouse.get_pos())
            self.btn_back.update_hover(pygame.mouse.get_pos())
            self.draw_summary()
        elif self.state == UIState.ERROR:
            self.btn_retry.update_hover(pygame.mouse.get_pos())
            self.btn_back.update_hover(pygame.mouse.get_pos())
            self.draw_error()

        pygame.display.flip()

    def run(self):
        while self.running:
            self.handle_events()
            self.update()
            self.draw()
            self.clock.tick(60)

        pygame.quit()

if __name__ == "__main__":
    app = App()
    app.run()
