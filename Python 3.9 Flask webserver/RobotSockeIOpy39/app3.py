import cv2
from flask import Flask, render_template, session, request, \
    copy_current_request_context
from flask_socketio import SocketIO, emit, join_room, leave_room, \
    close_room, rooms, disconnect
from threading import Event
from time import sleep
import os, imutils
import json
import base64
from threading import Lock
from ultralytics import YOLO
import socket  # Find Host IP
from function import *
import numpy as np
import pyrealsense2 as rs


import random
from paho.mqtt import client as mqtt_client

#cap=cv2.VideoCapture(0)  ##when removing debug=True or using gevent or eventlet uncomment this line and comment the cap=cv2.VideoCapture(0) in gen(json)
app = Flask(__name__)
app.config['SECRET_KEY'] = '78581099#lkjh'
socketio = SocketIO(app)
#socketio = SocketIO(app, async_mode=async_mode)
thread = None
thread_lock = Lock()
thread_event = Event()

thread1 = None
thread_lock1 = Lock()
thread_event1 = Event()


# ---------------------Global Variable------------------

# Global variable
cam_intel_enb =False
classes_detect =[0]
alarm_dist = 2000.0 #m
stop_dist = 1000.0  #meter
enb_safety_cam1 = False
                        # class:   0,2,7,1,3,6,16,



id = get_webcamID_logitect()
print(id)

cam2_video_link= id
cam2_model_link ="yolo11n.pt"
cam2_ctrl_enb = False

intel_setval = None
mqtt_setval= None
logitect_setval=None



#------------------------MQTT GLOBAL--------

thread2 = None
thread_lock2 = Lock()
thread_event2 = Event()

broker = "broker.emqx.io"
port = 1883
topic_pub = "robotcar/control"
topic_sub = "robotcar/feedback"
username = "robot"
password = "123456"
client = mqtt_client.Client(mqtt_client.CallbackAPIVersion.VERSION2)

# generate client ID with pub prefix randomly
client_id = f'python-mqtt-{random.randint(0, 1000)}'

#--------------------------------------------------------------
# Motor Control Global Variable
robot_mode = False
robot_state = False
motorspeed_cmd = 0
direct_cmd = 0
speed = 50
robot_move_status=0
enb_activate_stop = True
enable_deactivat_stop = False








#------------------WEB------------------
@app.route('/')
def index():
    return render_template('index.html')


@app.route("/index.html")
def index1():
    return render_template("index.html")


@app.route("/datamonitor.html")
def datamonitor():
    return render_template("datamonitor.html")


@app.route("/mqttdata.html")
def mqttdata():
    return render_template("mqttdata.html")


@app.route("/wsdata.html")
def wsdata():
    return render_template("wsdata.html")


@app.route("/about.html")
def about():
    return render_template("about.html")


@app.route("/map_control.html")
def mapcontrol():
    return render_template("map_control.html")


@app.route("/setup.html")
def setup():
    return render_template("setup.html")

@app.route("/camera.html")
def camera():
    return render_template("camera.html")

@app.route("/help.html")
def help():
    return render_template("help.html")




#-----------------------------------------

