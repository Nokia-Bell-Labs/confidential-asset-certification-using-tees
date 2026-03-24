# © 2026 Nokia
# Licensed under the BSD 3-Clause Clear License
# SPDX-License-Identifier: BSD-3-Clause-Clear

import json
from pathlib import Path
import shutil
import zipfile

import cv2
import numpy as np

from libprop import stats as lps

def detect_objects(image_path, model):
    net = model["net"]
    output_layers = model["output_layers"]
    class_map = model["class_map"]

    # Load and prepare image
    image = cv2.imread(image_path)
    height, width, _ = image.shape
    
    # Prepare blob and forward pass
    blob = cv2.dnn.blobFromImage(image, 0.00392, (416, 416), (0, 0, 0), True, crop=False)
    net.setInput(blob)
    outs = net.forward(output_layers)
    
    # Initialize lists for detected boxes and confidences
    detected_objects = {}
    object_boxes = {}
    object_confidences = {}

    # Process detections
    for out in outs:
        for detection in out:
            scores = detection[5:]
            class_id = np.argmax(scores)
            confidence = scores[class_id]

            # Filter for people (class_id 0 in COCO dataset)
            if confidence > 0.5: #and class_id == 0:
                # Get box coordinates
                center_x = int(detection[0] * width)
                center_y = int(detection[1] * height)
                w = int(detection[2] * width)
                h = int(detection[3] * height)
                
                # Rectangle coordinates
                x = int(center_x - w / 2)
                y = int(center_y - h / 2)
                
                if class_id not in object_boxes:
                    object_boxes[class_id] = []
                    object_confidences[class_id] = []

                object_boxes[class_id].append([x, y, w, h])
                object_confidences[class_id].append(float(confidence))
    
    for class_id in object_boxes:
        # Apply non-maximum suppression
        indexes = cv2.dnn.NMSBoxes(object_boxes[class_id], object_confidences[class_id], 0.5, 0.4)
        for i in range(len(object_boxes[class_id])):
            if i in indexes:
                x, y, w, h = object_boxes[class_id][i]
                cv2.rectangle(image, (x, y), (x + w, y + h), (255, 0, 0), 2)

                class_name = class_map[class_id]
                if class_name not in detected_objects:
                    detected_objects[class_name] = 0

                detected_objects[class_name] += 1

    # # Show and save result
    # cv2.imshow("Detection", image)
    # # cv2.imwrite("output.jpg", image)
    # cv2.waitKey(0)
    # cv2.destroyAllWindows()
    
    # print(detected_objects)
    
    return detected_objects

def compute_property(image_paths, model):
    output = {}

    num_images = len(image_paths)
    output["num_images"] = num_images
    print(num_images)
    i = 0
    all_detected_objects = {}
    for image_path in image_paths:
        print(image_path)
        detected_objects = detect_objects(image_path, model)
        i += 1
        if i % 100 == 0:
            print(f"Processed: {i/num_images*100.0}%")
        
        for key in detected_objects:
            if key not in all_detected_objects:
                all_detected_objects[key] = []
        
            all_detected_objects[key].append(detected_objects[key])

    # print(all_detected_objects)
    output["detected_object_info"] = {}
    for key in all_detected_objects:
        output["detected_object_info"][key] = {}
        output["detected_object_info"][key]["stats"] = lps.compute_cell_value_statistics(all_detected_objects[key])
        output["detected_object_info"][key]["count"] = len(all_detected_objects[key])

    return output

def init_model(yolov3_paths):
    # Load YOLO model
    yolov3_net = cv2.dnn.readNet(yolov3_paths["weights"], yolov3_paths["cfg"])
    layer_names = yolov3_net.getLayerNames()
    yolov3_output_layers = [layer_names[i - 1] for i in yolov3_net.getUnconnectedOutLayers()]
    
    # Load COCO class labels
    with open(yolov3_paths["coco.names"], "r") as f:
        classes = [line.strip() for line in f.readlines()]

    class_map = {}
    i = 0
    for c in classes:
        class_map[i] = c
        i += 1

    model = {}
    model["net"] = yolov3_net
    model["output_layers"] = yolov3_output_layers
    model["class_map"] = class_map

    return model

if __name__ == "__main__":
    yolov3_paths = {}
    yolov3_paths["weights"] = "/tmp/inputs/coco/2017/yolov3.weights"
    yolov3_paths["cfg"] = "/tmp/inputs/coco/2017/yolov3.cfg"
    yolov3_paths["coco.names"] = "/tmp/inputs/coco/2017/coco.names"
    
    model = init_model(yolov3_paths)

    data_path = "/tmp/inputs"
    data_dir = Path(data_path)
    
    # extract the zip files first
    glob = "**/*.zip"
    zip_files = list(data_dir.glob(glob))
    
    output = {}
    output["filenames"] = []
    for zf in zip_files:
        output["filenames"].append(str(zf))
        output[str(zf)] = {}

        image_folder = str(zf)[:-4]
        with zipfile.ZipFile(zf, 'r') as f:
            f.extractall(image_folder)

        image_dir = Path(image_folder)

        num_filetypes = {}
        image_files = {}
        for filetype in ["jpeg", "JPEG", "jpg", "JPG"]:
            glob = "**/*." + filetype
            image_files[filetype] = list(image_dir.glob(glob))
            image_files[filetype] = sorted(image_files[filetype])

        output[str(zf)]["filetypes"] = {}
        for filetype in image_files:
            output[str(zf)]["filetypes"][filetype] = compute_property(image_files[filetype], model)
        
        shutil.rmtree(image_folder, ignore_errors=True)

    print(json.dumps(output, indent=4, sort_keys=True))
    with open("/tmp/outputs/computation_result.json", "w") as f:
        json.dump(output, f, indent=4, sort_keys=True)
