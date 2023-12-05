# import necessary libraries
import asyncio
import websockets
from motor_control import MotorCommands  # Import your existing MotorCommands class
import functools
from CameraControls import Camera_Control
import serial
import time 
import PyLidar3
import threading
import math
import cv2
# Instantiate MotorCommands and connect motors
motor = MotorCommands()
cam = Camera_Control()
ser = motor.connect_motors("/dev/ttyUSB0")
motor.initialize_motors(ser)
camser = serial.Serial(port='/dev/ttyACM1', baudrate=9600,timeout=.015)
print("//waiting for Serial connection...")
bins=[]
for _ in range (360):  # clear the bins
    bins.append(0)
stop_distance = 900
right_turn_distance = 1000
backward_time = 0.2

port = "/dev/ttyUSB1" # define port for the YDLidar X4
Obj = PyLidar3.YdLidarX4(port) #PyLidar3.YDLidarX4(port,chunk_size)
gen = 0



motor_thread_run = True
async def read_serial_and_broadcast(websocket, path):
    ser = serial.Serial('/dev/ttyACM0', 9600)  # Replace 'COM3' with port of arduino that reads battery
    while True:
        data = ser.readline().strip().decode('utf-8')  # Read data from serial ort
        await websocket.send(data)
        await asyncio.sleep(0.1)

cap = cv2.VideoCapture(0)