def background_thread(event): #   IntelReaslses Camera
    global thread, classes_detect, stop_dist,alarm_dist,enb_safety_cam1
    global client, topic_pub, robot_move_status,robot_state,enb_activate_stop,enable_deactivat_stop

    model = YOLO("model/yolo11n.pt")

    if (event.is_set()):
        # Configure depth and color streams
        pipeline = rs.pipeline()
        config = rs.config()

        # Get device product line for setting a supporting resolution
        pipeline_wrapper = rs.pipeline_wrapper(pipeline)
        pipeline_profile = config.resolve(pipeline_wrapper)
        device = pipeline_profile.get_device()
        device_product_line = str(device.get_info(rs.camera_info.product_line))

        found_rgb = False
        for s in device.sensors:
            if s.get_info(rs.camera_info.name) == 'RGB Camera':
                found_rgb = True
                break
        if not found_rgb:
            print("The demo requires Depth camera with Color sensor")
            exit(0)

        config.enable_stream(rs.stream.depth, 640, 480, rs.format.z16, 30)
        config.enable_stream(rs.stream.color, 640, 480, rs.format.bgr8, 30)

        # Start streaming
        pipeline.start(config)

        try:
            while event.is_set():

                # Wait for a coherent pair of frames: depth and color
                frames = pipeline.wait_for_frames()
                depth_frame = frames.get_depth_frame()
                color_frame = frames.get_color_frame()

                if not depth_frame or not color_frame:
                    continue

                # Convert images to numpy arrays
                depth_image = np.asanyarray(depth_frame.get_data())

                color_image = np.asanyarray(color_frame.get_data())
                # ---------------YOLO-------------------
                results = model.predict(color_image, device=[0], classes=classes_detect)  # detect all object

                color_image = results[0].plot()
                # ----------Marking object detection-----------

                result = results[0]
                boxes = results[0].boxes.xyxy.tolist()
                classes = results[0].boxes.cls.tolist()
                names = results[0].names
                confidences = results[0].boxes.conf.tolist()
                object_classes = []
                cordinate = []
                obj_count = []  # [obj,count,onj1,count1.....]
                distance = []  # only used in Stereo Camera
                for box in result.boxes:
                    label1 = result.names[box.cls[0].item()]
                    cords1 = [round(x) for x in box.xyxy[0].tolist()]
                    prob1 = round(box.conf[0].item(), 2)
                    object_classes.append(label1)
                    cordinate.append(cords1)
                    cx, cy = drawCircle_center_image(cords1, color_image)
                    # find center poit of each obj and find depth matrix
                    distance.append(depth_image[
                                        cy, cx])  # Note ( height, width) . Image.shape  out put is (height,width,chanel)

                    dist_label = "Distance: " + str(depth_image[cx,cy])
                    cv2.putText(color_image,dist_label,(cx,cy),cv2.FONT_HERSHEY_PLAIN,2,(0,0,255))

                    # ----------------Calculation safety------------------
                    # 0: Stop, 1 fwd, 2, bwd, 3, left, 4 right, 5 upleft, 6, upright, 7, downleft, 8 downright, 9
                    # Spin left, 10	spin right.
                    dist_check = depth_image[cy, cx]

                    if enb_safety_cam1:
                        print(robot_move_status)
                        print(robot_state)
                        if (robot_move_status == 1 or robot_move_status == 5 or robot_move_status == 6) and robot_state == True:
                            print("here")
                            if dist_check < alarm_dist:
                                print("one or more objects are in safety range alarm, Warning")
                                datasend = label1 + " In the safey range (alarm) " + str(dist_check)
                                socketio.emit("camera1safetyevent", datasend)  # send to HMI

                            if dist_check < stop_dist:
                                print("one or more objects are in safety range Trip , Stop Car Immidiately")
                                datasend = label1 + " In the safey range (STOP) Car , Car can move backward" + str(
                                    dist_check)
                                socketio.emit("camera1safetyevent", datasend)  # send to HMI
                                ex_operate_robot(21)  # Stop Robot if find object in range


                        if robot_move_status == 0: # Car is Stop
                            if dist_check > stop_dist and enable_deactivat_stop==True:
                                print("Forward of Car is clear, safe to move forward")
                                datasend = "Forward of Car is clear, safe to move forward"
                                socketio.emit("camera1safetyevent", datasend)  # send to HMI
                                ex_operate_robot(22)  # Stop Robot if find object in range

                                enable_deactivat_stop = False
                        else:
                            enable_deactivat_stop = True

                obj_count = count_objects_in_image(object_classes, color_image)
                dict = {"objectclasses": object_classes, "obj_count": obj_count,
                        "distance": distance}
                #socketio.emit("camera1event",dict)  # send to HMI



                # ---------------------------------------
                # Apply colormap on depth image (image must be converted to 8-bit per pixel first)
                depth_colormap = cv2.applyColorMap(cv2.convertScaleAbs(depth_image, alpha=0.03),
                                                   cv2.COLORMAP_JET)

                depth_colormap_dim = depth_colormap.shape
                color_colormap_dim = color_image.shape

                # If depth and color resolutions are different, resize color image to match depth image for display
                if depth_colormap_dim != color_colormap_dim:
                    resized_color_image = cv2.resize(color_image,
                                                     dsize=(depth_colormap_dim[1], depth_colormap_dim[0]),
                                                     interpolation=cv2.INTER_AREA)
                    images = np.hstack((resized_color_image, depth_colormap))

                else:
                    images = np.hstack((color_image, depth_colormap))



                frame = cv2.imencode('.jpg', color_image)[1].tobytes()
                frame = base64.encodebytes(frame).decode("utf-8")
                message(frame)
                socketio.sleep(0.0)

        finally:

            # Stop streaming
            pipeline.stop()
            #event.clear()
            #thread = None






