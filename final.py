import torch
import cv2
from pyzbar import pyzbar 
from flask import request, jsonify
import mysql.connector

items = {"8906006720114": ["Lion Dates", "https://wawafresh.com/public/uploads/all/tR57MDJuVZmEofqZ7BrOYTqP9SGBV8hutF5CeNhn.jpg"],
         "8901030772290": ["Ponds", "https://newassets.apollo247.com/pub/media/catalog/product/p/o/pon0037_2_1.jpg"],
         "8901023015397": ["Godrej aer", "https://cdn01.pharmeasy.in/dam/products_otc/K01212/godrej-aer-power-pocket-bathroom-freshner-assorted-pack-of-5-1-1627280927.jpg"],
         "8901063016873": ["50-50","https://www.bigbasket.com/media/uploads/p/xxl/100012350_11-britannia-50-50-sweet-salty-biscuits.jpg"]}

device = torch.device('cuda:0' if torch.cuda.is_available() else 'cpu')
model = torch.hub.load('ultralytics/yolov5', 'custom', path='model.pt').to(device)

import firebase_admin
from firebase_admin import credentials, firestore
from datetime import datetime

# Initialize Firebase Admin SDK
cred = credentials.Certificate(r"C:\Users\Likhit\Downloads\swiftcart-c6125-firebase-adminsdk-teyoz-4213f8d26e.json")
firebase_admin.initialize_app(cred)
cap = cv2.VideoCapture(0)

first_y_coordinate = None
hand_event = ""

while cap.isOpened():
    _, frame = cap.read()
    results = model(frame)
    detections = results.pandas().xyxy[0]

    # Extract the coordinates, class id, and confidence for each detection
    for i, detection in detections.iterrows():
        x1, y1, x2, y2 = detection[['xmin', 'ymin', 'xmax', 'ymax']]
        x1, y1, x2, y2 = [round(num) for num in [x1, y1, x2, y2]]

        class_id = detection['class']
        confidence = detection['confidence']
        #print(f'Detection {i}: class {class_id}, confidence {confidence}, bbox [{x1}, {y1}, {x2}, {y2}]')

        # Draw bounding box on input image
        cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 0), 2)

        # Put label text on bounding box
        label = f'{"Barcode"} {confidence:.2f}'
        label_size, baseline = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 1)
        cv2.rectangle(frame, (x1, y1), (x1 + label_size[0], y1 - label_size[1] - baseline), (0, 255, 0), cv2.FILLED)
        cv2.putText(frame, label, (x1, y1 - baseline), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 0), 1)

        # Crop image to bounding box of first detected object
        cropped_img = frame[y1:y2, x1:x2]
        gray = cv2.cvtColor(cropped_img, cv2.COLOR_BGR2GRAY)
        barcodes = pyzbar.decode(gray)
        for barcode in barcodes:
            data = barcode.data.decode("utf-8")

            # Put barcode data on bounding box
            data_size, baseline = cv2.getTextSize(data, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 1)
            cv2.rectangle(frame, (x1, y2), (x1 + data_size[0], y2 + data_size[1]), (0, 255, 0), cv2.FILLED)
            cv2.putText(frame, data, (x1, y2 + data_size[1]), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 0), 1)

            if data == '':
                continue 

            try:
                # Initialize Firestore
                db = firestore.client()
                
                if first_y_coordinate is None:
                    first_y_coordinate = y1
                if abs(y1 - 0) < abs(y1 - frame.shape[0]):
                    hand_event = "adding"
                    # Add data to a collection
                    data_to_add = {
                        "name": items[data][0],
                        "imgUrl": items[data][1],
                        "event": hand_event
                    }
                    print(data_to_add)
                    # Add a new document with a generated ID
                    def generate_custom_document_id():
                        # Generate a custom document ID based on the current timestamp
                        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
                        return f"{timestamp}"

                    def store_data_in_firestore(collection_name, document_data):
                        try:
                            # Generate a new custom document ID
                            custom_document_id = generate_custom_document_id()
                            print(custom_document_id)

                            # Reference to the Firestore collection and document with custom ID
                            doc_ref = db.collection(collection_name).document(custom_document_id)

                            # Set the document data
                            doc_ref.set(document_data)

                            print(f"Document added with ID: {custom_document_id}")

                            return True
                        except Exception as e:
                            print(f"Error storing data in Firestore: {e}")
                            return False

                    store_data_in_firestore("705632441947", data_to_add)
                    first_y_coordinate = None
                    import time
                    time.sleep(1)
                else:
                    hand_event = "deleting"
                    a_name = "name"
                    a_value = items[data][0]
                    query = db.collection("705632441947").where(a_name, "==", a_value).stream()
                    data_to_add = {
                        "name": items[data][0],
                        "imgUrl": items[data][1],
                        "event": hand_event
                    }
                    print(data_to_add)
                    for doc in query:
                        doc.reference.delete()
                        break

            except Exception as e:
                print('error ', e)

            finally:
                pass
                #conn.close()

    # Display annotated image
    if first_y_coordinate is not None:
        cv2.putText(frame, f'First Y Coordinate: {first_y_coordinate}', (10, 20), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
    cv2.imshow('Result', frame)
    if cv2.waitKey(1) & ord('q') == 27:
        cv2.destroyAllWindows()
        break