import threading
import time
from ultralytics import YOLO
import cv2
import base64

#-------------------MQTT----------------
import random
from paho.mqtt import client as mqtt_client
broker = "localhost"
port = 1883
topic_pub = "robotcar/control"
topic_sub = "robotcar/feedback"
username = "robot"
password = "123456"

# generate client ID with pub prefix randomly
client_id = f'python-mqtt-{random.randint(0, 1000)}'
#-------------------------------------

#model = YOLOv10(r'C:\Users\Admin\PythonLession\YoloV8\yolov8n.pt')
model = YOLO(r'C:\Users\Admin\PythonLession\Yolo11\yolo11n.pt')
#cap = cv2.VideoCapture('C:/Users/Admin/PythonLession/pic/people1.mp4')

cap = cv2.VideoCapture(2)

#-------------------------------------------
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


    #client = mqtt_client.Client(client_id)
    client = mqtt_client.Client(mqtt_client.CallbackAPIVersion.VERSION2)
    #client.username_pw_set(username, password)
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
    #client.loop_start()
    subscribe(client)
    client.loop_forever()

def background_thread_yolo():
    while (cap.isOpened()):
        ret, img = cap.read()
        if ret:
            '''
            # img = cv2.resize(img, (0,0), fx=0.5, fy=0.5)
            img = cv2.resize(img, (600, 480))
            cv2.rectangle(img, (50, 30), (300, 250), (255, 0, 0), 2)
            # client.publish(topic_pub, " Received successfull")
            # results = model(img, classes=[0], device=[0])
            results = model(img, device=[0])
            img1 = results[0].plot()
            cv2.imshow("hinh",img1 )
            frame = cv2.imencode('.jpg', img1)[1].tobytes()
            frame = base64.encodebytes(frame).decode("utf-8")
            '''
            result = model(img, device=[0])
            img = result[0].plot()
            cv2.imshow("ky", img)
            cv2.waitKey(1)



if __name__ =="__main__":


    t1 = threading.Thread(target=background_run_mqtt)
    t2 = threading.Thread(target=background_thread_yolo)

    t1.start()
    t2.start()

    t1.join()
    t2.join()

    print("Done!")