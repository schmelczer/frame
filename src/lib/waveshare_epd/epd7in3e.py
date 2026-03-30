#!/usr/bin/env python3
# Waveshare 7.3" 6-color e-Paper driver (modified)
# Original: Waveshare team, 2022-10-20

import sys
import numpy as np
import cv2
from PIL import Image, ImageEnhance
from numba import jit
from . import epdconfig

EPD_WIDTH = 800
EPD_HEIGHT = 480

DEFAULT_SATURATION = 1.4
DEFAULT_CONTRAST = 1.2
DEFAULT_GAMMA = 0.9

PALETTE_RGB = np.array([
    [0, 0, 0],        # BLACK
    [255, 255, 255],  # WHITE
    [255, 255, 0],    # YELLOW
    [255, 0, 0],      # RED
    [0, 0, 255],      # BLUE
    [0, 255, 0],      # GREEN
], dtype=np.float64)

PERCEPTUAL_WEIGHTS = np.array([0.299, 0.587, 0.114], dtype=np.float64)


def _enhance_for_eink(image: Image.Image, saturation: float = None,
                      contrast: float = None, gamma: float = None) -> Image.Image:
    saturation = saturation or DEFAULT_SATURATION
    contrast = contrast or DEFAULT_CONTRAST
    gamma = gamma or DEFAULT_GAMMA

    img = image.convert('RGB')
    if saturation != 1.0:
        img = ImageEnhance.Color(img).enhance(saturation)
    if contrast != 1.0:
        img = ImageEnhance.Contrast(img).enhance(contrast)
    if gamma != 1.0:
        lut = [int((i / 255.0) ** (1.0 / gamma) * 255) for i in range(256)] * 3
        img = img.point(lut)
    return img


def _crop_center(image: Image.Image, target_w: int, target_h: int,
                 show_progress: bool = True) -> Image.Image:
    if show_progress:
        print("Center cropping...")

    img_cv = cv2.cvtColor(np.array(image), cv2.COLOR_RGB2BGR)
    img_h, img_w = img_cv.shape[:2]
    img_aspect, target_aspect = img_w / img_h, target_w / target_h

    if img_aspect < target_aspect:
        new_w, new_h = target_w, int(target_w / img_aspect)
    else:
        new_w, new_h = int(target_h * img_aspect), target_h

    img_cv = cv2.resize(img_cv, (new_w, new_h), interpolation=cv2.INTER_LANCZOS4)
    x_off = (new_w - target_w) // 2
    y_off = (new_h - target_h) // 2
    cropped = img_cv[y_off:y_off + target_h, x_off:x_off + target_w]
    return Image.fromarray(cv2.cvtColor(cropped, cv2.COLOR_BGR2RGB))


def _render_progress(desc: str, current: int, total: int, width: int = 30) -> None:
    if total == 0:
        return
    percent = int(100 * current / total)
    filled = int(width * current / total)
    bar = "█" * filled + "░" * (width - filled)
    sys.stdout.write(f"\r{desc}: |{bar}| {percent:3d}%")
    sys.stdout.flush()
    if current >= total:
        print()


@jit(nopython=True, cache=True)
def _find_nearest_color(r, g, b, palette, weights):
    best_idx, best_dist = 0, 1e10
    for i in range(palette.shape[0]):
        dr = (palette[i, 0] - r) * weights[0]
        dg = (palette[i, 1] - g) * weights[1]
        db = (palette[i, 2] - b) * weights[2]
        dist = dr * dr + dg * dg + db * db
        if dist < best_dist:
            best_dist, best_idx = dist, i
    return best_idx


@jit(nopython=True, cache=True)
def _atkinson_dither_rows(img, palette, weights, start_row, end_row):
    height, width = img.shape[:2]
    for y in range(start_row, end_row):
        for x in range(width):
            old_r, old_g, old_b = img[y, x, 0], img[y, x, 1], img[y, x, 2]
            idx = _find_nearest_color(old_r, old_g, old_b, palette, weights)
            new_r, new_g, new_b = palette[idx, 0], palette[idx, 1], palette[idx, 2]
            img[y, x, 0], img[y, x, 1], img[y, x, 2] = new_r, new_g, new_b

            err_r, err_g, err_b = (old_r - new_r) / 8.0, (old_g - new_g) / 8.0, (old_b - new_b) / 8.0

            if x + 1 < width:
                img[y, x + 1, 0] += err_r
                img[y, x + 1, 1] += err_g
                img[y, x + 1, 2] += err_b
            if x + 2 < width:
                img[y, x + 2, 0] += err_r
                img[y, x + 2, 1] += err_g
                img[y, x + 2, 2] += err_b
            if y + 1 < height:
                if x > 0:
                    img[y + 1, x - 1, 0] += err_r
                    img[y + 1, x - 1, 1] += err_g
                    img[y + 1, x - 1, 2] += err_b
                img[y + 1, x, 0] += err_r
                img[y + 1, x, 1] += err_g
                img[y + 1, x, 2] += err_b
                if x + 1 < width:
                    img[y + 1, x + 1, 0] += err_r
                    img[y + 1, x + 1, 1] += err_g
                    img[y + 1, x + 1, 2] += err_b
            if y + 2 < height:
                img[y + 2, x, 0] += err_r
                img[y + 2, x, 1] += err_g
                img[y + 2, x, 2] += err_b
    return img


