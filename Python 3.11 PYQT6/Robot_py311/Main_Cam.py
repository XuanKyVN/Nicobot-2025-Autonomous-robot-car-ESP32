import sys
from PyQt6.QtWidgets import QApplication, QMainWindow,QFileDialog,QMessageBox
from robotcontrol import Ui_MainWindow  # chính là file chuyển từ .ui
from PyQt6.QtGui import QImage,QPixmap,QPainter
from PyQt6.QtCore import pyqtSignal, pyqtSlot, Qt, QThread
from PyQt6 import QtGui,QtCore,QtWidgets
import multiprocessing
import os, json, time
import numpy as np
import imutils, cv2
#-------------------MQTT----------------
import random
from paho.mqtt import client as mqtt_client
#---------------------------------------------
from ultralytics import YOLO
from vidgear.gears import CamGear
#---------------------
import serial.tools.list_ports
import serial
from datetime import datetime
from datetime import date

import pyrealsense2 as rs
from pyusbcameraindex import enumerate_usb_video_devices_windows
from pathlib import Path




class VideoThread(QThread):
    change_pixmap_signal = pyqtSignal(np.ndarray) # Send Picture
    change_pixmap_signal_intel = pyqtSignal(np.ndarray) # Send picture
    signal_event = pyqtSignal(dict) # Send data back to HMI Screen
    def __init__(self, index):
        super().__init__()
        self._run_flag_aft = True
        self._run_flag_fwd = True
        self.index = index
        self.video_path =r"C:\Users\Admin\PythonLession\pic\Traffic4.mp4"

    def run(self):
        model = YOLO("yolo11n.pt")
        if self.index ==1: # AFT CAMERA
            #self.video_path =3

            options = {"STREAM_RESOLUTION": "720p", "STREAM_PARAMS": {"nocheckcertificate": True}}

            # To open live video stream on webcam at first index(i.e. 0)
            # device and apply source tweak parameters
            self.stream = CamGear(source=self.video_path, stream_mode=False, logging=True).start()

                       # loop over
            while self._run_flag_aft:
                 # read frames from stream
                frame = self.stream.read()
                # check for frame if Nonetype
                if frame is None:
                    break

                results = model.predict(frame, device=[0])
                # Visualize the results on the frame
                annotated_frame = results[0].plot()

                self.change_pixmap_signal.emit(annotated_frame)
                time.sleep(0.1)

            self.stream.stop()
        else: #-----------------------If Intel Camera-------------
                # Self.index =0 is forward camera

            if (self._run_flag_fwd):
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
                    while self._run_flag_fwd:

                        # Wait for a coherent pair of frames: depth and color
                        frames = pipeline.wait_for_frames()
                        depth_frame = frames.get_depth_frame()
                        color_frame = frames.get_color_frame()

                        if not depth_frame or not color_frame:
                            continue

                        # Convert images to numpy arrays
                        depth_image = np.asanyarray(depth_frame.get_data())
                        pointdata = depth_image[300, 300]
                        print(pointdata)

                        color_image = np.asanyarray(color_frame.get_data())
                        results = model.predict(color_image, device=[0], classes=[0])
                        color_image = results[0].plot()
                        # Apply colormap on depth image (image must be converted to 8-bit per pixel first)
                        depth_colormap = cv2.applyColorMap(cv2.convertScaleAbs(depth_image, alpha=0.03), cv2.COLORMAP_JET)

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

                        self.change_pixmap_signal.emit(color_image)
                        self.change_pixmap_signal_intel.emit(images)

                        # Show images

                        #cv2.circle(images, [300, 300], 5, (255, 0, 35), 2)
                        #cv2.circle(images, [940, 300], 5, (255, 255, 255), 2)
                        # cv2.line(images, (50, 50), (250, 250), (0, 255, 255), 5)

                        #cv2.namedWindow('RealSense', cv2.WINDOW_AUTOSIZE)
                        #cv2.imshow('RealSense', images)
                        #cv2.waitKey(0.5)
                        time.sleep(0.1)

                finally:

                    # Stop streaming
                    pipeline.stop()










    @pyqtSlot(dict)
    def video_receivedata(self, data):

        if ("stop_cam_fwd" in data.keys()):
            self._run_flag_fwd =False
            #self.stop()
        if ("start_cam_fwd" in data.keys()):
            self._run_flag_fwd = True
        if ("stop_cam_aft" in data.keys()):
            self._run_flag_aft =False
            #self.stop()
        if ("start_cam_aft" in data.keys()):
            self._run_flag_aft = True

        if ("set_video_path" in data.keys()):

            if len(data["set_video_path"]) >1:
                self.video_path = data["set_video_path"] # use for AFT CAMERA ONLY
            # Intel Camera it is automatically detect
            else:
                self.video_path = int(data["set_video_path"])  # use for AFT CAMERA ONLY


            print(self.video_path)


        pass

    def stop(self):
        """Sets run flag to False and waits for thread to finish"""
        self._run_flag = False
        self.terminate()
        self.quit()
        # self.wait()


