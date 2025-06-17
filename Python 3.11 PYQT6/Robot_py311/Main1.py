import sys
from PyQt6.QtWidgets import QApplication, QMainWindow,QFileDialog,QMessageBox
from robotcontrol import Ui_MainWindow  # chính là file chuyển từ .ui
from PyQt6.QtGui import QImage,QPixmap,QPainter
from PyQt6.QtCore import pyqtSignal, pyqtSlot, Qt, QThread
from PyQt6 import QtGui,QtCore,QtWidgets
import multiprocessing
import os, json

#-------------------MQTT----------------
import random
from paho.mqtt import client as mqtt_client
#---------------------------------------------
'''
class MultiThread(QThread): # Multi Processing working here

    data_send = pyqtSignal(dict)
    def __init__(self):
        super().__init__()
        self._run_flag = True


    def run(self):

        if self._run_flag and self.mode_annotator:
            # print(list_files(self.path))
            self.anotator_flag, self.names_classes = self.auto_anotate_image(self.path, self.yolo_path)
            # Create Directory data if it is not availabel
            directory = os.path.abspath(os.getcwd()) # get current directory path
            path = os.path.join(directory, "data")
            isExist = os.path.exists(path)
            # Create the directory
            if not isExist:
                try:
                    os.makedirs(path, exist_ok=True)
                    print("Directory '%s' created successfully")
                except OSError as error:
                    print("Directory '%s' can not be created")
            else:
                #print("Directory is availabled")
                pass

            open("data/classes.txt", 'w').close()

            for i in range(0, len(self.names_classes)):
                file1 = open("data/classes.txt", "a")
                file1.write(self.names_classes[i] + "\n")
                file1.close()
            print(" Write classes.txt complete and send data to main screen")
            self.data_send.emit({"annotate_flag": self.anotator_flag, "name_classes": self.names_classes})
            self.mode_annotator = False
        elif self._run_flag and self.mode_train:
            self.traing(self.yolo_path, self.datayaml, self.epoch, self.imagesize)
            self.mode_train = False
            self.data_send.emit({"train_flag": self.mode_train})
        elif self._run_flag and self.mode_download:
            self.dowloadimg(self.keyword, self.quantity_down, self.dest_folder_down)
            self.mode_download = False
            self.data_send.emit({"download_flag": self.mode_download})
        else:
            print("Not yet use this mode")

    # -------------------------------------------
    # MQTT Program here
    def connect_mqtt():
        # New Version 2.0
        def on_connect(client, userdata, flags, reason_code, properties):
            if flags.session_present:
                pass
            if reason_code == 0:
                # success connect
                print("success_connect")
            if reason_code > 0:
                print("Fail_connect")

        # client = mqtt_client.Client(client_id)
        client = mqtt_client.Client(mqtt_client.CallbackAPIVersion.VERSION2)
        # client.username_pw_set(username, password)
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

    def background_run_mqtt():
        client = connect_mqtt()
        # client.loop_start()
        subscribe(client)
        client.loop_forever()

    def background_thread_yolo():
        while (cap.isOpened()):
            ret, img = cap.read()
            if ret:
                
                result = model(img, device=[0])
                img = result[0].plot()
                





@pyqtSlot(dict)
    def receivedata(self, data):
        print("Receive data")
        print(data)
        key_to_check_annotate = 'annotate_flag'
        key_to_check_modetrain = 'mode_train'

        if key_to_check_annotate in data.keys():
            self.yolo_path = data["yolo_path"]
            self.path = data["path"]
            self._run_flag = data["run_flag"]
            self.mode_annotator = data["annotate_flag"]
        elif key_to_check_modetrain in data.keys():
            self.imagesize = data["imagesize"]
            self.yolo_path = data["yolo_path"]
            self.epoch = data["epoch"]
            self.datayaml = data["datayaml"]
            self.mode_train = data["mode_train"]
            self._run_flag = data["run_flag"]
        else: # Download mode
            self.keyword  = data["keyword"]
            self.quantity_down = data["quantity_down"]
            self.dest_folder_down = data["dest_folder_down"]
            self._run_flag = data["run_flag"]
            self.mode_download = data["mode_download"]
        # ---------------------------------------------------------------


    def stop(self):
        """Sets run flag to False and waits for thread to finish"""
        self._run_flag = False
        self.terminate()
        self.quit()

#--------------------------------------------------------------------
'''








class MainWindow(QMainWindow):
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

        self.sendatato_hmi() #display data image
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
            a = self.uic.bt_auto_radio
            if (a.isChecked):
                self.datacontroljson ={"robot_mode": True}
            else:
                self.datacontroljson = {"robot_mode":False}

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

        print(self.datacontroljson)

    def speeddisplay(self, value):
       self.uic.lbl_speeddisplay.setText(str(value))

    def sendatato_hmi(self):
        #data=data1 or data2

        datasim1 = {"robot_state": True,"robot_mode": True, "speedL_rpm":58, "speedL_kmh":1.8, "posL":88,"currentL":30, "directL":"FWD",
                    "speedR_rpm":9, "speedR_kmh":5.3,"posR":80, "currentR":10, "directR":"BWD","M_volt":12,"Ctr_volt":11.9,
                    "carmove":3
                    }

        datasim2 ={"gpslat": 37.8, "gpslon":40, "gpsdistance":58,"gpsspeed_kmh":87, "gpsspeed_ms":888,
                   "temp":21, "humi":80, "mqttstatus": False, "L_Hcurrent": True,  "R_Hcurrent":False, "low_volt_ctr":False,
                   "low_volt_motor": True, "clientId":"cli154922", "IP":"192.168.0.182"
                 }

        #-----------------Data package 1--------------
        if (datasim1['robot_state']):
            self.uic.lbl_robotready.setPixmap(QPixmap("png/ready.png"))
        else: self.uic.lbl_robotready.setPixmap(QPixmap("png/notready.png"))

        if (datasim1['robot_mode']):
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


        # -----------Data package 2--------------
        self.uic.lcd_humidity.display(datasim2["humi"])
        self.uic.lcd_temperature.display(datasim2["temp"])
        self.uic.lcd_gps_lat.display(datasim2["gpslat"])
        self.uic.lcd_gps_lon.display(datasim2["gpslon"])
        self.uic.lcd_gps_distancekm.display(datasim2["gpsdistance"])
        self.uic.lbl_controler_ip.setText(datasim2["IP"])

        if (datasim2['mqttstatus']):
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
        elif (carmovests ==5):
            return "FWD LEFT"
        elif (carmovests ==6):
            return "FWD RIGHT"
        elif (carmovests ==7):
            return "BWD LEFT"
        elif (carmovests ==8):
            return "BWD RIGHT"
        elif (carmovests == 9):
            return "SPIN LEFT"
        elif (carmovests == 10):
            return "SPIN RIGHT"


    '''  
# object["carmove"] = robot_move_status; 
// 0: Stop, 1 fwd, 2, bwd, 3, left,4 right,5 upleft,6, upright,7,downleft, 8 downright,9 Spin left, 10 spin right.
'''

if __name__ == "__main__":
    app = QApplication(sys.argv)
    main_win = MainWindow()
    main_win.show()
    sys.exit(app.exec())