# video frame processing function
def videocam(frame):

    # frame operations here
    #gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

    # display the resulting frame
    #rfr = cv2.resize(frame,(640,480))
    #rfr = cv2.rotate(frame, cv2.ROTATE_90_COUNTERCLOCKWISE)
    rfr = cv2.rotate(frame, cv2.ROTATE_90_CLOCKWISE)
    #cv2.imshow('frame',rgray)

    # colorReduce()
    div = 64 
    quantized = (rfr // div * div) + div // 2
    # ksize
    ksize = (10, 10) 
    # Using cv2.blur() method 
    quantized = cv2.blur(quantized, ksize) 



    cv2.line( rfr,
            (0,int(rfr.shape[0]/2)),
            (int(rfr.shape[1]), int(rfr.shape[0]/2)),
            (0, 255, 0), 1)

    cv2.line( rfr,
            (int(rfr.shape[1]/2),0),
            (int(rfr.shape[1]/2), int(rfr.shape[0])),
            (0, 255, 0), 1)

    cv2.imshow('frame',rfr)
    #cv2.imshow('quantized',quantized)

    return rfr  

def drive():
    global motor_thread_run

    while motor_thread_run:
                ret, frame = cap.read()
                if ret: frm = videocam(frame)
                if centy < stop_distance:     
                    motor.stop_motors(ser)
                    print("JARVIS detected object{}")
                if lefty < stop_distance and righty < stop_distance:
                    motor.go_backward(ser, 25)
                    time.sleep(backward_time)

                    if righty > right_turn_distance:
                        motor.turn_right(ser, 25)
                        time.sleep(0.2)
                        motor.go_forward(ser, 25)
                    else:
                        motor.turn_left(ser, 25)
                        time.sleep(0.2)
                        motor.go_forward(ser, 25)
                else:
                    motor.go_forward(ser, 25)

    motor.stop_motors(ser)


def lidar_scanner():
    global direction, centy, lefty, righty
    Obj.Connect()
    print(Obj.GetDeviceInfo())
    gen = Obj.StartScanning()
    while True:
        data = next(gen) # get lidar scan data
        left_total = 0
        right_total = 0
        center_total = 0
        bias = 0
        
        # measurement and calculation of averages and values
        for angle in range(340,360):  # measure the center
            if(data[angle]> 0):
                center_total = center_total + data[angle]
        for angle in range(0,20):  # measure the center
            if(data[angle]> 0):
                center_total = center_total + data[angle]
        center_average = round(center_total/40,2)
        for angle in range(20,100):  # measure the right side
            if(data[angle]> 0):
                right_total = right_total + data[angle]
        right_average = round(right_total/80,2)
        for angle in range(260,340): # measure the left side
            if(data[angle]> 0):
                left_total = left_total + data[angle]
        left_average = round(left_total/80,2)

        # convert to Cartesian coordinates
        left_y = math.sin(math.pi/4) * left_average
        left_x = -1*math.cos(math.pi/4) * left_average
        right_y = math.sin(math.pi/4) * right_average
        right_x = math.cos(math.pi/4) * right_average
        center_y = center_average

        sum_x = round(left_x + right_x,2) # calculate sum of x-coordinates
        sum_y = round(center_y - (left_y + right_y)/2,2) # calculate sum of y-coordinates
        
        if sum_y < 100:
            sum_y = 100  # ensure minimum value for y
        

        sum_angle = math.atan2(sum_x,sum_y) # calculate steering angle in radians

        # convert radians to degrees and ensure it's within [0, 2π]
        direction = sum_angle * (180 / math.pi) % 360
        sum_dist = math.sqrt(sum_x**2 + sum_y**2)

        righty = right_average
        centy = center_average
        lefty = left_average
        
        if centy < stop_distance:     
            motor.stop_motors(ser)
            print("JARVIS detected object{}")
            if lefty < stop_distance and righty < stop_distance:
                motor.go_backward(ser, 25)
                time.sleep(backward_time)
                if righty > right_turn_distance:
                    motor.turn_right(ser, 25)
                    time.sleep(0.2)
                    motor.go_forward(ser, 25)
                else:
                    motor.turn_left(ser, 25)
                    time.sleep(0.2)
                    motor.go_forward(ser, 25)
        else:
            motor.go_forward(ser, 25)

# Define the WebSocket server logic
async def server(websocket, path):
    # Process incoming messages from the WebSocket client
    speed = 25
    async for message in websocket:
        print(f"Received message: {message}")
        # Handle the message using MotorCommands methods
        if message == "Auto":
           task = asyncio.create_task(lidar_scanner())  # Start Lidar scanning as a separate task
        elif message == "Man":
            task.cancel()
            Obj.StopScanning()
            Obj.Disconnect()
        elif message == 'W':
            motor.go_forward(ser, speed)
        elif message == 'T':
            motor.go_forward(ser, speed) 
        elif message == 'A' or message == 'AX':
            motor.turn_left(ser, speed)  
        elif message == 'Q':
            motor.turn_left(ser, 25)
        elif message == 'S':
            motor.go_backward(ser, speed)
        elif message == 'D' or message == 'DX':
            motor.turn_right(ser, speed)  
        elif message == 'E':
            motor.turn_right(ser, 25)
        elif message == 'X':
            motor.stop_motors(ser)
        elif message == 'z':
            cam.move_up(camser)
            time.sleep(0.2)
        elif message == 'y':
            cam.move_left(camser)
            time.sleep(0.2)            
        elif message == 'u':
            cam.move_right(camser)
            time.sleep(0.2)  
        elif message == 'p':
            cam.move_down(camser)
            time.sleep(0.2)
        elif message == 'l':
            cam.change_mode(camser)
            time.sleep(0.2)
        elif message == 'home':
            speed = 5
        elif message == 'low':
            speed = 25
        elif message == 'med':
            speed = 50
        elif message == 'high':
            speed = 75

# Implement CORS check logic
async def check_origin(headers):
    # Check the 'Origin' header to ensure it's allowed
    origin = headers.get("Origin", None)
    if origin == "http://10.47.232.1:3000":
        return True  # Allow connections from this origin
    else:
        return False  # Reject connections from other origins

# Function to start the WebSocket server
async def start_websocket_server(websocket, path):
    headers = websocket.request_headers
    if await check_origin(headers):
        await asyncio.gather(server(websocket, path), read_serial_and_broadcast(websocket, path))
    else:
        await websocket.close()  # Close the connection for invalid origin

# Main function to start the server
async def main():
    start_server = websockets.serve(
        start_websocket_server,
        "10.47.232.1",
        # "0.0.0.0",
        8000,
        subprotocols=["websocket"]
    )
    await start_server
    await asyncio.Future()

if __name__ == "__main__":
    asyncio.run(main())