#----------------------------------------------------------------


#===------------------------------------------

class Mqtt_Thread(QThread):
    signal_mqtt2hmi = pyqtSignal(dict) # data transfer to HMI
    def __init__(self):
        super().__init__()
        self._run_flag = True
        self.broker = "localhost"
        self.port = 1883
        self.topic_pub = "robotcar/control"
        self.topic_sub = "robotcar/feedback"
        self.username = "robot"
        self.password = "123456"

        # generate client ID with pub prefix randomly
        self.client_id = f'python-mqtt-{random.randint(0, 1000)}'
        self.data ={}

    @pyqtSlot(dict)             # Data receive from HMI
    def mqtt_receivedata(self, data):
        if ("broker" in data.keys()):
            print("setup mqtt here")
            print(data)
            self.broker = data['broker']
            self.port = data['port']
            self.username = data['username']
            self.password = data['password']

        elif ("direct_cmd" in data.keys()):
            #print(data)
            mqtt_message= json.dumps(data) # convert json to mqtt message json string
            self.client.publish(self.topic_pub,mqtt_message)
        else:
            # Robot_state and Robot_mode here
            #print(data)
            mqtt_message =json.dumps(data)
            self.client.publish(self.topic_pub, mqtt_message)

    def connect_mqtt(self):
        # New Version 2.0
        def on_connect(client, userdata, flags, reason_code, properties):
            if flags.session_present:
                pass
            if reason_code == 0:
                # success connect
                print("success_connect")
                self.client.subscribe(self.topic_sub)

            if reason_code > 0:
                print("Fail_connect")



        #client = mqtt_client.Client(client_id)
        self.client = mqtt_client.Client(mqtt_client.CallbackAPIVersion.VERSION2)
        self.client.username_pw_set(self.username, self.password)
        self.client.on_connect = on_connect
        self.client.connect(self.broker, self.port)
        self.client.subscribe(self.topic_sub)
        return self.client



    def subscribe(self, client: mqtt_client):
        def on_message(client, userdata, msg):
            #print(f"Received `{msg.payload.decode()}` from `{msg.topic}` topic")
            json_mqtt ={}
            try:
                json_mqtt = json.loads(msg.payload)  # receive data conver from JsonString TO Json Object
                #print(json_mqtt)
            except ValueError:
                print("'data' value is not a valid integer in JSON data")

            self.signal_mqtt2hmi.emit(json_mqtt)  # send data to HMI when receive data





        client.subscribe(self.topic_sub)
        client.on_message = on_message

    def on_disconnect(self,client, userdata, flags, rc, properties):
        while True:
            # loop until client.reconnect()
            # returns 0, which means the
            # client is connected
            try:
                if not client.reconnect():
                    print("client is not connected")
                    break

            except ConnectionRefusedError:
                # if the server is not running,
                # then the host rejects the connection
                # and a ConnectionRefusedError is thrown
                # getting this error > continue trying to
                # connect
                pass
                # if the reconnect was not successful,
                # wait one second

            time.sleep(1)

    def run(self):  # this is Main program for running MQTT
        if self.broker!="":
            self.client = self.connect_mqtt()
            self.client.on_disconnect=self.on_disconnect
            self.subscribe(self.client)
            self.client.loop_forever(retry_first_connection=True)
        else:
            self.stop()
    def stop(self):
        """Sets run flag to False and waits for thread to finish"""
        self._run_flag = False
        self.terminate()
        self.quit()
        # self.wait()



#---------------------------------------------------------------------

