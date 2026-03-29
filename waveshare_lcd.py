from machine import Pin, SPI, PWM
import framebuf
import time
import machine

LCD_WIDTH  = 240
LCD_HEIGHT = 320

# Pin definitions
I2C_SDA = 12
I2C_SDL = 13
I2C_IRQ = 29
I2C_RST = 20

LCD_DC  = 16
LCD_CS  = 17
SCK     = 18
MOSI    = 19
MISO    = None
LCD_RST = 20
LCD_BL  = 15

machine.freq(230_000_000)


class lcd_st7789:
    def __init__(self):
        self.width  = LCD_WIDTH
        self.height = LCD_HEIGHT

        self.cs  = Pin(LCD_CS,  Pin.OUT)
        self.rst = Pin(LCD_RST, Pin.OUT)
        self.bl  = Pin(LCD_BL,  Pin.OUT)
        self.bl(1)
        self.cs(1)

        self.bus = SPI(0, 230_000_000, polarity=0, phase=0,
                       sck=Pin(SCK), mosi=Pin(MOSI), miso=MISO)
        self.dc = Pin(LCD_DC, Pin.OUT)
        self.dc(1)
        self.lcd_init()

    def write_cmd(self, cmd):
        self.dc(0)
        self.cs(0)
        self.bus.write(bytearray([cmd]))
        self.cs(1)

    def write_data(self, buf):
        self.dc(1)
        self.cs(0)
        self.bus.write(bytearray([buf]))
        self.cs(1)

    def lcd_init(self):
        self.rst(0)
        time.sleep_ms(100)
        self.rst(1)
        time.sleep_ms(10)

        self.write_cmd(0x11)
        time.sleep_ms(120)

        self.write_cmd(0x36);  self.write_data(0x48)  # MADCTL: mirror X
        self.write_cmd(0x3A);  self.write_data(0x05)
        self.write_cmd(0xF0);  self.write_data(0xC3)
        self.write_cmd(0xF0);  self.write_data(0x96)
        self.write_cmd(0xB4);  self.write_data(0x01)
        self.write_cmd(0xB7);  self.write_data(0xC6)

        self.write_cmd(0xC0)
        self.write_data(0x80); self.write_data(0x45)

        self.write_cmd(0xC1);  self.write_data(0x13)
        self.write_cmd(0xC2);  self.write_data(0xA7)
        self.write_cmd(0xC5);  self.write_data(0x0A)

        self.write_cmd(0xE8)
        for b in [0x40, 0x8A, 0x00, 0x00, 0x29, 0x19, 0xA5, 0x33]:
            self.write_data(b)

        self.write_cmd(0xE0)
        for b in [0xD0, 0x08, 0x0F, 0x06, 0x06, 0x33, 0x30,
                  0x33, 0x47, 0x17, 0x13, 0x13, 0x2B, 0x31]:
            self.write_data(b)

        self.write_cmd(0xE1)
        for b in [0xD0, 0x0A, 0x11, 0x0B, 0x09, 0x07, 0x2F,
                  0x33, 0x47, 0x38, 0x15, 0x16, 0x2C, 0x32]:
            self.write_data(b)

        self.write_cmd(0xF0);  self.write_data(0x3C)
        self.write_cmd(0xF0);  self.write_data(0x69)
        time.sleep_ms(120)

        self.write_cmd(0x21)
        self.write_cmd(0x29)

    def set_windows(self, Xstart, Ystart, Xend, Yend):
        self.write_cmd(0x2A)
        self.write_data(Xstart >> 8);   self.write_data(Xstart)
        self.write_data(Xend >> 8);     self.write_data(Xend)

        self.write_cmd(0x2B)
        self.write_data(Ystart >> 8);   self.write_data(Ystart)
        self.write_data(Yend >> 8);     self.write_data(Yend)

        self.write_cmd(0x2C)

    def draw_point(self, x, y, color):
        self.set_windows(x, y, x, y)
        self.dc(1)
        self.cs(0)
        self.bus.write(bytearray([color >> 8, color & 0xFF]))
        self.cs(1)

    def draw_square(self, x, y, s, color):
        self.set_windows(x, y, x + s, y + s)
        self.dc(1)
        self.cs(0)
        px = bytearray([color >> 8, color & 0xFF])
        for _ in range((s + 1) * (s + 1)):
            self.bus.write(px)
        self.cs(1)

    def lcd_fill(self, color):
        buf = bytearray([color >> 8, color & 0xFF] * LCD_WIDTH)
        self.set_windows(0, 0, LCD_WIDTH - 1, LCD_HEIGHT - 1)
        self.dc(1)
        self.cs(0)
        for _ in range(LCD_HEIGHT):
            self.bus.write(buf)
        self.cs(1)


class touch_cst816d:
    def __init__(self, device_addr=0x15, mode=0, i2c_num=0,
                 i2c_sda=I2C_SDA, i2c_scl=I2C_SDL,
                 irq_pin=I2C_IRQ, rst_pin=I2C_RST):

        self.bus = machine.I2C(id=i2c_num,
                               scl=machine.Pin(i2c_scl),
                               sda=machine.Pin(i2c_sda),
                               freq=400_000)
        self.device_addr = device_addr
        self.int = machine.Pin(irq_pin, machine.Pin.IN, machine.Pin.PULL_UP)
        self.rst = machine.Pin(rst_pin, machine.Pin.OUT)

        self.point_count = 0
        self.coordinates = [{"x": 0, "y": 0}]

        self.reset()
        self.read_flag = True
        self.int.irq(handler=self.int_cb, trigger=machine.Pin.IRQ_FALLING)

    def int_cb(self, pin):
        self.read_touch_data()

    def reset(self):
        self.rst(1); time.sleep(0.2)
        self.rst(0); time.sleep(0.2)
        self.rst(1); time.sleep(0.2)

    # NOTE: write_cmd removed — it referenced non-existent attributes
    #       (self.dc, self.cs, self.spi) and would crash on import.

    def read_bytes(self, reg_addr, length):
        try:
            self.bus.writeto(int(self.device_addr), bytes([reg_addr]))
            return self.bus.readfrom(int(self.device_addr), length)
        except Exception as e:
            print(f"Touch read error: {e}")
            return None

    def read_touch_data(self):
        TOUCH_NUM_REG = 0x02
        TOUCH_XY_REG  = 0x03
        buf = self.read_bytes(TOUCH_NUM_REG, 1)
        if buf is not None and buf[0] != 0:
            self.point_count = buf[0]
            buf = self.read_bytes(TOUCH_XY_REG, 6 * self.point_count)
            if buf is not None:
                for i in range(self.point_count):
                    self.coordinates[i]["x"] = ((buf[i*6+0] & 0x0F) << 8) | buf[i*6+1]
                    self.coordinates[i]["y"] = ((buf[i*6+2] & 0x0F) << 8) | buf[i*6+3]

    def get_touch_xy(self):
        if self.point_count != 0:
            self.point_count = 0
            return self.coordinates
        return None


if __name__ == '__main__':
    lcd   = lcd_st7789()
    touch = touch_cst816d()

    lcd.lcd_fill(0xF800)
    time.sleep(1)
    lcd.lcd_fill(0x07E0)
    time.sleep(1)
    lcd.lcd_fill(0x001F)
    time.sleep(1)
    lcd.lcd_fill(0xFFFF)

    while True:
        coords = touch.get_touch_xy()
        if coords:
            for i, c in enumerate(coords):
                lcd.draw_square(LCD_WIDTH - c['x'], c['y'], 4, 0xF800)
                print(f"Point {i+1}: x={c['x']}, y={c['y']}")
        time.sleep_ms(10)