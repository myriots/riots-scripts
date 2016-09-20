import time
import serial
import os

# Set Riots USB COM port here
#ser = serial.Serial('COM0', 38400) # Windows style
ser = serial.Serial('/dev/ttyUSB0', 38400) # Linux style

SHT21temp = 0
SHT21hum = 0
BMPtemph = 0
BMPtempl = 0
BMPpresh = 0
BMPpresl = 0
BMPaltih = 0
BMPaltil = 0

def update_values( data ):

    global SHT21temp
    global SHT21hum
    global BMPtemph
    global BMPtempl
    global BMPpresh
    global BMPpresl
    global BMPaltih
    global BMPaltil

    # Parsing data from serial port
    if "SHT21 temperature" in data:
        data = ser.readline()
        values = data.split()
        if values[1] :
            try:
                SHT21temp = float(values[1])
                SHT21temp = (SHT21temp/10) - 273
            except ValueError,e:
                print "error"

    if "SHT21 humidity" in data:
        data = ser.readline()
        values = data.split()
        if values[1] :
            try:
                SHT21hum = float(values[1])
                SHT21hum = (SHT21hum/10)
            except ValueError,e:
                print "error"

    if "BMP temp" in data:
        data = ser.readline()
        values = data.split()
        if values[1] :
            BMPtemph = values[1] # high digit
        data = ser.readline() # skip dot
        data = ser.readline()
        values = data.split()
        if values[1] :
            BMPtempl = values[1] # low digit

    if "BMP pres" in data:
        data = ser.readline()
        values = data.split()
        if values[1] :
            BMPpresh = values[1] # high digit
        data = ser.readline() # skip dot
        data = ser.readline()
        values = data.split()
        if values[1] :
            BMPpresl = values[1] # low digit

    if "BMP alti" in data:
        data = ser.readline()
        values = data.split()
        if values[1] :
            BMPaltih = values[1] # high digit
        data = ser.readline() # skip dot
        data = ser.readline()
        values = data.split()
        if values[1] :
            BMPaltil = values[1] # low digit


    # Update screen
    os.system('cls' if os.name == 'nt' else 'clear')
    print "Riots Air Temp: \t %.1f *C" % (SHT21temp)
    print "Riots Air Humidity: \t %.1f HR" % (SHT21hum)
    #print "Riots Air BMP280 Temp: \t %s.%s *C" % (BMPtemph, BMPtempl)
    print "Riots Air Pressure: \t %s.%s Pa" % (BMPpresh, BMPpresl)
    print "Riots Air Altitude: \t %s.%s m" % (BMPaltih, BMPaltil)

while True:

    data = ser.readline()
    update_values(data)