class Lora_Thread(QThread):
    signal_lora2hmi = pyqtSignal(dict) # data transfer to HMI
    def __init__(self):
        super().__init__()
        self._run_flag = True
        self.port_serial = "COM7"
        self.boudrate = 115200


    def run(self):  # this is Main program for running MQTT
        self.serialPort = serial.Serial(
            port=self.port_serial, baudrate=self.boudrate, bytesize=8, timeout=2, stopbits=serial.STOPBITS_ONE
        )
        serialString = ""  # Used to hold data coming over UART
        while 1:
            # Read data out of the buffer until a carraige return / new line is found
            serialString = self.serialPort.readline()

            # Print the contents of the serial data
            try:
                #print(serialString.decode("Ascii"))
                jsonobject = json.loads(serialString.decode("Ascii"))
                #print(jsonobject)
                self.signal_lora2hmi.emit(jsonobject)  # Send String data to HMI
                pass
            except:
                pass

    @pyqtSlot(dict) # Receive signal from HMI
    def lora_receivedata(self,data):

        if ("port_serial" in data.keys()):
            self.port_serial = data["port_serial"]
            #self.boudrate = data["boudrate"]

        elif ("direct_cmd" in data.keys()):
            # Control Motor here
            print(data)
            lora_message= json.dumps(data) # convert json to jsonString
            self.serialPort.write(lora_message.encode(encoding='ascii', errors='strict'))
        elif ("read_comport" in data.keys()):
            ports = serial.tools.list_ports.comports()
            com_port =[]
            descrip=[]

            for port, desc, hwid in sorted(ports):
                # print("{}: {} [{}]".format(port, desc, hwid))
                print(port)
                print(desc)
                com_port.append(port)
                descrip.append(desc)
            comport_info = {"comport":com_port, "desc":descrip}
            self.signal_lora2hmi.emit(comport_info)  # Send Json Object data to HMI

        else:
            # robot_mode and robot_state message here
            print(data)
            lora_message = json.dumps(data)  # convert json to jsonString
            self.serialPort.write(lora_message.encode(encoding='ascii', errors='strict'))





    def stop(self):
            """Sets run flag to False and waits for thread to finish"""
            self._run_flag = False
            self.terminate()
            self.quit()
            # self.wait()
#----------------------------------------------------------------



#-----------MAIN PROGRAM------------------------------------------
#---------------------------------------------------------------------
class MainWindow(QMainWindow):
    signal_to_mqttthread= pyqtSignal(dict)
    signal_to_videothread = pyqtSignal(dict)
    signal_to_lorathread= pyqtSignal(dict)

    def __init__(self):
        super().__init__()
        self.uic = Ui_MainWindow()
        self.uic.setupUi(self)
        # Setup MQTT ( save, load)
        #self.uic.Temperature.display(15.8)
        # MQTT SETUP
        self.broker = ""
        self.port =""
        self.username =""
        self.password = ""
        self.uic.bt_setupmqtt.clicked.connect(self.write_mqttsetup)
        self.read_mqttsetup()  # read mqtt file and send to hmi
        #------------------------------------
        #----ROBOT Operate-----
        self.datacontroljson ={}
        self.auto_manMode = 0 # if auto_manMode = 0 Manual, 1 Auto

        # After each value change, Slider Speed set
        self.uic.Slider_SpeedSet.valueChanged.connect(self.speeddisplay)
        self.uic.bt_stop.setStyleSheet("background-image : url(png/bt_stop.png);")
        self.uic.bt_start.setStyleSheet("background-image : url(png/bt_start.png);")
        self.uic.bt_exit.setStyleSheet("background-image : url(png/bt_exit.png);")
        self.uic.bt_spinleft.setStyleSheet("background-image : url(png/bt_spinleft.png);")
        self.uic.bt_spinright.setStyleSheet("background-image : url(png/bt_spinright.png);")

        self.uic.bt_setautoman.clicked.connect(lambda: self.operate_robot(0))
        self.uic.bt_stop.clicked.connect(lambda:self.operate_robot(1))
        self.uic.bt_start.clicked.connect(lambda:self.operate_robot(2))
        self.uic.bt_fwd.clicked.connect(lambda:self.operate_robot(3))
        self.uic.bt_bwd.clicked.connect(lambda:self.operate_robot(4))
        self.uic.bt_left.clicked.connect(lambda:self.operate_robot(5))
        self.uic.bt_right.clicked.connect(lambda:self.operate_robot(6))

        self.uic.bt_fwdright.clicked.connect(lambda:self.operate_robot(7))
        self.uic.bt_fwdleft.clicked.connect(lambda:self.operate_robot(8))
        self.uic.bt_bwdleft.clicked.connect(lambda:self.operate_robot(9))
        self.uic.bt_bwdright.clicked.connect(lambda:self.operate_robot(10))
        self.uic.bt_spinright.clicked.connect(lambda: self.operate_robot(11))
        self.uic.bt_spinleft.clicked.connect(lambda: self.operate_robot(12))

        #self.sendatato_hmi() #display data image , Use for Simulation
        #-----------Mqtt thread config------------
        self.config_mqtt_lora_thread()


        # VIDEO Start configuration
        self.config_videothread()

        self.display_width = 750
        self.display_height = 640
        self.uic.lbl_camera_aft.hide()
        self.uic.Cam_select.currentIndexChanged.connect(self.select_camera)
        #-------------------
        self.uic.bt_start_video_fwd.clicked.connect(self.start_video_front)
        self.uic.bt_stop_video_fwd.clicked.connect(self.stop_video_front)
        self.uic.bt_start_video_aft.clicked.connect(self.start_video_aft)
        self.uic.bt_stop_video_aft.clicked.connect(self.stop_video_aft)

        self.uic.bt_start_mqtt.clicked.connect(self.start_mqtt)
        self.uic.bt_stop_mqtt.clicked.connect(self.stop_mqtt)

        self.uic.bt_start_lora.clicked.connect(self.start_lora)
        self.uic.bt_stop_lora.clicked.connect(self.stop_lora)
        self.uic.bt_setup_lora.clicked.connect(self.setuplora_port)


        self.flag_mqtt = False
        self.flag_lora = False
        self.flag_video_fwd=False
        self.flag_video_bwd=False

        self.uic.comboBox_Com_mode.currentIndexChanged.connect(self.select_control_mode_mqtt_lora)
        self.lora_mqtt_mode = False # MQTT Com Mode selected,  True LORA mode Selected
        self.uic.bt_list_portLora.clicked.connect(self.list_available_comport)
        self.read_lorasetup()
        self.uic.bt_clear_event.clicked.connect(self.eventclear)
        self.uic.bt_exit.clicked.connect(self.stopandExit)

        self.auto_manual_flag = False  # not allow motor control by CAMERA AUTO
        # list webcam
        self.uic.bt_camera_list.clicked.connect(self.list_usb_webcam)
        self.uic.bt_set_video_aft.clicked.connect(self.set_aft_camera)

        self.uic.bt_selectvideo.clicked.connect(self.selectVideo)

        self.uic.bt_save_event.clicked.connect(self.save_event)


        if os.path.exists("./data/about.txt"):
            self.uic.txt_about.setPlainText("")
            with open("./data/about.txt", 'r') as fp:
                data_read = fp.read()
                self.uic.txt_about.setPlainText(data_read)