def _dither_atkinson(image: Image.Image, show_progress: bool = True) -> Image.Image:
    img = np.array(image.convert('RGB'), dtype=np.float64)
    height = img.shape[0]
    if show_progress:
        print("Dithering...")

    chunk_size = 48
    for i in range((height + chunk_size - 1) // chunk_size):
        start, end = i * chunk_size, min((i + 1) * chunk_size, height)
        img = _atkinson_dither_rows(img, PALETTE_RGB, PERCEPTUAL_WEIGHTS, start, end)
        if show_progress:
            _render_progress("Dithering", end, height)

    return Image.fromarray(np.clip(img, 0, 255).astype(np.uint8), 'RGB')


class EPD:
    def __init__(self):
        self.reset_pin = epdconfig.RST_PIN
        self.dc_pin = epdconfig.DC_PIN
        self.busy_pin = epdconfig.BUSY_PIN
        self.cs_pin = epdconfig.CS_PIN
        self.width = EPD_WIDTH
        self.height = EPD_HEIGHT

    def reset(self):
        epdconfig.digital_write(self.reset_pin, 1)
        epdconfig.delay_ms(20)
        epdconfig.digital_write(self.reset_pin, 0)
        epdconfig.delay_ms(2)
        epdconfig.digital_write(self.reset_pin, 1)
        epdconfig.delay_ms(20)

    def send_command(self, command):
        epdconfig.digital_write(self.dc_pin, 0)
        epdconfig.digital_write(self.cs_pin, 0)
        epdconfig.spi_writebyte([command])
        epdconfig.digital_write(self.cs_pin, 1)

    def send_data(self, data):
        epdconfig.digital_write(self.dc_pin, 1)
        epdconfig.digital_write(self.cs_pin, 0)
        epdconfig.spi_writebyte([data])
        epdconfig.digital_write(self.cs_pin, 1)

    def send_data2(self, data):
        epdconfig.digital_write(self.dc_pin, 1)
        epdconfig.digital_write(self.cs_pin, 0)
        epdconfig.spi_writebyte2(data)
        epdconfig.digital_write(self.cs_pin, 1)

    def wait_busy(self):
        while epdconfig.digital_read(self.busy_pin) == 0:
            epdconfig.delay_ms(5)

    def turn_on_display(self):
        self.send_command(0x04)  # POWER_ON
        self.wait_busy()
        self.send_command(0x12)  # DISPLAY_REFRESH
        self.send_data(0x00)
        self.wait_busy()
        self.send_command(0x02)  # POWER_OFF
        self.send_data(0x00)
        self.wait_busy()

    def init(self):
        if epdconfig.module_init() != 0:
            return -1
        self.reset()
        self.wait_busy()
        epdconfig.delay_ms(30)

        self.send_command(0xAA)
        for v in [0x49, 0x55, 0x20, 0x08, 0x09, 0x18]:
            self.send_data(v)

        self.send_command(0x01)
        self.send_data(0x3F)

        self.send_command(0x00)
        self.send_data(0x5F)
        self.send_data(0x69)

        self.send_command(0x03)
        for v in [0x00, 0x54, 0x00, 0x44]:
            self.send_data(v)

        self.send_command(0x05)
        for v in [0x40, 0x1F, 0x1F, 0x2C]:
            self.send_data(v)

        self.send_command(0x06)
        for v in [0x6F, 0x1F, 0x17, 0x49]:
            self.send_data(v)

        self.send_command(0x08)
        for v in [0x6F, 0x1F, 0x1F, 0x22]:
            self.send_data(v)

        self.send_command(0x30)
        self.send_data(0x03)

        self.send_command(0x50)
        self.send_data(0x3F)

        self.send_command(0x60)
        self.send_data(0x02)
        self.send_data(0x00)

        self.send_command(0x61)
        for v in [0x03, 0x20, 0x01, 0xE0]:
            self.send_data(v)

        self.send_command(0x84)
        self.send_data(0x01)

        self.send_command(0xE3)
        self.send_data(0x2F)

        self.send_command(0x04)
        self.wait_busy()
        return 0

    def getbuffer(self, image, saturation=None, contrast=None, gamma=None,
                  enhance=True, show_progress=True):
        pal_image = Image.new("P", (1, 1))
        pal_image.putpalette((0,0,0, 255,255,255, 255,255,0, 255,0,0, 0,0,0, 0,0,255, 0,255,0) + (0,0,0)*249)

        image = image.convert('RGB')
        imwidth, imheight = image.size

        if imwidth != self.width or imheight != self.height:
            if show_progress:
                print(f"Input: {imwidth}x{imheight} → {self.width}x{self.height}")
            image = _crop_center(image, self.width, self.height, show_progress)

        if enhance:
            if show_progress:
                print("Enhancing...")
            image = _enhance_for_eink(image, saturation, contrast, gamma)

        image = _dither_atkinson(image, show_progress)

        if show_progress:
            print("Packing buffer...")
        image_6color = image.quantize(palette=pal_image, dither=Image.Dither.NONE)
        buf_6color = bytearray(image_6color.tobytes('raw'))

        buf = [0x00] * (self.width * self.height // 2)
        for i in range(0, len(buf_6color), 2):
            buf[i // 2] = (buf_6color[i] << 4) + buf_6color[i + 1]

        if show_progress:
            print("Ready")
        return buf

    def display(self, image):
        self.send_command(0x10)
        self.send_data2(image)
        self.turn_on_display()

    def Clear(self, color=0x11):
        self.send_command(0x10)
        self.send_data2([color] * (self.height * self.width // 2))
        self.turn_on_display()

    def sleep(self):
        self.send_command(0x07)  # DEEP_SLEEP
        self.send_data(0xA5)
        epdconfig.delay_ms(2000)
        epdconfig.module_exit()