#  -----------------LOGITECH CAMERA----------------------------

def background_thread1(event , cam2_video_link,cam2_model_link,cam2_ctrl_enb):  # Logitect Camera
    global client, topic_pub
    #cap=cv2.VideoCapture(1)
    n = len(str(cam2_video_link))
    if n>2:
        cap=cv2.VideoCapture("video/"+ cam2_video_link)

    else : cap=cv2.VideoCapture(cam2_video_link)

    model1 = YOLO("model/"+cam2_model_link)

    global thread1

    #--------------------MQtt--------
    client.publish(topic_pub, "KY")



    try:
        while(cap.isOpened() and event.is_set()):
            ret,img=cap.read()
            if ret:
                img =imutils.resize(img,640)

                results = model1.predict(img, device=[0], conf = 0.8)
                img = results[0].plot()
                result = results[0]

                boxes = results[0].boxes.xyxy.tolist()
                classes = results[0].boxes.cls.tolist()
                names = results[0].names
                confidences = results[0].boxes.conf.tolist()
                object_classes = []
                cordinate = []
                obj_count = []  # [obj,count,onj1,count1.....]
                distance = []  # only used in Stereo Camera

                for box in result.boxes:
                    label1 = result.names[box.cls[0].item()]
                    cords1 = [round(x) for x in box.xyxy[0].tolist()]
                    prob1 = round(box.conf[0].item(), 2)

                    cordinate.append(cords1)
                    object_classes.append(label1)
                    drawCircle_center_image(cords1, img)
                    # Control Robot by Image processing
                    Controlbyimage(cam2_ctrl_enb, label1) # This function used to operate robot


                obj_count = count_objects_in_image(object_classes, img)

                dict = {"objectclasses": object_classes, "obj_count": obj_count, "distance": distance}
                # distance is empty in aft camera, aft camera only for detection
                socketio.emit("camera2event", dict)

                frame = cv2.imencode('.jpg', img)[1].tobytes()
                frame= base64.encodebytes(frame).decode("utf-8")
                message2(frame)
                #socketio.sleep(0.0)
            else:
                break
    finally:
        event.clear()
        thread1 = None




#-------------------------------------------------MQTT-------------


#-------------------------------------------
def connect_mqtt(broker,port,username,password):
    # New Version 2.0
    def on_connect(client, userdata, flags, reason_code, properties):
        if flags.session_present:
            pass
        if reason_code == 0:
            # success connect
            print("success_connect MQTT Broker")
        if reason_code > 0:
            print("Fail_connect MQTT Broker")


    #client = mqtt_client.Client(client_id)
    #client = mqtt_client.Client(mqtt_client.CallbackAPIVersion.VERSION2)
    client.username_pw_set(username, password)
    client.on_connect = on_connect
    client.connect(broker, port)

    client.subscribe(topic_sub)
    return client


