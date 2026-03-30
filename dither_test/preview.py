#!/usr/bin/env python3
"""
Interactive Dithering Preview Tool

Opens a window to preview different dithering algorithms in real-time.
Use keyboard shortcuts to cycle through algorithms.

Requirements:
    pip install pillow

Usage:
    python preview.py image.jpg
"""

import argparse
import sys
import os
from pathlib import Path

try:
    import tkinter as tk
    from tkinter import ttk, filedialog
    from PIL import Image, ImageTk
except ImportError as e:
    print(f"Error: Missing dependency - {e}")
    print("Install with: pip install pillow")
    sys.exit(1)

from dither_algorithms import (
    DITHER_ALGORITHMS,
    apply_dithering,
    get_algorithm_names,
    PALETTE_RGB,
    PALETTE_NAMES,
)

DISPLAY_WIDTH = 800
DISPLAY_HEIGHT = 480


class DitherPreview:
    def __init__(self, image_path: str = None):
        self.root = tk.Tk()
        self.root.title("Dithering Preview - 6-Color E-Ink")
        self.root.configure(bg='#1a1a2e')

        self.algorithms = get_algorithm_names()
        self.current_algo_idx = 0
        self.source_image = None
        self.prepared_image = None
        self.orientation = 0

        self.setup_ui()
        self.bind_keys()

        if image_path and os.path.exists(image_path):
            self.load_image(image_path)

    def setup_ui(self):
        # Main container
        main_frame = ttk.Frame(self.root)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # Style
        style = ttk.Style()
        style.configure('TFrame', background='#1a1a2e')
        style.configure('TLabel', background='#1a1a2e', foreground='#eee')
        style.configure('Title.TLabel', font=('Helvetica', 14, 'bold'), foreground='#00d9ff')
        style.configure('Info.TLabel', font=('Helvetica', 10))

        # Top bar with controls
        top_frame = ttk.Frame(main_frame)
        top_frame.pack(fill=tk.X, pady=(0, 10))

        # Algorithm selector
        ttk.Label(top_frame, text="Algorithm:", style='TLabel').pack(side=tk.LEFT)

        self.algo_var = tk.StringVar(value=self.algorithms[0])
        self.algo_combo = ttk.Combobox(
            top_frame,
            textvariable=self.algo_var,
            values=self.algorithms,
            state='readonly',
            width=25
        )
        self.algo_combo.pack(side=tk.LEFT, padx=(5, 20))
        self.algo_combo.bind('<<ComboboxSelected>>', self.on_algo_change)

        # Rotation
        ttk.Label(top_frame, text="Rotation:", style='TLabel').pack(side=tk.LEFT)
        self.rotation_var = tk.StringVar(value='0')
        rotation_combo = ttk.Combobox(
            top_frame,
            textvariable=self.rotation_var,
            values=['0', '90', '180', '270'],
            state='readonly',
            width=5
        )
        rotation_combo.pack(side=tk.LEFT, padx=(5, 20))
        rotation_combo.bind('<<ComboboxSelected>>', self.on_rotation_change)

        # Load button
        load_btn = ttk.Button(top_frame, text="Load Image", command=self.open_file_dialog)
        load_btn.pack(side=tk.LEFT, padx=5)

        # Save button
        save_btn = ttk.Button(top_frame, text="Save Result", command=self.save_result)
        save_btn.pack(side=tk.LEFT, padx=5)

        # Image display area
        display_frame = ttk.Frame(main_frame)
        display_frame.pack(fill=tk.BOTH, expand=True)

        # Source image
        source_frame = ttk.LabelFrame(display_frame, text="Source (Prepared)")
        source_frame.pack(side=tk.LEFT, padx=(0, 5))

        self.source_label = ttk.Label(source_frame)
        self.source_label.pack(padx=5, pady=5)

        # Result image
        result_frame = ttk.LabelFrame(display_frame, text="Dithered Result")
        result_frame.pack(side=tk.LEFT, padx=(5, 0))

        self.result_label = ttk.Label(result_frame)
        self.result_label.pack(padx=5, pady=5)

        # Info panel
        info_frame = ttk.Frame(main_frame)
        info_frame.pack(fill=tk.X, pady=(10, 0))

        self.algo_title = ttk.Label(info_frame, text="", style='Title.TLabel')
        self.algo_title.pack(anchor=tk.W)

        self.algo_desc = ttk.Label(info_frame, text="", style='Info.TLabel', wraplength=800)
        self.algo_desc.pack(anchor=tk.W)

        self.time_label = ttk.Label(info_frame, text="", style='Info.TLabel')
        self.time_label.pack(anchor=tk.W)

        # Palette display
        palette_frame = ttk.Frame(main_frame)
        palette_frame.pack(fill=tk.X, pady=(10, 0))

        ttk.Label(palette_frame, text="Palette:", style='TLabel').pack(side=tk.LEFT)

        for color, name in zip(PALETTE_RGB, PALETTE_NAMES):
            r, g, b = color
            hex_color = f'#{r:02x}{g:02x}{b:02x}'
            swatch = tk.Canvas(palette_frame, width=30, height=20, bg=hex_color,
                              highlightthickness=1, highlightbackground='#333')
            swatch.pack(side=tk.LEFT, padx=2)

        # Keyboard shortcuts info
        shortcuts_frame = ttk.Frame(main_frame)
        shortcuts_frame.pack(fill=tk.X, pady=(10, 0))

        ttk.Label(
            shortcuts_frame,
            text="Shortcuts: ← → or A/D = cycle algorithms | R = rotate | S = save | O = open | Q = quit",
            style='Info.TLabel'
        ).pack()

        # Set placeholder
        self.show_placeholder()

    def bind_keys(self):
        self.root.bind('<Left>', lambda e: self.prev_algo())
        self.root.bind('<Right>', lambda e: self.next_algo())
        self.root.bind('a', lambda e: self.prev_algo())
        self.root.bind('d', lambda e: self.next_algo())
        self.root.bind('r', lambda e: self.rotate())
        self.root.bind('s', lambda e: self.save_result())
        self.root.bind('o', lambda e: self.open_file_dialog())
        self.root.bind('q', lambda e: self.root.quit())
        self.root.bind('<Escape>', lambda e: self.root.quit())

    def show_placeholder(self):
        # Create placeholder images
        placeholder = Image.new('RGB', (400, 240), (40, 40, 60))
        try:
            from PIL import ImageDraw
            draw = ImageDraw.Draw(placeholder)
            draw.text((150, 110), "Load an image", fill=(100, 100, 120))
        except:
            pass

        self.source_photo = ImageTk.PhotoImage(placeholder)
        self.result_photo = ImageTk.PhotoImage(placeholder)

        self.source_label.configure(image=self.source_photo)
        self.result_label.configure(image=self.result_photo)

        self.algo_title.configure(text="No image loaded")
        self.algo_desc.configure(text="Press 'O' or click 'Load Image' to open an image file")
        self.time_label.configure(text="")

    def prepare_image(self, img: Image.Image) -> Image.Image:
        """Prepare image for display dimensions."""
        # Apply rotation
        if self.orientation == 90:
            img = img.transpose(Image.Transpose.ROTATE_270)
        elif self.orientation == 180:
            img = img.transpose(Image.Transpose.ROTATE_180)
        elif self.orientation == 270:
            img = img.transpose(Image.Transpose.ROTATE_90)

        # Scale to fit
        scale = min(DISPLAY_WIDTH / img.width, DISPLAY_HEIGHT / img.height)
        new_w = int(img.width * scale)
        new_h = int(img.height * scale)
        img = img.resize((new_w, new_h), Image.Resampling.LANCZOS)

        # Center on canvas
        canvas = Image.new('RGB', (DISPLAY_WIDTH, DISPLAY_HEIGHT), (255, 255, 255))
        x = (DISPLAY_WIDTH - new_w) // 2
        y = (DISPLAY_HEIGHT - new_h) // 2
        canvas.paste(img, (x, y))

        return canvas

    def load_image(self, path: str):
        try:
            self.source_image = Image.open(path).convert('RGB')
            self.image_path = path
            self.root.title(f"Dithering Preview - {Path(path).name}")
            self.update_display()
        except Exception as e:
            print(f"Error loading image: {e}")

    def update_display(self):
        if self.source_image is None:
            return

        import time

        # Prepare source image
        self.prepared_image = self.prepare_image(self.source_image)

        # Create display-size version for preview (half size to fit window)
        preview_size = (DISPLAY_WIDTH // 2, DISPLAY_HEIGHT // 2)
        source_preview = self.prepared_image.resize(preview_size, Image.Resampling.LANCZOS)

        # Apply dithering
        algo_name = self.algo_var.get()
        algo_info = DITHER_ALGORITHMS[algo_name]

        start_time = time.time()
        dithered = apply_dithering(self.prepared_image, algo_name)
        duration = time.time() - start_time

        self.dithered_result = dithered
        result_preview = dithered.resize(preview_size, Image.Resampling.LANCZOS)

        # Update display
        self.source_photo = ImageTk.PhotoImage(source_preview)
        self.result_photo = ImageTk.PhotoImage(result_preview)

        self.source_label.configure(image=self.source_photo)
        self.result_label.configure(image=self.result_photo)

        self.algo_title.configure(text=algo_info['name'])
        self.algo_desc.configure(text=algo_info['description'])
        self.time_label.configure(text=f"Processing time: {duration:.2f}s")

    def on_algo_change(self, event=None):
        self.current_algo_idx = self.algorithms.index(self.algo_var.get())
        self.update_display()

    def on_rotation_change(self, event=None):
        self.orientation = int(self.rotation_var.get())
        self.update_display()

    def next_algo(self):
        self.current_algo_idx = (self.current_algo_idx + 1) % len(self.algorithms)
        self.algo_var.set(self.algorithms[self.current_algo_idx])
        self.update_display()

    def prev_algo(self):
        self.current_algo_idx = (self.current_algo_idx - 1) % len(self.algorithms)
        self.algo_var.set(self.algorithms[self.current_algo_idx])
        self.update_display()

    def rotate(self):
        rotations = ['0', '90', '180', '270']
        current_idx = rotations.index(self.rotation_var.get())
        next_idx = (current_idx + 1) % 4
        self.rotation_var.set(rotations[next_idx])
        self.orientation = int(rotations[next_idx])
        self.update_display()

    def open_file_dialog(self):
        filetypes = [
            ('Image files', '*.jpg *.jpeg *.png *.bmp *.gif *.tiff'),
            ('All files', '*.*')
        ]
        path = filedialog.askopenfilename(filetypes=filetypes)
        if path:
            self.load_image(path)

    def save_result(self):
        if not hasattr(self, 'dithered_result') or self.dithered_result is None:
            return

        algo_name = self.algo_var.get()
        base_name = Path(self.image_path).stem if hasattr(self, 'image_path') else 'output'
        default_name = f"{base_name}_{algo_name}.png"

        path = filedialog.asksaveasfilename(
            defaultextension='.png',
            initialfile=default_name,
            filetypes=[('PNG', '*.png'), ('BMP', '*.bmp'), ('JPEG', '*.jpg')]
        )
        if path:
            self.dithered_result.save(path)
            print(f"Saved: {path}")

    def run(self):
        self.root.mainloop()


def main():
    parser = argparse.ArgumentParser(description='Interactive dithering preview')
    parser.add_argument('image', nargs='?', help='Input image file')
    args = parser.parse_args()

    app = DitherPreview(args.image)
    app.run()


if __name__ == '__main__':
    main()
