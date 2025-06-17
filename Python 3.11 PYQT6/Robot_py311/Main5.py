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
#from ultralytics import YOLO
from vidgear.gears import CamGear

class VideoThread(QThread):
    change_pixmap_signal = pyqtSignal(np.ndarray)

    def __init__(self, index):
        super().__init__()
        self._run_flag = True
        self.index = index

    def run(self):

        if self.index ==0:
            self.video_path =2
        else:
            self.video_path = r"C:\Users\Admin\Documents\MATLAB\Assignment\Fish_Green_LED.mp4"

        options = {"STREAM_RESOLUTION": "720p", "STREAM_PARAMS": {"nocheckcertificate": True}}

        # To open live video stream on webcam at first index(i.e. 0)
        # device and apply source tweak parameters
        self.stream = CamGear(source=self.video_path, stream_mode=False, logging=True).start()

                   # loop over
        while self._run_flag:
             # read frames from stream
            frame = self.stream.read()
            # check for frame if Nonetype
            if frame is None:
                break
            self.change_pixmap_signal.emit(frame)

        self.stream.stop()


    @pyqtSlot(dict)
    def video_receivedata(self, data):
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
        #self.read_mqttsetup()
        self.data ={}

    @pyqtSlot(dict)             # Data receive from HMI
    def mqtt_receivedata(self, data):

        if ("broker" in data.keys()):
            self.read_mqttsetup(data)
            print("setup mqtt here")
            print(data)
        elif ("direct_cmd" in data.keys()):
            keycheck1 = "robot_state"
            keycheck2 = "robot_mode"
            keycheck3 = "direct_cmd"
            #print("Data Received at Mqtt")
            print(data)
            mqtt_message= json.dumps(data) # convert json to mqtt message json string
            self.client.publish(self.topic_pub,mqtt_message)
        else:
            print("Robot Mode and State here")
            print(data)
            mqtt_message =json.dumps(data)
            print("JSON DUMP Robot Mode and State here")
            print(mqtt_message)
            self.client.publish(self.topic_pub, mqtt_message)



    def connect_mqtt(self):
        # New Version 2.0
        def on_connect(client, userdata, flags, reason_code, properties):
            if flags.session_present:
                pass
            if reason_code == 0:
                # success connect
                print("success_connect")
                client.subscribe(self.topic_sub)

            if reason_code > 0:
                print("Fail_connect")


        if (self.broker!=""):
            #client = mqtt_client.Client(client_id)
            self.client = mqtt_client.Client(mqtt_client.CallbackAPIVersion.VERSION2)
            self.client.username_pw_set(self.username, self.password)
            self.client.on_connect = on_connect
            self.client.connect(self.broker, self.port)
            self.client.subscribe(self.topic_sub)
            return self.client
        else: print("Please add mqtt broker")


    def subscribe(self, client: mqtt_client):
        def on_message(client, userdata, msg):
            #print(f"Received `{msg.payload.decode()}` from `{msg.topic}` topic")
            json_mqtt ={}
            try:
                json_mqtt = json.loads(msg.payload)  # receive data conver from JsonString TO Json Object
                print(json_mqtt)
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

    def read_mqttsetup(self):
        exit = os.path.exists("mqttsetup.json")
        # Opening JSON file
        if exit:
            with open('mqttsetup.json', 'r') as mqttjsonfile:
                # Reading from json file
                json_object = json.load(mqttjsonfile)
                self.broker = json_object['broker']
                self.port = json_object['port']
                self.username= json_object['username']
                self.password = json_object['password']

        else:
            print("mqtt setup file is not available")


class MainWindow(QMainWindow):
    signal_to_mqttthread= pyqtSignal(dict)
    signal_to_videothread = pyqtSignal(dict)

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
        self.config_mqtt_thread()


        # VIDEO Start configuration
        self.config_videothread()

        self.display_width = 750
        self.display_height = 640
        self.uic.lbl_camera_aft.hide()
        self.uic.Cam_select.currentIndexChanged.connect(self.select_camera)