#-----------------End of Main Program----------------------------------------------

#----------------------------------------------------------------------------------
    def write_mqttsetup(self):
        self.uic.plaintex_event.appendPlainText(str(datetime.now()) + ": " + "Setup MQTT")

        self.broker = self.uic.text_broker.text()
        self.port =self.uic.text_port.text()
        self.username =self.uic.text_username.text()
        self.password = self.uic.text_password.text()

        # Data to be written
        dictionary = {
            "broker": self.broker,
            "port": self.port,
            "username": self.username,
            "password": self.password
        }
        # send dictionery to MQTT Thread , Will do later

        with open("mqttsetup.json", "w") as outfile:
            json.dump(dictionary, outfile)

        # Reconnect MQTT Broker to new broker by restart Mqtt Thread
        self.signal_to_mqttthread.emit(dictionary)  # HMI Send Json Data To MQTT Thread

    def read_mqttsetup(self):
        exit = os.path.exists("mqttsetup.json")
        # Opening JSON file
        if exit:
            with open('mqttsetup.json', 'r') as mqttjsonfile:
                # Reading from json file
                json_object = json.load(mqttjsonfile)
                self.uic.text_broker.setText(json_object['broker'])
                self.uic.text_port.setText(json_object['port'])
                self.uic.text_username.setText(json_object['username'])
                self.uic.text_password.setText(json_object['password'])

                self.signal_to_mqttthread.emit(json_object)  # HMI Send Json Data To MQTT Thread

        else: print("mqtt setup file is not available")

    def operate_robot(self, n):
        if self.lora_mqtt_mode==False:  #mqtt select
            if self.flag_mqtt ==True:
                self.ex_operate_robot(n)
                self.signal_to_mqttthread.emit(self.datacontroljson)  # HMI Send Json Data To MQTT Thread
            else:  # Lora select
                self.uic.plaintex_event.appendPlainText(str(datetime.now()) + ": " + "MQTT is not stated")
                print("MQTT is not started")
        else:
            if self.flag_lora ==True: # Lora select  , Serial
                self.ex_operate_robot(n)
                self.signal_to_lorathread.emit(self.datacontroljson)  # HMI Send Json Data To Lora Thread
            else:
                self.uic.plaintex_event.appendPlainText(str(datetime.now()) + ": " + "LORA is not stated")
                print("LORA is not started")


    def ex_operate_robot(self,n):
        speed = int(self.uic.lbl_speeddisplay.text())

        if (n==0):
            if self.uic.bt_auto_radio.isChecked():
                #self.datacontroljson ={"robot_mode":True} //Auto
                self.datacontroljson = {"robot_mode": True}
                self.auto_manual_flag = True # allow motor control by CAMERA AUTO
            else:
                #self.datacontroljson = {"robot_mode":False}
                self.datacontroljson = {"robot_mode": False}
                self.auto_manual_flag = False  # not allow motor control by CAMERA AUTO

        if (n==1): #Stop
            self.datacontroljson = {"robot_state": False}
        if (n==2): #Start
            self.datacontroljson = {"robot_state": True}

        if (n==3):#fwd
            self.datacontroljson = {"motorspeed_cmd": speed,"direct_cmd":1}
        if (n==4):#bwd
            self.datacontroljson = {"motorspeed_cmd": speed,"direct_cmd":2}
        if (n==5):#left
            self.datacontroljson = {"motorspeed_cmd": speed,"direct_cmd":3}
        if (n==6):#right
            self.datacontroljson = {"motorspeed_cmd": speed,"direct_cmd":4}
        if (n==7):#fwdright
            self.datacontroljson = {"motorspeed_cmd": speed,"direct_cmd":5}
        if (n==8):#fwdleft
            self.datacontroljson = {"motorspeed_cmd": speed,"direct_cmd":6}
        if (n==9):#bwdleft
            self.datacontroljson = {"motorspeed_cmd": speed,"direct_cmd":7}
        if (n==10):#bwd right
            self.datacontroljson = {"motorspeed_cmd": speed,"direct_cmd":8}
        if (n==11):#spinright
            self.datacontroljson = {"motorspeed_cmd": speed,"direct_cmd":9}
        if (n==12):#spin left
            self.datacontroljson = {"motorspeed_cmd": speed,"direct_cmd":10}



    def speeddisplay(self, value):
       self.uic.lbl_speeddisplay.setText(str(value))

    def sendatato_hmi(self, datasim1):
        #data=data1 or data2
        '''
        datasim1 = {"robot_state": True,"robot_mode": True, "speedL_rpm":58, "speedL_kmh":1.8, "posL":88,"currentL":30, "directL":"FWD",
                    "speedR_rpm":9, "speedR_kmh":5.3,"posR":80, "currentR":10, "directR":"BWD","M_volt":12,"Ctr_volt":11.9,
                    "carmove":3
                    }
        datasim2 ={"gpslat": 37.8, "gpslon":40, "gpsdistance":58,"gpsspeed_kmh":87, "gpsspeed_ms":888,
                   "temp":21, "humi":80, "mqttstatus": False, "": True,  "R_Hcurrent":False, "low_volt_ctr":False,
                   "low_volt_motor": True, "clientId":"cli154922", "IP":"192.168.0.182"
                 }
        '''
        #-----------------Data package 1--------------


        if ('robot_state' in datasim1.keys()):

            if (datasim1['robot_state']==True):
                self.uic.lbl_robotready.setPixmap(QPixmap("png/ready.png"))
            else: self.uic.lbl_robotready.setPixmap(QPixmap("png/notready.png"))

            if (datasim1['robot_mode']==True):
                self.uic.lbl_auto_man.setPixmap(QPixmap("png/auto.png"))
            else: self.uic.lbl_auto_man.setPixmap(QPixmap("png/manu.png"))

            self.uic.lcd_left_rpm.display(datasim1["speedL_rpm"])
            self.uic.lcd_left_pos.display(datasim1["posL"])
            self.uic.lcd_left_current.display(datasim1["currentL"])
            self.uic.lbl_left_dir.setText(datasim1["directL"])

            self.uic.lcd_right_rpm.display(datasim1["speedR_rpm"])
            self.uic.lcd_right_pos.display(datasim1["posR"])
            self.uic.lcd_right_current.display(datasim1["currentR"])
            self.uic.lbl_right_dir.setText(datasim1["directR"])
            self.uic.lcd_ctrolvoltage.display(datasim1["Ctr_volt"])
            self.uic.lcd_motorvolt.display(datasim1["M_volt"])
            self.uic.lbl_carmove.setText(self.function_carmove(datasim1["carmove"]))
            self.uic.lbl_carmove2.setText(self.function_carmove(datasim1["carmove"]))


        elif ("gpslat" in datasim1.keys()):
            # -----------Data package 2--------------
            self.uic.lcd_humidity.display(datasim1["humi"])
            self.uic.lcd_temperature.display(datasim1["temp"])
            self.uic.lcd_gps_lat.display(datasim1["gpslat"])
            self.uic.lcd_gps_lon.display(datasim1["gpslon"])
            self.uic.lcd_gps_distancekm.display(datasim1["gpsdistance"])
            self.uic.lbl_controler_ip.setText(datasim1["IP"])

            if (datasim1['mqttstatus']):
                self.uic.lbl_mqtt_status.setPixmap(QPixmap("png/connect.png"))
            else: self.uic.lbl_mqtt_status.setPixmap(QPixmap("png/disconnect.png"))

            if (datasim1['L_Hcurrent']):
                self.uic.lbl_Lhighcurrent.setText("ABNORMAL")
            else: self.uic.lbl_Lhighcurrent.setText("NORMAL")
            if (datasim1['R_Hcurrent']):
                self.uic.lbl_Rhighcurrent.setText("ABNORMAL")
            else: self.uic.lbl_Rhighcurrent.setText("NORMAL")

            if (datasim1['low_volt_ctr']):
                self.uic.lbl_lowvolt_ctr.setText("ABNORMAL")
            else: self.uic.lbl_lowvolt_ctr.setText("NORMAL")
            if (datasim1['low_volt_motor']):
                self.uic.lbl_lowvolt_motor.setText("ABNORMAL")
            else: self.uic.lbl_lowvolt_motor.setText("NORMAL")
    def function_carmove(self, carmovests):

        if (carmovests ==0):
            self.uic.lbl_carmove1.setText("STOP")
            self.uic.lbl_carmove_img.setPixmap(QPixmap("png/stop.png"))
            return "STOP"
        elif (carmovests ==1):
            self.uic.lbl_carmove1.setText("MOVING FORWARD")
            self.uic.lbl_carmove_img.setPixmap(QPixmap("png/movefwd.png"))
            return "FWD"
        elif (carmovests ==2):
            self.uic.lbl_carmove1.setText("MOVING BACKWARD")
            self.uic.lbl_carmove_img.setPixmap(QPixmap("png/backward.png"))
            return "BWD"
        elif (carmovests ==3):
            self.uic.lbl_carmove1.setText("MOVING LEFT")
            self.uic.lbl_carmove_img.setPixmap(QPixmap("png/turnleft.png"))
            return "LEFT"
        elif (carmovests ==4):
            self.uic.lbl_carmove1.setText("MOVING RIGHT")
            self.uic.lbl_carmove_img.setPixmap(QPixmap("png/turnRight.png"))
            return "RIGHT"
        elif (carmovests ==6):
            self.uic.lbl_carmove1.setText("FORWARD LEFT")
            self.uic.lbl_carmove_img.setPixmap(QPixmap("png/fwdleft.png"))
            return "FWD LEFT"
        elif (carmovests ==5):
            self.uic.lbl_carmove1.setText("FORWARD RIGHT")
            self.uic.lbl_carmove_img.setPixmap(QPixmap("png/fwdright.png"))
            return "FWD RIGHT"
        elif (carmovests ==7):
            self.uic.lbl_carmove1.setText("BACKWARD LEFT")
            self.uic.lbl_carmove_img.setPixmap(QPixmap("png/bwdleft.png"))
            return "BWD LEFT"
        elif (carmovests ==8):
            self.uic.lbl_carmove1.setText("BACKWARD RIGHT")
            self.uic.lbl_carmove_img.setPixmap(QPixmap("png/bwdright.png"))
            return "BWD RIGHT"
        elif (carmovests == 10):
            self.uic.lbl_carmove1.setText("SPIN LEFT")
            self.uic.lbl_carmove_img.setPixmap(QPixmap("png/spin left.png"))
            return "SPIN LEFT"
        elif (carmovests == 9):
            self.uic.lbl_carmove1.setText("SPIN RIGHT")
            self.uic.lbl_carmove_img.setPixmap(QPixmap("png/spin_right.png"))
            return "SPIN RIGHT"

    def config_mqtt_lora_thread(self):

        self.mqttthread = Mqtt_Thread()
        #self.mqttthread.stop()
        #time.sleep(1)
        self.mqttthread.signal_mqtt2hmi.connect(self.receive_from_mqtt)
        self.signal_to_mqttthread.connect(self.mqttthread.mqtt_receivedata)  # connect signal from HMI to Mqtt thread
        #self.mqttthread.start()

        #----------Config Serial Lora Thread--------
        self.lorathread = Lora_Thread()
        self.lorathread.signal_lora2hmi.connect(self.receive_from_lora)

        self.signal_to_lorathread.connect(self.lorathread.lora_receivedata)
        #self.lorathread.start()

    @pyqtSlot(dict)
    def receive_from_mqtt(self,data):
        if (self.lora_mqtt_mode==False):
            self.sendatato_hmi(data) # Recive json from Mqtt and extract data to HMI immidiately
            #print(" Received data from MQTT to HMI HERE")
            #print(data)
