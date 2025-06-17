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
class_safety=[1,0,0,0,0,0,0,0]


id = get_webcamID_logitect()
print(id)

cam2_video_link= id
cam2_model_link ="yolo11n.pt"
cam2_ctrl_enb = False

intel_setval = None
mqtt_setval= None
logitect_setval=None


model = YOLO("model/yolo11n.pt")







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

	cap=cv2.VideoCapture("video/Traffic1.mp4")

	global thread

	try:
		while(cap.isOpened() and event.is_set()):
			ret,img=cap.read()
			if ret:
				#img = cv2.resize(img, (0,0), fx=0.5, fy=0.5)
				result = model.predict(img,device=[0])
				img= result[0].plot()
				#img = cv2.resize(img,(600,480))
				img =imutils.resize(img,580)
				#cv2.rectangle(img,(50,30),(300,250),(255,0,0),2)


				frame = cv2.imencode('.jpg', img)[1].tobytes()
				frame= base64.encodebytes(frame).decode("utf-8")
				message(frame)
				socketio.sleep(0.0)
			else:
				break
	finally:
		event.clear()
		thread = None


def background_thread1(event , cam2_video_link,cam2_model_link,cam2_ctrl_enb):  # Logitect Camera

	#cap=cv2.VideoCapture(1)
	n = len(str(cam2_video_link))


	if n>2:
		cap=cv2.VideoCapture("video/"+ cam2_video_link)

	else : cap=cv2.VideoCapture(cam2_video_link)

	model1 = YOLO("mode/"+cam2_model_link)


	global thread1

	try:
		while(cap.isOpened() and event.is_set()):
			ret,img=cap.read()
			if ret:
				#img = cv2.resize(img, (0,0), fx=0.5, fy=0.5)
				result = model1.predict(img, device=[0])
				img = result[0].plot()
				#img = cv2.resize(img,(300,300))
				#cv2.rectangle(img,(50,30),(300,250),(255,0,0),2)
				img =imutils.resize(img,580)
				#if n<2:
					#img = cv2.resize(img,(400,400))

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

thread2 = None
thread_lock2 = Lock()
thread_event2 = Event()

import random
from paho.mqtt import client as mqtt_client
broker = "broker.emqx.io"
port = 1883
topic_pub = "robotcar/control"
topic_sub = "robotcar/feedback"
username = "robot"
password = "123456"

# generate client ID with pub prefix randomly
client_id = f'python-mqtt-{random.randint(0, 1000)}'

#-------------------------------------------
def connect_mqtt(broker,port,username,password):
    # New Version 2.0
    def on_connect(client, userdata, flags, reason_code, properties):
        if flags.session_present:
            pass
        if reason_code == 0:
            # success connect
            print("success_connect")
        if reason_code > 0:
            print("Fail_connect")


    #client = mqtt_client.Client(client_id)
    client = mqtt_client.Client(mqtt_client.CallbackAPIVersion.VERSION2)
    client.username_pw_set(username, password)
    client.on_connect = on_connect
    client.connect(broker, port)

    client.subscribe(topic_sub)
    return client


def subscribe(client: mqtt_client):
    def on_message(client, userdata, msg):
        print(f"Received `{msg.payload.decode()}` from `{msg.topic}` topic")
        client.publish(topic_pub, " Received successfull")
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
    print('Client connected')


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
    #with thread_lock2:
        #if thread2 is None:
    thread_event2.set()
    thread2 = socketio.start_background_task(background_run_mqtt, thread_event2,broker,port,username,password)





@socketio.on('setup_mqtt')
def setup_mqtt(data):
	global mqtt_setval
	mqtt_setval = data
	broker = data['broker']
	port = int(data['port'])
	username = data['user']
	password = data['pass']
	print(data)
	start_mqtt(broker,port,username,password)
@socketio.on('setup_intelCam')
def setup_intelCam(data):
	global intel_setval,cam_intel_enb,class_safety
	#{ cam_intel_enb:cam_intel_enb, class_safety:[cls_person,cls_car,cls_truck,cls_bike,cls_motorbike,cls_train,cls_dog, cls_cow]}
	cam_intel_enb = data['cam_intel_enb']
	class_safety = data['class_safety']
	intel_setval =data
	print(data)


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
	exit = os.path.exists("data/setup_parameter.json")
	# Opening JSON file
	if exit:
		with open('data/setup_parameter.json', 'r') as jsonfile:
			# Reading from json file
			json_object = json.load(jsonfile)
			print(json_object)
			socketio.emit('datasetup', json_object)

	else:
		print("file setup file is not available")


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

	print(" Get webcam index")
	for camera_info in enumerate_cameras(cv2.CAP_MSMF):  # any Python
		print(f'{camera_info.index}: {camera_info.name}')
		camlist.append(str(camera_info.index) + " : "+ str(camera_info.name) +"\n")

	socketio.emit('datasetup', camlist)







if __name__== "__main__":
	#socketio.run(app,debug=True, host='127.0.0.1', port=5000)
	socketio.run(app, port=8000, debug=True,  host='0.0.0.0',allow_unsafe_werkzeug=True)