def subscribe(client: mqtt_client):
    def on_message(client, userdata, msg):
        global robot_state,robot_mode,robot_move_status
        try:
            json_mqtt = json.loads(msg.payload)  # receive data conver from JsonString TO Json Object
                #print(json_mqtt)
            if ('robot_state' in json_mqtt.keys()):
                robot_state = json_mqtt['robot_state']
                robot_mode= json_mqtt['robot_mode']
                robot_move_status = json_mqtt['carmove']

        except ValueError:
            print("'data' value is not a valid in JSON data, Check Data value in Subscribe Client")




    client.subscribe(topic_sub)
    client.on_message = on_message

def background_run_mqtt(event,broker,port,username,password): # worker1

    client = connect_mqtt(broker,port,username,password)
    #client.loop_start()
    subscribe(client)
    client.loop_forever()


#-------------------------------------------------------------------------------------------------

#-----------------------------------------------
@socketio.on('send_message')
def message(json, methods=['GET','POST']):
    #print("Recieved message")
    socketio.emit('camera1', json )
@socketio.on('send_message2')
def message2(json, methods=['GET','POST']):
    #print("Recieved message")
    socketio.emit('camera2', json )







@socketio.on('connect')
def test_connect():
    # need visibility of the global thread object
    print('Client SocketIO connected')


@socketio.on("start1")
def start1():
    global thread
    with thread_lock:
        if thread is None:
            thread_event.set()
            thread = socketio.start_background_task(background_thread, thread_event)


@socketio.on("stop1")
def stop1():
    print("Start Cam2 Intelrealses")
    global thread
    thread_event.clear()
    with thread_lock:
        if thread is not None:
            thread.join()
            thread = None



@socketio.on("start2")
def start2():
    global thread1,cam2_video_link,cam2_model_link,cam2_ctrl_enb
    with thread_lock1:
        if thread1 is None:
            thread_event1.set()
            thread1 = socketio.start_background_task(background_thread1, thread_event1, cam2_video_link,
                                                     cam2_model_link, cam2_ctrl_enb)
    print("Start Cam2 Logitect")


@socketio.on("stop2")
def stop2():
    global thread1,thread_event1,thread_lock1
    thread_event1.clear()
    with thread_lock1:
        if thread1 is not None:
            thread1.join()
            thread1 = None
    print("Stop Cam2 Logitect")



def start_mqtt(broker,port,username,password):
    global thread2
    stop_mqtt()
    with thread_lock2:
        if thread2 is None:
            thread_event2.set()
            thread2 = socketio.start_background_task(background_run_mqtt,thread_event2,broker,port,username,password)




@socketio.on("stop_mqtt")
def stop_mqtt():
    global thread2,thread_event2,thread_lock2
    thread_event2.clear()
    with thread_lock2:
        if thread2 is not None:
            thread2.join()
            thread2 = None
    print("Stop Mqtt")

@socketio.on('setup_mqtt')
def setup_mqtt(data):
    global mqtt_setval,broker,port,username,password
    mqtt_setval = data
    broker = data['broker']
    port = data['port']
    username = data['user']
    password = data['pass']
    print(data)
    start_mqtt(broker,port,username,password)


#start_mqtt(broker,port,username,password)



@socketio.on('setup_intelCam')
def setup_intelCam(data):
    global intel_setval,cam_intel_enb,classes_detect, alarm_dist,stop_dist,enb_safety_cam1
    cam_intel_enb = data['cam_intel_enb']
    classes_detect = data['classes']
    alarm_dist = data['alarm_dist']*1000
    stop_dist = data['stop_dist']*1000
    enb_safety_cam1 =data['enb_safety_cam1']
    intel_setval =data
    print(data)

    if (enb_safety_cam1==False):  # Clear Forward Block Stop Robot move FWD
        ex_operate_robot(22)


@socketio.on('setup_logitectCam')
def setup_logitectCam(data):
    global logitect_setval,cam2_video_link,cam2_model_link,cam2_ctrl_enb  # this line alow update global parameter
    #{"cam2_video_link": FileCamInput, "cam2_model_link": FileCamModel, "cam2_ctrl_enb": cam2_control}
    cam2_video_link= data['cam2_video_link']
    cam2_model_link= data['cam2_model_link']
    cam2_ctrl_enb= data['cam2_ctrl_enb']

    logitect_setval = data


    print(data)




