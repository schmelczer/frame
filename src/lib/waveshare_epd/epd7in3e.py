#!/usr/bin/env python3
# Waveshare 7.3" 6-color e-Paper driver (modified)
# Original: Waveshare team, 2022-10-20

import numpy as np
import cv2
from PIL import Image, ImageEnhance
from numba import jit
from progress import ProgressBar
from . import epdconfig

EPD_WIDTH = 800
EPD_HEIGHT = 480

# 6-color e-ink encoding: indices 0,1,2,3,5,6 are wire-format colors;
# 4 is reserved/unused (filled with BLACK so nearest-color never picks it).
PALETTE_RGB = np.array([
    [0, 0, 0],        # 0: BLACK
    [255, 255, 255],  # 1: WHITE
    [255, 255, 0],    # 2: YELLOW
    [255, 0, 0],      # 3: RED
    [0, 0, 0],        # 4: unused
    [0, 0, 255],      # 5: BLUE
    [0, 255, 0],      # 6: GREEN
], dtype=np.float64)

PERCEPTUAL_WEIGHTS = np.array([0.299, 0.587, 0.114], dtype=np.float64)


def _enhance_for_eink(image: Image.Image, saturation: float,
                      contrast: float, gamma: float) -> Image.Image:
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
def _atkinson_dither_rows(img, palette, weights, indices, start_row, end_row):
    height, width = img.shape[:2]
    for y in range(start_row, end_row):
        for x in range(width):
            old_r, old_g, old_b = img[y, x, 0], img[y, x, 1], img[y, x, 2]
            idx = _find_nearest_color(old_r, old_g, old_b, palette, weights)
            indices[y, x] = idx
            new_r, new_g, new_b = palette[idx, 0], palette[idx, 1], palette[idx, 2]

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


def _dither_atkinson(image: Image.Image, show_progress: bool = True) -> np.ndarray:
    """Atkinson-dither to the e-ink palette and return a uint8 array of palette indices."""
    img = np.array(image.convert('RGB'), dtype=np.float64)
    height, width = img.shape[:2]
    indices = np.zeros((height, width), dtype=np.uint8)
    if show_progress:
        print("Dithering...")
        progress = ProgressBar(height, desc="Dithering")

    chunk_size = 48
    for i in range((height + chunk_size - 1) // chunk_size):
        start, end = i * chunk_size, min((i + 1) * chunk_size, height)
        _atkinson_dither_rows(img, PALETTE_RGB, PERCEPTUAL_WEIGHTS, indices, start, end)
        if show_progress:
            progress.set(end)

    return indices


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

    def getbuffer(self, image, saturation: float, contrast: float, gamma: float,
                  enhance: bool = True, show_progress: bool = True):
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

        indices = _dither_atkinson(image, show_progress)

        if show_progress:
            print("Packing buffer...")
        flat = indices.reshape(-1)
        packed = (flat[0::2].astype(np.uint8) << 4) | flat[1::2].astype(np.uint8)
        buf = packed.tolist()

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