#----------------------------------------------------------------------
    def config_videothread(self):
        self.VThread1 = VideoThread(0)
        self.VThread1.change_pixmap_signal.connect(self.receive_image_fromvideo_fwd)
        self.VThread1.change_pixmap_signal_intel.connect(self.receive_image_fromvideo_fwd1)
        self.signal_to_videothread.connect(self.VThread1.video_receivedata)


        self.VThread2 = VideoThread(1)
        self.VThread2.change_pixmap_signal.connect(self.receive_image_fromvideo_aft)
        self.signal_to_videothread.connect(self.VThread2.video_receivedata)


    def start_video_front(self):
        self.signal_to_videothread.emit({"start_cam_fwd":1})
        self.VThread1.start()
        self.flag_video_fwd=True
        self.uic.plaintex_event.appendPlainText(str(datetime.now()) + ": " + "Start camera front")


    def start_video_aft(self):
        self.signal_to_videothread.emit({"start_cam_aft": 1})

        self.VThread2.start()
        self.flag_video_bwd = True
        self.uic.plaintex_event.appendPlainText(str(datetime.now()) + ": " + "Start camera aft")
    def stop_video_front(self):
        self.signal_to_videothread.emit({"stop_cam_fwd": 1})

        self.VThread1.stop()
        self.flag_video_fwd = False
        self.uic.plaintex_event.appendPlainText(str(datetime.now()) + ": " + "Stop camera front")

    def stop_video_aft(self):
        self.signal_to_videothread.emit({"stop_cam_aft": 1})
        self.VThread2.stop()
        self.flag_video_bwd = False
        self.uic.plaintex_event.appendPlainText(str(datetime.now()) + ": " + "Stop camera aft")


