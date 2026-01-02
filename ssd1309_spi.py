from micropython import const
import framebuf
import time

# SSD1306/SSD1309 command set (works for SSD1309 too)
SET_CONTRAST        = const(0x81)
SET_ENTIRE_ON       = const(0xA4)
SET_NORM_INV        = const(0xA6)
SET_DISP            = const(0xAE)
SET_MEM_ADDR        = const(0x20)
SET_COL_ADDR        = const(0x21)
SET_PAGE_ADDR       = const(0x22)
SET_DISP_START_LINE = const(0x40)
SET_SEG_REMAP       = const(0xA0)
SET_MUX_RATIO       = const(0xA8)
SET_COM_OUT_DIR     = const(0xC0)
SET_DISP_OFFSET     = const(0xD3)
SET_COM_PIN_CFG     = const(0xDA)
SET_DISP_CLK_DIV    = const(0xD5)
SET_PRECHARGE       = const(0xD9)
SET_VCOM_DESEL      = const(0xDB)

class SSD1309_SPI:
    def __init__(self, width, height, spi, dc, res, cs):
        self.width = width
        self.height = height
        self.spi = spi
        self.dc = dc
        self.res = res
        self.cs = cs

        self.pages = self.height // 8
        self.buffer = bytearray(self.pages * self.width)
        self.fb = framebuf.FrameBuffer(self.buffer, self.width, self.height, framebuf.MONO_VLSB)

        # pin modes
        self.dc.init(self.dc.OUT, value=0)
        self.res.init(self.res.OUT, value=1)
        self.cs.init(self.cs.OUT, value=1)

        self.reset()
        self.init_display()

    def reset(self):
        self.res.value(0)
        time.sleep_ms(20)
        self.res.value(1)
        time.sleep_ms(20)

    def write_cmd(self, cmd):
        self.cs.value(0)
        self.dc.value(0)  # command
        self.spi.write(bytearray([cmd]))
        self.cs.value(1)

    def write_data(self, buf):
        self.cs.value(0)
        self.dc.value(1)  # data
        self.spi.write(buf)
        self.cs.value(1)

    def init_display(self):
        # A safe init sequence for 128x64 SSD130x-family
        for cmd in (
            SET_DISP | 0x00,               # display off
            SET_DISP_START_LINE | 0x00,
            SET_SEG_REMAP | 0x01,
            SET_COM_OUT_DIR | 0x08,
            SET_MUX_RATIO, self.height - 1,
            SET_DISP_OFFSET, 0x00,
            SET_MEM_ADDR, 0x00,            # horizontal addressing
            SET_COM_PIN_CFG, 0x12,
            SET_DISP_CLK_DIV, 0x80,
            SET_PRECHARGE, 0x22,
            SET_VCOM_DESEL, 0x20,
            SET_CONTRAST, 0xFF,
            SET_ENTIRE_ON,
            SET_NORM_INV,
            SET_DISP | 0x01                # display on
        ):
            self.write_cmd(cmd)
        self.fill(0)
        self.show()

    def show(self):
        self.write_cmd(SET_COL_ADDR)
        self.write_cmd(0)
        self.write_cmd(self.width - 1)

        self.write_cmd(SET_PAGE_ADDR)
        self.write_cmd(0)
        self.write_cmd(self.pages - 1)

        self.write_data(self.buffer)

    # framebuf helpers
    def fill(self, c):
        self.fb.fill(c)

    def text(self, s, x, y, c=1):
        self.fb.text(s, x, y, c)

    def pixel(self, x, y, c):
        self.fb.pixel(x, y, c)
