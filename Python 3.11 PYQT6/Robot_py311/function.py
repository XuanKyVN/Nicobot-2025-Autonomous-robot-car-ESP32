import cv2
from collections import Counter  # Import Counter from collections module


def convert_BBxyxy_to_CWH(x1, y1, x2, y2):
    w = x2 - x1
    h = y2 - y1
    cx = int(x1 + w / 2)
    cy = int(y1 + h / 2)
    return cx, cy, w, h


def count_objects_in_image(object_classes, image):
    counter = Counter(object_classes)
    # print("Object Count in Image:")
    # print(counter)
    n = 0
    obj_count =[]
    for obj, count in counter.items():
        # print(f"{obj}: {count}")
        cv2.putText(image, f'{obj}', (50, 50 + n), cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 0, 0), 1)
        cv2.putText(image, f'{count}', (150, 50 + n), cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 0, 0), 1)

        n = n + 50

        # cv2.imshow("img", image)
        obj_count.append(obj)
        obj_count.append(count)

    #print(objquantity)
    return obj_count


def drawCircle_center_image(cord, image):
    cx, cy, w, h = convert_BBxyxy_to_CWH(cord[0], cord[1], cord[2], cord[3])
    cv2.circle(image, (cx, cy), 5, (255, 0, 0), 2)
    return cx,cy





def find_element_in_matrix(Matrix, element,distance):  #  THis function is used to  to sort min distance of element
    indexmatrix = []
    elementdistance=[]
    Min_distance=0


    if len(Matrix) > 0:
        index = 0

        for i in range(len(Matrix)):
            if Matrix[i] == element:
                indexmatrix.append(i)
        #print("index_matrix:")
        #print(indexmatrix)
        if len(indexmatrix)>0:
            for i in indexmatrix:
                elementdistance.append(distance[i])
            #print("Element_distance")
            #print(elementdistance)

            Min_distance = min(elementdistance)  # Min Matrix element

    return Min_distance,indexmatrix


def find_min(marks):

    minimum_val = marks[0]
    for i in range(1, len(marks)):
        if (marks[i] < minimum_val):
            minimum_val = marks[i]
    result = marks.index(minimum_val)
    return result,minimum_val


def arrage_2array_increase(arr_deg,arr_dist):
    new_array_deg = []  #
    new_array_dist = []  # distance
    array_temp = arr_deg.copy()
    arr_dist_temp = arr_dist.copy()

    for i in range(len(array_temp)):
        index, minval = find_min(array_temp)
        new_array_deg.append(array_temp[index])
        array_temp.pop(index)

        new_array_dist.append(arr_dist_temp[index])
        arr_dist_temp.pop(index)
    return new_array_deg,new_array_dist