@socketio.on('write_setting')
def write_setting():
    global logitect_setval,intel_setval,mqtt_setval,hostname,IPAddr
    print(mqtt_setval)
    # Data to be written
    dictionary = {
        "mqtt":mqtt_setval,
        "intelCam": intel_setval,
        "logitectCam":logitect_setval,
        "host":{"hostname": hostname, "ip":IPAddr,"port":8000}

    }
    # send dictionery to MQTT Thread , Will do later
    if (mqtt_setval!=None and intel_setval!=None and logitect_setval!=None):
        with open("data/setup_parameter.json", "w") as outfile:
            json.dump(dictionary, outfile)
    else:
        print("Please Settup All 3 Data - Mqtt, Intel and Logitect from web first before saving")

@socketio.on('read_setting')
def read_setting():

    global intel_setval,cam_intel_enb,classes_detect, alarm_dist,stop_dist,enb_safety_cam1
    global logitect_setval,cam2_video_link,cam2_model_link,cam2_ctrl_enb
    global mqtt_setval, broker, port, username, password

    exit = os.path.exists("data/setup_parameter.json")
    # Opening JSON file
    if exit:
        with open('data/setup_parameter.json', 'r') as jsonfile:
            # Reading from json file
            json_object = json.load(jsonfile)
            print(json_object)
            socketio.emit('datasetup', json_object)

            intel_setval= json_object['intelCam']
            logitect_setval=json_object['logitectCam']
            mqtt_setval = json_object['mqtt']

            # Extract data to program
            # Intel Cam
            cam_intel_enb=json_object['intelCam']['cam_intel_enb']
            classes_detect=json_object['intelCam']['classes']
            alarm_dist=json_object['intelCam']['stop_dist']
            stop_dist=json_object['intelCam']['stop_dist']
            enb_safety_cam1=json_object['intelCam']['enb_safety_cam1']
            # logitect cam
            cam2_video_link=json_object['logitectCam']['cam2_video_link']
            cam2_model_link=json_object['logitectCam']['cam2_model_link']
            cam2_ctrl_enb=json_object['logitectCam']['cam2_ctrl_enb']
            # Mqtt
            broker=json_object['mqtt']['broker']
            port=json_object['mqtt']['port']
            username=json_object['mqtt']['user']
            password=json_object['mqtt']['pass']


            start_mqtt(broker, port, username, password)


    else:
        print("file setup file is not available")



#read_setting()
#------------------------Get IP----------

hostname = socket.gethostname()
IPAddr = socket.gethostbyname(hostname)

#print("Your Computer Name is:" + hostname)
#print("Your Computer IP Address is:" + IPAddr)
host= {"hostname": hostname, "ip":IPAddr,"port":8000}

@socketio.on('getdata_web')
def getdat_web():
    socketio.emit('host_ip', host)


@socketio.on('get_webcamID')
def get_webcamID():
    camlist=[]
    global client
    print(" Get webcam index")
    for camera_info in enumerate_cameras(cv2.CAP_MSMF):  # any Python
        print(f'{camera_info.index}: {camera_info.name}')
        camlist.append(str(camera_info.index) + " : "+ str(camera_info.name) +"\n")

    socketio.emit('datasetup', camlist)


#-----------------------ROBOT OPERATION----------------------------

