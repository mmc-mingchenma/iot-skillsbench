## Pin Mapping for Testing with IoT-SkillsBench

[ATmega2560 Pinout Diagram](https://docs.arduino.cc/resources/pinouts/A000067-full-pinout.pdf)

- Outputs / actuators
	- LED1: D12
	- LED2: D11
	- Active buzzer: D9
	- Passive buzzer: D7
	- Laser emitter (KY-008): D24

- Human input / simple digital sensors
	- Push button: D10 
	- Temperature & humidity sensor (DHT11): D8
	- Sound sensor digital output (KY-037): D3 (with Interrupt)
	- Ultrasonic distance sensor (HC-SR04): D23 (TRIG), D22 (ECHO)

- Analog inputs
	- Temperature sensor (TMP36): A0
	- Sound sensor analog output (KY-037): A1
	- Photoresistor light sensor (KY-018): A2

- LCD1602 (4-bit mode)
	- RS: D48
	- E:  D49
	- D4: D46
	- D5: D47
	- D6: D44
	- D7: D45

- I2C (SDA: D20, SCL: D21)
	- IMU (MPU6050, GY-521)
	- RTC (DS1307)