#--------------------------
    def start_mqtt(self):
        self.mqttthread.start()
        self.flag_mqtt = True
        self.uic.plaintex_event.appendPlainText(str(datetime.now()) + ": " + "Start MQTT")

    def stop_mqtt(self):
        self.mqttthread.stop()
        self.flag_mqtt = False
        self.uic.plaintex_event.appendPlainText(str(datetime.now()) + ": " + "Stop MQTT")
    #-----------------
    def start_lora(self):
        self.lorathread.start()
        self.flag_lora = True
        self.uic.plaintex_event.appendPlainText(str(datetime.now()) + ": " + "Start LORA")

    def stop_lora(self):
        self.lorathread.stop()
        self.flag_lora = False
        self.uic.plaintex_event.appendPlainText(str(datetime.now()) + ": " + "Stop LORA")


    @pyqtSlot(np.ndarray)
    def receive_image_fromvideo_fwd(self, cv_img):
        """Updates the image_label with a new opencv image"""
        qt_img = self.convert_cv_qt(cv_img)
        self.uic.lbl_camera_fwd.setPixmap(qt_img)

    @pyqtSlot(np.ndarray)
    def receive_image_fromvideo_fwd1(self, cv_img):
        """Updates the image_label with a new opencv image"""
        qt_img = self.convert_cv_qt1(cv_img)
        self.uic.lbl_camera_fwd2.setPixmap(qt_img)

    def convert_cv_qt(self, cv_img):
        """Convert from an opencv image to QPixmap"""
        rgb_image = cv2.cvtColor(cv_img, cv2.COLOR_BGR2RGB)
        h, w, ch = rgb_image.shape
        bytes_per_line = ch * w
        convert_to_Qt_format = QtGui.QImage(rgb_image.data, w, h, bytes_per_line, QtGui.QImage.Format.Format_RGB888)
        p = convert_to_Qt_format.scaled(self.display_width, self.display_height, Qt.AspectRatioMode.KeepAspectRatio)
        #p = convert_to_Qt_format.scaled(self.scaled_size, QtCore.Qt.KeepAspectRatio)
        return QPixmap.fromImage(p)

    def convert_cv_qt1(self, cv_img):
        """Convert from an opencv image to QPixmap"""
        rgb_image = cv2.cvtColor(cv_img, cv2.COLOR_BGR2RGB)
        h, w, ch = rgb_image.shape
        bytes_per_line = ch * w
        convert_to_Qt_format = QtGui.QImage(rgb_image.data, w, h, bytes_per_line, QtGui.QImage.Format.Format_RGB888)
        p = convert_to_Qt_format.scaled(1200, 700, Qt.AspectRatioMode.KeepAspectRatio)
        #p = convert_to_Qt_format.scaled(self.scaled_size, QtCore.Qt.KeepAspectRatio)
        return QPixmap.fromImage(p)
    @pyqtSlot(np.ndarray)
    def receive_image_fromvideo_aft(self, cv_img):
        """Updates the image_label with a new opencv image"""
        qt_img = self.convert_cv_qt(cv_img) # Resolution 600x480
        self.uic.lbl_camera_aft.setPixmap(qt_img)

        qt_img1 = self.convert_cv_qt1(cv_img) # Resolution 1200x768
        self.uic.lbl_camera_aft2.setPixmap(qt_img1)

    def select_camera(self):
        if (self.uic.Cam_select.currentIndex()==0):
            self.uic.lbl_camera_fwd.show()
            self.uic.lbl_camera_aft.hide()
        else:
            self.uic.lbl_camera_fwd.hide()
            self.uic.lbl_camera_aft.show()

    @pyqtSlot(dict)
    def receive_from_lora(self, data):
        #comport_info = {"comport": com_port, "desc": descrip}
        if ("comport" in data.keys()):
            comport = data["comport"] # Array
            description = data["desc"]
            self.uic.comboBox_ComPort.clear()
            for i in range(len(comport)):
                self.uic.plaintex_event.appendPlainText(str(datetime.now()) + ", " + comport[i] + ", " + description[i] )
                self.uic.comboBox_ComPort.addItem(comport[i])

            #print(" Received data from Lora to HMI HERE")
            #print(data)  # Json Data Here
        else:
            if (self.lora_mqtt_mode):
                self.sendatato_hmi(data)  # Recive json from Lora and extract data to HMI immidiately
                #print(" Received data from Lora to HMI HERE")
                #print(data)  # Json Data Here



    def select_control_mode_mqtt_lora(self):
        if self.uic.comboBox_Com_mode.currentIndex()==0:
            self.lora_mqtt_mode =False
        else: self.lora_mqtt_mode =True  # Use LORA

    def list_available_comport(self):
        datasend = {"read_comport":1}
        self.signal_to_lorathread.emit(datasend)

    def setuplora_port(self):
        self.lora_comport= self.uic.comboBox_ComPort.currentText()
        dictionary = {"port_serial":self.lora_comport}

        self.signal_to_lorathread.emit(dictionary)

        with open("lorasetup.json", "w") as outfile:
            json.dump(dictionary, outfile)




    def read_lorasetup(self):
        exit = os.path.exists("lorasetup.json")
        # Opening JSON file
        if exit:
            with open('lorasetup.json', 'r') as lorajsonfile:
                # Reading from json file
                json_object = json.load(lorajsonfile)
                self.uic.comboBox_ComPort.clear()
                self.uic.comboBox_ComPort.addItem(json_object['port_serial'])
                self.signal_to_lorathread.emit(json_object)  # HMI Send Json Data To MQTT Thread

        else: print("mqtt setup file is not available")



    def eventclear(self):
        self.uic.plaintex_event.clear()

    def stopandExit(self):
        dlg = QMessageBox(self)
        dlg.setWindowTitle("Close and Exit!")
        dlg.setText("Do you want to close application?")
        dlg.setStandardButtons(
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        dlg.setIcon(QMessageBox.Icon.Question)
        button = dlg.exec()

        if button == QMessageBox.StandardButton.Yes:
            #print("Yes Exit!")
            self.mqttthread.stop()
            self.lorathread.stop()
            self.VThread1.stop()
            self.VThread2.stop()
            self.close()
        else:
            #print("No!")
            pass


    def list_usb_webcam(self):
        devices = enumerate_usb_video_devices_windows()
        for device in devices:
            print(f"{device.index} == {device.name} (VID: {device.vid}, PID: {device.pid}, Path: {device.path}")
            self.uic.plaintex_event.appendPlainText(str(datetime.now()) + ", " + str(device.index) + ", " + str(device.name))

    def set_aft_camera(self):
        cam = self.uic.txt_video_cam.text()
        self.signal_to_videothread.emit({"set_video_path": cam})

    def selectVideo(self):
        dialog = QFileDialog(self)
        dialog.setDirectory(r'C:\image')
        dialog.setFileMode(QFileDialog.FileMode.ExistingFiles)
        dialog.setNameFilter("VideoFile (*.mp4  *.avi)")
        dialog.setViewMode(QFileDialog.ViewMode.List)
        if dialog.exec():
            filenames = dialog.selectedFiles()
            #print(filenames)
            if filenames:
                # self.file_list.addItems([str(Path(filename)) for filename in filenames])
                self.uic.txt_video_cam.setText(str(Path(filenames[0])))


    def save_event(self):
        t = time.localtime(time.time())
        #print('Hours:', t.tm_hour)
        #print('Minutes:', t.tm_min)
        #print('Seconds:', t.tm_sec)
        today = date.today()
        #print('Current Date:', today)
        filename= str(today)+"_"+str(t.tm_hour)+str(t.tm_min)+str(t.tm_sec)+"_event.txt"
        a= os. getcwd()
        print(a)
        with open(a+"/log/"+filename, 'w') as f:
            my_text = self.uic.plaintex_event.toPlainText()
            f.write(my_text)





#---------------------------------------------------------
if __name__ == "__main__":
    app = QApplication(sys.argv)
    main_win = MainWindow()
    main_win.show()
    sys.exit(app.exec())