def ex_operate_robot( n):
    global client, robot_mode,robot_state,direct_cmd,motorspeed_cmd,speed

    datacontroljson= None

    if n==0:
        datacontroljson = {"robot_mode": True}
        if not robot_mode:
            mqtt_message = json.dumps(datacontroljson)
            client.publish(topic_pub,mqtt_message)
            socketio.emit("control_event", "Robot Auto")
            robot_mode =True
    if n==1:
        datacontroljson = {"robot_mode": False}
        if robot_mode:
            mqtt_message = json.dumps(datacontroljson)
            client.publish(topic_pub,mqtt_message)
            socketio.emit("control_event", "Robot Manual")
            robot_mode =False

    if n==2:  # Stop
        datacontroljson = {"robot_state": False}
        if robot_state:
            mqtt_message = json.dumps(datacontroljson)
            client.publish(topic_pub,mqtt_message)
            socketio.emit("control_event", "Stop Robot")
            robot_state = False

    if n==3:  # Start
        datacontroljson = {"robot_state": True}
        if not robot_state:
            mqtt_message = json.dumps(datacontroljson)
            client.publish(topic_pub,mqtt_message)
            socketio.emit("control_event", "Start Robot")
            robot_state =True

    if n==4:  # fwd
        datacontroljson = {"motorspeed_cmd": speed, "direct_cmd": 1}
        if robot_state and direct_cmd!=1:
            mqtt_message = json.dumps(datacontroljson)
            client.publish(topic_pub,mqtt_message)
            socketio.emit("control_event", "Move FWD")
            direct_cmd=1


    if n==5:  # bwd
        datacontroljson = {"motorspeed_cmd": speed, "direct_cmd": 2}
        if robot_state and direct_cmd != 2:
            mqtt_message = json.dumps(datacontroljson)
            client.publish(topic_pub, mqtt_message)
            socketio.emit("control_event", "Move BWD")
            direct_cmd = 2

    if n==6:  # left
        datacontroljson = {"motorspeed_cmd": speed, "direct_cmd": 3}
        if robot_state and direct_cmd != 3:
            mqtt_message = json.dumps(datacontroljson)
            client.publish(topic_pub, mqtt_message)
            socketio.emit("control_event", "Turn Left")
            direct_cmd = 3

    if n==7:  # right
        datacontroljson = {"motorspeed_cmd": speed, "direct_cmd": 4}
        if robot_state and direct_cmd != 4:
            mqtt_message = json.dumps(datacontroljson)
            client.publish(topic_pub, mqtt_message)
            socketio.emit("control_event", "Turn Right")
            direct_cmd = 4

    if n==8:  # fwdright
        datacontroljson = {"motorspeed_cmd": speed, "direct_cmd": 5}
        if robot_state and direct_cmd != 5:
            mqtt_message = json.dumps(datacontroljson)
            client.publish(topic_pub, mqtt_message)
            socketio.emit("control_event", "FWD Right")
            direct_cmd = 5

    if n==9:  # fwdleft
        datacontroljson = {"motorspeed_cmd": speed, "direct_cmd": 6}
        if robot_state and direct_cmd != 6:
            mqtt_message = json.dumps(datacontroljson)
            client.publish(topic_pub, mqtt_message)
            socketio.emit("control_event", "FWD Left")
            direct_cmd = 6

    if n==10:  # bwdleft
        datacontroljson = {"motorspeed_cmd": speed, "direct_cmd": 7}
        if robot_state and direct_cmd != 7:
            mqtt_message = json.dumps(datacontroljson)
            client.publish(topic_pub, mqtt_message)
            socketio.emit("control_event", "BWD Left")
            direct_cmd = 7

    if n==11:  # bwd right
        datacontroljson = {"motorspeed_cmd": speed, "direct_cmd": 8}
        if robot_state and direct_cmd != 8:
            mqtt_message = json.dumps(datacontroljson)
            client.publish(topic_pub, mqtt_message)
            socketio.emit("control_event", "BWD Right")
            direct_cmd = 8

    if n==12:  # spinright
        datacontroljson = {"motorspeed_cmd": speed, "direct_cmd": 9}
        if robot_state and direct_cmd != 9:
            mqtt_message = json.dumps(datacontroljson)
            client.publish(topic_pub, mqtt_message)
            socketio.emit("control_event", "Spin Right")
            direct_cmd = 9

    if n==13:  # spin left
        datacontroljson = {"motorspeed_cmd": speed, "direct_cmd": 10}
        if robot_state and direct_cmd!=10:
            mqtt_message = json.dumps(datacontroljson)
            client.publish(topic_pub,mqtt_message)
            socketio.emit("control_event", "Spin Left")
            direct_cmd=10
    #----------------------------------Speed change---------------
    if n==14: # speed 30
        datacontroljson = {"speed": 30}
        if robot_state and speed!=30:
            mqtt_message = json.dumps(datacontroljson)
            client.publish(topic_pub,mqtt_message)
            socketio.emit("control_event", "Speed 30")

        speed=30
    if n==15:  # speed 30
        datacontroljson = {"speed": 90}
        if robot_state and speed!=90:
            mqtt_message = json.dumps(datacontroljson)
            client.publish(topic_pub, mqtt_message)
            socketio.emit("control_event", "Speed 90")
        speed=90
    if n==16:  # speed 30
        datacontroljson = {"speed": 40}
        if robot_state:
            mqtt_message = json.dumps(datacontroljson)
            client.publish(topic_pub, mqtt_message)
            socketio.emit("control_event", "Speed 40")
        speed=40
    if n==17:  # speed 30
        datacontroljson = {"speed": 50}
        if robot_state and speed!=50:
            mqtt_message = json.dumps(datacontroljson)
            client.publish(topic_pub, mqtt_message)
            socketio.emit("control_event", "Speed 50")
        speed=50
    if n==18:  # speed 30
        datacontroljson = {"speed": 60}
        if robot_state and speed!=60:
            mqtt_message = json.dumps(datacontroljson)
            client.publish(topic_pub, mqtt_message)
            socketio.emit("control_event", "Speed 60")
            speed=60
    if n==19:  # speed 30
        datacontroljson = {"speed": 80}
        if robot_state and speed!=80:
            mqtt_message = json.dumps(datacontroljson)
            client.publish(topic_pub, mqtt_message)
            socketio.emit("control_event", "Speed 80")
            speed=80
    if n==20:  # speed 30
        datacontroljson = {"speed": 100}
        if robot_state and speed!=100:
            mqtt_message = json.dumps(datacontroljson)
            client.publish(topic_pub, mqtt_message)
            socketio.emit("control_event", "Speed 100")
        speed=100
    if n==21:  # Block Move FWD
        datacontroljson = {"block_move_fwd": True,"block_move_bwd": False,}
        if robot_state:
            mqtt_message = json.dumps(datacontroljson)
            client.publish(topic_pub, mqtt_message)
            socketio.emit("control_event", "Stop and Block Car moving forward, due to find object in safety region FWD camera IntelRealsens")


    if n== 22:  #  Enable move FWD
        datacontroljson = {"block_move_fwd": False, "block_move_bwd": True, }
        if robot_state:
            mqtt_message = json.dumps(datacontroljson)
            client.publish(topic_pub, mqtt_message)
            socketio.emit("control_event",
                          "Robot is in Normal operation No object in safety region FWD camera IntelRealsens")


# Stop Robot When first Start for safety
ex_operate_robot(2)


def Controlbyimage(enableCtrl,label):
    if enableCtrl:
        n = label.strip()

        if n=="start":
            ex_operate_robot(3)
        if n=="stop":
            ex_operate_robot(2)
        if n=="forward":
            ex_operate_robot(4)
        if n=="backward":
            ex_operate_robot(5)
        if n=="left":
            ex_operate_robot(6)
        if n=="right":
            ex_operate_robot(7)
        #-----------------------------Speed
        if n=="speed20":
            ex_operate_robot(14)
        if n=="speed30":
            ex_operate_robot(15)
        if n=="speed40":
            ex_operate_robot(16)
        if n=="speed50":
            ex_operate_robot(17)
        if n=="speed60":
            ex_operate_robot(18)
        if n=="speed80":
            ex_operate_robot(19)
        if n=="speed100":
            ex_operate_robot(20)




if __name__== "__main__":
    #socketio.run(app,debug=True, host='127.0.0.1', port=5000)
    socketio.run(app, port=8000, debug=True,  host='0.0.0.0',allow_unsafe_werkzeug=True)