#-----------------End of Main Program------------------------------------
    def write_mqttsetup(self):

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

        else: print("mqtt setup file is not available")

    def operate_robot(self, n):
        speed = int(self.uic.lbl_speeddisplay.text())

        if (n==0):

            if self.uic.bt_auto_radio.isChecked():
                #self.datacontroljson ={"robot_mode":True} //Auto
                self.datacontroljson = {"robot_mode": True}
            else:
                #self.datacontroljson = {"robot_mode":False}
                self.datacontroljson = {"robot_mode": False}

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

        #print(self.datacontroljson)

        self.signal_to_mqttthread.emit(self.datacontroljson) # HMI Send Json Data To MQTT Thread

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
                   "temp":21, "humi":80, "mqttstatus": False, "L_Hcurrent": True,  "R_Hcurrent":False, "low_volt_ctr":False,
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


    def function_carmove(self, carmovests):

        if (carmovests ==0):
            return "STOP"
        elif (carmovests ==1):
            return "FWD"
        elif (carmovests ==2):
            return "BWD"
        elif (carmovests ==3):
            return "LEFT"
        elif (carmovests ==4):
            return "RIGHT"
        elif (carmovests ==6):
            return "FWD LEFT"
        elif (carmovests ==5):
            return "FWD RIGHT"
        elif (carmovests ==7):
            return "BWD LEFT"
        elif (carmovests ==8):
            return "BWD RIGHT"
        elif (carmovests == 10):
            return "SPIN LEFT"
        elif (carmovests == 9):
            return "SPIN RIGHT"

    def config_mqtt_thread(self):
        self.mqttthread = Mqtt_Thread()
        #self.mqttthread.stop()
        #time.sleep(1)
        self.mqttthread.signal_mqtt2hmi.connect(self.receive_from_mqtt)
        self.signal_to_mqttthread.connect(self.mqttthread.mqtt_receivedata)  # connect signal from HMI to Mqtt thread
        self.mqttthread.start()

    @pyqtSlot(dict)
    def receive_from_mqtt(self,data):

        self.sendatato_hmi(data) # Recive json from Mqtt and extract data to HMI immidiately
        print(" Received data from MQTT to HMI HERE")
        print(data)

    def config_videothread(self):
        self.VThread1 = VideoThread(0)
        self.VThread1.change_pixmap_signal.connect(self.receive_image_fromvideo_fwd)
        #self.signal_to_videothread1.connect(self.VThread1.video_receivedata)
        self.VThread1.start()

        self.VThread2 = VideoThread(1)
        self.VThread2.change_pixmap_signal.connect(self.receive_image_fromvideo_aft)
        #self.signal_to_videothread1.connect(self.VThread1.video_receivedata)
        self.VThread2.start()


    @pyqtSlot(np.ndarray)
    def receive_image_fromvideo_fwd(self, cv_img):
        """Updates the image_label with a new opencv image"""
        qt_img = self.convert_cv_qt(cv_img)
        self.uic.lbl_camera_fwd.setPixmap(qt_img)

    def convert_cv_qt(self, cv_img):
        """Convert from an opencv image to QPixmap"""
        rgb_image = cv2.cvtColor(cv_img, cv2.COLOR_BGR2RGB)
        h, w, ch = rgb_image.shape
        bytes_per_line = ch * w
        convert_to_Qt_format = QtGui.QImage(rgb_image.data, w, h, bytes_per_line, QtGui.QImage.Format.Format_RGB888)
        p = convert_to_Qt_format.scaled(self.display_width, self.display_height, Qt.AspectRatioMode.KeepAspectRatio)
        #p = convert_to_Qt_format.scaled(self.scaled_size, QtCore.Qt.KeepAspectRatio)
        return QPixmap.fromImage(p)


    @pyqtSlot(np.ndarray)
    def receive_image_fromvideo_aft(self, cv_img):
        """Updates the image_label with a new opencv image"""
        qt_img = self.convert_cv_qt(cv_img)
        self.uic.lbl_camera_aft.setPixmap(qt_img)



    def select_camera(self):
        if (self.uic.Cam_select.currentIndex()==0):
            self.uic.lbl_camera_fwd.show()
            self.uic.lbl_camera_aft.hide()
        else:
            self.uic.lbl_camera_fwd.hide()
            self.uic.lbl_camera_aft.show()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    main_win = MainWindow()
    main_win.show()
    sys.exit(app.exec())
