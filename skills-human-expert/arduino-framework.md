---
name: Arduino
description: This skill is for the Arduino framework only.
---

## I2C
In Arduino, the Wire library allows you to communicate with I2C devices.
For Arduino boards, `Wire.begin()` doesn’t take pin arguments because it always uses the fixed hardware I2C pins. Valid forms: 
`Wire.begin();` (master) or `Wire.begin(address);` (slave, optional address)

## ISR
General form::
```ino
void myISR() {
  // Keep this short and fast
}

void setup() {
  attachInterrupt(digitalPinToInterrupt(INTERRUPT_PIN), myISR, TRIGGER_MODE);
}
```
Keypoints:
- ISR must be void and take no arguments.
- Do not use delay() or long operations inside the ISR.

## LiquidCrystal library 
The LiquidCrystal library is an Arduino framework library for controlling text-based LCD displays based on the Hitachi HD44780 (or compatible) chipset. This library is Arduino framework only and is not available in other frameworks.


### Usage
`setCursor()`: Positions the LCD cursor — defines where the next printed character will appear.
Syntax: `lcd.setCursor(column, row);`